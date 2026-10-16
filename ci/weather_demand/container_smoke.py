"""Execute only inside the CI test container with --network none; synthetic API."""
import http.server,json,os,sqlite3,subprocess,sys,tempfile,threading,time
from datetime import datetime,timedelta,timezone
from pathlib import Path

class API(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        assert self.path=='/states'
        now=datetime.now(timezone.utc).isoformat()
        rows=[dict(entity_id='sensor.example_temperature',state='8',attributes={'unit_of_measurement':'°C'},last_reported=now),
              dict(entity_id='sensor.example_energy',state='100',attributes={'unit_of_measurement':'kWh'},last_reported=now),
              dict(entity_id='binary_sensor.example_workday',state='on',attributes={},last_reported=now)]
        body=json.dumps(rows).encode();self.send_response(200);self.end_headers();self.wfile.write(body)
    def do_POST(self):
        assert self.path=='/services/weather/get_forecasts?return_response'
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        assert payload=={'entity_id':'weather.example','type':'hourly'}
        now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
        rows=[dict(datetime=(now+timedelta(hours=i+1)).isoformat(),temperature=8) for i in range(24)]
        self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'service_response':{'weather.example':{'forecast':rows}}}).encode())

server=http.server.ThreadingHTTPServer(('127.0.0.1',0),API)
threading.Thread(target=server.serve_forever,daemon=True).start()
base='http://127.0.0.1:'+str(server.server_port)
os.environ['SUPERVISOR_TOKEN']='synthetic-only'
with tempfile.TemporaryDirectory() as td:
    root=Path(td);options=root/'options.json';data=root/'new';data.mkdir()
    old=root/'legacy.sqlite';old.write_bytes(b'synthetic legacy marker');old_before=old.read_bytes()
    options.write_text(json.dumps({'observation':{'enabled':True,'weather':{
        'local_entity':'sensor.example_temperature','weather_entity':'weather.example','max_ha_age_seconds':900},
        'boiler_sources':{'energy':'sensor.example_energy','workday':'binary_sensor.example_workday'}}}))
    report=Path('/ha_config/ems_shadow/demand_report.yaml')
    def start():
        code="import demand_runtime as d,sys; R=d.ReadAPI; d.ReadAPI=lambda token:R(token,base="+repr(base)+"); sys.argv=['demand','--options',"+repr(str(options))+",'--root',"+repr(str(data))+"]; raise SystemExit(d.main())"
        return subprocess.Popen([sys.executable,'-c',code])
    def wait(count):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if report.exists():
                try:
                    r=json.loads(report.read_text())
                    if r['captures']>=count:return r
                except (ValueError,OSError):pass
            time.sleep(.05)
        raise AssertionError('actual_runtime_report_missing')
    child=None
    try:
        child=start();r=wait(1)
        assert r['status']=='insufficient_data' and not r['control_enabled']
        assert any(x['forecast_temperature_c']==8 for x in r['horizon'])
        child.terminate();assert child.wait(timeout=25)==0
        child=start();wait(2);child.kill();child.wait(timeout=5)
        db=data/'weather-demand-v1.sqlite'
        probe="import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from captures').fetchone()[0])"
        assert subprocess.check_output([sys.executable,'-c',probe,str(db)],text=True).strip()=='ok 2'
        assert old.read_bytes()==old_before
        print('PASS synthetic HTTP, forecasts, actual worker, SIGTERM, SIGKILL, restart, SQLite reopen, legacy untouched; no trained forecast claimed')
    finally:
        if child and child.poll() is None:child.kill();child.wait(timeout=5)
        server.shutdown()
