"""Offline weather observations; no HA access or heating control."""
import hashlib,json,math
from datetime import datetime,timezone

def stamp(v):
 if not isinstance(v,str):raise ValueError('missing_timestamp')
 t=datetime.fromisoformat(v)
 if t.tzinfo is None:raise ValueError('timezone_required')
 return t.astimezone(timezone.utc)
class WeatherChannel:
 def __init__(self,config):
  self.config=dict(config)
  if set(config)!= {'local_entity','weather_entity','max_ha_age_seconds','jump_c_per_hour','min_jump_interval_seconds'}:raise ValueError('invalid_config')
  if not config['local_entity'].startswith('sensor.') or not config['weather_entity'].startswith('weather.'):raise ValueError('invalid_entity')
  if any(not isinstance(config[k],(int,float)) or isinstance(config[k],bool) or not math.isfinite(config[k]) or config[k]<=0 for k in ('max_ha_age_seconds','jump_c_per_hour','min_jump_interval_seconds')):raise ValueError('invalid_policy')
  self.fingerprint=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
  self.observations=[];self.forecasts=[];self.seen={};self.previous=None
 def observe(self,id,captured,state):
  payload=json.dumps([captured,state],sort_keys=True,allow_nan=False)
  if id in self.seen:
   if self.seen[id]!=payload:raise ValueError('id_conflict')
   return 'duplicate'
  ct=stamp(captured);issues=[];temp=None;ha=None
  try:
   if state.get('entity_id')!=self.config['local_entity']:raise ValueError('wrong_entity')
   if state.get('unit')!='°C':raise ValueError('invalid_unit')
   if isinstance(state.get('value'),bool):raise ValueError('invalid_temperature')
   temp=float(state['value'])
   if not math.isfinite(temp):raise ValueError('invalid_temperature')
  except (ValueError,TypeError,KeyError):issues.append('invalid_or_missing_temperature')
  try:
   ha=stamp(state.get('last_reported'));age=(ct-ha).total_seconds()
   if age<0:issues.append('future_ha_write')
   if age>self.config['max_ha_age_seconds']:issues.append('stale_ha_write')
  except (ValueError,TypeError):issues.append('missing_or_invalid_ha_write_time');age=None
  for field in ('last_changed','last_updated'):
   if state.get(field) is not None:
    try:
     if stamp(state[field])>ct:issues.append('future_'+field)
    except (ValueError,TypeError):issues.append('invalid_'+field)
  warning=None
  if not issues and self.previous:
   pt,pv=self.previous
   if ha<pt:issues.append('out_of_order')
   elif ha==pt and temp!=pv:issues.append('timestamp_conflict')
   elif ha>pt:
    dt=(ha-pt).total_seconds()
    if dt>=self.config['min_jump_interval_seconds'] and abs(temp-pv)/dt*3600>self.config['jump_c_per_hour']:warning='rapid_change_requires_review'
  if not issues:self.previous=(ha,temp)
  record={'id':id,'captured_at':ct.isoformat(),'temperature_c':temp,'ha_timestamps':{k:state.get(k) for k in ('last_reported','last_updated','last_changed')},'device_measured_at':None,'ha_write_age_seconds':age,'quality':'invalid' if issues else 'valid_ha_observation','issues':issues,'warning':warning,'raw':dict(state),'fingerprint':self.fingerprint}
  self.observations.append(record);self.seen[id]=payload;return record['quality']
 def archive_forecast(self,id,retrieved,valid_for,temp,issued_at=None):
  if isinstance(temp,bool):raise ValueError('invalid_forecast')
  rt,vt=stamp(retrieved),stamp(valid_for);v=float(temp)
  if not math.isfinite(v):raise ValueError('invalid_forecast')
  if issued_at is not None and stamp(issued_at)>rt:raise ValueError('future_issue_time')
  self.forecasts.append({'snapshot_id':id,'source':self.config['weather_entity'],'retrieved_at':rt.isoformat(),'valid_for':vt.isoformat(),'issued_at':issued_at,'temperature_c':v,'kind':'forecast'})
 def available_forecasts(self,decision_time):
  t=stamp(decision_time)
  return [x for x in self.forecasts if stamp(x['retrieved_at'])<=t]
