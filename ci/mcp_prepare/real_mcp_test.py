"""Actual HA HTTP/MCP + real OIDC token validator; loopback and test files only.
No browser consent grant or production Nabu Casa session. No Modbus connection.
"""
import asyncio,hashlib,json,os,shutil,sys,tempfile,threading,time,traceback,zipfile
from pathlib import Path
from types import MappingProxyType
ROOT=Path.cwd();CONFIG=ROOT/'isolated-ha';OUT=ROOT/'mcp-evidence';OUT.mkdir(exist_ok=True)
NAMES={'ems_admin_solaredge_prepare','ems_admin_solaredge_prepare_status'}
ID='a'*32;DISCONNECT='b'*32;INCOMPLETE='c'*32

def prepare():
 CONFIG.mkdir();cc=CONFIG/'custom_components';cc.mkdir();(cc/'__init__.py').write_text('')
 (CONFIG/'configuration.yaml').write_text(json.dumps({'homeassistant':{'name':'Isolated MCP','country':'PL','latitude':0,'longitude':0,'elevation':0,'unit_system':'metric','time_zone':'Europe/Warsaw'},'http':{'server_host':['127.0.0.1'],'server_port':8123},'logger':{'default':'critical'}}))
 with zipfile.ZipFile(ROOT/'mcp-package/mcp-1.18.0-ems.2-prepare.zip') as z:z.extractall(CONFIG)
 shutil.copytree(ROOT/'oidc-upstream/custom_components/oidc_provider',cc/'oidc_provider')
 shutil.copytree(ROOT/'solar-upstream/custom_components/solaredge_modbus_multi',cc/'solaredge_modbus_multi')

def entry(domain,data,disabled=False):
 from homeassistant.config_entries import ConfigEntry,ConfigEntryDisabler
 return ConfigEntry(version=1,minor_version=1,domain=domain,title='Isolated '+domain,data=data,options={},source='user',unique_id='isolated-'+domain,discovery_keys=MappingProxyType({}),subentries_data=None,disabled_by=ConfigEntryDisabler.USER if disabled else None)

