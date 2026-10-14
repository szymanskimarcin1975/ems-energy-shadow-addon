import unittest
from pathlib import Path
class Tests(unittest.TestCase):
 def test_observer_byte_identical(self):
  base=Path(__file__).resolve().parent
  import hashlib,json
  original=base.parents[1]/'ems_shadow/app'
  packaged=original if original.exists() else Path('/app')
  manifest=json.loads((base/'observer_manifest.json').read_text())
  for name,digest in manifest.items():
   self.assertEqual(hashlib.sha256((packaged/name).read_bytes()).hexdigest(),digest,name)
   if original.exists():self.assertEqual(hashlib.sha256((original/name).read_bytes()).hexdigest(),digest,name)
 def test_same_identity_no_extra_permissions(self):
  base=Path(__file__).resolve().parent
  text=(base.parents[1]/'ems_shadow/config.yaml').read_text()
  self.assertIn('slug: ems_energy_shadow',text)
  self.assertIn('diagnostic_export_enabled: false',text)
  self.assertIn('stdin: true',text);self.assertIn('timeout: 30',text)
  for unsafe in ('docker_api: true','privileged:','full_access: true','host_network: true','ports:'):
   self.assertNotIn(unsafe,text)
