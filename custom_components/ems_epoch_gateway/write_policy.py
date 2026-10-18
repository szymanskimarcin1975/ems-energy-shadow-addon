"""Local wear policy, NOT SolarEdge flash endurance or a manufacturer guarantee."""
import json
import math


def validate_policy(policy):
    if not isinstance(policy,dict) or policy.get('basis')!='LOCAL_EMS_WRITE_BUDGET_NOT_MANUFACTURER_LIMIT':
        raise ValueError('FLASH_WRITE_POLICY_NOT_CONFIGURED')
    interval,budget=policy.get('minimum_interval_s'),policy.get('maximum_writes_per_24h')
    if type(interval) not in (int,float) or not math.isfinite(interval) or interval<=0 or type(budget) is not int or budget<1:
        raise ValueError('FLASH_WRITE_POLICY_INVALID')
    return interval,budget


def reserve(db, request_id, changes, policy, now, emergency=False):
    db.execute('CREATE TABLE IF NOT EXISTS setting_write_audit(request_id TEXT NOT NULL,role TEXT NOT NULL,value TEXT NOT NULL,emergency INTEGER NOT NULL,state TEXT NOT NULL,at REAL NOT NULL,PRIMARY KEY(request_id,role))')
    # A row counts as a possible write until positively known skipped. Never
    # release budget after a timeout or process death; no hidden retry allowance.
    if db.execute('SELECT 1 FROM setting_write_audit WHERE request_id=? AND emergency=?',(request_id,int(emergency))).fetchone():
        raise ValueError('SETTING_BATCH_ALREADY_RESERVED_NO_RETRY')
    writes=[row for row in changes if row['required']]
    if not emergency:
        interval,budget=validate_policy(policy)
        if not writes:raise ValueError('IDENTICAL_SETTINGS_NO_WRITE_NO_TIMEOUT_RENEWAL')
        last=db.execute("SELECT MAX(at) FROM setting_write_audit WHERE emergency=0 AND state!='SKIPPED_READBACK'").fetchone()[0]
        count=db.execute("SELECT COUNT(*) FROM setting_write_audit WHERE at>? AND state!='SKIPPED_READBACK'",(now-86400,)).fetchone()[0]
        if last is not None and now-last<interval:raise ValueError('FLASH_MINIMUM_CHANGE_INTERVAL')
        if count+len(writes)>budget:raise ValueError('FLASH_LOCAL_WRITE_BUDGET_EXCEEDED')
    for row in changes:
        role=('stop_' if emergency else '')+row['role']
        db.execute('INSERT INTO setting_write_audit VALUES(?,?,?,?,?,?)',
            (request_id,role,json.dumps(row['value'],allow_nan=False),int(emergency),
             'RESERVED_UNKNOWN' if row['required'] else 'SKIPPED_READBACK',now))
    return len(writes)
