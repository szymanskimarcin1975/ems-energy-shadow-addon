import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

class SupervisionTests(unittest.TestCase):
    def test_crash_restart_and_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=str(pathlib.Path(__file__).resolve().parents[1]/'app')
            marker=pathlib.Path(tmp)/'runs'
            code="import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_text(p.read_text()+'x' if p.exists() else 'x'); sys.exit(3)"
            wrapper="import sys; sys.path.insert(0,sys.argv[1]); from supervise import supervise; supervise([sys.executable,'-c',sys.argv[3],sys.argv[2]],retry=.05)"
            proc=subprocess.Popen([sys.executable,'-c',wrapper,app,str(marker),code],stdout=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    if marker.exists() and len(marker.read_text())>=2:break
                    time.sleep(.02)
                self.assertGreaterEqual(len(marker.read_text()),2)
                proc.terminate();self.assertEqual(proc.wait(timeout=5),0)
                count=marker.read_text();time.sleep(.1);self.assertEqual(marker.read_text(),count)
            finally:
                if proc.poll() is None:proc.kill();proc.wait()

if __name__=='__main__':unittest.main()
