"""Audit snapshot; coverage is interval union, not sample percentage."""
import hashlib,json,sqlite3
from pathlib import Path
from datetime import timedelta
from exporter import validate,utc
CATEGORIES=('building','boiler','heatpump')
def union_seconds(intervals):
    total=0;end=None
    for a,b in sorted(intervals):
        if end is None or a>end:total+=(b-a).total_seconds();end=b
        elif b>end:total+=(b-end).total_seconds();end=b
    return total

def source_quality(s):
    from shadow import dt,finite
    issues={k:[] for k in ('inverter','grid','boiler','heatpump','workday','balance')}
    try:t=dt(s['time'])
    except (ValueError,TypeError,KeyError):return {'capture':['invalid_time']}
    stamps={}
    for role,key in [('inverter','inverter_time'),('grid','grid_time'),('boiler','boiler_time'),('heatpump','heatpump_time')]:
        try:
            stamp=dt(s[key]);stamps[role]=stamp;age=(t-stamp).total_seconds()
            if age<0:issues[role].append('future')
            elif age<1:issues[role].append('too_fresh')
            elif age>210:issues[role].append('stale')
        except (ValueError,TypeError,KeyError):issues[role].append('invalid_timestamp')
    if 'inverter' in stamps and 'grid' in stamps and abs((stamps['inverter']-stamps['grid']).total_seconds())>2:
        issues['inverter'].append('solar_skew');issues['grid'].append('solar_skew')
    values={}
    for role,key in [('inverter','inverter_w'),('grid','grid_kw'),('boiler','boiler_w'),('heatpump','heatpump_w')]:
        try:values[role]=finite(s[key])
        except (ValueError,TypeError,KeyError):issues[role].append('invalid_number')
    if len(values)==4:
        building=values['inverter']-1000*values['grid']
        if min(building,values['boiler'],values['heatpump'])<0:issues['balance'].append('negative_power')
        if building<values['boiler'] or values['heatpump']>values['boiler']:issues['balance'].append('inconsistent')
    if s.get('workday') not in ('on','off'):issues['workday'].append('invalid_workday')
    return {k:v for k,v in issues.items() if v}

def analyze(path,manifest_path,start,end):
    path=Path(path);meta=json.loads(Path(manifest_path).read_text())
    if meta.get('complete') is not True or hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('incomplete_or_changed_export')
    start=utc(start);end=utc(end)
    if (end-start).total_seconds()!=86400:raise ValueError('expected_24_elapsed_hours')
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        validate(db,meta['sources_digest'])
        samples=[(utc(t),q,json.loads(raw)) for t,q,raw in db.execute('SELECT time,quality,raw FROM samples')]
        increments={c:[] for c in CATEGORIES}
        for cat,a,b in db.execute("SELECT category,start,end FROM increments WHERE method='power_trapezoid'"):
            if cat in increments:
                a=utc(a);b=utc(b)
                if b<=a:raise ValueError('invalid_interval')
                if a<end and b>start:increments[cat].append((max(a,start),min(b,end)))
        grids={}
        # Import only pure, unchanged validation; never instantiate Shadow.
        from shadow import power
        for minutes in (60,15,30):
            rows=[];left=start
            while left<end:
                right=min(left+timedelta(minutes=minutes),end)
                selected=[(q,s) for t,q,s in samples if left<=t<right]
                quality={};valid=0;source_issues={}
                for q,s in selected:
                    quality[q]=quality.get(q,0)+1
                    for source,reasons in source_quality(s).items():
                        for reason in reasons:
                            key=source+':'+reason;source_issues[key]=source_issues.get(key,0)+1
                    try:power(s);valid+=1
                    except (ValueError,TypeError,KeyError):pass
                cats={}
                for cat in CATEGORIES:
                    sec=union_seconds([(max(a,left),min(b,right)) for a,b in increments[cat] if a<right and b>left])
                    cats[cat]=dict(integrated_seconds=sec,coverage_percent=100*sec/(right-left).total_seconds(),missing_seconds=(right-left).total_seconds()-sec,
                      candidate_full_coverage=abs(sec-(right-left).total_seconds())<.001,
                      training_approved=False,reason='topology_and_source_alignment_not_confirmed')
                rows.append(dict(start=left.isoformat(),end=right.isoformat(),samples=len(selected),valid=valid,rejected=len(selected)-valid,quality=quality,source_issues=source_issues,categories=cats));left=right
            grids[str(minutes)]=rows
        return dict(ledger_id=meta['ledger_id'],topology_confirmed=False,interval_methods_separate=True,grids=grids)
    finally:db.close()
