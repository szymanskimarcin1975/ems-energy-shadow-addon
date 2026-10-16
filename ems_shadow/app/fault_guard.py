"""Durable fail-closed HA fault gate; HA publication is not device-sample proof."""
import json
from datetime import datetime, timezone

READY='FAULT_GUARD_STABLE_HA_OBSERVATIONS_NOT_PHYSICAL_PROOF'
class FaultGuard:
 def __init__(self,db):
  self.db=db
  db.execute('CREATE TABLE IF NOT EXISTS fault_guard(id INTEGER PRIMARY KEY CHECK(id=1),record TEXT NOT NULL)')
  # Restart never restores readiness from a stale persisted flag.
  self.reset('FAULT_RECOVERY_REQUIRED_AFTER_START')
 def reset(self,reason):
  self.record={'status':reason,'first':None,'last':None,'updates':0,'ready':False}
  self.save()
  return reason
 def save(self):
  self.db.execute('INSERT OR REPLACE INTO fault_guard VALUES(1,?)',(json.dumps(self.record,allow_nan=False),))
 def observe(self,ha,sources,now):
  try:
   if set(sources)!={'inverter_status','vendor_status'} or len(set(sources.values()))!=2:
    return self.reset('FAULT_SOURCES_UNCONFIRMED')
   rows=ha.current_states(sources.values());times=[]
   for entity in sources.values():
    row=rows[entity];t=datetime.fromisoformat(row['last_reported'])
    if t.tzinfo is None or not 0<=(now-t).total_seconds()<=180:
     return self.reset('FAULT_TELEMETRY_STALE_OR_FUTURE')
    times.append(t.astimezone(timezone.utc))
   state=rows[sources['inverter_status']]['state'];vendor=rows[sources['vendor_status']]['state']
   if state=='I_STATUS_FAULT':return self.reset('INVERTER_FAULT')
   if str(vendor).lower() in ('1dx88','0x1d88'):return self.reset('INVERTER_HEARTBEAT_ERROR')
   if state!='I_STATUS_MPPT' or str(vendor).lower()!='0x0':return self.reset('INVERTER_RETURN_AMBIGUOUS')
   if (max(times)-min(times)).total_seconds()>5:return self.reset('FAULT_TELEMETRY_UNSYNCHRONISED')
   # Count only snapshots in which BOTH HA source publications advance.
   stamps=[t.isoformat() for t in times];last=self.record['last']
   if last is not None:
    old=[datetime.fromisoformat(s) for s in last]
    if any(t<o for t,o in zip(times,old)):return self.reset('FAULT_TELEMETRY_OUT_OF_ORDER')
    if (max(times)-min(old)).total_seconds()>180:
     self.reset('FAULT_RECOVERY_GAP')
     last=None
   if last is None:
    self.record.update(first=stamps,last=stamps,updates=1)
   elif all(t>datetime.fromisoformat(o) for t,o in zip(times,last)):
    self.record.update(last=stamps,updates=self.record['updates']+1)
   first=[datetime.fromisoformat(s) for s in self.record['first']]
   span=min((t-o).total_seconds() for t,o in zip(times,first))
   self.record['ready']=self.record['updates']>=3 and span>=240
   self.record['status']=READY if self.record['ready'] else 'FAULT_RECOVERY_STABILISING'
   self.record['healthy_ha_span_seconds']=span
   self.save();return self.record['status']
  except (KeyError,TypeError,ValueError,OSError,RuntimeError):
   return self.reset('FAULT_TELEMETRY_READ_UNCONFIRMED')
