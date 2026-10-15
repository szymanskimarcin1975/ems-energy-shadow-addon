"""Synthetic API only, attached to Docker internal network."""
import json,time
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path!='/core/api/states':self.send_error(404);return
  ids=json.loads((Path(__file__).parent/'example_options.json').read_text())['sources'];stamp=(datetime.now(timezone.utc)-timedelta(seconds=5)).isoformat();rows=[]
  values=dict(inverter_w=1000,grid_kw=-1,boiler_w=500,heatpump_w=300,boiler_kwh=10+int(time.monotonic()/20)*.001,heatpump_kwh=5,workday='on')
  def add(entity,value,unit):rows.append(dict(entity_id=entity,state=str(value),last_reported=stamp,last_updated=stamp,last_changed=stamp,attributes={'unit_of_measurement':unit}))
  for key,entity in ids.items():add(entity,values[key],None if key=='workday' else 'kWh' if key.endswith('kwh') else 'kW' if key=='grid_kw' else 'W')
  units={'m1_import':'kWh','m1_export':'kWh','ac_power':'W','b1_power':'W','b1_soc':'%','b1_status':None,'b1_import':'kWh','b1_export':'kWh','cloud_production':'kWh'}
  for key,unit in units.items():add('sensor.example_'+key,'B_STATUS_CHARGE' if key=='b1_status' else 60 if key=='b1_soc' else 100+int(time.monotonic()/20)*.001 if key.startswith('m1_') else 50,unit)
  add('sensor.example_outdoor',15,'°C')
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps(rows).encode())
 def do_POST(self):
  if self.path!='/core/api/services/weather/get_forecasts?return_response':self.send_error(403);return
  n=int(self.headers.get('Content-Length',0));payload=json.loads(self.rfile.read(n));assert payload=={'entity_id':'weather.example','type':'hourly'}
  valid=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'service_response':{'weather.example':{'forecast':[{'datetime':valid,'temperature':14}]}}}).encode())
 def log_message(self,*_):pass
if __name__=='__main__':HTTPServer(('0.0.0.0',80),Handler).serve_forever()
