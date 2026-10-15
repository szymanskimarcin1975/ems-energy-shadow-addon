"""Offline G13 scheduling, matching the existing seasonal convention.
Workday is supplied by the caller; this module does not infer holidays.
"""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
ZONE=ZoneInfo('Europe/Warsaw')
def tariff(t,workday):
    if workday not in ('on','off'):return 'unallocated'
    if workday=='off':return 'dolina'
    local=t.astimezone(ZONE);h=local.hour+local.minute/60+local.second/3600
    if 7<=h<13:return 'szczyt_przedpoludniowy'
    if (19<=h<22) if 4<=local.month<=9 else (16<=h<21):return 'szczyt_popoludniowy'
    return 'dolina'
def pieces(a,b,workday_a,workday_b):
    cuts={a,b};day=a.astimezone(ZONE).date();last=b.astimezone(ZONE).date()
    while day<=last:
        for h in (0,7,13,16,19,21,22):
            t=datetime.combine(day,datetime.min.time(),ZONE).replace(hour=h).astimezone(timezone.utc)
            if a<t<b:cuts.add(t)
        day+=timedelta(days=1)
    same_day=a.astimezone(ZONE).date()==b.astimezone(ZONE).date()
    wd=workday_a if same_day and workday_a==workday_b else None
    ordered=sorted(cuts)
    return [(x,y,tariff(x+(y-x)/2,wd)) for x,y in zip(ordered,ordered[1:])]
