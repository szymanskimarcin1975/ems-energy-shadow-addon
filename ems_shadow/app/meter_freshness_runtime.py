"""Isolated read-only publisher for boiler/heatpump source freshness.

Reads HA states using Supervisor GET only. No device control, no restart
commands, no secrets or entity IDs in published diagnostic.
"""
import json,os,urllib.request
from datetime import datetime,timezone
from zigbee_freshness import classify

def snapshot(options_path='/data/options.json', token=None, opener=None, now=None):
    now=now or datetime.now(timezone.utc)
    try:
        options=json.loads(open(options_path,encoding='utf-8').read())
        sources=options.get('sources',{})
        wanted={key:sources.get(key) for key in ('boiler_w','heatpump_w')}
        if not all(isinstance(v,str) and v for v in wanted.values()):
            return {'status':'SOURCES_NOT_CONFIGURED','advisory_only':True,'automatic_restart_permitted':False}
        token=token if token is not None else os.environ['SUPERVISOR_TOKEN']
        req=urllib.request.Request('http://supervisor/core/api/states',headers={'Authorization':'Bearer '+token})
        response=(opener or urllib.request.urlopen)(req,timeout=5)
        with response as stream:
            states=json.load(stream)
        by_id={x.get('entity_id'):x for x in states if isinstance(x,dict)}
        readings={key:by_id.get(eid) for key,eid in wanted.items()}
        result=classify(now.isoformat(),readings)
        result['recorded_at']=now.isoformat()
        return result
    except Exception:
        return {'status':'READ_UNAVAILABLE','recorded_at':now.isoformat(),
                'advisory_only':True,'automatic_restart_permitted':False}
