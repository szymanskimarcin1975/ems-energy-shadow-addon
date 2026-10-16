"""Explicit read-only HA state-machine snapshot; no arbitrary templates accepted.
Preserve REST values/times. HA reporting times remain distinct from device times.
"""
import json,re
from urllib.request import Request,urlopen
from weather_demand import stamp

def refresh(api,states,entities):
 entities=sorted(set(entities))
 if len(entities)>20 or any(not isinstance(e,str) or not re.fullmatch(r'sensor\.[a-z0-9_]+',e) for e in entities):raise ValueError('invalid_snapshot_entities')
 template="{% set ns=namespace(rows={}) %}{% for e in "+json.dumps(entities)+" %}{% set s=states[e] %}{% if s is not none %}{% set ns.rows=dict(ns.rows, **{e:{'state':s.state,'unit':s.attributes.get('unit_of_measurement'),'last_reported':s.last_reported.isoformat(),'last_updated':s.last_updated.isoformat(),'last_changed':s.last_changed.isoformat()}}) %}{% endif %}{% endfor %}{{ ns.rows|tojson }}"
 request=Request(api.base+'/template',data=json.dumps({'template':template}).encode(),headers={'Authorization':'Bearer '+api.token,'Content-Type':'application/json'},method='POST')
 try:
  with urlopen(request,timeout=3) as response:rows=json.load(response)
  if not isinstance(rows,dict) or set(rows)-set(entities):raise ValueError('invalid_snapshot_response')
 except (OSError,ValueError,TypeError):rows={}
 for e in entities:
  if e not in states:continue
  old=states[e];row=rows.get(e,{})
  for key in ('state','last_reported','last_updated','last_changed'):old['rest_'+key]=old.get(key)
  try:
   for key in ('last_reported','last_updated','last_changed'):stamp(row[key])
   if not isinstance(row['state'],str):raise ValueError('invalid_snapshot_state')
   old.update({key:row[key] for key in ('state','last_reported','last_updated','last_changed')})
   old['attributes']=dict(old.get('attributes',{}),unit_of_measurement=row['unit'])
   old['timestamp_origin']='HA_STATE_MACHINE_TEMPLATE_NOT_DEVICE'
  except (KeyError,ValueError,TypeError):
   old['last_reported']=None;old['timestamp_origin']='SNAPSHOT_UNCONFIRMED'
 return states
