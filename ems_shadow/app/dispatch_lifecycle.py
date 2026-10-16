"""Durable command lifecycle. A HA ACK or elapsed timeout never proves termination.
No actuator or cancellation transport exists here. Confirmation requires separately
verified, request-correlated device evidence; production does not fabricate it.
"""
import json
from datetime import datetime

def initialise(db):
 db.execute('CREATE TABLE IF NOT EXISTS active_dispatch(id INTEGER PRIMARY KEY CHECK(id=1),request_id TEXT NOT NULL,option TEXT NOT NULL,status TEXT NOT NULL,issued_at TEXT NOT NULL,updated_at TEXT NOT NULL)')
 db.execute('CREATE TABLE IF NOT EXISTS dispatch_audit(id INTEGER PRIMARY KEY,request_id TEXT NOT NULL,event TEXT NOT NULL,record TEXT NOT NULL)')
 # Import no claims of completion from an older executor journal.
 if db.execute('SELECT 1 FROM active_dispatch').fetchone() is None:
  old=db.execute("SELECT id,mode FROM commands WHERE status IN ('ACK','PENDING','UNKNOWN') ORDER BY rowid DESC LIMIT 1").fetchone()
  if old:
   db.execute('INSERT INTO active_dispatch VALUES(1,?,?,?,?,?)',(old[0],old[1],'UNKNOWN_IMPORTED_HISTORY','1970-01-01T00:00:00+00:00','1970-01-01T00:00:00+00:00'));db.commit()
def state(db):
 row=db.execute('SELECT request_id,option,status,issued_at,updated_at FROM active_dispatch').fetchone()
 if row is None:return {'status':'NO_EMS2_COMMAND_RECORDED','termination_confirmed':False,'termination_method':'UNCONFIRMED_NO_CANCEL_COMMAND_IMPLEMENTED'}
 r=dict(zip(('request_id','option','status','issued_at','updated_at'),row));r.update(termination_confirmed=row[2] in ('ENDED_CONFIRMED','REJECTED_NO_WRITE'),termination_method='VERIFIED_EXTERNAL_DEVICE_EVIDENCE_REQUIRED')
 return r
def permit(db,request_id):
 s=state(db)
 if s['status']!='NO_EMS2_COMMAND_RECORDED' and not s['termination_confirmed']:return 'PREVIOUS_COMMAND_TERMINATION_UNCONFIRMED'
 return None
def event(db,request_id,name,record):db.execute('INSERT INTO dispatch_audit(request_id,event,record) VALUES(?,?,?)',(request_id,name,json.dumps(record,allow_nan=False,sort_keys=True)))
def begin(db,request_id,option,now):
 db.execute('INSERT OR REPLACE INTO active_dispatch VALUES(1,?,?,?,?,?)',(request_id,option,'PENDING',now.isoformat(),now.isoformat()));event(db,request_id,'PENDING',{'at':now.isoformat(),'option':option})
def finish(db,request_id,status,now):
 new={'ACK':'ACK_ACTIVE_NOT_TERMINATED','REJECTED':'REJECTED_NO_WRITE'}.get(status,'UNKNOWN_REQUIRES_RECONCILIATION')
 db.execute('UPDATE active_dispatch SET status=?,updated_at=? WHERE request_id=?',(new,now.isoformat(),request_id));event(db,request_id,new,{'at':now.isoformat()})
def hold(db,now,reason):
 s=state(db)
 # HOLD never rewrites an active/unknown command into a completed one.
 return {'status':'HOLD_REQUIRES_TERMINATION' if s['status']!='NO_EMS2_COMMAND_RECORDED' and not s['termination_confirmed'] else 'HOLD_NO_EMS2_COMMAND_TO_CANCEL','reason':reason,'cancel_sent':False,'active_command':s}
def confirm_termination(db,request_id,evidence,now):
 """Explicit verified-evidence interface; not called automatically in production."""
 s=state(db)
 if s.get('request_id')!=request_id:raise ValueError('termination_request_mismatch')
 t=datetime.fromisoformat(evidence.get('observed_at',''));issued=datetime.fromisoformat(s['issued_at'])
 if t.tzinfo is None or not issued<=t<=now or (now-t).total_seconds()>180:raise ValueError('termination_evidence_time')
 if evidence.get('inverter_command_inactive_confirmed') is not True or evidence.get('source')!='verified_manufacturer_device_status' or not isinstance(evidence.get('reference'),str) or not evidence['reference'].strip():raise ValueError('termination_evidence_unverified')
 db.execute('BEGIN IMMEDIATE')
 try:
  # Recheck the identity while holding the write lock.
  if state(db).get('request_id')!=request_id:raise ValueError('termination_request_changed')
  event(db,request_id,'ENDED_CONFIRMED',evidence)
  db.execute("UPDATE active_dispatch SET status='ENDED_CONFIRMED',updated_at=? WHERE request_id=?",(now.isoformat(),request_id));db.commit()
 except BaseException:
  db.rollback();raise
