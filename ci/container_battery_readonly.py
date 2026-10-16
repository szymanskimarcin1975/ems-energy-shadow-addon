"""Isolated image check, synthetic API only, no real HA address."""
import json,os,subprocess,tempfile,uuid
from pathlib import Path

def run(*a):return subprocess.run(['docker',*a],check=True,capture_output=True,text=True).stdout
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);data=root/'data';ha=root/'ha';data.mkdir();ha.mkdir()
 options=json.loads(Path('ems_shadow/tests/example_options.json').read_text())
 options.setdefault('observation',{})['enabled']=True
 (data/'options.json').write_text(json.dumps(options))
 key=uuid.uuid4().hex[:10];network='battery-'+key;api='battery-api-'+key
 try:
  run('network','create','--internal',network)
  run('run','-d','--name',api,'--network',network,'--network-alias','supervisor','--entrypoint','python','ems-shadow:ci','/tests/mock_api.py')
  run('run','--rm','--user',str(os.getuid())+':'+str(os.getgid()),'--network',network,'-v',str(data)+':/data','-v',str(ha)+':/ha_config','-e','SUPERVISOR_TOKEN=synthetic','--entrypoint','python','ems-shadow:ci','/app/observation/battery_runtime.py','--cycles','2','--interval','.1')
  report=json.loads((ha/'ems_shadow/battery_executor_report.yaml').read_text())
  assert report['mode']=='READ_ONLY' and report['state']=='BLOCKED'
  assert report['commands_enabled'] is False and report['commands_sent']==0
  assert report['policy']['soc_min'] is None and report['policy']['soc_max'] is None
  heartbeat=json.loads((data/'observation-v1/battery-heartbeat.json').read_text())
  assert heartbeat['completed_cycles']==2 and heartbeat['committed_cycles']==0
  assert not list(data.rglob('*.sqlite'))
  print('battery_readonly_image_PASS; cycles=2; commands=0; sqlite_opened=0')
 finally:
  subprocess.run(['docker','rm','-f',api],capture_output=True)
  subprocess.run(['docker','network','rm',network],capture_output=True)
