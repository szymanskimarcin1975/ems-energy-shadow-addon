"""One shared shutdown deadline; unknown identities are never signalled."""
import os,signal,time

def shutdown_all(legacy,guards,publisher=None,budget=22,grace=18,term_already_sent=()):
 start=time.monotonic();targets=[];unknown=[]
 # Legacy and publisher are directly owned children; no PID discovery.
 for name,c in [('legacy',legacy),('publisher',publisher)]:
  if c is not None and c.poll() is None:targets.append((name,c,None))
 for name,g in guards:
  c=g.child
  if c is None or c.poll() is not None:continue
  if g.state=='UNKNOWN' or g.identity_monitor.sample(time.monotonic())['state']!='VERIFIED':
   g.state='UNKNOWN';unknown.append(name);continue
  targets.append((name,c,g))
 def send(name,c,g,sig):
  if c.poll() is not None:return
  if g is not None and g.identity_monitor.sample(time.monotonic())['state']!='VERIFIED':
   g.state='UNKNOWN'
   if name not in unknown:unknown.append(name)
   return
  try:os.killpg(c.pid,sig)
  except ProcessLookupError:pass
 for n,c,g in targets:
  if n not in term_already_sent:send(n,c,g,signal.SIGTERM)
 while time.monotonic()-start<min(grace,budget) and any(c.poll() is None for _,c,_ in targets):time.sleep(.02)
 for n,c,g in targets:send(n,c,g,signal.SIGKILL)
 while time.monotonic()-start<budget and any(c.poll() is None for n,c,_ in targets if n not in unknown):time.sleep(.02)
 for n,c,g in targets:
  if c.poll() is None and n not in unknown:unknown.append(n)
  if c.poll() is not None:
   try:os.killpg(c.pid,0)
   except ProcessLookupError:pass
   else:
    if n not in unknown:unknown.append(n)
 return {'state':'UNKNOWN' if unknown else 'STOPPED','unconfirmed':unknown,'elapsed_seconds':time.monotonic()-start}
