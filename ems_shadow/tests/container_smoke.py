"""Host-side Docker smoke test; never connects to real Home Assistant."""
import json
import subprocess
import time
import uuid
import shlex
from pathlib import Path

def docker(*args):
    return subprocess.check_output(['docker',*args],text=True).strip()

def observer_processes(output):
    lines=output.splitlines()
    assert lines and lines[0].split()[0]=='PID', 'process_listing_missing_pid'
    found={'supervise.py':[], 'runner.py':[]}
    for line in lines[1:]:
        pid,command=line.strip().split(None,1)
        assert pid.isdigit(), 'invalid_process_pid'
        args=shlex.split(command)
        if len(args)>=2 and Path(args[0]).name.startswith('python'):
            script=Path(args[1]).name
            if script in found:found[script].append(int(pid))
    assert all(len(pids)==1 for pids in found.values()), 'expected_one_supervisor_and_one_observer: '+repr(found)
    return found

def check_processes(name):
    # Docker requires PID to map host ps results to container processes.
    output=docker('top',name,'-eo','pid,args')
    print(output,flush=True)
    return observer_processes(output)

def wait_report(name, minimum, previous=None):
    for _ in range(45):
        try:
            r=json.loads(docker('exec',name,'cat','/ha_config/ems_shadow/report.yaml'))
            if r['samples']>=minimum and (previous is None or r['last_sample']!=previous): return r
        except (subprocess.CalledProcessError,json.JSONDecodeError): pass
        time.sleep(2)
    raise AssertionError('report_timeout')

def main():
    suffix=uuid.uuid4().hex[:8];network='shadow-test-'+suffix
    name=network+'-observer';mock=network+'-api'
    volume=network+'-data';reports=network+'-reports'
    root=str(Path(__file__).resolve().parent)
    try:
        docker('network','create','--internal',network)
        docker('volume','create',volume);docker('volume','create',reports)
        docker('run','-d','--name',mock,'--network',network,'--network-alias','supervisor',
               '-e','PYTHONPATH=/app','-v',root+':/fixtures:ro','--entrypoint','python3','ems-shadow:ci','/fixtures/mock_api.py')
        docker('run','-d','--name',name,'--network',network,'-e','SUPERVISOR_TOKEN=ci-dummy',
               '-v',volume+':/data','-v',reports+':/ha_config',
               '-v',root+'/example_options.json:/data/options.json:ro','ems-shadow:ci')
        first=wait_report(name,2)
        assert first['integrated_seconds']>0 and first['valid_measurements_percent']==100
        assert all(x['timestamp_field']=='last_updated' for x in first['source_diagnostics'].values())
        command=json.loads(docker('inspect','--format','{{json .Config.Cmd}}',name))
        assert command==['python3','supervise.py']
        processes=check_processes(name)
        # Crash only the synthetic observer; parent must start another worker.
        killer="import os,signal; [(os.kill(int(p),signal.SIGKILL)) for p in os.listdir('/proc') if p.isdigit() and b'runner.py' in open('/proc/'+p+'/cmdline','rb').read() and int(p)!=os.getpid()]"
        docker('exec',name,'python3','-c',killer)
        second=wait_report(name,first['samples']+1,first['last_sample'])
        assert second['quality'].get('restart_or_invalid_baseline',0)>=1
        restarted=check_processes(name)
        assert restarted['supervise.py']==processes['supervise.py']
        assert restarted['runner.py']!=processes['runner.py']
        docker('stop','--time','25',name)
        assert docker('inspect','--format','{{.State.ExitCode}}',name)=='0'
        stopped=json.loads(docker('run','--rm','--network','none','-v',reports+':/report:ro',
                                  '--entrypoint','cat','ems-shadow:ci','/report/ems_shadow/report.yaml'))
        assert stopped['running'] is False
        docker('start',name)
        final=wait_report(name,second['samples']+1,second['last_sample'])
        check_processes(name)
        assert final['samples']>second['samples']
        assert final['integrated_seconds']>=second['integrated_seconds']
        docker('stop','--time','25',name)
        print('PASS: isolated API, correct CMD/processes, crash recovery, stop, restart, persistent SQLite')
    except BaseException:
        # CI uses only synthetic data/dummy token. Capture diagnostics BEFORE cleanup.
        for container in (name,mock):
            subprocess.run(['docker','logs','--tail','80',container],check=False)
            subprocess.run(['docker','inspect','--format','{{json .State}}',container],check=False)
            subprocess.run(['docker','top',container,'-eo','pid,args'],check=False)
        subprocess.run(['docker','exec',name,'cat','/ha_config/ems_shadow/report.yaml'],check=False)
        raise
    finally:
        for container in (name,mock): subprocess.run(['docker','rm','-f',container],check=False)
        for v in (volume,reports): subprocess.run(['docker','volume','rm',v],check=False)
        subprocess.run(['docker','network','rm',network],check=False)

if __name__=='__main__':main()
