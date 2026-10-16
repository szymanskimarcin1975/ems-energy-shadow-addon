"""Independent observer and optional export sidecar; no automatic export restart."""
import json, os, signal, subprocess, sys, time
from pathlib import Path

def status(state, reason):
    # Allowlisted fixed reasons only; never print exception text or options.
    print(json.dumps({'component':'diagnostic_export','state':state,'reason':reason}),flush=True)

def signal_group(child, sig):
    if child is not None and child.poll() is None:
        try: os.killpg(child.pid,sig)
        except ProcessLookupError: pass

def run(observer_command, controller_command=None, retry=10, grace=15, kill_grace=2):
    stopping=False; observer=None; controller=None; next_start=0; exit_code=0;term_sent=False
    def shutdown(*_):
        nonlocal stopping,term_sent
        stopping=True
        # Signal both process groups immediately, including export grandchildren.
        if not term_sent:
            term_sent=True
            signal_group(observer,signal.SIGTERM);signal_group(controller,signal.SIGTERM)
    previous={s:signal.signal(s,shutdown) for s in (signal.SIGTERM,signal.SIGINT)}
    try:
        observer=subprocess.Popen(observer_command,start_new_session=True,stdin=subprocess.DEVNULL)
        if controller_command:
            try: controller=subprocess.Popen(controller_command,start_new_session=True)
            except Exception: status('ERROR','controller_start_failed')
        else: status('DISABLED','export_disabled')
        while not stopping:
            if controller is not None and controller.poll() is not None:
                # Kill surviving descendants; never replay accepted exports.
                try:os.killpg(controller.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                status('ERROR','controller_exited');controller=None
            if observer is not None and observer.poll() is not None:
                code=observer.returncode;observer=None
                if code==78:exit_code=78;break
                next_start=time.monotonic()+retry
                print('observer_exited; retrying_after_delay',flush=True)
            if observer is None and time.monotonic()>=next_start:
                observer=subprocess.Popen(observer_command,start_new_session=True,stdin=subprocess.DEVNULL)
            time.sleep(.05)
    finally:
        shutdown()
        deadline=time.monotonic()+grace
        children=[c for c in (observer,controller) if c is not None]
        while any(c.poll() is None for c in children) and time.monotonic()<deadline:time.sleep(.05)
        for c in children:
            # Also kill descendants of a controller which exited on TERM.
            try:os.killpg(c.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        deadline=time.monotonic()+kill_grace
        while any(c.poll() is None for c in children) and time.monotonic()<deadline:time.sleep(.05)
        if any(c.poll() is None for c in children):
            status('UNKNOWN','shutdown_unconfirmed');exit_code=70
        for s,handler in previous.items():signal.signal(s,handler)
    return exit_code

def main():
    app=Path(__file__).resolve().parent
    # Invalid export options cannot prevent the observer validating its own config.
    enabled=False
    try:
        value=json.loads(Path('/data/options.json').read_text()).get('diagnostic_export_enabled',False)
        if type(value) is not bool:raise ValueError()
        enabled=value
    except Exception:status('ERROR','export_options_invalid')
    if not enabled:status('DISABLED','export_disabled')
    return run([sys.executable,str(app.parent/'runner.py')],
               [sys.executable,str(app/'service.py')] if enabled else [sys.executable,str(app/'disabled_stdin.py')])
if __name__=='__main__':raise SystemExit(main())
