import json
import sqlite3
import tempfile
import threading
import unittest
import fcntl
from pathlib import Path
from unittest.mock import patch
import test_runner  # Establish app path both on host and inside the image.
import runner
from settings import ConfigurationError, load_ledger_id

class LedgerTests(unittest.TestCase):
    def options(self, root, ledger='new_measurements', changed=False):
        o=json.loads((Path(__file__).parent/'example_options.json').read_text())
        o['ledger_id']=ledger
        if changed:o['sources']['grid_kw']='sensor.example_corrected_grid'
        p=root/'options.json';p.write_text(json.dumps(o));return p
    def run_one(self, root, options, stamp='2026-10-12T08:00:00+00:00'):
        stop=threading.Event()
        def capture(*_):stop.set();return test_runner.RunnerTests().sample(stamp)
        with patch.dict('os.environ',SUPERVISOR_TOKEN='synthetic'),patch.object(runner,'capture',capture):
            runner.run(root,root/'report.yaml',stop,options_path=options)
        return json.loads((root/'report.yaml').read_text())
    def test_invalid_or_missing_id_no_files_no_capture(self):
        for value in (None,'','../other','/data','legacy','shadow','UPPER',123,'a'*65):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);p=self.options(root,value)
                with patch.object(runner,'capture') as capture:
                    with self.assertRaises(ConfigurationError):runner.run(root/'data',root/'r',options_path=p)
                    capture.assert_not_called();self.assertFalse((root/'data').exists())
    def test_new_ledger_preserves_real_legacy_wal_shm_and_no_history_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=sqlite3.connect(root/'shadow.sqlite')
            old.execute('PRAGMA journal_mode=WAL');old.execute('CREATE TABLE old_data(value)')
            old.execute('INSERT INTO old_data VALUES(42)');old.commit()
            try:
                paths=[root/('shadow.sqlite'+suffix) for suffix in ('','-wal','-shm')]
                before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
                r=self.run_one(root,self.options(root,changed=True))
                self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths})
                self.assertEqual(r['samples'],1);self.assertEqual(r['energy'],[])
                self.assertEqual(r['ledger_id'],'new_measurements')
                self.assertEqual(old.execute('SELECT value FROM old_data').fetchone()[0],42)
            finally:old.close()
    def test_restart_same_id_preserves_samples_and_digest_no_gap_energy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=self.options(root)
            first=self.run_one(root,p);second=self.run_one(root,p,'2026-10-12T08:00:20+00:00')
            self.assertEqual(second['samples'],2);self.assertEqual(second['integrated_seconds'],0)
            self.assertEqual(first['sources_digest'],second['sources_digest'])
    def test_changed_sources_block_same_id_allow_explicit_new_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);first=self.run_one(root,self.options(root))
            p=self.options(root,changed=True)
            with patch.dict('os.environ',SUPERVISOR_TOKEN='synthetic'),patch.object(runner,'capture') as capture:
                with self.assertRaisesRegex(ConfigurationError,'source_change_requires_separate_ledger'):
                    runner.run(root,root/'report.yaml',options_path=p)
                capture.assert_not_called()
            self.assertEqual(json.loads((root/'report.yaml').read_text()),first)
            second=self.run_one(root,self.options(root,'explicit_second',True))
            self.assertEqual(second['samples'],1)
            self.assertNotEqual(first['sources_digest'],second['sources_digest'])
            c=sqlite3.connect(root/'ledgers/new_measurements/shadow.sqlite')
            try:self.assertEqual(c.execute('SELECT COUNT(*) FROM samples').fetchone()[0],1)
            finally:c.close()
    def test_global_lock_covers_different_ledger_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=self.options(root,'another')
            with open(root/'observer.lock','a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):runner.run(root,root/'report.yaml',options_path=p)
            self.assertFalse((root/'ledgers').exists())
    def test_symlink_ledger_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'ledgers').symlink_to(root/'victim')
            with patch.dict('os.environ',SUPERVISOR_TOKEN='synthetic'):
                with self.assertRaisesRegex(ConfigurationError,'symlink'):runner.run(root,root/'report.yaml',options_path=self.options(root))

if __name__=='__main__':unittest.main()
