"""Only isolated Docker network and synthetic data. No HA server address accepted."""
import json,subprocess,tempfile,time,uuid,os
from pathlib import Path
from datetime import datetime,timedelta,timezone
IMAGE='ems-shadow:ci'
def run(*args):return subprocess.run(['docker',*args],check=True,capture_output=True,text=True).stdout
with tempfile.TemporaryDirectory() as d:
    root=Path(d);data=root/'data';ha=root/'ha';data.mkdir();ha.mkdir()
    options=json.loads(Path('ems_shadow/tests/example_options.json').read_text());options['ledger_id']='synthetic';options['diagnostic_export_enabled']=True
    (data/'options.json').write_text(json.dumps(options))
    key=uuid.uuid4().hex[:10];network='ems-'+key;api='api-'+key;observer='observer-'+key;p=None
    def wait_report(predicate,seconds=50):
        deadline=time.monotonic()+seconds;file=ha/'ems_shadow/report.yaml'
        while time.monotonic()<deadline:
            if file.exists():
                report=json.loads(file.read_text())
                if predicate(report):return report
            time.sleep(.2)
        raise AssertionError('observer_report_timeout')
    try:
        run('network','create','--internal',network)
        run('run','-d','--name',api,'--network',network,'--network-alias','supervisor','--entrypoint','python',IMAGE,'/tests/mock_api.py')
        # First boot on fresh synthetic data with export explicitly disabled.
        options['diagnostic_export_enabled']=False
        (data/'options.json').write_text(json.dumps(options))
        p=subprocess.Popen(['docker','run','--user',str(os.getuid())+':'+str(os.getgid()),'--name',observer,'--network',network,'-i','-v',str(data)+':/data','-v',str(ha)+':/ha_config','-e','SUPERVISOR_TOKEN=synthetic',IMAGE],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL)
        fresh=wait_report(lambda r:r['running'] and r['samples']>=2)
        assert not (data/'diagnostic_exports_control').exists()
        assert not (data/'diagnostic_exports').exists()
        inspect_script="import os,json,pathlib;cmds=[]\nfor p in pathlib.Path('/proc').iterdir():\n if p.name.isdigit() and int(p.name)!=os.getpid():\n  try:cmds.append((p/'cmdline').read_bytes().replace(bytes([0]),b' ').decode())\n  except (OSError,UnicodeError):pass\nprint(json.dumps(cmds))"
        cmds=json.loads(run('exec',observer,'python','-c',inspect_script))
        assert sum('/app/runner.py' in c for c in cmds)==1
        assert sum('/app/staging/disabled_stdin.py' in c for c in cmds)==1
        assert not any('/app/staging/service.py' in c or '/app/staging/worker.py' in c or '/app/diagnostic_export/exporter.py' in c for c in cmds)
        now=datetime.now(timezone.utc)
        disabled_request=dict(operation='diagnostic_export',request_id='disabled_fresh_request',ledger_id='synthetic',expires_at=(now+timedelta(seconds=120)).isoformat(),start=(now-timedelta(days=2)).isoformat(),end=(now-timedelta(days=1)).isoformat())
        p.stdin.write((json.dumps(disabled_request)+'\n').encode());p.stdin.flush()
        deadline=time.monotonic()+5;received=False
        while time.monotonic()<deadline:
            for line in run('logs',observer).splitlines():
                try:value=json.loads(line)
                except ValueError:continue
                if value.get('request_id')=='disabled_fresh_request' and value.get('reason')=='export_disabled':received=True
            if received:break
            time.sleep(.1)
        assert received,'fresh_disabled_ack_missing'
        seeded=wait_report(lambda r:r['samples']>fresh['samples'])
        assert not (data/'diagnostic_exports_control').exists() and not (data/'diagnostic_exports').exists()
        run('stop','--time','30',observer);p.wait(timeout=35);assert p.returncode==0
        run('rm',observer)
        options['diagnostic_export_enabled']=True
        (data/'options.json').write_text(json.dumps(options))
        p=subprocess.Popen(['docker','run','--user',str(os.getuid())+':'+str(os.getgid()),'--name',observer,'--network',network,'-i','-v',str(data)+':/data','-v',str(ha)+':/ha_config','-e','SUPERVISOR_TOKEN=synthetic',IMAGE],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL)
        first=wait_report(lambda r:r['running'] and r['samples']>seeded['samples'])
        now=datetime.now(timezone.utc)
        req=dict(operation='diagnostic_export',request_id='synthetic_request',ledger_id='synthetic',expires_at=(now+timedelta(seconds=120)).isoformat(),start=(now-timedelta(days=2)).isoformat(),end=(now-timedelta(days=1)).isoformat())
        p.stdin.write((json.dumps(req)+'\n').encode());p.stdin.flush()
        reportfile=ha/'ems_shadow/diagnostics/synthetic_request.yaml';deadline=time.monotonic()+20
        while not reportfile.exists() and time.monotonic()<deadline:time.sleep(.1)
        assert reportfile.exists(),'aggregate_timeout'
        aggregate=json.loads(reportfile.read_text());assert len(aggregate['grids']['15'])==96
        assert (data/'diagnostic_exports/synthetic_request/snapshot.sqlite').exists()
        later=wait_report(lambda r:r['samples']>first['samples'])
        p.stdin.write((json.dumps(req)+'\n').encode());p.stdin.flush();time.sleep(.3)
        assert len(list((data/'diagnostic_exports').glob('*/snapshot.sqlite')))==1
        run('stop','--time','15',observer);p.wait(timeout=20)
        assert p.returncode==0
        # Corrupt only the synthetic control DB, never the observer ledger.
        run('rm',observer)
        (data/'diagnostic_exports_control/requests.sqlite').write_bytes(b'synthetic corrupt controller database')
        p=subprocess.Popen(['docker','run','--user',str(os.getuid())+':'+str(os.getgid()),'--name',observer,'--network',network,'-i','-v',str(data)+':/data','-v',str(ha)+':/ha_config','-e','SUPERVISOR_TOKEN=synthetic',IMAGE],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL)
        recovered=wait_report(lambda r:r['running'] and r['samples']>later['samples'])
        continued=wait_report(lambda r:r['samples']>recovered['samples'])
        assert 'controller_failure' in run('logs',observer)
        run('stop','--time','30',observer);p.wait(timeout=35);assert p.returncode==0
        run('rm',observer)
        # Disabled export must not touch even an already corrupt control DB.
        options['diagnostic_export_enabled']=False
        (data/'options.json').write_text(json.dumps(options))
        corrupt_before=(data/'diagnostic_exports_control/requests.sqlite').read_bytes()
        p=subprocess.Popen(['docker','run','--user',str(os.getuid())+':'+str(os.getgid()),'--name',observer,'--network',network,'-i','-v',str(data)+':/data','-v',str(ha)+':/ha_config','-e','SUPERVISOR_TOKEN=synthetic',IMAGE],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL)
        disabled=wait_report(lambda r:r['running'] and r['samples']>continued['samples'])
        assert (data/'diagnostic_exports_control/requests.sqlite').read_bytes()==corrupt_before
        assert 'DISABLED' in run('logs',observer)
        req['expires_at']=(datetime.now(timezone.utc)+timedelta(seconds=120)).isoformat()
        p.stdin.write(((json.dumps(req)+'\n')*2+'{broken\n').encode());p.stdin.flush()
        deadline=time.monotonic()+5;acks=[]
        while time.monotonic()<deadline:
            acks=[]
            for line in run('logs',observer).splitlines():
                try:value=json.loads(line)
                except ValueError:continue
                if value.get('component')=='diagnostic_stdin' and value.get('status')=='REJECTED':acks.append(value)
            if len(acks)>=3:break
            time.sleep(.1)
        assert len(acks)==3,'stdin_ack_missing'
        assert [x['reason'] for x in acks]==['export_disabled','export_disabled','invalid_json']
        assert acks[0]['request_id']==req['request_id'] and acks[1]['repeated']
        assert (data/'diagnostic_exports_control/requests.sqlite').read_bytes()==corrupt_before
        assert len(list((data/'diagnostic_exports').glob('*/snapshot.sqlite')))==1
        wait_report(lambda r:r['samples']>disabled['samples'])
        run('stop','--time','30',observer);p.wait(timeout=35);assert p.returncode==0
        # Old 0.1.2 observer code can reopen this synthetic current ledger.
        # This is NOT proof of a Supervisor downgrade or installed image identity.
        run('rm',observer)
        last=json.loads((ha/'ems_shadow/report.yaml').read_text())['samples']
        p=subprocess.Popen(['docker','run','--user',str(os.getuid())+':'+str(os.getgid()),'--name',observer,'--network',network,'-v',str(data)+':/data','-v',str(ha)+':/ha_config','-e','SUPERVISOR_TOKEN=synthetic','--entrypoint','python',IMAGE,'/app/supervise.py'],stdout=subprocess.DEVNULL)
        old=wait_report(lambda r:r['running'] and r['samples']>last)
        assert old['ledger_id']=='synthetic' and old['addon_version']=='0.1.2'
        run('stop','--time','30',observer);p.wait(timeout=35);assert p.returncode==0
        print(json.dumps(dict(fresh_disabled_start='PASS; no controller or exporter process/files; correlated STDIN ack',observer_samples_before=first['samples'],observer_samples_after=later['samples'],exports=1,report='aggregate_only',impact='continued_collection; short export does not establish timing equivalence')))
    finally:
        for name in (observer,api):subprocess.run(['docker','rm','-f',name],capture_output=True)
        subprocess.run(['docker','network','rm',network],capture_output=True)
        if p and p.poll() is None:p.terminate();p.wait(timeout=10)
