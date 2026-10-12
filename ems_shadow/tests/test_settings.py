import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import runner
from settings import load_sources, ConfigurationError

class SettingsTests(unittest.TestCase):
    def test_empty_missing_duplicate_wrong_domain(self):
        original=json.loads((Path(__file__).parent/'example_options.json').read_text())
        for kind in ('empty','missing','duplicate','wrong_domain'):
            options=json.loads(json.dumps(original))
            if kind=='empty': options['sources']['inverter_w']=''
            if kind=='missing': options['sources'].pop('grid_kw')
            if kind=='duplicate': options['sources']['grid_kw']=options['sources']['inverter_w']
            if kind=='wrong_domain': options['sources']['workday']='sensor.example_workday'
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'options.json';p.write_text(json.dumps(options))
                with self.assertRaises(ConfigurationError):load_sources(p)
                with patch.object(runner,'capture') as capture:
                    with self.assertRaises(ConfigurationError):runner.run(Path(tmp)/'data',Path(tmp)/'r.yaml',options_path=p)
                    capture.assert_not_called();self.assertFalse((Path(tmp)/'data').exists())
    def test_source_change_blocks_existing_ledger(self):
        import threading
        original=json.loads((Path(__file__).parent/'example_options.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'options.json';p.write_text(json.dumps(original));stop=threading.Event();stop.set()
            with patch.dict('os.environ',SUPERVISOR_TOKEN='test-only'):
                runner.run(tmp,Path(tmp)/'report.yaml',stop,options_path=p)
                original['sources']['boiler_w']='sensor.example_other_boiler'
                p.write_text(json.dumps(original))
                with self.assertRaises(ConfigurationError):runner.run(tmp,Path(tmp)/'report.yaml',stop,options_path=p)

if __name__=='__main__':unittest.main()
