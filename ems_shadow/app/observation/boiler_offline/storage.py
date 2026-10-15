"""Isolated additive SQLite prototype. Never use on a production database."""
import json
import sqlite3
import uuid
from prototype import timestamp, number, validate
from g13 import pieces

CATEGORIES = ('boiler', 'solar_ac_balance', 'pv', 'battery', 'grid')
DDL = '''
CREATE TABLE IF NOT EXISTS split_v1_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS split_v1_samples(id TEXT PRIMARY KEY,time TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS split_v1_baselines(category TEXT PRIMARY KEY,time TEXT NOT NULL,power REAL NOT NULL,session TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS split_v1_quality(sample_id TEXT NOT NULL,category TEXT NOT NULL,reason TEXT NOT NULL,valid INTEGER NOT NULL,PRIMARY KEY(sample_id,category));
CREATE TABLE IF NOT EXISTS split_v1_intervals(category TEXT NOT NULL,method TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,kwh REAL NOT NULL,seconds REAL NOT NULL,PRIMARY KEY(category,method,start,end));
CREATE TABLE IF NOT EXISTS split_v1_register(category TEXT PRIMARY KEY,time TEXT NOT NULL,value REAL NOT NULL,session TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS split_v2_baseline_tariff(category TEXT PRIMARY KEY,workday TEXT);
CREATE TABLE IF NOT EXISTS split_v2_tariffs(category TEXT,method TEXT,start TEXT,end TEXT,tariff TEXT,kwh REAL,PRIMARY KEY(category,method,start,end));
CREATE TABLE IF NOT EXISTS split_v2_register_quality(sample_id TEXT PRIMARY KEY,reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS split_v1_diagnostics(sample_id TEXT PRIMARY KEY,status TEXT NOT NULL);
'''

