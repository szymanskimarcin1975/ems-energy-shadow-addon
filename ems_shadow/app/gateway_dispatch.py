"""Build an EMS2-only compound branch for the existing queued HA gateway.
No API, credentials or real installation identifiers. LEGACY sequence is preserved.
"""
from copy import deepcopy
import re
OPTIONS=['Charge from Solar Power','Charge from Solar Power and Grid','Discharge to Minimize Import']
ROLES={'owner','authorization','soc','safety_min','safety_max','control_mode','command_mode','charge_limit','discharge_limit','fault_status','vendor_status','m1_power','b1_power','bms_status','max_charge','peak_charge','max_discharge','peak_discharge'}
GUARD="""{% set p=ems2_dispatch_sources %}{% set ns=namespace(ok=true,ts=[]) %}
{% set charging=ems2_d_option in ['Charge from Solar Power','Charge from Solar Power and Grid'] %}
{% set direction='charge' if charging else 'discharge' %}
{% set soc=states(p.soc)|float(-1) %}{% set lo=states(p.safety_min)|float(-1) %}{% set hi=states(p.safety_max)|float(-1) %}
{% set vmax=states(p['max_'~direction])|float(-1) %}{% set vpeak=states(p['peak_'~direction])|float(-1) %}
{% if operation|default('') != 'dispatch' or not (request_id|default('')|string|regex_match('^[A-Za-z0-9_-]{1,64}$')) or not (as_timestamp(now()) < expires_at|default(-1)|float(-1) <= as_timestamp(now())+60) or not (plan_id|default('')|string|regex_match('^[a-f0-9]{64}$')) or owner_epoch|default(-1) is boolean or not owner_epoch|default(-1) is integer or owner_epoch|default(-1)<0 or ems2_d_option not in ['Charge from Solar Power','Charge from Solar Power and Grid','Discharge to Minimize Import'] or not command_value is mapping or command_value.get('power_w') is boolean or not (0 < ems2_d_requested <= 50000) %}INVALID_REQUEST
{% elif not is_state(p.owner,'EMS2') or not is_state(p.authorization,'on') %}OWNER_OR_AUTHORIZATION_REJECTED
{% elif charging and soc>=100 %}SOC_CEILING
{% elif vmax<=0 or vpeak<=0 %}BMS_DIRECTION_LIMIT_ZERO
{% else %}
{% for e in p.old_writers %}{% if not is_state(e,'off') or state_attr(e,'current')!=0 %}{% set ns.ok=false %}{% endif %}{% endfor %}
{% for role in ['soc','m1_power','b1_power','bms_status','fault_status','vendor_status','max_'~direction,'peak_'~direction] %}
{% set s=states[p[role]] %}{% if s is none %}{% set ns.ok=false %}{% else %}
{% set age=as_timestamp(now())-as_timestamp(s.last_reported) %}{% if not (0<=age<=180) %}{% set ns.ok=false %}{% endif %}{% set ns.ts=ns.ts+[as_timestamp(s.last_reported)] %}{% endif %}{% endfor %}
{% for role,unit in [('soc','%'),('m1_power','kW'),('b1_power','W'),('max_'~direction,'W'),('peak_'~direction,'W')] %}{% if not is_number(states(p[role])) or state_attr(p[role],'unit_of_measurement')!=unit %}{% set ns.ok=false %}{% endif %}{% endfor %}
{% if not is_number(states(p.safety_min)) or not is_number(states(p.safety_max)) or not (0<=lo<hi<=100) %}{% set ns.ok=false %}{% endif %}
{% if ns.ts|length!=8 or (ns.ts|max)-(ns.ts|min)>5 %}{% set ns.ok=false %}{% endif %}
{% if is_state(p.fault_status,'I_STATUS_FAULT') or not is_state(p.vendor_status,'0x0') %}INVERTER_FAULT_OR_VENDOR_ERROR
{% elif not is_state(p.fault_status,'I_STATUS_MPPT') %}INVERTER_STATE_AMBIGUOUS
{% elif not is_state(p.control_mode,'Remote Control') %}REMOTE_CONTROL_NOT_ACTIVE
{% elif states(p.bms_status) not in ['B_STATUS_STANDBY','B_STATUS_IDLE','B_STATUS_CHARGE','B_STATUS_DISCHARGE'] %}BMS_STATUS_NOT_APPROVED
{% elif not ((charging and lo<=soc<hi) or (not charging and lo<soc<=hi)) %}SOC_OUT_OF_RANGE
{% elif not charging and states(p.m1_power)|float(999)>=0 %}NO_FRESH_GRID_IMPORT
{% elif not ns.ok %}LIVE_SAFETY_OR_FRESHNESS_REJECTED
{% else %}ALLOW{% endif %}{% endif %}"""
CAP="{{ [5000,ems2_d_requested,states(ems2_dispatch_sources['max_'~ems2_d_direction])|float(-1),states(ems2_dispatch_sources['peak_'~ems2_d_direction])|float(-1)]|min|round(0,'floor')|int }}"
def branch(bindings):
 if set(bindings)!=(ROLES|{'old_writers'}):raise ValueError('gateway_roles')
 for role in ROLES:
  if not isinstance(bindings[role],str) or not re.fullmatch('[a-z_]+\\.[a-z0-9_]+',bindings[role]):raise ValueError('gateway_entity')
 if not bindings['old_writers'] or any(not re.fullmatch('automation\\.[a-z0-9_]+',e) for e in bindings['old_writers']):raise ValueError('gateway_writers')
 identity={'gateway_contract':'EMS2_COMPOUND_V28','plan_id':'{{ plan_id | default('') }}','owner_epoch':'{{ owner_epoch | default(-1) }}','owner':'{{ states(ems2_dispatch_sources.owner) }}'}
 reject={**identity,'writes_started':False,'status':'REJECTED','reason':'{{ ems2_d_reason | trim }}','request_id':'{{ request_id | default(\'\') }}'}
 partial={**identity,'writes_started':True,'status':'PARTIAL_OR_UNKNOWN','reason':'Safety or limits changed after power write; reconcile before another command','request_id':'{{ request_id }}'}
 seq=[{'variables':{'ems2_dispatch_sources':deepcopy(bindings),'ems2_d_option':"{{ command_value.get('option','') if command_value is mapping else '' }}",'ems2_d_requested':"{{ command_value.get('power_w',-1)|float(-1) if command_value is mapping else -1 }}"}},
 {'variables':{'ems2_d_direction':"{{ 'charge' if ems2_d_option in ['Charge from Solar Power','Charge from Solar Power and Grid'] else 'discharge' }}",'ems2_d_reason':GUARD}},
 {'if':[{'condition':'template','value_template':"{{ ems2_d_reason | trim != 'ALLOW' }}"}],'then':[{'variables':{'reply':reject}},{'stop':'EMS2 dispatch rejected before writes','response_variable':'reply'}]},
 {'variables':{'ems2_d_applied':CAP}},
 {'if':[{'condition':'template','value_template':'{{ ems2_d_applied|int<=0 }}'}],'then':[{'variables':{'reply':{**identity,'writes_started':False,'status':'REJECTED','reason':'BMS_DIRECTION_LIMIT_ZERO','request_id':'{{ request_id }}'}}},{'stop':'No positive safe power','response_variable':'reply'}]},
 {'action':'number.set_value','target':{'entity_id':"{{ ems2_dispatch_sources[ems2_d_direction~'_limit'] }}"},'data':{'value':'{{ ems2_d_applied }}'}},
 {'variables':{'ems2_d_reason':GUARD,'ems2_d_current_cap':CAP}},
 {'if':[{'condition':'template','value_template':"{{ ems2_d_reason | trim != 'ALLOW' or ems2_d_current_cap|int < ems2_d_applied|int }}"}],'then':[{'variables':{'reply':partial}},{'stop':'Partial dispatch requires reconciliation','response_variable':'reply'}]},
 {'action':'select.select_option','target':{'entity_id':'{{ ems2_dispatch_sources.command_mode }}'},'data':{'option':'{{ ems2_d_option }}'}},
 {'variables':{'reply':{**identity,'writes_started':True,'status':'SERVICE_COMPLETED','request_id':'{{ request_id }}','applied_power_w':'{{ ems2_d_applied }}','option':'{{ ems2_d_option }}','device_execution_confirmed':False,'gateway_contract':'EMS2_COMPOUND_V28'}}},
 {'stop':'Serialized EMS2 power and mode service calls completed; physical execution unproven','response_variable':'reply'}]
 return {'if':[{'condition':'template','value_template':"{{ caller|default('') == 'EMS2' }}"}],'then':seq}
def extend(existing,bindings):
 if existing.get('mode')!='queued' or not isinstance(existing.get('sequence'),list):raise ValueError('queued_gateway_required')
 result=deepcopy(existing)
 if any('ems2_dispatch_sources' in str(s) for s in result['sequence']):raise ValueError('compound_branch_already_installed')
 result['sequence'].insert(1,branch(bindings))
 result['description']=result.get('description','')+' EMS2 compound dispatch v28: live power clamp and before/after-write safety checks; LEGACY unchanged.'
 return result
