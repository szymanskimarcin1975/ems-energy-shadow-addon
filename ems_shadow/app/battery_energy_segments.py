"""Append-only interval-quality ledger; never repairs hardware/HA counters.
Logical BMS endpoints, not physical module count, define aggregation membership.
"""
import json
import math
import sqlite3
from datetime import datetime

class Ledger:
    def __init__(self,path):
        self.path=path
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS battery_energy_baseline(source TEXT PRIMARY KEY,stamp TEXT,imp REAL,exp REAL,segment INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS battery_energy_intervals(source TEXT,stamp TEXT,segment INTEGER,quality TEXT,detail TEXT,PRIMARY KEY(source,stamp))')
    def observe(self,source,stamp,imp,exp,unit='kWh',raw=False):
        t=datetime.fromisoformat(stamp)
        if not source or t.tzinfo is None or unit not in ('Wh','kWh'):raise ValueError('ENERGY_SOURCE_UNIT_OR_TIME_INVALID')
        values=[float(v)/(1000 if unit=='Wh' else 1) for v in (imp,exp)]
        if any(isinstance(v,bool) for v in (imp,exp)) or any(not math.isfinite(v) or v<0 for v in values):raise ValueError('ENERGY_COUNTER_INVALID')
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT stamp,imp,exp,segment FROM battery_energy_baseline WHERE source=?',(source,)).fetchone()
            if prior and t<=datetime.fromisoformat(prior[0]):return dict(quality='DUPLICATE_OR_OUT_OF_ORDER',usable_for_cost=False)
            segment=prior[3] if prior else 0
            delta=None if prior is None else [values[0]-prior[1],values[1]-prior[2]]
            quality='BASELINE' if prior is None else 'INTERVAL'
            if delta and min(delta)<0:segment+=1;quality='COUNTER_DISCONTINUITY'
            gap=prior is not None and (t-datetime.fromisoformat(prior[0])).total_seconds()>180
            if gap and quality=='INTERVAL':quality='GAP_REBASELINED';segment+=1
            accepted=quality=='INTERVAL'
            result=dict(quality=quality,segment=segment,source=source,stamp=stamp,interval_start=prior[0] if prior else None,
                import_delta_kwh=delta[0] if accepted else None,export_delta_kwh=delta[1] if accepted else None,
                raw_counter_deltas_kwh=delta,usable_for_cost=bool(raw and accepted),raw_register_source=raw,
                ha_restore_filter_may_hide_discontinuity=not raw,
                physical_reset_cause='UNCONFIRMED' if quality=='COUNTER_DISCONTINUITY' else None)
            db.execute('INSERT INTO battery_energy_intervals VALUES(?,?,?,?,?)',(source,stamp,segment,quality,json.dumps(result,allow_nan=False)))
            db.execute('INSERT OR REPLACE INTO battery_energy_baseline VALUES(?,?,?,?,?)',(source,stamp,*values,segment))
            return result
    @staticmethod
    def aggregate(rows,expected_sources):
        # Never multiply a logical B1 total by number of modules. Require each
        # distinct expected endpoint once, same interval endpoint and valid deltas.
        sources=[r.get('source') for r in rows]
        if (len(set(sources))!=len(sources) or set(sources)!=set(expected_sources) or not rows or
            len({r.get('stamp') for r in rows})!=1 or len({r.get('interval_start') for r in rows})!=1 or any(not r.get('usable_for_cost') for r in rows)):
            return dict(quality='INCOMPLETE_OR_UNVERIFIED_BATTERY_GROUP',import_delta_kwh=None,export_delta_kwh=None,usable_for_cost=False)
        return dict(quality='VERIFIED_DISTINCT_LOGICAL_ENDPOINTS',usable_for_cost=True,
            import_delta_kwh=sum(r['import_delta_kwh'] for r in rows),export_delta_kwh=sum(r['export_delta_kwh'] for r in rows))
