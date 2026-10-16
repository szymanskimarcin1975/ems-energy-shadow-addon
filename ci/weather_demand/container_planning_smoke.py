"""Actual demand loop plus planner, synthetic HTTP and isolated SQLite only."""
import http.server,json,os,sqlite3,subprocess,sys,tempfile,threading,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from test_planning import fixture
from demand_runtime import Store
from planning_runtime import Planner
class API(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  assert self.path=='/states'
  now=datetime.now(timezone.utc);s,_,at,_,_=fixture(now)
  s.update({'sensor.example_temperature':dict(state='8',attributes={'unit_of_measurement':'°C'},last_reported=at),
            'sensor.example_energy':dict(state='100.3',attributes={'unit_of_measurement':'kWh'},last_reported=at)})
  body=json.dumps([dict(v,entity_id=k) for k,v in s.items()]).encode();self.send_response(200);self.end_headers();self.wfile.write(body)
 def do_POST(self):
  if self.path=='/template':
   payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
   assert 'last_reported' in payload['template']
   now=datetime.now(timezone.utc);states,_,at,_,_=fixture(now)
   states.update({'sensor.example_temperature':dict(state='8',attributes={'unit_of_measurement':'°C'},last_reported=at),'sensor.example_energy':dict(state='100.3',attributes={'unit_of_measurement':'kWh'},last_reported=at)})
   rows={e:dict(state=v['state'],unit=v.get('attributes',{}).get('unit_of_measurement'),last_reported=at,last_updated=at,last_changed=at) for e,v in states.items() if e.startswith('sensor.example_') and json.dumps(e) in payload['template']}
   # Mimic the precise constrained template entity selection.
   rows={e:v for e,v in rows.items() if json.dumps(e) in payload['template']}
   self.send_response(200);self.end_headers();self.wfile.write(json.dumps(rows).encode());return
  assert self.path=='/services/weather/get_forecasts?return_response'
  self.rfile.read(int(self.headers['Content-Length']))
  now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
  rows=[dict(datetime=(now+timedelta(hours=i+1)).isoformat(),temperature=8) for i in range(24)]
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'service_response':{'weather.example':{'forecast':rows}}}).encode())
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),API);threading.Thread(target=server.serve_forever,daemon=True).start()
os.environ['SUPERVISOR_TOKEN']='synthetic-only'
with tempfile.TemporaryDirectory() as td:
 root=Path(td);now=datetime.now(timezone.utc)
 _,_,_,c,o=fixture(now)
 c['refresh_ha_state_snapshot']=True
 o['observation'].update(enabled=True,weather=dict(local_entity='sensor.example_temperature',weather_entity='weather.example',max_ha_age_seconds=900))
 o['observation']['boiler_sources']['energy']='sensor.example_energy'
 options=root/'options.json';options.write_text(json.dumps(o));config=root/'planning.json';config.write_text(json.dumps(c))
 sc={**o['observation']['weather'],'energy':'sensor.example_energy','workday':'binary_sensor.example_workday'}
 db=root/'weather-demand-v1.sqlite';store=Store(db,sc)
 for i in range(46):
  t=(now-timedelta(seconds=920-i*20)).isoformat()
  states={'sensor.example_temperature':dict(entity_id='sensor.example_temperature',state='8',attributes={'unit_of_measurement':'°C'},last_reported=t),'sensor.example_energy':dict(state=str(100+i/180),attributes={'unit_of_measurement':'kWh'},last_reported=t),'binary_sensor.example_workday':dict(state='on')}
  store.capture(t,states,sc)
 store.c.close()
 planner=Planner(root/'planning-v1.sqlite')
 for i in range(7):
  states,_,at,_,_=fixture(now-timedelta(seconds=720-i*120))
  planner.quality.observe(states,at,o)
 planner.c.close()
 code="import demand_runtime as d,sys; R=d.ReadAPI;d.ReadAPI=lambda token:R(token,base="+repr('http://127.0.0.1:'+str(server.server_port))+");sys.argv=['d','--options',"+repr(str(options))+",'--root',"+repr(str(root))+",'--planning-config',"+repr(str(config))+",'--stop-after-cycles','1'];raise SystemExit(d.main())"
 child=subprocess.Popen([sys.executable,'-c',code]);assert child.wait(timeout=25)==0
 r=json.loads(Path('/ha_config/ems_shadow/planning_report.yaml').read_text())
 assert r['status']=='HYPOTHETICAL_SCHEDULE_READY',r
 assert not r['control_enabled'] and len(r['decisions'])==4 and r['persisted_runs']==1
 assert all(len(d['schedule'])==24 for d in r['decisions'])
 assert len(r['building_decisions'])==4 and not r['active_control_readiness']['ready']
 assert all(len(d['schedule'])==24 for d in r['building_decisions'])
 probe="import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from runs').fetchone()[0])"
 assert subprocess.check_output([sys.executable,'-c',probe,str(root/'planning-v1.sqlite')],text=True).strip()=='ok 1'
 print('PASS actual worker -> baseline -> planning -> SQLite COMMIT -> published report; hypothetical only, no device calls')
server.shutdown()