async def main(phase):
 import aiohttp,jwt
 from cryptography.hazmat.primitives import serialization
 from cryptography.hazmat.primitives.asymmetric import rsa
 from homeassistant.runner import RuntimeConfig
 from homeassistant.bootstrap import async_setup_hass
 from homeassistant.const import __version__
 from homeassistant.auth.const import GROUP_ID_ADMIN,GROUP_ID_USER
 assert __version__=='2026.10.0';assert sys.version_info[:2]==(3,14)
 checks=[];hass=None
 def check(name,ok):
  checks.append({'name':name,'pass':bool(ok)})
  if not ok:raise AssertionError(name)
 try:
  hass=await async_setup_hass(RuntimeConfig(config_dir=str(CONFIG),log_no_color=True));check('real_HA_bootstrap',hass is not None)
  if phase=='candidate':
   admin=await hass.auth.async_create_user('Synthetic admin',group_ids=[GROUP_ID_ADMIN])
   other=await hass.auth.async_create_user('Synthetic nonadmin',group_ids=[GROUP_ID_USER])
   inactive=await hass.auth.async_create_user('Synthetic inactive admin',group_ids=[GROUP_ID_ADMIN])
   await hass.auth.async_update_user(inactive,is_active=False)
   await hass.config_entries.async_add(entry('oidc_provider',{},True))
   mcp=entry('mcp_server_http_transport',{'native_auth_enabled':False,'server_name':'isolated-ci'})
   await hass.config_entries.async_add(mcp);check('real_MCP_loaded',str(mcp.state)=='ConfigEntryState.LOADED')
   key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
   (CONFIG/'synthetic-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
   (CONFIG/'test-identities.json').write_text(json.dumps(dict(admin=admin.id,other=other.id,inactive=inactive.id)))
  else:
   ids=json.loads((CONFIG/'test-identities.json').read_text());admin=await hass.auth.async_get_user(ids['admin']);other=await hass.auth.async_get_user(ids['other']);inactive=await hass.auth.async_get_user(ids['inactive'])
   key=serialization.load_pem_private_key((CONFIG/'synthetic-key.pem').read_bytes(),password=None)
  hass.data['oidc_provider']={'jwt_public_key':key.public_key(),'clients':{}}
  await hass.async_start();await hass.async_block_till_done();check('real_HA_running',hass.is_running)
  issuer='https://synthetic.invalid';resource=issuer+'/api/mcp_http'
  device_calls=[]
  def audit_service_event(event):
   if event.data.get('domain') in ('select','number','solaredge_modbus_multi','ems_epoch_gateway'):
    device_calls.append((event.data['domain'],event.data.get('service')))
  hass.bus.async_listen('call_service',audit_service_event)
  tokens=[]
  def token(user,**changes):
   claims=dict(sub=user.id,iat=int(time.time()),exp=int(time.time())+600,iss=issuer+'/oidc',aud=resource);claims.update(changes)
   value=jwt.encode(claims,key,algorithm='RS256');tokens.append(value);return value
  def headers(user=admin,**claims):return {'Authorization':'Bearer '+token(user,**claims),'X-Forwarded-Proto':'https','X-Forwarded-Host':'synthetic.invalid'}
  async with aiohttp.ClientSession() as client:
   async def rpc(method,params=None,auth=None):
    async with client.post('http://127.0.0.1:8123/api/mcp_http',json={'jsonrpc':'2.0','id':1,'method':method,'params':params or {}},headers=auth if auth is not None else headers()) as r:
     return r.status,await r.json()
   for _ in range(150):
    async with client.get('http://127.0.0.1:8123/api/mcp_http') as r:
     if r.status==401:break
    await asyncio.sleep(.2)
   status,body=await rpc('initialize');check('real_OAuth_access_token_validated',status==200 and 'result' in body)
   status,body=await rpc('tools/list');names={t['name'] for t in body['result']['tools']}
   check('tools_list_correct',NAMES.issubset(names) if phase!='rollback' else not NAMES.intersection(names))
   check('old_tools_retained',{'ems_admin_options_inspect','get_state','call_service'}.issubset(names))
   for auth in ({},headers(admin,exp=int(time.time())-1),headers(admin,aud='wrong-resource')):
    status,_=await rpc('tools/list',auth=auth);check('invalid_token_denied',status==401)
   async def call(name,id,auth=None,extra=None):
    args={'operation_id':id};args.update(extra or {})
    status,b=await rpc('tools/call',{'name':name,'arguments':args},auth)
    check('MCP_roundtrip',status==200 and 'result' in b)
    result=b['result'];text=result['content'][0]['text']
    try:value=json.loads(text)
    except ValueError:value={'error':text}
    return result,value
   if phase=='rollback':
    check('same_identity_original_code_reconnected',json.loads((CONFIG/'custom_components/mcp_server_http_transport/manifest.json').read_text())['version']=='1.18.0+ems.1')
   else:
    for user in [other,inactive]:
     for name in NAMES:
      result,value=await call(name,'d'*32,headers(user));check('nonadmin_or_inactive_denied',result.get('isError') is True and 'ACTIVE_HA_ADMIN_REQUIRED' in value.get('error',''))
    if phase=='candidate':
     check('denial_has_no_backup_write',not (CONFIG/'ems_prepare_backups').exists())
     source=CONFIG/'custom_components/solaredge_modbus_multi'
     def hashes():return {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
     before=hashes()
     _,a=await call('ems_admin_solaredge_prepare',ID);check('admin_prepare_complete',a['status']=='COMPLETE')
     _,b=await call('ems_admin_solaredge_prepare_status',ID);check('admin_verify_complete',b['status']=='COMPLETE' and a['manifest_sha256']==b['manifest_sha256'])
     _,b=await call('ems_admin_solaredge_prepare',ID);check('duplicate_id_no_copy',a['manifest_sha256']==b['manifest_sha256'])
     count=len(list((CONFIG/'ems_prepare_backups').iterdir()))
     for extra in [{'path':'/config/secrets.yaml'},{'command':'reboot'},{'action':'install'}]:
      result,_=await call('ems_admin_solaredge_prepare','e'*32,extra=extra);check('arbitrary_argument_denied',result.get('isError') is True)
     result,_=await call('ems_admin_solaredge_prepare','../secrets.yaml');check('path_id_denied',result.get('isError') is True)
     check('invalid_input_no_files',len(list((CONFIG/'ems_prepare_backups').iterdir()))==count)
     # Actual HTTP client disconnect while the real handler is copying test files.
     from custom_components.mcp_server_http_transport import prepare_operations as operations
     original=operations.write;started=threading.Event();release=threading.Event();attempts=[]
     def delayed(fd,name,data):
      if name=='hub.py':attempts.append(1);started.set();assert release.wait(5)
      return original(fd,name,data)
     operations.write=delayed
     try:
      task=asyncio.create_task(call('ems_admin_solaredge_prepare',DISCONNECT))
      check('copy_in_progress',await asyncio.to_thread(started.wait,5))
      task.cancel()
      try:await task
      except asyncio.CancelledError:pass
      release.set()
      outcome=None
      for _ in range(50):
       _,outcome=await call('ems_admin_solaredge_prepare_status',DISCONNECT)
       if outcome.get('status')=='COMPLETE':break
       await asyncio.sleep(.1)
      check('disconnect_reconciled_by_same_id',outcome.get('status')=='COMPLETE' and len(attempts)==1)
     finally:release.set();operations.write=original
     # Incomplete copy is durable UNKNOWN, never replayed.
     def fail(fd,name,data):
      if name=='hub.py':raise OSError('synthetic interrupted write')
      return original(fd,name,data)
     operations.write=fail
     try:_,failed=await call('ems_admin_solaredge_prepare',INCOMPLETE)
     finally:operations.write=original
     check('interrupted_copy_unknown',failed['status']=='UNKNOWN')
     _,failed=await call('ems_admin_solaredge_prepare',INCOMPLETE);check('unknown_not_replayed',failed['status']=='UNKNOWN')
     check('source_files_unchanged',hashes()==before)
     # Corrupt only the isolated BACKUP, never the source.
     (CONFIG/'ems_prepare_backups'/ID/'original/hub.py').write_text('synthetic corrupted backup')
     _,bad=await call('ems_admin_solaredge_prepare_status',ID);check('corruption_detected',bad['status']=='UNKNOWN')
     check('zero_device_service_calls',device_calls==[])
    else:
     _,a=await call('ems_admin_solaredge_prepare_status',ID);check('restart_preserves_integrity_failure',a['status']=='UNKNOWN')
     _,a=await call('ems_admin_solaredge_prepare_status',DISCONNECT);check('restart_existing_copy_integrity',a['status']=='COMPLETE')
     _,a=await call('ems_admin_solaredge_prepare',INCOMPLETE);check('restart_no_replay_unknown',a['status']=='UNKNOWN')
  evidence=json.dumps(dict(phase=phase,status='PASS',checks=checks,scope='Real HA2026.10.0/Python3.14 HTTP MCP and OIDC RS256 access-token validation; no browser consent/authorization-code UI or production Nabu Casa'),indent=2)
  assert not any(token in evidence for token in tokens)
  (OUT/(phase+'.json')).write_text(evidence)
 finally:
  if hass is not None:await hass.async_stop()

if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 else:
  try:asyncio.run(main(sys.argv[1]))
  except Exception:
   (OUT/(sys.argv[1]+'-failure.txt')).write_text(traceback.format_exc());print(traceback.format_exc(),flush=True);raise
