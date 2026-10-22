"""Synthetic storage boundaries; never opens production data or deletes rows."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from planning_runtime import Planner
from demand_runtime import planning_error_report

class StorageDiagnosticsTests(unittest.TestCase):
    def check_limit(self,size,free,reason):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'private-database.sqlite'
            planner=Planner(path)
            try:
                planner.c.execute("INSERT INTO runs VALUES('preserved','f','{}')")
                with patch.object(Path,'stat',return_value=SimpleNamespace(st_size=size)), patch('planning_runtime.shutil.disk_usage',return_value=SimpleNamespace(free=free)):
                    with self.assertRaises(OSError) as caught:planner.storage_guard()
                self.assertEqual(str(caught.exception),'planning_storage_limit')
                report=planning_error_report(caught.exception,'2026-10-22T17:00:00+00:00','observe')
                self.assertEqual(report['error']['storage']['reason'],reason)
                self.assertFalse(report['current_plan_usable_for_simulation'])
                self.assertNotIn(td,json.dumps(report));self.assertNotIn(path.name,json.dumps(report))
                self.assertEqual(planner.c.execute('SELECT COUNT(*) FROM runs').fetchone()[0],1)
            finally:planner.c.close()
    def test_database_limit(self):self.check_limit(100*1024*1024,128*1024*1024,'DATABASE_SIZE_LIMIT')
    def test_disk_floor(self):self.check_limit(1024,63*1024*1024,'DISK_FREE_FLOOR')
    def test_both(self):self.check_limit(100*1024*1024,0,'DATABASE_AND_DISK_LIMIT')
    def test_legacy_error_unchanged(self):
        report=planning_error_report(OSError('planning_storage_limit'),'2026-10-22T17:00:00+00:00','observe')
        self.assertNotIn('storage',report['error'])
    def test_arbitrary_detail_not_exported(self):
        error=OSError('planning_storage_limit');error.planning_storage_diagnostics={'reason':'secret/path'}
        report=planning_error_report(error,'2026-10-22T17:00:00+00:00','observe')
        self.assertNotIn('storage',report['error'])
    def test_floor_boundary_allows_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            planner=Planner(Path(td)/'p.sqlite')
            try:
                with patch('planning_runtime.shutil.disk_usage',return_value=SimpleNamespace(free=64*1024*1024)):
                    planner.storage_guard()
            finally:planner.c.close()
