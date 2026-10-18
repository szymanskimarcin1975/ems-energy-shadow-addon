"""Guarded actuator library. Not scheduled or enabled by importing it.
External single-writer fencing and safe hardware fallback must be independently
validated before setting enabled. Never disables or re-enables an old controller.
"""
from contextlib import closing
import fcntl
import json
import math
import time
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

class GatewayRejected(RuntimeError):
    pass

class SupervisorHA:
    """Real HA transport; token is injected at runtime, never persisted."""
    def __init__(self, token, base='http://supervisor/core/api'):
        self.token=token; self.base=base.rstrip('/')
    def _request(self,path,data=None):
        remaining=getattr(self,'deadline',float('inf'))-time.monotonic()
        if remaining<=0:raise RuntimeError('ha_cycle_deadline')
        req=urllib.request.Request(self.base+path,
          data=None if data is None else json.dumps(data).encode(),
          headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=min(5,remaining)) as r: return json.load(r)
        except Exception:
            raise RuntimeError('ha_transport_error') from None
    def state(self,entity):
        if not re.fullmatch(r'[a-z_]+\.[a-z0-9_]+',entity): raise ValueError('entity')
        return self._request('/states/'+entity)
    def current_states(self,entities):
        ids=list(entities)
        if not ids or any(not re.fullmatch(r'sensor\.[a-z0-9_]+',e) for e in ids):raise ValueError('bms_entities')
        template="{% set ns=namespace(rows=[]) %}{% for id in ids %}{% set s=states[id] %}{% if s is not none %}{% set ns.rows=ns.rows+[{'entity_id':id,'state':s.state,'attributes':{'unit_of_measurement':s.attributes.get('unit_of_measurement')},'last_reported':s.last_reported.isoformat()}] %}{% endif %}{% endfor %}{{ ns.rows|to_json }}"
        rows=self._request('/template',{'template':template,'variables':{'ids':ids}})
        if isinstance(rows,str):rows=json.loads(rows)
        if not isinstance(rows,list):raise ValueError('bms_snapshot')
        result={r['entity_id']:r for r in rows}
        if len(result)!=len(rows) or set(result)!=set(ids):raise ValueError('bms_snapshot_incomplete')
        return result # HA current State metadata, never proof of physical sample time.

    def dispatch(self,entity,option,power_w,*,request_id,expires_at,plan_id,owner_epoch):
        # Sole production write transport. Correlate even a negative reply before
        # interpreting it; only an explicit pre-write rejection is unambiguous.
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',request_id or '') or not re.fullmatch(r'[a-f0-9]{64}',plan_id or '') or type(owner_epoch) is not int or owner_epoch<0:
            raise GatewayRejected('invalid_local_dispatch_identity_before_transport')
        result=self._request('/services/script/ems_battery_command_gateway?return_response',
          {'caller':'EMS2','operation':'dispatch','command_value':{'option':option,'power_w':power_w},
           'request_id':request_id,'expires_at':expires_at.timestamp(),'plan_id':plan_id,'owner_epoch':owner_epoch})
        reply=result.get('service_response') if isinstance(result,dict) else None
        if not isinstance(reply,dict) or reply.get('gateway_contract')!='EMS2_COMPOUND_V28' or reply.get('request_id')!=request_id or reply.get('plan_id')!=plan_id or type(reply.get('owner_epoch')) is not int or reply['owner_epoch']!=owner_epoch:
            raise RuntimeError('gateway_identity_or_outcome_unknown')
        if reply.get('status')=='REJECTED' and reply.get('writes_started') is False:
            raise GatewayRejected('gateway_confirmed_rejection_before_writes')
        if reply.get('status')!='SERVICE_COMPLETED' or reply.get('writes_started') is not True or reply.get('owner')!='EMS2' or reply.get('option')!=option:
            raise RuntimeError('gateway_outcome_unknown')
        return reply

    def shadow_dispatch(self, intent, owner_epoch):
        """Send a pending intent only to the HA gateway's non-actuating fence.

        This is used in READ_ONLY to verify the vertical path. The installed
        ems_epoch_gateway contract has no hardware transport and must return an
        explicit REJECTED/writes_started=false response. Anything else is UNKNOWN.
        """
        try:
            expiry=datetime.fromisoformat(intent['expires_at']).timestamp()
            payload={'caller':'EMS2','operation':'dispatch',
                     'request_id':intent['request_id'],'plan_id':intent['plan_id'],
                     'owner_epoch':owner_epoch,'option':intent['option'],
                     'power_w':intent['maximum_power_w'],'expires_at':expiry}
            result=self._request('/services/ems_epoch_gateway/dispatch?return_response',payload)
        except Exception:
            return {'status':'UNKNOWN','reason':'GATEWAY_TRANSPORT_OR_RESPONSE_UNKNOWN',
                    'writes_started':None,'physical_dispatch_supported':None}
        reply=result.get('service_response') if isinstance(result,dict) else None
        identity=(isinstance(reply,dict) and
                  reply.get('request_id')==intent.get('request_id') and
                  reply.get('plan_id')==intent.get('plan_id') and
                  type(reply.get('owner_epoch')) is int and reply.get('owner_epoch')==owner_epoch)
        if (identity and reply.get('status')=='REJECTED' and
                reply.get('writes_started') is False and
                reply.get('device_execution_confirmed') is False and
                reply.get('physical_dispatch_supported') is False):
            return {'status':'REJECTED_NO_HARDWARE_WRITE','reason':reply.get('reason'),
                    'writes_started':False,'physical_dispatch_supported':False,
                    'request_id':intent['request_id'],'plan_id':intent['plan_id'],
                    'owner_epoch':owner_epoch}
        return {'status':'UNKNOWN','reason':'GATEWAY_CONTRACT_OR_IDENTITY_MISMATCH',
                'writes_started':reply.get('writes_started') if isinstance(reply,dict) else None,
                'physical_dispatch_supported':reply.get('physical_dispatch_supported') if isinstance(reply,dict) else None,
                'request_id':intent.get('request_id'),'plan_id':intent.get('plan_id'),
                'owner_epoch':owner_epoch}

