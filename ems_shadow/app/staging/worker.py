"""Fixed paths, isolated backup/analyzer, no shell and no new network listener."""
import json,os,subprocess,sys,time,shutil
from pathlib import Path
from controller import atomic_json,aggregate_report

def supervised(command,stop,timeout=30,pythonpath=None,monitor=None):
    env={k:v for k,v in os.environ.items() if k not in ('SUPERVISOR_TOKEN','HA_TOKEN')}
    if pythonpath:env['PYTHONPATH']=str(pythonpath)
    child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env)
    deadline=time.monotonic()+timeout
    while True:
        try:
            if monitor:
                try:monitor(child.pid)
                except ResourceLimit:raise
                except Exception:raise ResourceLimit('monitor_unavailable') from None
            out,_=child.communicate(timeout=.1)
            if child.returncode:raise RuntimeError('worker_failed')
            return json.loads(out)
        except (subprocess.TimeoutExpired,ResourceLimit) as interruption:
            if isinstance(interruption,subprocess.TimeoutExpired) and not stop.is_set() and time.monotonic()<deadline:continue
            child.terminate()
            try:child.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                child.kill()
                try:child.communicate(timeout=1)
                except subprocess.TimeoutExpired:raise RuntimeError('worker_stop_unconfirmed') from None
            if isinstance(interruption,ResourceLimit):raise interruption
            raise TimeoutError('worker_cancelled_or_timeout')

class ResourceLimit(RuntimeError):pass
class Monitor:
    def __init__(self,source,observer_report=None):
        self.wal=Path(str(source)+'-wal');self.initial=self.wal.stat().st_size if self.wal.exists() else 0
        self.report=Path(observer_report) if observer_report else None;self.samples=[];self.peak_rss=0;self.max_wal=self.initial
    def __call__(self,pid):
        try:
            for line in (Path('/proc')/str(pid)/'status').read_text().splitlines():
                if line.startswith('VmRSS:'):self.peak_rss=max(self.peak_rss,int(line.split()[1])*1024)
        except FileNotFoundError:pass # Child may have just exited.
        available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        try:
            limit=Path('/sys/fs/cgroup/memory.max').read_text().strip()
            if limit!='max':available=min(available,max(0,int(limit)-int(Path('/sys/fs/cgroup/memory.current').read_text())))
        except FileNotFoundError:pass
        size=self.wal.stat().st_size if self.wal.exists() else 0;self.max_wal=max(self.max_wal,size)
        if self.peak_rss>256*1024*1024 or available<128*1024*1024:raise ResourceLimit('ram_budget')
        if size>512*1024*1024 or size-self.initial>64*1024*1024:raise ResourceLimit('wal_budget')
        if self.report:
            if not self.report.exists():raise ResourceLimit('observer_report_missing')
            data=json.loads(self.report.read_text());self.samples.append((time.monotonic(),data.get('samples'),data.get('last_sample')))
            from datetime import datetime,timezone
            stamp=datetime.fromisoformat(data['last_sample'])
            if stamp.tzinfo is None or not data.get('running') or (datetime.now(timezone.utc)-stamp).total_seconds()>45:raise ResourceLimit('observer_stale_or_stopped')
    def summary(self):
        distinct=[]
        for _,count,stamp in self.samples:
            if count is not None and (not distinct or count!=distinct[-1][0]):distinct.append((count,stamp))
        return dict(worker_peak_rss_bytes=self.peak_rss,wal_initial_bytes=self.initial,wal_max_bytes=self.max_wal,
            observer_distinct_reports=len(distinct),observer_samples_delta=distinct[-1][0]-distinct[0][0] if len(distinct)>1 else None,
            impact_conclusion='insufficient_observation' if len(distinct)<3 else 'requires_baseline_comparison')

class Worker:
    def __init__(self,data,report_root,ledger,digest,export_module_dir,observer_app_dir="/app",observer_report=None):
        self.data=Path(data);self.report_root=Path(report_root);self.ledger=ledger;self.digest=digest;self.modules=Path(export_module_dir);self.observer_app_dir=Path(observer_app_dir);self.observer_report=observer_report
    def __call__(self,request,stop):
        source=self.data/'ledgers'/self.ledger/'shadow.sqlite'
        output=self.data/'diagnostic_exports'/request['request_id']
        if any(p.is_symlink() for p in (output,*output.parents)):raise ValueError('symlink_refused')
        estimated=sum(p.stat().st_size for p in (source,Path(str(source)+'-wal')) if p.exists())
        if estimated>512*1024*1024 or shutil.disk_usage(self.data).free<2*estimated+128*1024*1024:raise ValueError('insufficient_export_budget')
        output.mkdir(mode=0o700,parents=True,exist_ok=False)
        # Entire backup, validation AND analysis live in bounded child.
        command=[sys.executable,str(Path(__file__).resolve()),'--child',str(source),str(output/'snapshot.sqlite'),
            self.ledger,self.digest,request['start'],request['end'],str(self.modules),str(self.report_root),request['request_id']]
        monitor=Monitor(source,self.observer_report)
        result=supervised(command,stop,pythonpath=self.observer_app_dir,monitor=monitor)
        return dict(result,resource_diagnostics=monitor.summary())
if __name__=='__main__':
    if len(sys.argv)!=11 or sys.argv[1]!='--child':raise SystemExit(78)
    _,_,source,destination,ledger,digest,start,end,module_dir,report_root,request_id=sys.argv
    sys.path.insert(0,module_dir)
    from exporter import export
    from analyzer import analyze
    export(source,destination,ledger,digest,timeout=30)
    result=analyze(destination,Path(destination).with_suffix('.manifest.json'),start,end)
    report=aggregate_report(result,dict(request_id=request_id,ledger_id=ledger,start=start,end=end))
    atomic_json(Path(report_root)/(request_id+'.yaml'),report)
    print(json.dumps({'published':True,'request_id':request_id}))
