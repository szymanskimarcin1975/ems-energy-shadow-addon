"""OFFLINE single entry: JSONL fixtures only. No HA client, controls or integration."""
import argparse,hashlib,json,math,sqlite3,signal,sys,threading
from datetime import datetime,timezone
CHANNELS={'m1_import':'kWh','m1_export':'kWh','ac_power':'W','b1_power':'W','b1_soc':'%','b1_status':None,'b1_import':'kWh','b1_export':'kWh','cloud_production':'kWh'}
STATUSES={'B_STATUS_'+s for s in ('OFF','STANDBY','INIT','CHARGE','DISCHARGE','FAULT','PRESERVE_CHARGE','IDLE','POWER_SAVING')}
def ts(v):
 if not isinstance(v,str):raise ValueError('timestamp_missing')
 t=datetime.fromisoformat(v)
 if t.tzinfo is None:raise ValueError('timezone_missing')
 return t.astimezone(timezone.utc)
def num(v):
 if isinstance(v,bool):raise ValueError('invalid_number')
 x=float(v)
 if not math.isfinite(x):raise ValueError('invalid_number')
 return x
class Adapter:
 def __init__(self,path,config):
  if set(config)!=set(CHANNELS) or any(not isinstance(v,str) or not v.startswith('sensor.') for v in config.values()) or len(set(config.values()))!=len(config):raise ValueError('invalid_source_config')
  self.config=dict(config)
  self.fingerprint=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest();self.c=sqlite3.connect(path,timeout=1,isolation_level=None)
  try:
   self.c.execute('pragma journal_mode=WAL');self.c.execute('pragma synchronous=FULL');self.c.execute('BEGIN IMMEDIATE')
   self.c.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT)')
   old=self.c.execute("select value from metadata where key='fingerprint'").fetchone()
   if old and old[0]!=self.fingerprint:raise ValueError('source_change_requires_separate_database')
   self.c.execute("insert or ignore into metadata values('fingerprint',?)",(self.fingerprint,));self.c.execute("insert or ignore into metadata values('schema_version','1')")
   self.c.execute('CREATE TABLE IF NOT EXISTS observations(channel,id,captured,raw_json,quality,PRIMARY KEY(channel,id))')
   self.c.execute('CREATE TABLE IF NOT EXISTS baselines(channel TEXT PRIMARY KEY,report_time TEXT,value REAL)')
   self.c.execute('CREATE TABLE IF NOT EXISTS quarantine(channel TEXT PRIMARY KEY,reason TEXT)')
   self.c.execute('CREATE TABLE IF NOT EXISTS quarantine_origin(channel TEXT PRIMARY KEY,baseline_json TEXT)')
   self.c.execute('CREATE TABLE IF NOT EXISTS deltas(channel,id,kwh REAL,start_report,end_report,allocation TEXT,PRIMARY KEY(channel,id))')
   self.c.execute('CREATE TABLE IF NOT EXISTS approvals(request_id TEXT PRIMARY KEY,payload_hash TEXT,channel TEXT,old_json TEXT,new_time TEXT,new_value REAL,actor TEXT,reason TEXT)')
   self.c.execute('COMMIT')
  except Exception:self.c.close();raise
 def close(self):self.c.close()
 def ingest(self,ch,id,captured,state):
  if ch not in CHANNELS:raise ValueError('unknown_channel')
  ct=ts(captured);raw=json.dumps(state,sort_keys=True,allow_nan=False)
  self.c.execute('BEGIN IMMEDIATE')
  try:
   oldobs=self.c.execute('select raw_json from observations where channel=? and id=?',(ch,id)).fetchone()
   if oldobs:
    if oldobs[0]!=raw:raise ValueError('capture_id_conflict')
    self.c.execute('ROLLBACK');return 'duplicate'
   q='valid_observation';old=self.c.execute('select report_time,value from baselines where channel=?',(ch,)).fetchone()
   try:
    if state.get('entity_id')!=self.config[ch]:raise ValueError('wrong_or_missing_entity')
    if state.get('unit')!=CHANNELS[ch]:raise ValueError('invalid_unit')
    v=state['value']
    if ch=='b1_status':
     if v not in STATUSES:raise ValueError('invalid_status')
    else:
     v=num(v)
     if ch=='b1_soc' and not 0<=v<=100:raise ValueError('invalid_soc')
    # HA timestamps are preserved; never claim device acquisition time.
    for field in ('last_reported','last_updated','last_changed'):
     if state.get(field) is not None and ts(state[field])>ct:raise ValueError('future_ha_timestamp')
    if ch in ('m1_import','m1_export'):
     rt=ts(state.get('last_reported'));age=(ct-rt).total_seconds()
     if age>210:raise ValueError('stale_ha_write') # test policy, not approved production
     if v<0:raise ValueError('negative_register')
     if old and rt<ts(old[0]):raise ValueError('out_of_order')
     if old and rt==ts(old[0]):
      if v!=old[1]:raise ValueError('report_conflict')
      q='repeated_ha_write'
     else:
      if old and v<old[1]:
       self.c.execute('insert or ignore into quarantine_origin values(?,?)',(ch,json.dumps(old)))
       self.c.execute('insert or replace into quarantine values(?,?)',(ch,'register_drop'));q='quarantined_drop'
      elif self.c.execute('select 1 from quarantine where channel=?',(ch,)).fetchone():q='quarantined'
      elif old and v>old[1]:self.c.execute('insert into deltas values(?,?,?,?,?,?)',(ch,id,v-old[1],old[0],rt.isoformat(),'unallocated'))
      self.c.execute('insert or replace into baselines values(?,?,?)',(ch,rt.isoformat(),v))
   except (ValueError,TypeError,KeyError) as e:q=str(e)
   self.c.execute('insert into observations values(?,?,?,?,?)',(ch,id,ct.isoformat(),raw,q));self.c.execute('COMMIT');return q
  except Exception:
   if self.c.in_transaction:self.c.execute('ROLLBACK')
   raise
 def approval_status(self,id):
  r=self.c.execute('select channel,new_time,new_value,actor,reason from approvals where request_id=?',(id,)).fetchone()
  return {'status':'COMMITTED','details':r} if r else {'status':'NOT_FOUND','instruction':'no_automatic_retry_or_resume'}
 def approve(self,id,ch,expected_time,value,report_time,captured,actor,reason):
  if ch not in ('m1_import','m1_export') or not all(isinstance(x,str) and x.strip() for x in (id,actor,reason)):raise ValueError('approval_required')
  v=num(value);rt=ts(report_time);ct=ts(captured)
  if v<0 or not 0<=(ct-rt).total_seconds()<=210:raise ValueError('invalid_baseline')
  payload=hashlib.sha256(json.dumps([ch,expected_time,v,rt.isoformat(),actor,reason]).encode()).hexdigest()
  self.c.execute('BEGIN IMMEDIATE')
  try:
   existing=self.c.execute('select payload_hash from approvals where request_id=?',(id,)).fetchone()
   if existing:
    if existing[0]!=payload:raise ValueError('request_id_conflict')
    self.c.execute('ROLLBACK');return 'ALREADY_COMMITTED'
   old=self.c.execute('select report_time,value from baselines where channel=?',(ch,)).fetchone()
   if not old or old[0]!=expected_time:raise ValueError('baseline_changed')
   if rt<ts(old[0]):raise ValueError('older_baseline')
   if not self.c.execute('select 1 from quarantine where channel=?',(ch,)).fetchone():raise ValueError('not_quarantined')
   origin=self.c.execute('select baseline_json from quarantine_origin where channel=?',(ch,)).fetchone()
   audit_old={'last_observed_baseline':old,'pre_quarantine_baseline':json.loads(origin[0]) if origin else None}
   self.c.execute('insert into approvals values(?,?,?,?,?,?,?,?)',(id,payload,ch,json.dumps(audit_old),rt.isoformat(),v,actor,reason))
   self.c.execute('insert or replace into baselines values(?,?,?)',(ch,rt.isoformat(),v));self.c.execute('delete from quarantine where channel=?',(ch,));self.c.execute('delete from quarantine_origin where channel=?',(ch,));self.c.execute('COMMIT');return 'COMMITTED'
  except Exception:
   if self.c.in_transaction:self.c.execute('ROLLBACK')
   raise
 def summary(self):
  return {'fingerprint':self.fingerprint,'quality':self.c.execute('select channel,quality,count(*) from observations group by channel,quality').fetchall(),'register_kwh':self.c.execute('select channel,sum(kwh) from deltas group by channel').fetchall(),'power_integration':'disabled','device_measurement_coverage':None,'integrity':self.c.execute('pragma integrity_check').fetchone()[0]}
def isolated_call(factory,operation):
 """Optional-layer boundary; never invokes or restarts legacy observer."""
 a=None
 try:a=factory();return {'status':'OK','result':operation(a)}
 except Exception:return {'status':'ERROR','reason':'new_layer_failed'}
 finally:
  if a:
   try:a.close()
   except Exception:pass
def main():
 p=argparse.ArgumentParser();p.add_argument('--fixture',required=True);p.add_argument('--config',required=True);p.add_argument('--test-db',required=True);args=p.parse_args()
 stop=threading.Event();signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
 a=Adapter(args.test_db,json.load(open(args.config)))
 try:
  with open(args.fixture) as f:
   for line in f:
    if stop.is_set():break
    s=json.loads(line);a.ingest(**s)
  print(json.dumps(a.summary()))
 finally:a.close()
if __name__=='__main__':main()
