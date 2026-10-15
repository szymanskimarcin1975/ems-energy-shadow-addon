"""Offline progress watchdog; heartbeat must originate from worker loop."""
import json,time,os,signal
from pathlib import Path
from process_guard import Guard
class ProgressGuard(Guard):
 def __init__(self,command,heartbeat,stall_timeout=1,idle_interval=0,**kwargs):
  super().__init__(command,**kwargs);self.heartbeat=Path(heartbeat);self.stall=stall_timeout;self.progress_at=None;self.sequence=None;self.active_since=None;self.idle_interval=idle_interval;self.waiting=False
 def tick(self):
  if self.state in ('DISABLED','UNKNOWN','STOPPED'):return
  now=time.monotonic()
  if self.child is not None and self.child.poll() is None:
   try:
    h=json.loads(self.heartbeat.read_text())
    if h['pid']!=self.child.pid or not isinstance(h['sequence'],int) or h['sequence']<0:raise ValueError()
    if self.sequence is None or h['sequence']>self.sequence:self.sequence=h['sequence'];self.progress_at=now
    elif h['sequence']<self.sequence:raise ValueError()
    # Sequence increments only after loop completes a poll/idle cycle.
    # Separate active transaction watchdog: heartbeat thread cannot hide a hang.
    if h['phase'] in ('polling','writing'):
     if self.active_since is None:self.active_since=now
    elif h['phase'] in ('idle','completed'):self.active_since=None
    else:raise ValueError()
    self.waiting=h['phase'] in ('idle','completed')
   except (OSError,ValueError,KeyError,TypeError):pass
   timed_out=(now-self.active_since>self.stall) if self.active_since is not None else (now-(self.progress_at or self.started)>self.stall+(self.idle_interval if self.waiting else 0))
   if timed_out:
    self.events.append('progress_timeout')
    if not self.shutdown():return
    self.next_start=now+self.delay
    if self.attempts>=self.max_attempts:self.state='DISABLED';return
  # Legacy Guard's total runtime cap disabled only for this watchdog.
  self.timeout=float('inf')
  previous=self.child
  super().tick()
  if self.child is not None and self.child is not previous:
   self.sequence=None;self.progress_at=None;self.active_since=None;self.waiting=False
 def shutdown(self):
  c=self.child
  if c is None:return True
  pgid=c.pid
  if not super().shutdown():return False
  deadline=time.monotonic()+self.kill_grace
  while time.monotonic()<deadline:
   try:os.killpg(pgid,0)
   except ProcessLookupError:return True
   time.sleep(.01)
  self.state='UNKNOWN';self.events.append('process_group_exit_unconfirmed');return False
