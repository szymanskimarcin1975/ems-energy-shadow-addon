"""Durable local ownership protocol. NOT an external HA automation fence.
No device calls. All ambiguous recovery paths remain BLOCKED, never auto-resume.
"""
import hashlib,json,sqlite3
class Ownership:
 def __init__(self,path,sources):
  self.fingerprint=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
  self.c=sqlite3.connect(path,timeout=1,isolation_level=None)
  try:
   self.c.execute('PRAGMA journal_mode=WAL')
   self.c.execute('PRAGMA synchronous=FULL')
   self.c.execute('BEGIN IMMEDIATE')
   self.c.execute('CREATE TABLE IF NOT EXISTS owner(id INTEGER PRIMARY KEY CHECK(id=1),name TEXT NOT NULL,epoch INTEGER NOT NULL,fingerprint TEXT NOT NULL)')
   self.c.execute('CREATE TABLE IF NOT EXISTS audit(request_id TEXT PRIMARY KEY,previous TEXT NOT NULL,next TEXT NOT NULL,epoch INTEGER NOT NULL)')
   self.c.execute('INSERT OR IGNORE INTO owner VALUES(1,?,?,?)',('LEGACY',0,self.fingerprint))
   if self.c.execute('SELECT fingerprint FROM owner').fetchone()[0]!=self.fingerprint:raise ValueError('ownership_source_change')
   self.c.execute('COMMIT')
  except BaseException:
   if self.c.in_transaction:self.c.execute('ROLLBACK')
   self.c.close();raise
 def state(self):
  n,e=self.c.execute('SELECT name,epoch FROM owner WHERE id=1').fetchone()
  return {'owner':n,'epoch':e,'local_durable_fence':True,'external_fence_verified':False,'commands_permitted':False}
 def transition(self,request_id,expected_epoch,target,*,old_stopped=False,new_stopped=False,external_fence_verified=False):
  # No direct LEGACY -> EMS2 shortcut. Flags are test protocol inputs, not proof.
  if not isinstance(request_id,str) or not request_id or len(request_id)>64:raise ValueError('invalid_request')
  self.c.execute('BEGIN IMMEDIATE')
  try:
   existing=self.c.execute('SELECT previous,next,epoch FROM audit WHERE request_id=?',(request_id,)).fetchone()
   if existing:
    if existing[1]!=target or existing[2]!=expected_epoch+1:raise ValueError('request_conflict')
    self.c.execute('COMMIT');return 'DUPLICATE'
   current,epoch=self.c.execute('SELECT name,epoch FROM owner WHERE id=1').fetchone()
   if epoch!=expected_epoch:raise ValueError('ownership_epoch_conflict')
   allowed=(current=='LEGACY' and target=='TRANSFER_PENDING') or (current=='TRANSFER_PENDING' and target=='EMS2' and old_stopped is True and external_fence_verified is True) or (target=='BLOCKED') or (current=='BLOCKED' and target=='LEGACY' and new_stopped is True and external_fence_verified is True)
   if not allowed:raise ValueError('handover_proof_missing')
   self.c.execute('UPDATE owner SET name=?,epoch=? WHERE id=1',(target,epoch+1))
   self.c.execute('INSERT INTO audit VALUES(?,?,?,?)',(request_id,current,target,epoch+1))
   self.c.execute('COMMIT');return 'COMMITTED'
  except BaseException:
   if self.c.in_transaction:self.c.execute('ROLLBACK')
   raise
 def close(self):self.c.close()
