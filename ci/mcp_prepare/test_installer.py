"""Exact server installer logic, isolated filesystem and mocked ha CLI only."""
import hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/mcp_prepare'))
from build_package import build
base=Path(sys.argv[1])

def scenario(fail=False):
 with tempfile.TemporaryDirectory() as t:
  root=Path(t);config=root/'config';source=config/'custom_components/mcp_server_http_transport'
  source.parent.mkdir(parents=True);shutil.copytree(base,source)
  (config/'.storage').mkdir();(config/'.storage/keep.txt').write_text('current data must not be restored')
  package=root/'package';build(base,package)
  script=package/'install.sh';script.write_text(script.read_text().replace('/config/',str(config)+'/'))
  sums=package/'SHA256SUMS';lines=[]
  for line in sums.read_text().splitlines():
   h,n=line.split('  ',1)
   if n=='install.sh':h=hashlib.sha256(script.read_bytes()).hexdigest()
   lines.append(h+'  '+n+'\n')
  sums.write_text(''.join(lines))
  mock=root/'bin';mock.mkdir();ha=mock/'ha'
  ha.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$HA_AUDIT"
if [ "$2" = start ] && [ "${HA_FAIL_ONCE:-0}" = 1 ] && [ ! -f "$HA_FAILED" ]; then touch "$HA_FAILED"; exit 1; fi
exit 0
''');ha.chmod(0o700)
  env=dict(os.environ,PATH=str(mock)+':'+os.environ['PATH'],EMS_MCP_DETACHED='1',HA_AUDIT=str(root/'ha-calls'),HA_FAILED=str(root/'failed'),HA_FAIL_ONCE='1' if fail else '0')
  def run(*args):return subprocess.run(['sh',str(script),*args],env=env,capture_output=True,text=True)
  r=run('prepare');assert r.returncode==0,r.stdout+r.stderr
  assert not (root/'ha-calls').exists()
  old=hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest()
  r=run('apply');assert r.returncode!=0
  assert hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest()==old
  r=run('apply','CONFIRM_CORE_RESTART')
  if fail:
   assert r.returncode!=0
   assert hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest()==old
  else:
   assert r.returncode==0,r.stdout+r.stderr
   assert json.loads((source/'manifest.json').read_text())['version']=='1.18.0+ems.2'
   r=run('rollback','CONFIRM_CORE_RESTART');assert r.returncode==0,r.stdout+r.stderr
   assert hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest()==old
  assert (config/'.storage/keep.txt').read_text()=='current data must not be restored'
  calls=(root/'ha-calls').read_text().splitlines()
  assert calls[:3]==['core check','core stop','core start']
  assert all(c in ('core check','core stop','core start') for c in calls)
scenario();scenario(True)
print('SERVER_INSTALLER_PREPARE_APPLY_ROLLBACK_AND_FAILED_START_RECOVERY_PASS (MOCKED_CLI_ONLY)')
