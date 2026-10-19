"""Narrow admin tools for the SolarEdge options/read-only diagnostic workflow."""
from . import register_tool,ANNOTATION_READ_ONLY,ANNOTATION_NON_IDEMPOTENT,dumps
from ..admin_operations import invoke

def tool(name,operation,properties):
    schema={'type':'object','properties':{k:{'type':'string'} for k in properties},'required':list(properties),'additionalProperties':False}
    @register_tool(name=name,description='Admin-only SolarEdge diagnostic preparation; no inverter service or Modbus write. UNKNOWN is never retried.',input_schema=schema,annotations=ANNOTATION_READ_ONLY if operation=='inspect' else ANNOTATION_NON_IDEMPOTENT)
    async def handler(hass,arguments):
        result=await invoke(hass,operation,arguments)
        return {'content':[{'type':'text','text':dumps(result)}],'isError':result.get('status') in ('UNKNOWN','REJECTED')}
    return handler

inspect=tool('ems_admin_options_inspect','inspect',('entry_id',))
protect=tool('ems_admin_site_controls_protect','protect',('entry_id',))
begin=tool('ems_admin_options_begin','begin',('entry_id',))
advance=tool('ems_admin_options_advance','advance',('flow_id','expected_step'))
