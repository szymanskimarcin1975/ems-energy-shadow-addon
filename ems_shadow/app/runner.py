"""Supervisor-managed single-process observer. No control API requests."""
import fcntl
import json
import os
from pathlib import Path
import signal
import threading
import uuid
from datetime import datetime, timezone
from shadow import Shadow, capture
from zigbee_freshness import classify as classify_freshness
from settings import load_sources, load_ledger_id, fingerprint, ConfigurationError

def atomic_report(path, report):
    path = Path(path)
    if path.parent.is_symlink():
        raise RuntimeError('report_directory_symlink_refused')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError('report_symlink_refused')
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(report, out, ensure_ascii=False, allow_nan=False, indent=2)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(directory)
    finally: os.close(directory)

def make_report(sh, running=True):
    c = sh.con
    c.execute('BEGIN')
    try:
        r = sh.report()
        first, last = c.execute('SELECT MIN(time),MAX(time) FROM samples').fetchone()
        good = c.execute("SELECT MAX(time) FROM samples WHERE quality='valid_sampled'").fetchone()[0]
        elapsed = (datetime.fromisoformat(last)-datetime.fromisoformat(first)).total_seconds() if first else 0
        # Count actual numeric validity independently of baseline/status labels.
        from shadow import power
        accepted = 0
        accepted = sh.valid_count
        for raw, in c.execute('SELECT raw FROM samples WHERE rowid>?', (sh.checked_rowid,)):
            try: power(json.loads(raw)); accepted += 1
            except (ValueError, TypeError, KeyError): pass
        sh.valid_count = accepted
        sh.checked_rowid = c.execute('SELECT COALESCE(MAX(rowid),0) FROM samples').fetchone()[0]
        failures = c.execute("SELECT COUNT(*) FROM events WHERE reason='capture_failed'").fetchone()[0]
        previous=c.execute("SELECT value FROM state WHERE key='previous'").fetchone()
        previous_sample=json.loads(previous[0])['sample'] if previous else {}
        diagnostics=previous_sample.get('source_diagnostics',{})
        meter_freshness=classify_freshness(datetime.now(timezone.utc).isoformat(),{
            k:{'state':previous_sample.get(k),'last_reported':previous_sample.get(k+'_time')}
            for k in ('boiler_w','heatpump_w')
        })
        r.update(schema_version=1, generated_at=datetime.now(timezone.utc).isoformat(),
                 running=running, first_sample=first, last_sample=last,
                 last_valid_sample=good, observation_seconds=elapsed,
                 valid_measurements=accepted, failed_capture_attempts=failures,
                 valid_measurements_percent=100*accepted/(r['samples']+failures) if r['samples']+failures else None,
                 integrated_period_percent=100*r['integrated_seconds']/elapsed if elapsed else None,
                 topology_confirmed=False, cumulative_since_database_creation=True,
                 source_diagnostics=diagnostics, meter_freshness=meter_freshness, ledger_id=sh.ledger_id,
                 sources_digest=sh.sources_digest, addon_version='0.1.2')
        return r
    finally: c.rollback()

def run(data='/data', report='/ha_config/ems_shadow/report.yaml', stop=None, options_path='/data/options.json'):
    ledger_id=load_ledger_id(options_path)
    sources=load_sources(options_path) # Validate before files/DB/network are touched.
    os.umask(0o077)
    data = Path(data); data.mkdir(parents=True, exist_ok=True)
    stop = stop or threading.Event()
    with open(data/'observer.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # capture() appends /api/states; /core is the proxy base, not /core/api.
        os.environ['HA_URL'] = 'http://supervisor/core'
        os.environ['HA_TOKEN'] = os.environ['SUPERVISOR_TOKEN']
        # Never open the legacy database or its WAL/SHM, even for migration.
        ledger_dir=data/'ledgers'/ledger_id
        for component in (data/'ledgers',ledger_dir,ledger_dir/'shadow.sqlite'):
            if component.is_symlink(): raise ConfigurationError('ledger_symlink_refused')
        ledger_dir.mkdir(parents=True,exist_ok=True)
        sh = Shadow(ledger_dir/'shadow.sqlite')
        sh.ledger_id=ledger_id
        sh.sources_digest=fingerprint(sources)
        digest=fingerprint(sources)
        old=sh.con.execute("SELECT value FROM state WHERE key='sources_digest'").fetchone()
        if (old and old[0]!=digest) or (old is None and sh.report()['samples']):
            sh.close()
            raise ConfigurationError('source_change_requires_separate_ledger')
        sh.con.execute("INSERT OR IGNORE INTO state VALUES('sources_digest',?)",(digest,));sh.con.commit()
        sh.valid_count = 0
        sh.checked_rowid = 0
        try:
            while not stop.is_set():
                try: sample = capture(sources)
                except Exception:
                    # Persist a time-stamped gap; never expose tokens or HTTP body.
                    sh.con.execute('INSERT INTO events VALUES(?,?)',
                        (datetime.now(timezone.utc).isoformat(), 'capture_failed'))
                    sh.con.commit()
                    # Mark next register change unallocated after missing capture.
                    sh.session = uuid.uuid4().hex
                    print('capture_failed', flush=True)
                else:
                    # Storage failures must terminate rather than silently skip writes.
                    print('sample_quality='+sh.process(sample), flush=True)
                atomic_report(report, make_report(sh))
                stop.wait(20)
        finally:
            try: atomic_report(report, make_report(sh, running=False))
            finally: sh.close()

if __name__ == '__main__':
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    try: run(stop=stopping)
    except ConfigurationError as exc:
        print(str(exc),flush=True)
        raise SystemExit(78)
