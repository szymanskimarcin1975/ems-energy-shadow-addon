"""Synthetic API, isolated CI Docker network. No user data or credentials."""
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/core/api/states':
            self.send_error(404); return
        IDS=json.loads((Path(__file__).parent/'example_options.json').read_text())['sources']
        stamp=(datetime.now(timezone.utc)-timedelta(seconds=5)).isoformat()
        values=dict(inverter_w='1000',grid_kw='-1',boiler_w='500',heatpump_w='300',
                    boiler_kwh='10',heatpump_kwh='5',workday='on')
        rows=[dict(entity_id=id,state=values[k],last_reported=None,last_updated=stamp,last_changed=stamp,attributes={}) for k,id in IDS.items()]
        extra={'sensor.example_b1_soc':'50','sensor.example_b1_power':'500','sensor.example_b1_status':'B_STATUS_CHARGE','sensor.example_ac_power':'1000','sensor.example_m1_import':'100','sensor.example_m1_export':'20'}
        old=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        rows += [dict(entity_id=id,state=value,last_reported=old if id=='sensor.example_b1_status' else stamp,last_updated=old if id=='sensor.example_b1_status' else stamp,last_changed=old if id=='sensor.example_b1_status' else stamp,attributes={}) for id,value in extra.items()]
        rows.append(dict(entity_id='input_select.example_owner',state='LEGACY',last_reported=stamp,last_updated=stamp,last_changed=stamp,attributes={'friendly_name':'EMS Battery Control Owner','options':['UNKNOWN','LEGACY','EMS2']}))
        body=json.dumps(rows).encode()
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        if self.path!='/core/api/template':self.send_error(404);return
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
        ids=body.get('variables',{}).get('ids',[])
        stamp=(datetime.now(timezone.utc)-timedelta(seconds=5)).isoformat()
        extra={'sensor.example_b1_soc':'50','sensor.example_b1_power':'500','sensor.example_b1_status':'B_STATUS_CHARGE','sensor.example_ac_power':'1000','sensor.example_m1_import':'100','sensor.example_m1_export':'20'}
        extra['sensor.example_m1_power']='-1'
        units={'sensor.example_m1_power':'kW','sensor.example_b1_power':'W','sensor.example_b1_soc':'%'}
        rows=[dict(entity_id=id,state=extra.get(id,'unknown'),attributes={'unit_of_measurement':units.get(id)},last_reported=stamp,last_updated=stamp,last_changed=stamp) for id in ids]
        if 'soc_entity' in body.get('variables',{}):
            source=body['variables']['soc_entity']
            rows=[dict(entity_id=source,state='50',last_reported=stamp)]
            for role,value in [('status','B_STATUS_CHARGE'),('max_charge_power',5000),('peak_charge_power',0),('max_discharge_power',5000),('peak_discharge_power',5000)]:
                rows.append(dict(entity_id='sensor.example_b1_'+role,state=str(value),attributes={'unit_of_measurement':'W'},last_reported=stamp,last_updated=stamp,last_changed=stamp))
            payload={'device_found':True,'rows':rows}
        else:payload=rows
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(payload).encode())
    def log_message(self,*_): pass

if __name__=='__main__': HTTPServer(('0.0.0.0',80),Handler).serve_forever()