@dataclass(frozen=True)
class Policy:
    enabled: bool=False
    operating_soc_min: float|None=None
    operating_soc_max: float|None=None
    # Owner-approved EMS operating envelope; not an internal BMS boundary.
    soc_operating_range_approved: bool=False
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
    CHARGES={'Charge from Solar Power','Charge from Solar Power and Grid'}
    ALLOWED=CHARGES|{'Discharge to Minimize Import'}
    def __init__(self,ha,policy,db,lock,*,old_writers,soc_entity,mode_entity,power_entities,owner_entity=None,ownership=None,expected_epoch=None,clock=None,control_entity=None,bms_sources=None,telemetry_check=None):
        self.ha=ha;self.p=policy;self.db=db;self.lock=lock
        self.old=tuple(old_writers);self.soc=soc_entity;self.mode=mode_entity
        self.powers=tuple(power_entities);self.owner_entity=owner_entity;self.ownership=ownership;self.expected_epoch=expected_epoch
        self.clock=clock or (lambda: datetime.now(timezone.utc))
        self.control_entity=control_entity
        self.bms=dict(bms_sources or {})
        self.telemetry_check=telemetry_check
    def preflight(self):
        p=self.p
        if p.enabled is not True:return 'DISABLED'
        if not (p.soc_operating_range_approved is True and p.handover_verified is True and p.no_export_verified is True and p.fallback_verified is True):return 'UNAPPROVED_SAFETY'
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (p.operating_soc_min,p.operating_soc_max)):return 'INVALID_SOC_LIMITS'
        if not 0<=p.operating_soc_min<p.operating_soc_max<=100:return 'INVALID_SOC_LIMITS'
        if not self.old or len(self.powers)!=2 or not self.owner_entity or not self.control_entity:return 'INCOMPLETE_CONFIGURATION'
        if set(self.bms)!={'status','max_charge','peak_charge','max_discharge','peak_discharge'}:return 'BMS_SOURCES_UNCONFIRMED'
        if self.local_owner_guard():return 'OWNERSHIP_UNCONFIRMED'
        return None
    def local_owner_guard(self):
        if self.ownership is None or isinstance(self.expected_epoch,bool) or not isinstance(self.expected_epoch,int):return True
        try:
            state=self.ownership.state()
            return not (state.get('owner')=='EMS2' and state.get('epoch')==self.expected_epoch and state.get('commands_permitted') is True and state.get('external_fence_verified') is True)
        except Exception:return True
    def bms_guard(self,option,now,setting_power=False):
        try:
            rows=self.ha.current_states(self.bms.values())
            status=rows[self.bms['status']]
            age=(self.clock()-datetime.fromisoformat(status['last_reported'])).total_seconds()
            if not 0<=age<=180:return 'BMS_HA_UPDATE_UNCONFIRMED'
            if status['state'] not in {'B_STATUS_STANDBY','B_STATUS_IDLE','B_STATUS_CHARGE','B_STATUS_DISCHARGE'}:
                return 'BMS_STATUS_NOT_APPROVED' # Preserve Charge is not declared a fault.
            direction='charge' if option in self.CHARGES else 'discharge'
            ceiling=self.p.max_charge_w if direction=='charge' else self.p.max_discharge_w
            limits=[]
            for role in ('max_'+direction,'peak_'+direction):
                raw=rows[self.bms[role]]
                age=(self.clock()-datetime.fromisoformat(raw['last_reported'])).total_seconds()
                if not 0<=age<=180:return 'BMS_HA_UPDATE_UNCONFIRMED'
                if raw.get('attributes',{}).get('unit_of_measurement')!='W':return 'BMS_LIMIT_UNIT_INVALID'
                value=float(raw['state'])
                if not math.isfinite(value) or value<0:return 'BMS_LIMIT_INVALID'
                limits.append(value)
            cap=min(ceiling,*limits)
            if cap<=0:return 'BMS_DIRECTION_LIMIT_ZERO'
            self.direction_ceiling_w=cap
            remote=float(self.ha.state(self.powers[0 if direction=='charge' else 1])['state'])
            if not math.isfinite(remote) or remote<0 or (not setting_power and remote>cap):return 'REMOTE_LIMIT_EXCEEDS_BMS'
        except Exception:return 'BMS_READ_UNCONFIRMED'
        return None

    def live_guard(self,option,now,setting_power=False):
        try:
            quality=self.telemetry_check() if self.telemetry_check else 'TELEMETRY_CHECK_MISSING'
            if quality!='HA_TRANSPORT_CHECK_PASSED_NOT_DEVICE_PROOF':return quality
        except Exception:return 'TELEMETRY_READ_UNCONFIRMED'
        if self.local_owner_guard():return 'OWNERSHIP_UNCONFIRMED'
        if self.ha.state(self.owner_entity).get('state')!='EMS2':return 'SHARED_OWNER_NOT_EMS2'
        if self.ha.state(self.control_entity).get('state')!='Remote Control':return 'REMOTE_CONTROL_NOT_ACTIVE'
        if self.ha.state(self.mode).get('state') in (None,'unknown','unavailable'):return 'COMMAND_INTERFACE_UNAVAILABLE' 
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
        if not self.p.operating_soc_min<=soc<=self.p.operating_soc_max:return 'SOC_OUT_OF_RANGE'
        if option=='Discharge to Minimize Import' and soc<=self.p.operating_soc_min:return 'SOC_RESERVE'
        if option in self.CHARGES and soc>=self.p.operating_soc_max:return 'SOC_CEILING'
        for entity,limit in zip(self.powers,(self.p.max_charge_w,self.p.max_discharge_w)):
            try:
                value=float(self.ha.state(entity)['state'])
                if not math.isfinite(value) or not 0<=value<=limit:return 'POWER_LIMIT_UNSAFE'
            except (KeyError,TypeError,ValueError):return 'POWER_LIMIT_INVALID'
        return self.bms_guard(option,now,setting_power=setting_power)
    def execute(self,request_id,option,expires_at,now=None,*,maximum_power_w=None,intent_check=None,plan_id=None):
        if maximum_power_w is not None and (type(maximum_power_w) not in (int,float) or not math.isfinite(maximum_power_w) or not 0<maximum_power_w):return 'PLAN_POWER_INVALID'
        why=self.preflight()
        if why:return why # Disabled never opens SQLite, lock, or HA connection.
        if maximum_power_w is None:return 'PLAN_POWER_REQUIRED'
        if not re.fullmatch(r'[a-f0-9]{64}',plan_id or ''):return 'PLAN_ID_REQUIRED'
        now=now or self.clock()
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',request_id or ''):return 'INVALID_REQUEST'
        if option not in self.ALLOWED:return 'FORBIDDEN_MODE'
        if option=='Charge from Solar Power and Grid' and maximum_power_w is None:return 'GRID_CHARGE_REQUIRES_POWER_REQUEST'
        if expires_at.tzinfo is None or not now<expires_at<=now+timedelta(seconds=60):return 'EXPIRED_REQUEST'
        with open(self.lock,'a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return 'BUSY'
            with closing(sqlite3.connect(self.db,timeout=1)) as db:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('PRAGMA synchronous=FULL')
                db.execute('CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY, mode TEXT NOT NULL,status TEXT NOT NULL)')
                db.execute('CREATE TABLE IF NOT EXISTS command_identity(request_id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,owner_epoch INTEGER NOT NULL,requested_power_w REAL NOT NULL)')
                from dispatch_lifecycle import initialise,permit,begin,finish
                from dispatch_reservations import initialise as reservations_init, inspect, reserve, set_status
                initialise(db)
                reservations_init(db)
                existing_reservation=inspect(db,request_id=request_id,plan_id=plan_id,owner_epoch=self.expected_epoch,
                                              option=option,power_w=maximum_power_w,expires_at=expires_at)
                if existing_reservation:return existing_reservation
                row=db.execute('SELECT mode,status FROM commands WHERE id=?',(request_id,)).fetchone()
                if row:
                    db.rollback()
                    identity=db.execute('SELECT plan_id,owner_epoch,requested_power_w FROM command_identity WHERE request_id=?',(request_id,)).fetchone()
                    if identity is None:return 'UNKNOWN_IDENTITY_REQUIRES_RECONCILIATION'
                    return 'DUPLICATE_'+row[1] if row[0]==option and identity==(plan_id,self.expected_epoch,maximum_power_w) else 'REQUEST_CONFLICT'
                if db.execute("SELECT 1 FROM commands WHERE status IN ('PENDING','UNKNOWN')").fetchone():
                    db.rollback();return 'UNKNOWN_REQUIRES_RECONCILIATION'
                lifecycle=permit(db,request_id)
                if lifecycle:
                    db.rollback();return lifecycle
                check_time=self.clock()
                if not check_time<expires_at:
                    db.rollback();return 'EXPIRED_REQUEST'
                why=self.live_guard(option,check_time,setting_power=maximum_power_w is not None)
                if why:
                    db.rollback();return why
                if intent_check is not None and not intent_check():
                    db.rollback();return 'PLAN_CHANGED_OR_EXPIRED'
                # Reserve the request atomically before any service transport.
                # HA reads above remain outside the SQLite write transaction.
                db.execute('BEGIN IMMEDIATE')
                reservation=reserve(db,request_id=request_id,plan_id=plan_id,owner_epoch=self.expected_epoch,
                                    option=option,power_w=maximum_power_w,expires_at=expires_at,now=check_time)
                if reservation!='RESERVED':
                    db.rollback();return reservation
                db.execute('INSERT INTO commands VALUES(?,?,?)',(request_id,option,'PENDING'))
                db.execute('INSERT INTO command_identity VALUES(?,?,?,?)',(request_id,plan_id,self.expected_epoch,maximum_power_w))
                begin(db,request_id,option,check_time)
                set_status(db,request_id,'PENDING',check_time)
                db.commit()
                try:
                    # Recheck immediately before issuing. External fencing still mandatory.
                    check_time=self.clock()
                    why='EXPIRED_REQUEST' if not check_time<expires_at else self.live_guard(option,check_time,setting_power=maximum_power_w is not None)
                    if not why and intent_check is not None and not intent_check():why='PLAN_CHANGED_OR_EXPIRED'
                    if why:
                        db.execute('UPDATE commands SET status=? WHERE id=?',('REJECTED',request_id));finish(db,request_id,'REJECTED',self.clock());set_status(db,request_id,'REJECTED',self.clock());db.commit();return why
                    issued_at=self.clock()
                    if not issued_at<expires_at:
                        db.execute('UPDATE commands SET status=? WHERE id=?',('REJECTED',request_id));finish(db,request_id,'REJECTED',self.clock());set_status(db,request_id,'REJECTED',self.clock());db.commit();return 'EXPIRED_REQUEST'
                    requested=math.floor(min(maximum_power_w,self.direction_ceiling_w,self.p.max_charge_w if option in self.CHARGES else self.p.max_discharge_w))
                    if requested<=0:raise GatewayRejected('zero_direction_limit_before_transport')
                    reply=self.ha.dispatch(self.mode,option,requested,request_id=request_id,expires_at=expires_at,plan_id=plan_id,owner_epoch=self.expected_epoch)
                    applied=reply['applied_power_w']
                    if type(applied) not in (int,float) or not math.isfinite(applied) or not 0<applied<=requested:raise RuntimeError('invalid_gateway_power_ack')
                    s=self.ha.state(self.mode)
                    stamp=datetime.fromisoformat(s['last_updated'])
                    ack=s['state']==option and stamp.tzinfo is not None and issued_at<=stamp<=self.clock()
                    if applied is not None:
                        power=self.ha.state(self.powers[0 if option in self.CHARGES else 1])
                        pt=datetime.fromisoformat(power['last_updated'])
                        ack=ack and float(power['state'])==applied and pt.tzinfo is not None and issued_at<=pt<=self.clock()
                    # An ownership or plan change after writes is UNKNOWN, never REJECTED.
                    still_authorized=self.local_owner_guard() is False and self.ha.state(self.owner_entity).get('state')=='EMS2'
                    still_current=intent_check is None or intent_check()
                    status='ACK' if ack and still_authorized and still_current and self.clock()<expires_at else 'UNKNOWN'
                except GatewayRejected:status='REJECTED'
                except Exception:status='UNKNOWN'
                db.execute('UPDATE commands SET status=? WHERE id=?',(status,request_id))
                finish(db,request_id,status,self.clock())
                set_status(db,request_id,status,self.clock())
                db.commit()
                return status

