"""Install as MCP tools/ems_prepare.py; uses existing OAuth admin context."""
import asyncio
from . import register_tool, ANNOTATION_READ_ONLY, ANNOTATION_NON_IDEMPOTENT, dumps
from ..admin_context import require_admin
from ..prepare_operations import run

async def invoke(hass,arguments,action):
    await require_admin(hass) # No caller-supplied user/token and no Context(None) fallback.
    if not isinstance(arguments,dict) or set(arguments)!={'operation_id'}:
        raise ValueError('ONLY_OPERATION_ID_ACCEPTED')
    locks=hass.data.setdefault('ems_prepare_operation_locks',{})
    lock=locks.setdefault('solaredge',asyncio.Lock())
    if lock.locked():return {'status':'BUSY','automatic_retry':False}
    async with lock:
        return await hass.async_add_executor_job(run,hass.config.path(),arguments['operation_id'],action)

SCHEMA={'type':'object','properties':{'operation_id':{'type':'string','pattern':'^[a-f0-9]{32}$'}},'required':['operation_id'],'additionalProperties':False}

@register_tool(name='ems_admin_solaredge_prepare',description='Admin-only code backup and SHA256 for fixed SolarEdge component; no shell/install/restart/device write.',input_schema=SCHEMA,annotations=ANNOTATION_NON_IDEMPOTENT)
async def prepare(hass,arguments):
    result=await invoke(hass,arguments,'prepare')
    return {'content':[{'type':'text','text':dumps(result)}],'isError':result.get('status')!='COMPLETE'}

@register_tool(name='ems_admin_solaredge_prepare_status',description='Admin-only verification of an existing code backup by operation ID; no write or device access.',input_schema=SCHEMA,annotations=ANNOTATION_READ_ONLY)
async def status(hass,arguments):
    result=await invoke(hass,arguments,'status')
    return {'content':[{'type':'text','text':dumps(result)}],'isError':result.get('status')!='COMPLETE'}
