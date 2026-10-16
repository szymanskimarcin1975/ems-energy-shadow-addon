"""CI-only full gateway transition; synthetic API and private Docker network."""
import json,os,sqlite3,subprocess,tempfile,time,uuid
from pathlib import Path
from datetime import datetime,timezone

def docker(*args):return subprocess.check_output(['docker',*args],text=True)

key=uuid.uuid4().hex[:8];network='demand-'+key;api='api-'+key;app='ems-'+key
with tempfile.TemporaryDirectory() as td:
    root=Path(td);data=root/'data';ha=root/'ha';data.mkdir();ha.mkdir()
    options=json.loads(Path('ems_shadow/tests/example_options.json').read_text())
    options['ledger_id']='synthetic_ci';options['diagnostic_export_enabled']=False
    options['observation']={'enabled':True,'solar_sources':{k:'sensor.example_'+k for k in ('m1_import','m1_export','ac_power','b1_power','b1_soc','b1_status','b1_import','b1_export','cloud_production')},
      'weather':{'local_entity':'sensor.example_temperature','weather_entity':'weather.example','max_ha_age_seconds':900,'jump_c_per_hour':10,'min_jump_interval_seconds':60},
      'boiler_sources':{'power':options['sources']['boiler_w'],'energy':options['sources']['boiler_kwh'],'workday':options['sources']['workday']}}
    (data/'options.json').write_text(json.dumps(options))
    original=(data/'options.json').read_bytes();previous=0;digest=None
    try:
        docker('network','create','--internal',network)
        docker('run','-d','--name',api,'--network',network,'--network-alias','supervisor','-v',str(Path('ci/weather_demand/full_mock_api.py').resolve())+':/mock.py:ro','--entrypoint','python','ems-demand:candidate','/mock.py')
        for phase,image in [('baseline','ems-demand:baseline'),('candidate','ems-demand:candidate'),('rollback','ems-demand:baseline')]:
            docker('run','-d','-i','--name',app,'--network',network,'-v',str(data)+':/data','-v',str(ha)+':/ha_config','-e','SUPERVISOR_TOKEN=synthetic-only',image)
            deadline=time.monotonic()+60;confirmed=False
            while time.monotonic()<deadline:
                try:
                    r=json.loads((ha/'ems_shadow/report.yaml').read_text())
                    if r['running'] and r['samples']>previous:
                        if phase=='candidate':
                            d=json.loads((ha/'ems_shadow/demand_report.yaml').read_text())
                            if (datetime.now(timezone.utc)-datetime.fromisoformat(d['generated_at'])).total_seconds()>30:raise ValueError('old_demand_report')
                            assert d['captures']>=1 and d['predictions']>=1 and not d['control_enabled']
                        confirmed=True;break
                except (OSError,ValueError,KeyError):pass
                time.sleep(.2)
            assert confirmed,phase+'_progress_missing'
            if digest is None:digest=r['sources_digest']
            assert r['sources_digest']==digest and r['ledger_id']=='synthetic_ci'
            previous=r['samples'];before=time.monotonic()
            docker('stop','--time','30',app)
            assert time.monotonic()-before<30
            assert docker('inspect','--format','{{.State.ExitCode}}',app).strip()=='0'
            docker('rm',app)
            assert (data/'options.json').read_bytes()==original
            for db in data.rglob('*.sqlite'):
                c=sqlite3.connect(db);assert c.execute('pragma integrity_check').fetchone()[0]=='ok';c.close()
            print('PASS',phase,'legacy_samples',previous,'all_sqlite_integrity_ok',flush=True)
        assert (data/'observation-v1/weather-demand-v1.sqlite').exists()
    finally:
        subprocess.run(['docker','rm','-f',app,api],capture_output=True,timeout=30)
        subprocess.run(['docker','network','rm',network],capture_output=True,timeout=30)