class Ledger:
    def __init__(self, path, ledger_id, fingerprint):
        self.session = uuid.uuid4().hex
        self.db = sqlite3.connect(path, isolation_level=None, timeout=2)
        try:
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('BEGIN IMMEDIATE')
            # Validate identity before creating anything. Legacy state stays untouched.
            has_state = self.db.execute("SELECT 1 FROM sqlite_master WHERE name='state' AND type='table'").fetchone()
            if has_state:
                for key, expected in [('ledger_id', ledger_id), ('sources_digest', fingerprint)]:
                    row = self.db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
                    if row and row[0] != expected: raise ValueError('legacy_identity_mismatch')
            for statement in DDL.split(';'):
                if statement.strip(): self.db.execute(statement)
            for key, value in [('ledger_id',ledger_id), ('sources_digest',fingerprint), ('method_version','split_v1')]:
                row = self.db.execute('SELECT value FROM split_v1_meta WHERE key=?',(key,)).fetchone()
                if row and row[0] != value: raise ValueError('identity_mismatch')
                self.db.execute('INSERT OR IGNORE INTO split_v1_meta VALUES(?,?)',(key,value))
            self.db.commit()
        except BaseException:
            self.db.rollback(); self.db.close(); raise

    def close(self): self.db.close()

    def ingest(self, sample_id, s, fail_at=None):
        t = timestamp(s['time']).isoformat()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM split_v1_samples WHERE id=? OR time=?',(sample_id,t)).fetchone():
                self.db.rollback(); return 'duplicate'
            last = self.db.execute('SELECT time FROM split_v1_samples ORDER BY time DESC LIMIT 1').fetchone()
            if last and timestamp(t) <= timestamp(last[0]):
                self.db.rollback(); return 'out_of_order'
            self.db.execute('INSERT INTO split_v1_samples VALUES(?,?)',(sample_id,t))
            self.db.execute('INSERT OR IGNORE INTO split_v1_meta VALUES(?,?)',('cutover',t))
            for c in CATEGORIES:
                valid = 0
                try: p = validate(s,c); valid = 1
                except (ValueError, TypeError, KeyError) as e:
                    reason = str(e) if isinstance(e,ValueError) else 'invalid_'+c
                    self.db.execute('DELETE FROM split_v1_baselines WHERE category=?',(c,))
                else:
                    reason = 'baseline'
                    prev = self.db.execute('SELECT time,power,session FROM split_v1_baselines WHERE category=?',(c,)).fetchone()
                    if prev and prev[2] == self.session:
                        seconds = (timestamp(t)-timestamp(prev[0])).total_seconds()
                        if 0 < seconds <= 45:
                            self.db.execute('INSERT INTO split_v1_intervals VALUES(?,?,?,?,?,?)',
                                (c,'power_trapezoid',prev[0],t,(prev[1]+p)/2*seconds/3600000,seconds))
                            self.allocate(c,'power_trapezoid',prev[0],t,prev[1],p,s.get('workday'))
                            reason = 'valid_sampled'
                        else: reason = 'communication_gap'
                    self.db.execute('INSERT OR REPLACE INTO split_v1_baselines VALUES(?,?,?,?)',(c,t,p,self.session))
                    self.db.execute('INSERT OR REPLACE INTO split_v2_baseline_tariff VALUES(?,?)',(c,s.get('workday')))
                self.db.execute('INSERT INTO split_v1_quality VALUES(?,?,?,?)',(sample_id,c,reason,valid))
            if fail_at == 'after_power': raise sqlite3.OperationalError('synthetic_transaction_failure')
            self.db.execute('SAVEPOINT register_only')
            register_reason='baseline_or_unchanged'
            try:
                register_reason=self.register(s,t)
            except (ValueError,TypeError,KeyError) as e:
                self.db.execute('ROLLBACK TO register_only')
                # Reject this reading, retain the last accepted cumulative endpoint.
                # No energy is inferred until another valid monotonic endpoint arrives.
                register_reason=str(e) if isinstance(e,ValueError) and str(e) else 'invalid_register'
            self.db.execute('RELEASE register_only')
            self.db.execute('INSERT INTO split_v2_register_quality VALUES(?,?)',(sample_id,register_reason))
            try:
                hp = read_diagnostic(s)
                status = 'comparison_warning' if hp > number(s['boiler_w']) else 'available'
            except (ValueError, TypeError, KeyError): status = 'unavailable'
            self.db.execute('INSERT INTO split_v1_diagnostics VALUES(?,?)',(sample_id,status))
            if fail_at == 'before_commit': raise sqlite3.OperationalError('synthetic_commit_failure')
            self.db.commit(); return 'stored'
        except BaseException:
            self.db.rollback(); raise

    def allocate(self,c,method,a,b,p0,p1,workday):
        old=self.db.execute('SELECT workday FROM split_v2_baseline_tariff WHERE category=?',(c,)).fetchone()
        a=timestamp(a);b=timestamp(b);total=(b-a).total_seconds()
        for x,y,zone in pieces(a,b,old[0] if old else None,workday):
            v0=p0+(p1-p0)*(x-a).total_seconds()/total
            v1=p0+(p1-p0)*(y-a).total_seconds()/total
            kwh=(v0+v1)/2*(y-x).total_seconds()/3600000
            self.db.execute('INSERT INTO split_v2_tariffs VALUES(?,?,?,?,?,?)',(c,method,x.isoformat(),y.isoformat(),zone,kwh))

    def register(self,s,t):
        try:
            value = number(s['boiler_kwh']); stamp = timestamp(s['boiler_kwh_time']).isoformat()
            age = (timestamp(t)-timestamp(stamp)).total_seconds()
            if value < 0 or not 1 <= age <= 210: raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise ValueError('invalid_register_time_or_value')
        else:
            old = self.db.execute('SELECT time,value,session FROM split_v1_register WHERE category=?',('boiler',)).fetchone()
            reason='baseline_or_unchanged'
            if old and (timestamp(stamp) < timestamp(old[0]) or (stamp == old[0] and value != old[1])):
                raise ValueError('register_timestamp_conflict')
            if old and stamp != old[0]:
                if timestamp(stamp) > timestamp(old[0]) and value >= old[1]:
                    seconds = (timestamp(stamp)-timestamp(old[0])).total_seconds()
                    if value > old[1]:
                        self.db.execute('INSERT INTO split_v1_intervals VALUES(?,?,?,?,?,?)',
                            ('boiler','register_delta',old[0],stamp,value-old[1],seconds))
                        reason='valid_register_delta'
                        self.db.execute('INSERT INTO split_v2_tariffs VALUES(?,?,?,?,?,?)',('boiler','register_delta',old[0],stamp,'unallocated',value-old[1]))
            if old and value < old[1]:reason='register_drop_baseline'
            # Cumulative deltas may span downtime; timing remains unallocated.
            # Power integration still never bridges a restart or missing samples.
            self.db.execute('INSERT OR REPLACE INTO split_v1_register VALUES(?,?,?,?)',('boiler',stamp,value,self.session))
            return reason

    def report(self):
        self.db.execute('BEGIN')
        try:return self._report()
        finally:self.db.rollback()

    def _report(self):
        meta = dict(self.db.execute('SELECT key,value FROM split_v1_meta'))
        count = self.db.execute('SELECT COUNT(*) FROM split_v1_samples').fetchone()[0]
        bounds = self.db.execute('SELECT MIN(time),MAX(time) FROM split_v1_samples').fetchone()
        elapsed = (timestamp(bounds[1])-timestamp(bounds[0])).total_seconds() if count > 1 else 0
        categories = {}
        for c in CATEGORIES:
            q = dict(self.db.execute('SELECT reason,COUNT(*) FROM split_v1_quality WHERE category=? GROUP BY reason',(c,)))
            valid = self.db.execute('SELECT COALESCE(SUM(valid),0) FROM split_v1_quality WHERE category=?',(c,)).fetchone()[0]
            kwh, seconds = self.db.execute("SELECT COALESCE(SUM(kwh),0),COALESCE(SUM(seconds),0) FROM split_v1_intervals WHERE category=? AND method='power_trapezoid'",(c,)).fetchone()
            register = self.db.execute("SELECT COALESCE(SUM(kwh),0) FROM split_v1_intervals WHERE category=? AND method='register_delta'",(c,)).fetchone()[0]
            categories[c] = dict(valid=valid,rejected=count-valid,quality=q,power_kwh=kwh,
                register_kwh=register if c=='boiler' else None,integrated_seconds=seconds,
                coverage_percent=100*seconds/elapsed if elapsed else None)
        return dict(metadata=meta,samples=count,elapsed_seconds=elapsed,categories=categories,
                    register_quality=dict(self.db.execute('SELECT reason,COUNT(*) FROM split_v2_register_quality GROUP BY reason')),
                    tariffs=[dict(category=c,method=m,tariff=z,kwh=e) for c,m,z,e in self.db.execute('SELECT category,method,tariff,SUM(kwh) FROM split_v2_tariffs GROUP BY category,method,tariff')],
                    billing_approved=False,integrity=self.db.execute('PRAGMA integrity_check').fetchone()[0])

def read_diagnostic(s):
    from prototype import read
    return read(s,'heatpump')
