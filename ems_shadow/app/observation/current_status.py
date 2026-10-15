"""Evaluate persisted evidence without confusing it with current liveness."""
from datetime import datetime,timezone

def assess(saved,heartbeat,now,process_identity,max_age=10,final=None):
 def age(value):
  try:
   t=datetime.fromisoformat(value)
   if t.tzinfo is None:return None
   return (now-t.astimezone(timezone.utc)).total_seconds()
  except (ValueError,TypeError):return None
 status_age=age(saved.get('latest',{}).get('time'))
 heartbeat_age=age((heartbeat or {}).get('captured_at'))
 fresh=lambda x:x is not None and 0<=x<=max_age
 current='UNKNOWN';reason='process_identity_unconfirmed'
 if process_identity=='verified_matching':
  if fresh(status_age) and fresh(heartbeat_age):current='RUNNING';reason='fresh_evidence_and_verified_process'
  else:reason='stale_or_invalid_progress'
 elif final and process_identity=='verified_absent' and final.get('state')=='STOPPED':
  current='STOPPED';reason='verified_exit_with_final_report'
 return {'last_recorded_state':saved.get('state'),'current_confirmed_state':current,'reason':reason,'status_age_seconds':status_age,'heartbeat_age_seconds':heartbeat_age,'automatic_start_permitted':False}

def resource_sample_consistent(expected_pid,expected_start_ticks,stat_text,previous=None):
 # Require correct PID/start identity; /proc PID alone is not sufficient.
 try:
  pid=int(stat_text.split(' ',1)[0]);tail=stat_text.rsplit(')',1)[1].split()
  start=int(tail[19]);cpu=int(tail[11])+int(tail[12]);rss=int(tail[21])
  if pid!=expected_pid or start!=expected_start_ticks or cpu<0 or rss<0:return None
  if previous and cpu<previous['cpu_ticks']:return None
  return {'cpu_ticks':cpu,'rss_pages':rss,'identity_verified':True}
 except (ValueError,IndexError):return None
