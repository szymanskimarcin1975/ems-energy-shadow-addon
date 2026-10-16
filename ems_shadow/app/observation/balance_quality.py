"""Diagnostic snapshot quality; never reports device coverage or integrates energy."""
import hashlib,json
from statistics import median
from datetime import timedelta
from weather_demand import stamp
from building_balance import inspect

class Quality:
 def __init__(self,c):
  self.c=c
  c.executescript('CREATE TABLE IF NOT EXISTS quality_metadata(key PRIMARY KEY,value);CREATE TABLE IF NOT EXISTS balance_checks(id PRIMARY KEY,quality,report_key,record);CREATE TABLE IF NOT EXISTS balance_reports(id PRIMARY KEY,captured,record);')
 def observe(self,states,at,options):
  ac=states.get(options['observation']['solar_sources']['ac_power'],{})
  grid=states.get(options['sources']['grid_kw'],{})
  result=inspect(ac,grid,at)
  sources=[{k:s.get(k) for k in ('entity_id','state','last_reported','last_updated','last_changed')} for s in (ac,grid)]
  key=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
  valid=result['status']=='DIAGNOSTIC_ONLY'
  record=dict(result,sources=sources,captured_at=at,device_measured_at=None)
  sources_hash=hashlib.sha256(json.dumps([options['observation']['solar_sources']['ac_power'],options['sources']['grid_kw']]).encode()).hexdigest()
  self.c.execute('BEGIN IMMEDIATE')
  try:
   old=self.c.execute("SELECT value FROM quality_metadata WHERE key='source_fingerprint'").fetchone()
   if old and old[0]!=sources_hash:raise ValueError('separate_quality_ledger_required')
   self.c.execute("INSERT OR IGNORE INTO quality_metadata VALUES('source_fingerprint',?)",(sources_hash,))
   if self.c.execute('SELECT 1 FROM balance_checks WHERE id=?',(at,)).fetchone():self.c.execute('ROLLBACK');return 'duplicate_capture'
   repeated=self.c.execute('SELECT 1 FROM balance_reports WHERE id=?',(key,)).fetchone()
   quality='REPEATED_HA_SNAPSHOT' if valid and repeated else result['status']
   if valid and not repeated:self.c.execute('INSERT INTO balance_reports VALUES(?,?,?)',(key,at,json.dumps(record,allow_nan=False)))
   self.c.execute('INSERT INTO balance_checks VALUES(?,?,?,?)',(at,quality,key,json.dumps(record,allow_nan=False)))
   self.c.execute('COMMIT')
  except Exception:
   if self.c.in_transaction:self.c.execute('ROLLBACK')
   raise
  return quality
 def summary(self,at):
  now=stamp(at);since=(now-timedelta(minutes=30)).isoformat()
  rows=[json.loads(x[0]) for x in self.c.execute('SELECT record FROM balance_reports WHERE captured>=? AND captured<=? ORDER BY captured',(since,at))]
  suffix=[]
  for row in rows:
   if suffix and (stamp(row['captured_at'])-stamp(suffix[-1]['captured_at'])).total_seconds()>300:suffix=[]
   suffix.append(row)
  ready=False
  if len(suffix)>=6:
   span=(stamp(suffix[-1]['captured_at'])-stamp(suffix[0]['captured_at'])).total_seconds()
   ready=span>=600 and (now-stamp(suffix[-1]['captured_at'])).total_seconds()<=240
  result={'ready':ready,'status':'CONDITIONAL_PROFILE_READY' if ready else 'INSUFFICIENT_QUALIFIED_SNAPSHOTS',
      'unique_ha_snapshots':len(suffix),'method':'median_of_distinct_HA_snapshots_not_device_reports',
      'control_approved':False,'energy_integrated_kwh':None,'device_report_coverage':None,
      'checks_30m':dict(self.c.execute('SELECT quality,count(*) FROM balance_checks WHERE id>=? AND id<=? GROUP BY quality',(since,at)))}
  if ready:
   powers=sorted(r['candidate_building_w'] for r in suffix)
   result.update(power_w=median(powers),observed_min_max_w=[min(powers),max(powers)],observed_start=suffix[0]['captured_at'],observed_end=suffix[-1]['captured_at'],uncertainty_calibrated=False)
  return result
