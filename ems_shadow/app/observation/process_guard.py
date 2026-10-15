"""Offline optional-layer process supervisor. Does not own legacy observer."""
import os,signal,subprocess,time,resource
class Guard:
 def __init__(self,command,max_attempts=2,retry_delay=.1,grace=.2,kill_grace=.5,run_timeout=2,memory_bytes=None):
  if max_attempts<1 or min(retry_delay,grace,kill_grace,run_timeout)<=0:raise ValueError('invalid_limits')
  self.command=command;self.max_attempts=max_attempts;self.delay=retry_delay;self.grace=grace;self.kill_grace=kill_grace;self.timeout=run_timeout;self.memory=memory_bytes
  self.child=None;self.attempts=0;self.state='IDLE';self.next_start=0;self.events=[]
 def _limit(self):
  if self.memory:resource.setrlimit(resource.RLIMIT_AS,(self.memory,self.memory))
 def shutdown(self):
  c=self.child
  if c is None:return True
  def send(sig):
   try:os.killpg(c.pid,sig)
   except ProcessLookupError:pass
  send(signal.SIGTERM)
  try:c.wait(timeout=self.grace)
  except subprocess.TimeoutExpired:pass
  # Also remove descendants, even if group leader already exited.
  send(signal.SIGKILL)
  try:c.wait(timeout=self.kill_grace)
  except subprocess.TimeoutExpired:
   self.state='UNKNOWN';self.events.append('shutdown_unconfirmed');return False
  self.child=None;return True
 def tick(self):
  if self.state in ('DISABLED','UNKNOWN','STOPPED'):return
  now=time.monotonic()
  if self.child:
   if self.child.poll() is not None or now-self.started>self.timeout:
    reason='process_exit' if self.child.poll() is not None else 'execution_timeout'
    self.events.append(reason)
    if not self.shutdown():return
    self.next_start=now+self.delay
    if self.attempts>=self.max_attempts:self.state='DISABLED';return
  if self.child is None and now>=self.next_start:
   self.attempts+=1
   try:
    self.child=subprocess.Popen(self.command,start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,preexec_fn=self._limit if self.memory else None)
    self.started=now;self.state='RUNNING'
   except OSError:
    self.events.append('launch_failed');self.next_start=now+self.delay
    if self.attempts>=self.max_attempts:self.state='DISABLED'
 def stop(self):
  was_unknown=self.state=='UNKNOWN'
  if self.shutdown() and not was_unknown:self.state='STOPPED'

def run_guard(guard):
 """Main-thread signal handler for the isolated offline harness."""
 stopping=False
 def stop(*_):
  nonlocal stopping
  stopping=True
 old={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT)}
 try:
  while not stopping and guard.state not in ('DISABLED','UNKNOWN'):
   guard.tick();time.sleep(.01)
 finally:
  guard.stop()
  for s,h in old.items():signal.signal(s,h)
