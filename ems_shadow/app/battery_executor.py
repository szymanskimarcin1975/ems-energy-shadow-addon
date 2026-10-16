"""Guarded actuator library. Not scheduled or enabled by importing it.
External single-writer fencing and safe hardware fallback must be independently
validated before setting enabled. Never disables or re-enables an old controller.
"""
import fcntl
import json
import math
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

class SupervisorHA:
    """Real HA transport; token is injected at runtime, never persisted."""
    def __init__(self, token, base='http://supervisor/core/api'):
        self.token=token; self.base=base.rstrip('/')
    def _request(self,path,data=None):
        req=urllib.request.Request(self.base+path,
          data=None if data is None else json.dumps(data).encode(),
          headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=5) as r: return json.load(r)
        except Exception:
            raise RuntimeError('ha_transport_error') from None
    def state(self,entity):
        if not re.fullmatch(r'[a-z_]+\.[a-z0-9_]+',entity): raise ValueError('entity')
        return self._request('/states/'+entity)
    def select(self,entity,option):
        return self._request('/services/select/select_option',{'entity_id':entity,'option':option})

@dataclass(frozen=True)
class Policy:
    enabled: bool=False
    soc_min: float|None=None
    soc_max: float|None=None
    soc_bounds_approved: bool=False
    rated_wh: int=9200
    max_charge_w: int=5000
    max_discharge_w: int=5000
    handover_verified: bool=False
    no_export_verified: bool=False
    fallback_verified: bool=False

class Executor:
    """One idempotent mode command; PENDING/UNKNOWN require manual reconciliation.
    Local flock is only process exclusivity, NOT a fence against HA automations.
    """
    ALLOWED={'Charge from Solar Power','Discharge to Minimize Import'}
    def __init__(self,ha,policy,db,lock,*,old_writers,soc_entity,mode_entity,power_entities,owner_entity=None,ownership=None,expected_epoch=None,clock=None):
        self.ha=ha;self.p=policy;self.db=db;self.lock=lock
        self.old=tuple(old_writers);self.soc=soc_entity;self.mode=mode_entity
        self.powers=tuple(power_entities);self.owner_entity=owner_entity;self.ownership=ownership;self.expected_epoch=expected_epoch
        self.clock=clock or (lambda: datetime.now(timezone.utc))
    def preflight(self):
        p=self.p
        if p.enabled is not True:return 'DISABLED'
        if not (p.soc_bounds_approved is True and p.handover_verified is True and p.no_export_verified is True and p.fallback_verified is True):return 'UNAPPROVED_SAFETY'
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (p.soc_min,p.soc_max)):return 'INVALID_SOC_LIMITS'
        if not 0<=p.soc_min<p.soc_max<=100:return 'INVALID_SOC_LIMITS'
        if not self.old or len(self.powers)!=2 or not self.owner_entity:return 'INCOMPLETE_CONFIGURATION'
        if self.local_owner_guard():return 'OWNERSHIP_UNCONFIRMED'
        return None
    def local_owner_guard(self):
        if self.ownership is None or isinstance(self.expected_epoch,bool) or not isinstance(self.expected_epoch,int):return True
        try:
            state=self.ownership.state()
            return not (state.get('owner')=='EMS2' and state.get('epoch')==self.expected_epoch and state.get('commands_permitted') is True and state.get('external_fence_verified') is True)
        except Exception:return True
    def live_guard(self,option,now):
        if self.local_owner_guard():return 'OWNERSHIP_UNCONFIRMED'
        if self.ha.state(self.owner_entity).get('state')!='EMS2':return 'SHARED_OWNER_NOT_EMS2' 
        for entity in self.old:
            s=self.ha.state(entity)
            if s.get('state')!='off' or s.get('attributes',{}).get('current')!=0:return 'OLD_WRITER_NOT_QUIESCENT'
        s=self.ha.state(self.soc)
        # HA timestamp is an entity update, not a proven device measurement.
        try:
            t=datetime.fromisoformat(s['last_reported'])
            if t.tzinfo is None or not 0<=(now-t).total_seconds()<=180:return 'STALE_SOC'
            soc=float(s['state'])
            if not math.isfinite(soc):return 'INVALID_SOC'
        except (KeyError,TypeError,ValueError):return 'INVALID_SOC'
        if not self.p.soc_min<=soc<=self.p.soc_max:return 'SOC_OUT_OF_RANGE'
        if option=='Discharge to Minimize Import' and soc<=self.p.soc_min:return 'SOC_RESERVE'
        if option=='Charge from Solar Power' and soc>=self.p.soc_max:return 'SOC_CEILING'
        for entity,limit in zip(self.powers,(self.p.max_charge_w,self.p.max_discharge_w)):
            try:
                value=float(self.ha.state(entity)['state'])
                if not math.isfinite(value) or not 0<=value<=limit:return 'POWER_LIMIT_UNSAFE'
            except (KeyError,TypeError,ValueError):return 'POWER_LIMIT_INVALID'
        return None
    def execute(self,request_id,option,expires_at,now=None):
        why=self.preflight()
        if why:return why # Disabled never opens SQLite, lock, or HA connection.
        now=now or self.clock()
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',request_id or ''):return 'INVALID_REQUEST'
        if option not in self.ALLOWED:return 'FORBIDDEN_MODE'
        if expires_at.tzinfo is None or not now<expires_at<=now+timedelta(seconds=60):return 'EXPIRED_REQUEST'
        with open(self.lock,'a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return 'BUSY'
            with sqlite3.connect(self.db,timeout=1) as db:
                db.execute('CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY, mode TEXT NOT NULL,status TEXT NOT NULL)')
                row=db.execute('SELECT mode,status FROM commands WHERE id=?',(request_id,)).fetchone()
                if row:return 'DUPLICATE_'+row[1] if row[0]==option else 'REQUEST_CONFLICT'
                if db.execute("SELECT 1 FROM commands WHERE status IN ('PENDING','UNKNOWN')").fetchone():return 'UNKNOWN_REQUIRES_RECONCILIATION'
                check_time=self.clock()
                if not check_time<expires_at:return 'EXPIRED_REQUEST'
                why=self.live_guard(option,check_time)
                if why:return why
                db.execute('INSERT INTO commands VALUES(?,?,?)',(request_id,option,'PENDING'));db.commit()
                try:
                    # Recheck immediately before issuing. External fencing still mandatory.
                    check_time=self.clock()
                    why='EXPIRED_REQUEST' if not check_time<expires_at else self.live_guard(option,check_time)
                    if why:
                        db.execute('UPDATE commands SET status=? WHERE id=?',('REJECTED',request_id));db.commit();return why
                    issued_at=self.clock()
                    if not issued_at<expires_at:
                        db.execute('UPDATE commands SET status=? WHERE id=?',('REJECTED',request_id));db.commit();return 'EXPIRED_REQUEST'
                    self.ha.select(self.mode,option)
                    s=self.ha.state(self.mode)
                    stamp=datetime.fromisoformat(s['last_updated'])
                    ack=s['state']==option and stamp.tzinfo is not None and issued_at<=stamp<=self.clock()
                    status='ACK' if ack else 'UNKNOWN'
                except Exception:status='UNKNOWN'
                db.execute('UPDATE commands SET status=? WHERE id=?',(status,request_id));db.commit()
                return status
