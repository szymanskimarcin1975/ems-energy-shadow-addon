"""Injectable transport only; no live HTTP implementation or credentials."""
class HAReader:
 def __init__(self,config,transport):self.config=config;self.transport=transport
 def local(self):
  s=self.transport('GET','/api/states/'+self.config['local_entity'],None)
  if not isinstance(s,dict):raise ValueError('invalid_api_response')
  if s.get('entity_id')!=self.config['local_entity']:raise ValueError('wrong_entity_response')
  return {'entity_id':s.get('entity_id'),'value':s.get('state'),'unit':s.get('attributes',{}).get('unit_of_measurement'),'last_reported':s.get('last_reported'),'last_updated':s.get('last_updated'),'last_changed':s.get('last_changed')}
 def forecast_request(self):
  # Read-only weather service request specification, not executed here.
  return {'service':'weather.get_forecasts','target':{'entity_id':self.config['weather_entity']},'data':{'type':'hourly'},'return_response':True}
