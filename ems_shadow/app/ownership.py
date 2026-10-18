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
   self._verified_state()
   self.c.execute('COMMIT')
  except BaseException:
   if self.c.in_transaction:self.c.execute('ROLLBACK')
   self.c.close();raise
 def _verified_state(self):
  """Check the *entire* durable epoch chain, never just a mutable owner row.

  A mismatched or incomplete journal is not proof of ownership. The audit is
  local evidence only: it does not establish exclusive external device writers.
  Must be called within a consistent SQLite read/write transaction.
  """
  rows=self.c.execute('SELECT name,epoch,fingerprint FROM owner WHERE id=1').fetchall()
  if len(rows)!=1:raise ValueError('ownership_row_invalid')
  name,epoch,fingerprint=rows[0]
  if fingerprint!=self.fingerprint or type(epoch) is not int or epoch<0:
   raise ValueError('ownership_row_invalid')
  previous='LEGACY';expected_epoch=0
  for old,new,observed_epoch in self.c.execute('SELECT previous,next,epoch FROM audit ORDER BY epoch'):
   if old!=previous or type(observed_epoch) is not int or observed_epoch!=expected_epoch+1:
    raise ValueError('ownership_epoch_chain_invalid')
   if not ((old=='LEGACY' and new=='TRANSFER_PENDING') or
           (old=='TRANSFER_PENDING' and new=='EMS2') or
           new=='BLOCKED' or
           (old=='BLOCKED' and new=='LEGACY')):
    raise ValueError('ownership_transition_chain_invalid')
   previous=new;expected_epoch=observed_epoch
  if name!=previous or epoch!=expected_epoch:raise ValueError('ownership_head_audit_mismatch')
  return name,epoch

 def state(self):
  # A fresh consistent SQLite snapshot prevents observing owner/audit at
  # different commit boundaries. Any uncertainty is explicitly fail closed.
  try:
   self.c.execute('BEGIN')
   try:
    n,e=self._verified_state()
   finally:
    if self.c.in_transaction:self.c.execute('ROLLBACK')
   return {'owner':n,'epoch':e,'local_durable_fence':True,
           'external_fence_verified':False,'commands_permitted':False}
  except (sqlite3.Error,ValueError):
   if self.c.in_transaction:self.c.execute('ROLLBACK')
   return {'owner':'BLOCKED','epoch':-1,'local_durable_fence':False,
           'external_fence_verified':False,'commands_permitted':False,
           'integrity':'OWNER_AUDIT_UNCONFIRMED'}
 def transition(self,request_id,expected_epoch,target,*,old_stopped=False,new_stopped=False,external_fence_verified=False):
  # No direct LEGACY -> EMS2 shortcut. Flags are test protocol inputs, not proof.
  if not isinstance(request_id,str) or not request_id or len(request_id)>64:raise ValueError('invalid_request')
  self.c.execute('BEGIN IMMEDIATE')
  try:
   self._verified_state() # Reject even idempotent replay if journal integrity is unknown.
   existing=self.c.execute('SELECT previous,next,epoch FROM audit WHERE request_id=?',(request_id,)).fetchone()
   if existing:
    if existing[1]!=target or existing[2]!=expected_epoch+1:raise ValueError('request_conflict')
    self.c.execute('COMMIT');return 'DUPLICATE'
   current,epoch=self._verified_state()
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
