"""Synthetic HA responses for isolated CI only."""
from http.server import BaseHTTPRequestHandler,HTTPServer
from datetime import datetime,timezone,timedelta
import json

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path!='/core/api/states':self.send_error(404);return
        ts=(datetime.now(timezone.utc)-timedelta(seconds=5)).isoformat()
        values={
          'sensor.example_inverter_power':('1000','W'),'sensor.example_grid_power':('-1','kW'),
          'sensor.example_boiler_power':('500','W'),'sensor.example_heatpump_power':('300','W'),
          'sensor.example_boiler_energy':('100','kWh'),'sensor.example_heatpump_energy':('50','kWh'),
          'binary_sensor.example_workday':('on',None),'sensor.example_temperature':('8','°C'),
          'sensor.example_m1_import':('100','kWh'),'sensor.example_m1_export':('50','kWh'),
          'sensor.example_ac_power':('1000','W'),'sensor.example_b1_power':('0','W'),
          'sensor.example_b1_soc':('50','%'),'sensor.example_b1_status':('B_STATUS_IDLE',None),
          'sensor.example_b1_import':('1','kWh'),'sensor.example_b1_export':('1','kWh'),
          'sensor.example_cloud_production':('1','kWh')}
        rows=[dict(entity_id=k,state=v,last_reported=ts,last_updated=ts,last_changed=ts,attributes={} if u is None else {'unit_of_measurement':u}) for k,(v,u) in values.items()]
        self.send_response(200);self.end_headers();self.wfile.write(json.dumps(rows).encode())
    def do_POST(self):
        if self.path!='/core/api/services/weather/get_forecasts?return_response':self.send_error(404);return
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if payload!={'entity_id':'weather.example','type':'hourly'}:self.send_error(400);return
        now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
        rows=[dict(datetime=(now+timedelta(hours=i+1)).isoformat(),temperature=8) for i in range(24)]
        self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'service_response':{'weather.example':{'forecast':rows}}}).encode())

HTTPServer(('0.0.0.0',80),Handler).serve_forever()
