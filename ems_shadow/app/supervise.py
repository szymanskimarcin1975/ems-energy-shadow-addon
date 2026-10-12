"""Restart crashed observer, forward stop signals, never overlap children."""
import os
import signal
import subprocess
import sys
import threading

def supervise(command, stop=None, retry=10):
    stop = stop or threading.Event()
    child = None
    def shutdown(*_):
        stop.set()
        if child is not None and child.poll() is None:
            child.terminate()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    while not stop.is_set():
        child = subprocess.Popen(command)
        if stop.is_set(): child.terminate()
        while child.poll() is None:
            if stop.wait(.2):
                try: child.wait(timeout=15)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
                break
        # Child is reaped before any replacement; DB/lock belong to observer.
        if child.returncode==78 and not stop.is_set():
            print('configuration_error; observation_disabled',flush=True)
            return 78
        if not stop.is_set():
            print('observer_exited; retrying_after_delay', flush=True)
            stop.wait(retry)
    return 0

if __name__ == '__main__':
    sys.exit(supervise([sys.executable, os.path.join(os.path.dirname(__file__), 'runner.py')]))
