"""Isolated image check, synthetic API only, no real HA address."""
import json,os,sqlite3,subprocess,tempfile,uuid
from pathlib import Path

def run(*a):
 result=subprocess.run(['docker',*a],capture_output=True,text=True)
 if result.returncode:
  print(result.stdout);print(result.stderr)
  result.check_returncode()
 return result.stdout
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);data=root/'data';ha=root/'ha';data.mkdir();ha.mkdir()
 (ha/'ems_shadow').mkdir()
 (ha/'ems_shadow/battery_executor_config.yaml').write_text(json.dumps({'mode':'READ_ONLY','telemetry_sources':{'m1_power':'sensor.example_m1_power','b1_power':'sensor.example_b1_power','soc':'sensor.example_b1_soc'}}))
 options=json.loads(Path('ems_shadow/tests/example_options.json').read_text())
 options.setdefault('observation',{})['enabled']=True
 options['observation']['solar_sources']={role:'sensor.example_'+({'ac_power':'ac_power','m1_import':'m1_import','m1_export':'m1_export'}.get(role,role)) for role in ('b1_soc','b1_power','b1_status','ac_power','m1_import','m1_export')}
 (data/'options.json').write_text(json.dumps(options))
 key=uuid.uuid4().hex[:10];network='battery-'+key;api='battery-api-'+key
 try:
  run('network','create','--internal',network)
  run('run','-d','--name',api,'--network',network,'--network-alias','supervisor','--entrypoint','python','ems-shadow:ci','/tests/mock_api.py')
  run('run','--rm','--user',str(os.getuid())+':'+str(os.getgid()),'--network',network,'-v',str(data)+':/data','-v',str(ha)+':/ha_config','-e','SUPERVISOR_TOKEN=synthetic','--entrypoint','python','ems-shadow:ci','/app/battery_runtime.py','--cycles','2','--interval','.1')
  report=json.loads((ha/'ems_shadow/battery_executor_report.yaml').read_text())
  assert report['mode']=='READ_ONLY' and report['state']=='BLOCKED'
  assert report['commands_enabled'] is False and report['commands_sent']==0
  assert report['template_status']=='AVAILABLE'
  assert report['bms']['quality']=='HA_DEVICE_BOUND_SNAPSHOT'
  assert report['bms']['charge_conservative_ceiling_w']==0
  assert report['bms']['discharge_conservative_ceiling_w']==5000
  assert report['bms']['commands_authorized'] is False
  assert report['shared_owner']['state']=='LEGACY' and report['owner_states_consistent'] is True
  assert report['inputs']['b1_status']['quality']=='HA_UPDATE_STALE_OR_FUTURE'
  assert report['inputs']['b1_status']['memory_quality']=='HA_WRITE_RECENT_DEVICE_TIME_UNCONFIRMED'
  assert report['policy']['soc_min'] is None and report['policy']['soc_max'] is None
  heartbeat=json.loads((data/'observation-v1/battery-heartbeat.json').read_text())
  assert heartbeat['completed_cycles']==2 and heartbeat['committed_cycles']==2
  dbs=list(data.rglob('*.sqlite'));assert {p.name for p in dbs}=={'battery-ownership.sqlite','battery-execution.sqlite'}
  assert report['execution_service']['executor_initialized'] is True
  assert report['execution_service']['requested_mode']=='READ_ONLY'
  assert report['execution_service']['effective_state']=='READ_ONLY'
  assert report['execution_service']['telemetry_quality']=='HA_TRANSPORT_CHECK_PASSED_NOT_DEVICE_PROOF'
  assert report['execution_service']['cycles']==2
  with sqlite3.connect(data/'observation-v1/battery-execution.sqlite') as execution:
   assert execution.execute('pragma integrity_check').fetchone()[0]=='ok'
   assert execution.execute('select count(*) from commands').fetchone()[0]==0
   assert execution.execute('select cycles from runtime').fetchone()[0]==2
  with sqlite3.connect(data/'observation-v1/battery-ownership.sqlite') as db:
   assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
   assert db.execute('select name from owner').fetchone()[0]=='LEGACY'
   assert db.execute('select count(*) from audit').fetchone()[0]==0
  print('battery_readonly_image_PASS; cycles=2; commands=0; old_ledgers_opened=0; local_owner=LEGACY')
 finally:
  subprocess.run(['docker','rm','-f',api],capture_output=True)
  subprocess.run(['docker','network','rm',network],capture_output=True)
