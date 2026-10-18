"""Legacy observer plus isolated optional workers and diagnostic publisher."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'observation'))
from identity_monitor import IdentityProgressGuard
from worker import atomic,INTERVALS
from shutdown_budget import shutdown_all

def main():
 app=Path(__file__).parent;guards=[];stopping=False;legacy=None;publisher=None;last_reports={};legacy_term_sent=False
 def shutdown(*_):
  nonlocal stopping,legacy_term_sent
  stopping=True
  # Immediately notify legacy gateway, not after optional-worker shutdowns.
  if not legacy_term_sent and legacy is not None and legacy.poll() is None:
   try:
    os.killpg(legacy.pid,signal.SIGTERM);legacy_term_sent=True
   except ProcessLookupError:pass
 previous={s:signal.signal(s,shutdown) for s in (signal.SIGTERM,signal.SIGINT)}
 legacy=subprocess.Popen([sys.executable,str(app/'staging'/'gateway.py')],start_new_session=True)
 try:
  try:
   options=json.loads(Path('/data/options.json').read_text()).get('observation',{})
   enabled=options.get('enabled') is True
   publisher=subprocess.Popen([sys.executable,str(app/'observation'/'publisher.py'),str(enabled).lower()],start_new_session=True,stdin=subprocess.DEVNULL)
   if enabled:
    root=Path('/data/observation-v1');root.mkdir(exist_ok=True)
    for role in ('solar','weather','boiler','demand','battery'):
     command=[sys.executable,str(app/'observation'/'demand_runtime.py')] if role=='demand' else ([sys.executable,str(app/'battery_runtime.py')] if role=='battery' else [sys.executable,str(app/'observation'/'worker.py'),'--role',role])
     g=IdentityProgressGuard(command,root/(role+'-heartbeat.json'),stall_timeout=45,idle_interval=20 if role in ('demand','battery') else INTERVALS[role],max_attempts=3,retry_delay=10,grace=1,kill_grace=.2)
     guards.append((role,g))
  except Exception:print('observation_init_failed; legacy_unaffected',flush=True)
  while not stopping and legacy.poll() is None:
   for role,g in guards:
    try:
     g.tick()
     if time.monotonic()-last_reports.get(role,0)>=2:
      atomic('/data/observation-v1/'+role+'-supervision.json',{'recorded_at':time.time(),'state':g.state,'attempts':g.attempts,'resource_status':g.resource_status,'events':g.events[-20:]})
      last_reports[role]=time.monotonic()
    except Exception:
     g.state='UNKNOWN';print('observation_supervision_unknown; legacy_unaffected',flush=True)
   time.sleep(.1)
 finally:
  result=shutdown_all(legacy,guards,publisher,budget=22,term_already_sent={'legacy'} if legacy_term_sent else ())
  print(json.dumps({'component':'observation_shutdown',**result}),flush=True)
  for s,h in previous.items():signal.signal(s,h)
 # SIGTERM is the intentional container shutdown path. Only normalize it
 # after shutdown_all has confirmed every child stopped cleanly; unexpected
 # child exits and any incomplete shutdown retain their nonzero status.
 if result['state']=='UNKNOWN' or result.get('unconfirmed'):
  return 70
 if legacy.returncode == -signal.SIGTERM and legacy_term_sent and result['state']=='STOPPED':
  return 0
 return legacy.returncode or 0
if __name__=='__main__':raise SystemExit(main())
