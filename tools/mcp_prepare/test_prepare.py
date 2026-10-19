import asyncio
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('prepare',ROOT/'prepare_operations.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ID='a'*32

class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.src=self.root/'custom_components/solaredge_modbus_multi';self.src.mkdir(parents=True)
        for p,c in {'hub.py':'source','manifest.json':'{"version":"4.0.4"}','translations/pl.json':'{}'}.items():
            f=self.src/p;f.parent.mkdir(exist_ok=True);f.write_text(c)
        self.expected={p:hashlib.sha256((self.src/p).read_bytes()).hexdigest() for p in ['hub.py','manifest.json']}
    def run_prepare(self,id=ID):return m.run(self.root,id,'prepare',self.expected)
    def test_copy_all_hashes_and_originals_unchanged(self):
        before={p.relative_to(self.src):p.read_bytes() for p in self.src.rglob('*') if p.is_file()}
        result=self.run_prepare();self.assertEqual(result['status'],'COMPLETE');self.assertEqual(result['file_count'],3)
        self.assertEqual(before,{p.relative_to(self.src):p.read_bytes() for p in self.src.rglob('*') if p.is_file()})
        self.assertEqual(m.run(self.root,ID,'status')['status'],'COMPLETE')
        self.assertFalse(result['independent_off_host_copy'])
    def test_duplicate_id_never_recopies(self):
        first=self.run_prepare();second=self.run_prepare()
        self.assertEqual(first['manifest_sha256'],second['manifest_sha256'])
        self.assertEqual(len(list((self.root/'ems_prepare_backups').iterdir())),1)
    def test_wrong_original_hash_has_no_backup_write(self):
        self.assertEqual(m.run(self.root,ID,'prepare')['status'],'REJECTED')
        self.assertFalse((self.root/'ems_prepare_backups').exists())
    def test_arbitrary_command_path_or_action_refused(self):
        for id in ['../config','x;reboot','',None]:
            with self.assertRaises(ValueError):self.run_prepare(id)
        with self.assertRaises(ValueError):m.run(self.root,ID,'install')
    def test_source_symlink_refused(self):
        (self.src/'hub.py').unlink();(self.src/'hub.py').symlink_to(self.src/'manifest.json')
        with self.assertRaises(ValueError):self.run_prepare()
    def test_source_parent_symlink_refused(self):
        src=self.root/'custom_components';src.rename(self.root/'moved');src.symlink_to(self.root/'moved',target_is_directory=True)
        with self.assertRaises(OSError):self.run_prepare()
    def test_destination_symlink_refused(self):
        (self.root/'elsewhere').mkdir();(self.root/'ems_prepare_backups').symlink_to(self.root/'elsewhere',target_is_directory=True)
        with self.assertRaises(OSError):self.run_prepare()
    def test_corrupt_backup_detected_not_repaired(self):
        self.run_prepare();p=self.root/'ems_prepare_backups'/ID/'original/hub.py';p.write_text('changed')
        self.assertEqual(m.run(self.root,ID,'status')['status'],'UNKNOWN');self.assertEqual(self.run_prepare()['status'],'UNKNOWN')
        self.assertEqual(p.read_text(),'changed')
    def test_interrupted_copy_unknown_no_retry(self):
        original=m.write
        def fail(fd,name,data):
            if name=='hub.py':raise OSError('simulated full disk')
            return original(fd,name,data)
        with patch.object(m,'write',fail):self.assertEqual(self.run_prepare()['status'],'UNKNOWN')
        self.assertEqual(self.run_prepare()['status'],'UNKNOWN')
    def test_status_missing_does_not_create_directory(self):
        self.assertEqual(m.run(self.root,ID,'status')['status'],'NOT_FOUND');self.assertFalse((self.root/'ems_prepare_backups').exists())
    def test_no_sqlite_or_unexpected_file_copied(self):
        (self.src/'active.sqlite').write_text('not copied')
        with self.assertRaises(ValueError):self.run_prepare()
        self.assertFalse((self.root/'ems_prepare_backups').exists())
    def test_unsafe_existing_backup_root_refused(self):
        base=self.root/'ems_prepare_backups';base.mkdir();base.chmod(0o777)
        with self.assertRaisesRegex(ValueError,'UNSAFE_BACKUP_ROOT_PERMISSIONS'):self.run_prepare()
        self.assertFalse((base/ID).exists())
    def test_private_backup_permissions(self):
        self.run_prepare();op=self.root/'ems_prepare_backups'/ID
        self.assertEqual(op.stat().st_mode&0o777,0o700);self.assertEqual((op/'original/hub.py').stat().st_mode&0o777,0o600)

class AuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_admin_and_extra_arguments_refused_before_io(self):
        pkg='isolated_mcp_prepare';parent=types.ModuleType(pkg);parent.__path__=[]
        tools=types.ModuleType(pkg+'.tools');tools.__path__=[]
        tools.register_tool=lambda **kwargs:lambda f:f
        tools.ANNOTATION_READ_ONLY={};tools.ANNOTATION_NON_IDEMPOTENT={};tools.dumps=json.dumps
        context=types.ModuleType(pkg+'.admin_context')
        async def deny(hass):raise PermissionError('ACTIVE_HA_ADMIN_REQUIRED')
        context.require_admin=deny
        names={pkg:parent,pkg+'.tools':tools,pkg+'.admin_context':context,pkg+'.prepare_operations':m}
        with patch.dict(sys.modules,names):
            spec=importlib.util.spec_from_file_location(pkg+'.tools.ems_prepare',ROOT/'ems_prepare.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
            with patch.object(w,'run') as run:
                with self.assertRaises(PermissionError):await w.invoke(None,{'operation_id':ID},'prepare')
                async def allow(hass):return 'verified-admin'
                w.require_admin=allow
                with self.assertRaises(ValueError):await w.invoke(None,{'operation_id':ID,'command':'reboot'},'prepare')
                run.assert_not_called()

if __name__=='__main__':unittest.main()
