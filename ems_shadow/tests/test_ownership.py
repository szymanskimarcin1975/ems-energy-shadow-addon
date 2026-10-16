import unittest,tempfile,sqlite3
from pathlib import Path
from ownership import Ownership
class Tests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.p=Path(self.t.name)/'ownership.sqlite'
 def open(self):return Ownership(self.p,{'example':'sensor.example_battery'})
 def test_restart_preserves_pending_and_never_activates(self):
  a=self.open();a.transition('r',0,'TRANSFER_PENDING');a.close();b=self.open();self.assertEqual(b.state()['owner'],'TRANSFER_PENDING');self.assertFalse(b.state()['commands_permitted']);b.close()
 def test_direct_takeover_rejected(self):
  a=self.open()
  with self.assertRaises(ValueError):a.transition('r',0,'EMS2',old_stopped=True,external_fence_verified=True)
  self.assertEqual(a.state()['owner'],'LEGACY');self.assertEqual(a.c.execute('select count(*) from audit').fetchone()[0],0);a.close()
 def test_competing_epochs_and_replay(self):
  a=self.open();b=self.open();a.transition('r',0,'TRANSFER_PENDING')
  with self.assertRaises(ValueError):b.transition('other',0,'TRANSFER_PENDING')
  self.assertEqual(b.transition('r',0,'TRANSFER_PENDING'),'DUPLICATE');a.close();b.close()
 def test_missing_external_fence_blocks(self):
  a=self.open();a.transition('r',0,'TRANSFER_PENDING')
  with self.assertRaises(ValueError):a.transition('s',1,'EMS2',old_stopped=True)
  self.assertEqual(a.state()['owner'],'TRANSFER_PENDING');a.close()
 def test_unknown_no_auto_legacy(self):
  a=self.open();a.transition('r',0,'BLOCKED')
  with self.assertRaises(ValueError):a.transition('s',1,'LEGACY')
  a.close()
 def test_reopen_integrity_atomic_audit(self):
  a=self.open();a.transition('r',0,'TRANSFER_PENDING');a.close()
  with sqlite3.connect(self.p) as c:
   self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok');self.assertEqual(c.execute('select epoch from owner').fetchone()[0],c.execute('select max(epoch) from audit').fetchone()[0])
 def test_source_change_refused(self):
  a=self.open();a.close()
  with self.assertRaises(ValueError):Ownership(self.p,{'different':'sensor.example_other'})
 def test_process_crash_before_commit_rolls_back_owner_and_audit(self):
  import subprocess,sys
  a=self.open();a.close()
  script="import sqlite3,os,sys;c=sqlite3.connect(sys.argv[1]);c.execute('BEGIN IMMEDIATE');c.execute(\"UPDATE owner SET name='TRANSFER_PENDING',epoch=1\");c.execute(\"INSERT INTO audit VALUES('crash','LEGACY','TRANSFER_PENDING',1)\");os._exit(9)"
  self.assertEqual(subprocess.run([sys.executable,'-c',script,str(self.p)]).returncode,9)
  a=self.open();self.assertEqual(a.state()['owner'],'LEGACY');self.assertEqual(a.c.execute('select count(*) from audit').fetchone()[0],0);self.assertEqual(a.c.execute('pragma integrity_check').fetchone()[0],'ok');a.close()
 def test_commit_then_crash_has_durable_audit_and_no_automatic_retry(self):
  import subprocess,sys
  a=self.open();a.close()
  script="import sqlite3,os,sys;c=sqlite3.connect(sys.argv[1]);c.execute('BEGIN IMMEDIATE');c.execute(\"UPDATE owner SET name='TRANSFER_PENDING',epoch=1\");c.execute(\"INSERT INTO audit VALUES('crash','LEGACY','TRANSFER_PENDING',1)\");c.commit();os._exit(9)"
  self.assertEqual(subprocess.run([sys.executable,'-c',script,str(self.p)]).returncode,9)
  a=self.open();self.assertEqual(a.state()['owner'],'TRANSFER_PENDING');self.assertFalse(a.state()['commands_permitted']);self.assertEqual(a.transition('crash',0,'TRANSFER_PENDING'),'DUPLICATE');self.assertEqual(a.c.execute('pragma integrity_check').fetchone()[0],'ok');a.close()
