"""Stage 2: isolated SQLite diagnostic ledger. No HA writes, MQTT or control.
Run offline: python shadow.py --replay samples.jsonl --db /private/shadow.sqlite
Read-only server observation requires explicit --observe and environment secrets.
"""
import argparse
import hashlib
import json
import math
import os
import sqlite3
import time
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from engine import tariff
ZONE=ZoneInfo('Europe/Warsaw')
SOURCE_KEYS=('inverter_w','grid_kw','boiler_w','heatpump_w','boiler_kwh','heatpump_kwh','workday')

def finite(v):
    if isinstance(v,bool): raise ValueError('invalid_number')
    n=float(v)
    if not math.isfinite(n): raise ValueError('invalid_number')
    return n

def dt(s,field='timestamp'):
    if not isinstance(s,str) or not s.strip(): raise ValueError('invalid_timestamp_'+field)
    try: d=datetime.fromisoformat(s)
    except ValueError: raise ValueError('invalid_timestamp_'+field) from None
    if d.tzinfo is None: raise ValueError('timezone_required_'+field)
    return d.astimezone(timezone.utc)

def power(s):
    t=dt(s['time'],'time'); a=dt(s['inverter_time'],'inverter_time'); g=dt(s['grid_time'],'grid_time')
    if abs((a-g).total_seconds())>2: raise ValueError('solar_skew')
    for k in ('inverter_time','grid_time','boiler_time','heatpump_time'):
        if not 1 <= (t-dt(s[k],k)).total_seconds() <= 210: raise ValueError('stale_or_unsettled_'+k)
    p={'building':finite(s['inverter_w'])-1000*finite(s['grid_kw']),
       'boiler':finite(s['boiler_w']),'heatpump':finite(s['heatpump_w'])}
    if min(p.values())<0: raise ValueError('negative_power')
    p['house']=p['building']-p['boiler']
    # Invalid topology/time alignment is reported, not hidden by max(0,...).
    if p['house']<0 or p['heatpump']>p['boiler']: raise ValueError('power_balance_inconsistent')
    tariff(t,s['workday'])
    return p

def cuts(start,end):
    """UTC instants of local midnight/G13 boundaries, including DST days."""
    result={start,end}
    day=start.astimezone(ZONE).date()
    last=end.astimezone(ZONE).date()
    while day<=last:
        for hour in (0,7,13,16,19,21,22):
            x=datetime.combine(day,datetime.min.time(),ZONE)+timedelta(hours=hour)
            u=x.astimezone(timezone.utc)
            if start<u<end: result.add(u)
        day+=timedelta(days=1)
    return sorted(result)

def segments(start,end,workday):
    boundaries=cuts(start,end)
    for a,b in zip(boundaries,boundaries[1:]):
        # Workday is a current-day signal: do not apply it to a different date.
        known=a.astimezone(ZONE).date()==end.astimezone(ZONE).date()
        yield a,b,tariff(a,workday) if known else 'unallocated'

