"""Bounded synthetic unit suite; emit stack traces instead of hiding CI hangs."""
import faulthandler,sys,unittest
from pathlib import Path
faulthandler.enable()
faulthandler.dump_traceback_later(45,exit=True)
try:
    suite=unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
finally:faulthandler.cancel_dump_traceback_later()
raise SystemExit(0 if result.wasSuccessful() else 1)
