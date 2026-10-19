const assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const auth=require('../../tools/mcp_prepare/watchdog-auth.js');
async function main(){
 const entries=new Map(),requests=[],navigation=[];let saved;
 const e={href:'https://synthetic.invalid/local/ems-watchdog-auth.html',storage:{getItem:k=>entries.get(k),setItem:(k,v)=>entries.set(k,v),removeItem:k=>entries.delete(k)},crypto:webcrypto,navigate:p=>navigation.push(p),clearQuery:p=>{},download:v=>saved=v,fetch:async(url,options)=>{
  requests.push({url,options});
  return {ok:true,json:async()=>url==='/oidc/register'?{client_id:'A'.repeat(32),client_secret:'SYNTHETIC_CLIENT_SECRET',client_name:JSON.parse(options.body).client_name}:{token_type:'Bearer',access_token:'SYNTHETIC_ACCESS',refresh_token:'MUST_NOT_SAVE_REFRESH',id_token:'MUST_NOT_SAVE_ID',expires_in:3600}};
 }};
 await auth.begin(e);assert.equal(requests.length,1);
 const nav=new URL(navigation[0],'https://synthetic.invalid');assert.equal(nav.searchParams.get('scope'),'openid');assert.equal(nav.searchParams.get('code_challenge_method'),'S256');assert(!nav.searchParams.has('resource'));
 await assert.rejects(auth.begin(e));assert.equal(requests.length,1);
 e.href+='?code=SYNTHETIC_CODE&state='+nav.searchParams.get('state');await auth.finish(e);
 assert.equal(requests.length,2);assert.equal(saved.access_token,'SYNTHETIC_ACCESS');assert(!JSON.stringify(saved).includes('MUST_NOT_SAVE'));assert(!JSON.stringify(saved).includes('SYNTHETIC_CLIENT_SECRET'));assert.equal(entries.size,0);
 await assert.rejects(auth.finish(e));assert.equal(requests.length,2);
 // Failed exchange remains UNKNOWN and cannot be automatically repeated.
 navigation.length=0;requests.length=0;saved=null;e.href='https://synthetic.invalid/local/ems-watchdog-auth.html';await auth.begin(e);
 const state=new URL(navigation[0],'https://synthetic.invalid').searchParams.get('state');e.href+='?code=SYNTHETIC_CODE&state='+state;
 e.fetch=async()=>{throw Error('synthetic disconnect')};await assert.rejects(auth.finish(e));assert.equal(JSON.parse(entries.get(auth.KEY)).phase,'TOKEN_EXCHANGE_UNKNOWN');await assert.rejects(auth.finish(e));assert.equal(saved,null);
 console.log('AUTH_PAGE_PASS: PKCE/S256, explicit start, no resource/extra scopes, no refresh/id/client-secret export, no replay');
}
main().catch(()=>{console.error('AUTH_PAGE_FAIL_NO_SECRET_DETAILS');process.exitCode=1});
