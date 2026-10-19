/* Browser-only dedicated OAuth grant. No HA/ChatGPT/session-token extraction. */
(function (root) {
  'use strict';
  const KEY='ems-watchdog-pkce-once';
  const hex = a => Array.from(a,b=>b.toString(16).padStart(2,'0')).join('');
  const b64 = a => btoa(String.fromCharCode(...a)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  function callback(e) {
    const u=new URL(e.href);
    if(u.protocol!=='https:' || u.pathname!=='/local/ems-watchdog-auth.html') throw Error('APPROVED_HTTPS_CALLBACK_REQUIRED');
    return u.origin+u.pathname;
  }
  async function jsonRequest(e,path,body,form=false) {
    const response=await e.fetch(path,{method:'POST',credentials:'omit',redirect:'error',cache:'no-store',referrerPolicy:'no-referrer',
      headers:{'Content-Type':form?'application/x-www-form-urlencoded':'application/json'},
      body:form?new URLSearchParams(body):JSON.stringify(body),signal:AbortSignal.timeout(10000)});
    if(!response.ok) throw Error('OAUTH_REQUEST_NOT_CONFIRMED');
    return response.json();
  }
  async function begin(e) {
    const redirect=callback(e);
    if(e.storage.getItem(KEY))throw Error('EXISTING_OPERATION_DO_NOT_RETRY');
    const random=()=>hex(e.crypto.getRandomValues(new Uint8Array(32)));
    const p={state:random(),verifier:random(),client_name:'ems-watchdog-'+random().slice(0,32),redirect,created:Date.now(),phase:'REGISTRATION_UNKNOWN'};
    e.storage.setItem(KEY,JSON.stringify(p));
    const reg=await jsonRequest(e,'/oidc/register',{client_name:p.client_name,redirect_uris:[redirect],grant_types:['authorization_code'],response_types:['code'],token_endpoint_auth_method:'client_secret_post'});
    if(!reg.client_id || !reg.client_secret || reg.client_name!==p.client_name)throw Error('CLIENT_REGISTRATION_NOT_CONFIRMED');
    p.client_id=reg.client_id;p.client_secret=reg.client_secret;p.phase='AWAITING_OWNER_CONSENT';
    const challenge=b64(new Uint8Array(await e.crypto.subtle.digest('SHA-256',new TextEncoder().encode(p.verifier))));
    e.storage.setItem(KEY,JSON.stringify(p));
    const query=new URLSearchParams({response_type:'code',client_id:p.client_id,redirect_uri:redirect,scope:'openid',state:p.state,code_challenge:challenge,code_challenge_method:'S256'});
    // Deliberately omit resource: OIDC1.5.2 supports client-id audiences, which
    // can be invalidated by revoking just this dedicated client.
    e.navigate('/oidc/authorize?'+query);
  }
  async function finish(e) {
    const redirect=callback(e),u=new URL(e.href),stored=e.storage.getItem(KEY);
    e.clearQuery(redirect); // Remove authorization code from browser history.
    if(!stored)throw Error('NO_PENDING_OPERATION');
    const p=JSON.parse(stored);
    if(p.phase!=='AWAITING_OWNER_CONSENT' || p.redirect!==redirect || Date.now()-p.created>600000 || u.searchParams.get('state')!==p.state || !u.searchParams.get('code'))throw Error('CALLBACK_REFUSED_NO_RETRY');
    p.phase='TOKEN_EXCHANGE_UNKNOWN';e.storage.setItem(KEY,JSON.stringify(p));
    const response=await jsonRequest(e,'/oidc/token',{grant_type:'authorization_code',client_id:p.client_id,client_secret:p.client_secret,code:u.searchParams.get('code'),redirect_uri:redirect,code_verifier:p.verifier},true);
    if(response.token_type!=='Bearer' || typeof response.access_token!=='string' || response.expires_in>3600)throw Error('TOKEN_RESPONSE_REFUSED');
    const file={access_token:response.access_token,public_origin:new URL(redirect).origin,client_id:p.client_id,client_name:p.client_name};
    // Never retain response.refresh_token, response.id_token or client_secret.
    e.download(file);e.storage.removeItem(KEY);
    return true;
  }
  const api={begin,finish,KEY};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.EMSWatchdogAuthorization=api;
  if(typeof document!=='undefined') {
    const info=document.getElementById('status'),button=document.getElementById('approve');
    const env={href:location.href,storage:sessionStorage,crypto:root.crypto,fetch:root.fetch.bind(root),navigate:p=>location.assign(p),clearQuery:p=>history.replaceState(null,'',p),download:file=>{
      const blob=new Blob([JSON.stringify(file)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='oauth-probe.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }};
    button.onclick=()=>{button.disabled=true;begin(env).catch(()=>{info.textContent='Operacja niepotwierdzona. Nie ponawiaj. Nie pokazuj sekretów ani pamięci przeglądarki.';});};
    if(new URL(location.href).searchParams.has('code')) {
      button.disabled=true;finish(env).then(()=>{info.textContent='Plik pobrany. Umieść go prywatnie na HA; nie przesyłaj przez czat.';}).catch(()=>{info.textContent='Autoryzacja niepotwierdzona. Nie ponawiaj wymiany kodu.';});
    }
  }
})(typeof window!=='undefined'?window:globalThis);
