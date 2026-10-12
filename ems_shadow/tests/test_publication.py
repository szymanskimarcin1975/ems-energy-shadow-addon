import re
from pathlib import Path
import unittest

class PublicationTests(unittest.TestCase):
    def test_no_device_addresses_or_installation_defaults(self):
        root=Path(__file__).resolve().parents[1]
        # In image /tests and /app are separate; check both explicitly.
        paths=[root] if (root/'config.yaml').exists() else [Path('/app'),Path('/tests')]
        for directory in paths:
            for p in directory.rglob('*'):
                if not p.is_file() or '__pycache__' in p.parts:continue
                if p.suffix not in ('.py','.md','.yaml','.json'):continue
                text=p.read_text()
                self.assertIsNone(re.search(r'0x[0-9a-fA-F]{16}',text),p.name)
                self.assertIsNone(re.search(r'(?:sensor|binary_sensor)\.(?!example_)[a-z][a-z0-9_]+',text),p.name)

if __name__=='__main__':unittest.main()