class Shadow:
    def __init__(self,path):
        self.session=uuid.uuid4().hex
        self.con=sqlite3.connect(path,timeout=15)
        self.con.execute('PRAGMA journal_mode=WAL')
        self.con.execute('PRAGMA synchronous=FULL')
        self.con.executescript('''
        CREATE TABLE IF NOT EXISTS samples(id TEXT PRIMARY KEY, time TEXT, session TEXT, raw TEXT, quality TEXT);
        CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS increments(sample_id TEXT, category TEXT, tariff TEXT, method TEXT,
          start TEXT, end TEXT, kwh REAL, PRIMARY KEY(sample_id,category,tariff,method,start));
        CREATE TABLE IF NOT EXISTS events(sample_id TEXT, reason TEXT);
        ''')
    def close(self): self.con.close()
    def process(self,s):
        raw=json.dumps(s,sort_keys=True,allow_nan=False)
        id=hashlib.sha256(raw.encode()).hexdigest()
        c=self.con
        c.execute('BEGIN IMMEDIATE')
        try:
            if c.execute('SELECT 1 FROM samples WHERE id=?',(id,)).fetchone():
                c.rollback();return 'duplicate'
            previous=c.execute("SELECT value FROM state WHERE key='previous'").fetchone()
            prev=json.loads(previous[0]) if previous else None
            quality='baseline'
            try: p=power(s)
            except (ValueError,TypeError,KeyError) as e: p=None;quality=str(e)
            if prev and dt(s['time'])<=dt(prev['sample']['time']):
                c.rollback();return 'out_of_order'
            c.execute('INSERT INTO samples VALUES(?,?,?,?,?)',(id,s['time'],self.session,raw,quality))
            if p is not None and prev and prev['session']==self.session and prev['valid']:
                ps=prev['sample'];start=dt(ps['time']);end=dt(s['time']);seconds=(end-start).total_seconds()
                if seconds<=45:
                    pp=power(ps)
                    # Building power integration: both left rectangle and trapezoid.
                    # Keep both; their spread is sensitivity, not a guaranteed error bound.
                    for a,b,zone in segments(start,end,s['workday']):
                        fraction0=(a-start).total_seconds()/seconds;fraction1=(b-start).total_seconds()/seconds
                        hours=(b-a).total_seconds()/3600
                        for cat in ('building','boiler','house','heatpump'):
                            v0=pp[cat]+(p[cat]-pp[cat])*fraction0
                            v1=pp[cat]+(p[cat]-pp[cat])*fraction1
                            self.add(id,cat,zone,'power_trapezoid',a,b,(v0+v1)/2*hours/1000)
                            self.add(id,cat,zone,'power_left',a,b,pp[cat]*hours/1000)
                    quality='valid_sampled'
                else: quality='communication_gap'
            elif prev and p is not None: quality='restart_or_invalid_baseline'
            # Physical register deltas use their own change timestamps and baselines.
            # Never pretend a delayed delta was consumed at receipt time.
            for cat,key in [('boiler','boiler_kwh'),('heatpump','heatpump_kwh')]:
                try:
                    n=finite(s[key]); stamp=dt(s[key+'_time'])
                    row=c.execute('SELECT value FROM state WHERE key=?',(key,)).fetchone()
                    old=json.loads(row[0]) if row else None
                    if old and n!=old['value']:
                        delta=n-old['value'];a=dt(old['time']);b=stamp
                        if delta<0:
                            c.execute('INSERT INTO events VALUES(?,?)',(id,'register_drop_'+cat))
                        elif delta>0 and b>a:
                            pieces=list(segments(a,b,s['workday'])) if s['workday'] in ('on','off') else []
                            zones={x[2] for x in pieces}
                            zone=next(iter(zones)) if len(zones)==1 and old['session']==self.session and p is not None else 'unallocated'
                            self.add(id,cat,zone,'register_delta',a,b,delta)
                    if n<0: raise ValueError('negative_register')
                    if old is None or n!=old['value']:
                        value=dict(value=n,time=stamp.isoformat(),session=self.session)
                        c.execute('INSERT OR REPLACE INTO state VALUES(?,?)',(key,json.dumps(value)))
                except (ValueError,TypeError,KeyError):
                    c.execute('INSERT INTO events VALUES(?,?)',(id,'register_invalid_'+cat))
            c.execute('UPDATE samples SET quality=? WHERE id=?',(quality,id))
            c.execute("INSERT OR REPLACE INTO state VALUES('previous',?)",(json.dumps(dict(sample=s,valid=p is not None,session=self.session)),))
            c.commit();return quality
        except BaseException:
            c.rollback();raise
    def add(self,id,cat,zone,method,a,b,kwh):
        self.con.execute('INSERT INTO increments VALUES(?,?,?,?,?,?,?)',
            (id,cat,zone,method,a.isoformat(),b.isoformat(),kwh))
    def report(self):
        c=self.con
        return {'samples':c.execute('SELECT COUNT(*) FROM samples').fetchone()[0],
                'quality':dict(c.execute('SELECT quality,COUNT(*) FROM samples GROUP BY quality')),
                'energy':[dict(category=a,tariff=b,method=d,kwh=e) for a,b,d,e in c.execute('SELECT category,tariff,method,SUM(kwh) FROM increments GROUP BY category,tariff,method')],
                'events':list(c.execute('SELECT reason,COUNT(*) FROM events GROUP BY reason')),
                'integrated_seconds':c.execute("SELECT COALESCE(SUM((julianday(end)-julianday(start))*86400),0) FROM increments WHERE category='building' AND method='power_trapezoid'").fetchone()[0],
                'note':'Diagnostic sampled energy, not billing. Raw readings retained; no HA writes.'}

def snapshot_from_states(sources,rows,now):
    states={s['entity_id']:s for s in rows if isinstance(s,dict) and isinstance(s.get('entity_id'),str)}
    result={'time':now.isoformat(),'source_diagnostics':{}}
    for k,id in sources.items():
        s=states.get(id,{})
        result[k]=s.get('state','unavailable')
        stamp=None;selected=None
        for field in ('last_reported','last_updated','last_changed'):
            try: stamp=dt(s.get(field),field).isoformat();selected=field;break
            except ValueError: pass
        result[k+'_time']=stamp
        result['source_diagnostics'][k]={'entity_present':id in states,
            'timestamp_field':selected,'timestamp_valid':stamp is not None,
            'field_types':{f:type(s.get(f)).__name__ for f in ('last_reported','last_updated','last_changed')}}
    for k,source in [('inverter_time','inverter_w'),('grid_time','grid_kw'),('boiler_time','boiler_w'),('heatpump_time','heatpump_w')]: result[k]=result[source+'_time']
    return result

def capture(sources):
    req=urllib.request.Request(os.environ['HA_URL'].rstrip('/')+'/api/states',headers={'Authorization':'Bearer '+os.environ['HA_TOKEN']})
    with urllib.request.urlopen(req,timeout=10) as r: rows=json.load(r)
    return snapshot_from_states(sources,rows,datetime.now(timezone.utc))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--db',required=True)
    group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--replay');group.add_argument('--observe',action='store_true')
    parser.add_argument('--duration',type=int,default=3600)
    args=parser.parse_args(); sh=Shadow(args.db)
    try:
        if args.replay:
            with open(args.replay) as f:
                for line in f:
                    if line.strip(): sh.process(json.loads(line))
        else:
            from settings import load_sources
            sources=load_sources('/data/options.json')
            stop=time.monotonic()+args.duration
            while time.monotonic()<stop:
                try: sh.process(capture(sources))
                except Exception: print('capture_failed',flush=True) # no credential/raw response leakage
                time.sleep(20)
        print(json.dumps(sh.report(),ensure_ascii=False,indent=2))
    finally: sh.close()
if __name__=='__main__':main()
