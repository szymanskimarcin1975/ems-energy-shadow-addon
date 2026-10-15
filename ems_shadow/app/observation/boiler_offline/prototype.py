"""Offline design only. No API, database writes or production migration."""
from collections import Counter
from datetime import datetime, timezone
import math

def timestamp(x):
    if not isinstance(x, str): raise ValueError('invalid_timestamp')
    t = datetime.fromisoformat(x)
    if t.tzinfo is None: raise ValueError('timezone_required')
    return t.astimezone(timezone.utc)

def number(x):
    if isinstance(x, bool): raise ValueError('invalid_number')
    n = float(x)
    if not math.isfinite(n): raise ValueError('invalid_number')
    return n

def read(s, role):
    age = (timestamp(s['time']) - timestamp(s[role+'_time'])).total_seconds()
    if not 1 <= age <= 210: raise ValueError('stale_or_unsettled_'+role)
    return number(s[role+'_w' if role != 'grid' else 'grid_kw'])

def validate(s, category):
    if category in ('pv', 'battery', 'grid'):
        p = read(s,category)
        if category == 'pv' and p < 0: raise ValueError('negative_pv')
        return p*1000 if category == 'grid' else p
    if category == 'boiler':
        p = read(s, 'boiler')
        if p < 0: raise ValueError('negative_boiler')
        return p
    if category == 'solar_ac_balance':
        if abs((timestamp(s['inverter_time'])-timestamp(s['grid_time'])).total_seconds()) > 2:
            raise ValueError('solar_skew')
        # AC balance is not labelled PV production or confirmed building load.
        return read(s, 'inverter') - 1000*read(s, 'grid')
    raise ValueError('unknown_category')

class Prototype:
    def __init__(self):
        self.previous = {}
        self.seen = set()
        self.kwh = Counter()
        self.coverage = Counter()
        self.quality = {c: Counter() for c in ('boiler','solar_ac_balance')}

    def restart(self):
        # Keep totals/deduplication; no energy bridge over downtime.
        self.previous.clear()

    def ingest(self, sample_id, s):
        if sample_id in self.seen: return 'duplicate'
        t = timestamp(s['time'])
        if any(t <= v[0] for v in self.previous.values()): return 'out_of_order'
        self.seen.add(sample_id)
        for c in self.quality:
            try: p = validate(s, c)
            except (ValueError, TypeError, KeyError) as e:
                self.quality[c][str(e)] += 1
                self.previous.pop(c, None)
                continue
            prev = self.previous.get(c)
            reason = 'baseline'
            if prev:
                seconds = (t-prev[0]).total_seconds()
                if 0 < seconds <= 45:
                    self.kwh[c] += (prev[1]+p)/2*seconds/3600000
                    self.coverage[c] += seconds
                    reason = 'valid_sampled'
                else: reason = 'communication_gap'
            self.quality[c][reason] += 1
            self.previous[c] = (t,p)
