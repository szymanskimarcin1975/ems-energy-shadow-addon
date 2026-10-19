"""Bounded HA APIs only. No Modbus client, services, OAuth edits or .storage IO."""
import asyncio,hashlib,json,os,tempfile
from pathlib import Path
from datetime import datetime,timezone
from copy import deepcopy
from homeassistant.helpers import entity_registry as er
from .admin_context import require_admin

STEPS={
 'init':('scan_interval','close_after_polling','detect_meters','detect_batteries','detect_extras','advanced_power_control','request_timeout','sleep_after_write'),
 'battery_options':('allow_battery_energy_reset','battery_energy_reset_cycles','battery_rating_adjust'),
 'adv_pwr_ctl':('adv_storage_control','adv_site_limit_control'),
}
CONTROL_SUFFIXES=(('number','site_limit'),('number','external_production_max'),('select','limit_control_mode'),('select','limit_control'))
DOMAIN='solaredge_modbus_multi'
REQUEST_TIMEOUT_SECONDS=5
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def atomic_json(path,data):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(data,f);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
        parent=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(parent)
        finally:os.close(parent)
    finally:
        if os.path.exists(name):os.unlink(name)

class Operations:
    def __init__(self,hass):
        self.hass=hass;self.lock=asyncio.Lock()
        self.root=Path(hass.config.path('mcp_admin_backups'))
        self.state=None;self.uncertain=False
        # Existing journal on a new instance/restart must be reconciled by an
        # administrator. Do not resurrect a flow or retry its last operation.
        if (self.root/'operation.json').exists():self.uncertain=True
    async def persist(self,data):
        await asyncio.wait_for(self.hass.async_add_executor_job(atomic_json,self.root/'operation.json',data),3)
    async def backup(self,data):
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        await asyncio.wait_for(self.hass.async_add_executor_job(atomic_json,self.root/(stamp+'.json'),data),3)
    def entry(self,entry_id):
        e=self.hass.config_entries.async_get_entry(entry_id)
        if e is None or e.domain!=DOMAIN:raise ValueError('ENTRY_NOT_SOLAREDGE')
        return e
    def anchors(self,e,registry):
        anchors=[r for r in registry.entities.values() if r.config_entry_id==e.entry_id and r.platform==DOMAIN and r.domain=='select' and r.unique_id.endswith('_storage_control_mode')]
        if not anchors:raise ValueError('NO_VERIFIED_STORAGE_IDENTITY')
        return anchors
    def controls(self,e,registry):
        out=[]
        for a in self.anchors(e,registry):
            base=a.unique_id.removesuffix('_storage_control_mode')
            for domain,suffix in CONTROL_SUFFIXES:
                uid=base+'_'+suffix;eid=registry.async_get_entity_id(domain,DOMAIN,uid)
                r=registry.async_get(eid) if eid else None
                if r and (r.config_entry_id!=e.entry_id or r.device_id!=a.device_id):raise ValueError('ENTITY_IDENTITY_COLLISION')
                out.append((a,domain,uid,r))
        return out
    async def inspect(self,entry_id):
        await require_admin(self.hass);e=self.entry(entry_id);registry=er.async_get(self.hass)
        return {'status':'READ_ONLY','entry_id':entry_id,'options_fingerprint':fingerprint(dict(e.options)),
          'options':{k:e.options[k] for ks in STEPS.values() for k in ks if k in e.options},
          'controls':[{'domain':d,'unique_id':u,'entity_id':r.entity_id if r else None,'disabled_by':str(r.disabled_by) if r and r.disabled_by else None} for a,d,u,r in self.controls(e,registry)],
          'reconciliation_required':self.uncertain}
    async def protect(self,entry_id):
        await require_admin(self.hass)
        async with self.lock:
            e=self.entry(entry_id);registry=er.async_get(self.hass);items=self.controls(e,registry)
            # No mutation until a complete rollback record has been fsynced.
            await self.backup({'kind':'registry_before','entry_id':entry_id,'items':[{'domain':d,'unique_id':u,'entity_id':r.entity_id if r else None,'device_id':a.device_id,'disabled_by':str(r.disabled_by) if r and r.disabled_by else None} for a,d,u,r in items]})
            for anchor,domain,uid,r in items:
                if r is None:
                    r=registry.async_get_or_create(domain,DOMAIN,uid,config_entry=e,device_id=anchor.device_id,disabled_by=er.RegistryEntryDisabler.USER,suggested_object_id='ems_disabled_'+fingerprint(uid)[:16])
                elif not r.disabled_by:
                    r=registry.async_update_entity(r.entity_id,disabled_by=er.RegistryEntryDisabler.USER)
            if any(not r or not r.disabled_by for a,d,u,r in self.controls(e,registry)):raise ValueError('REGISTRY_PROTECTION_READBACK_FAILED')
            return {'status':'PROTECTED_BEFORE_OPTIONS','count':len(items),'no_modbus_writes':True}
    async def begin(self,entry_id):
        actor=await require_admin(self.hass)
        async with self.lock:
            if self.uncertain or self.state:raise ValueError('RECONCILIATION_OR_FLOW_REQUIRED')
            e=self.entry(entry_id);opts=dict(e.options)
            if opts.get('advanced_power_control') is not True:raise ValueError('UNEXPECTED_OPTIONS_PATH')
            await self.backup({'kind':'options_before','entry_id':entry_id,'options':opts})
            self.uncertain=True
            await self.persist({'phase':'STARTING','entry_id':entry_id,'actor':actor})
            r=await asyncio.wait_for(self.hass.config_entries.options.async_init(entry_id),REQUEST_TIMEOUT_SECONDS)
            if r.get('type')!='form' or r.get('step_id')!='init' or not isinstance(r.get('flow_id'),str):raise ValueError('UNKNOWN_FLOW_RESULT')
            self.state={'phase':'FORM','entry_id':entry_id,'actor':actor,'flow_id':r['flow_id'],'step_id':'init','options':opts}
            await self.persist(self.state);self.uncertain=False
            return {k:self.state[k] for k in ('phase','flow_id','step_id')}
    async def advance(self,flow_id,expected_step):
        actor=await require_admin(self.hass)
        async with self.lock:
            f=self.state
            if self.uncertain or not f or f['flow_id']!=flow_id or f['actor']!=actor or f['step_id']!=expected_step:raise ValueError('FLOW_IDENTITY_MISMATCH')
            e=self.entry(f['entry_id'])
            if dict(e.options)!=f['options']:raise ValueError('OPTIONS_CHANGED')
            current=self.hass.config_entries.options.async_get(flow_id)
            if current.get('step_id')!=expected_step:raise ValueError('FLOW_STEP_CHANGED')
            # This ephemeral capability can be installed only by the trusted
            # backend after independently verifying device/reload safety.
            # There is deliberately no MCP setter and no caller approval flag.
            approval=self.hass.data.get('ems_mcp_reload_approval')
            if not callable(approval) or approval(e.entry_id,fingerprint(f['options'])) is not True:
                return {'status':'BLOCKED','reason':'RELOAD_SAFETY_UNCONFIRMED'}
            items=self.controls(e,er.async_get(self.hass))
            if any(not r or not r.disabled_by for a,d,u,r in items):raise ValueError('WRITE_CONTROLS_NOT_PREPROTECTED')
            keys=STEPS[expected_step];opts=f['options']
            if any(k not in opts for k in keys):raise ValueError('PRESERVED_OPTION_MISSING')
            body={k:opts[k] for k in keys}
            if expected_step=='adv_pwr_ctl':body['adv_site_limit_control']=True
            self.uncertain=True
            await self.persist({**f,'phase':'SUBMITTING'})
            r=await asyncio.wait_for(self.hass.config_entries.options.async_configure(flow_id,body),REQUEST_TIMEOUT_SECONDS)
            next_step={'init':'battery_options' if opts.get('detect_batteries') else 'adv_pwr_ctl','battery_options':'adv_pwr_ctl'}.get(expected_step)
            if r.get('type')=='form' and r.get('flow_id')==flow_id and r.get('step_id')==next_step:
                self.state={**f,'step_id':next_step};await self.persist(self.state);self.uncertain=False
                return {'status':'FORM','flow_id':flow_id,'step_id':next_step}
            if expected_step=='adv_pwr_ctl' and r.get('type')=='create_entry':
                await self.persist({**f,'phase':'SAVED_RECONCILE_RELOAD'})
                return {'status':'UNKNOWN','reason':'SAVED_VERIFY_RELOAD_AND_READBACK_NO_RETRY'}
            raise ValueError('UNKNOWN_FLOW_RESPONSE')

async def invoke(hass,operation,args):
    # No credentials/error strings or tracebacks are returned or logged.
    # Read operations also require a current admin identity.
    try:
        await require_admin(hass)
        if operation not in ('inspect','protect','begin','advance'):raise ValueError('OPERATION_NOT_ALLOWED')
        expected={'advance':{'flow_id','expected_step'}}.get(operation,{'entry_id'})
        if set(args)!=expected or any(not isinstance(v,str) or not v or len(v)>128 for v in args.values()):raise ValueError('INVALID_ARGUMENTS')
        key='ems_mcp_admin_operations'
        if key not in hass.data:hass.data[key]=Operations(hass)
        return await getattr(hass.data[key],operation)(**args)
    except PermissionError:return {'status':'REJECTED','reason':'ADMIN_REQUIRED','writes_started':False}
    except asyncio.CancelledError:raise
    except Exception:
        op=hass.data.get('ems_mcp_admin_operations')
        if op is not None:op.uncertain=True
        return {'status':'UNKNOWN','reason':'RECONCILIATION_REQUIRED_NO_RETRY'}
