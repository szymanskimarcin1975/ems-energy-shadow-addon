"""Synthetic credential persistence/lifecycle only. Never registers a real client."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/mcp_prepare'))
import credential_lifecycle as c

def token(**changes):
 now=int(time.time());body=dict(sub='synthetic-admin',iat=now,exp=now+3600,iss='https://synthetic.invalid/oidc',aud='A'*32,scope='openid',token_use='access');body.update(changes)
 enc=lambda x:base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip('=')
 return enc({'alg':'RS256'})+'.'+enc(body)+'.SYNTHETIC_NOT_A_VALID_SIGNATURE'

def value(**claims):return dict(access_token=token(**claims),public_origin='https://synthetic.invalid',client_id='A'*32,client_name='ems-watchdog-'+'a'*32)

class Credentials(unittest.TestCase):
 def test_expected_metadata(self):self.assertEqual(c.inspect(value())[0],'synthetic.invalid')
 def test_resource_audience_refused_because_not_client_revocable(self):
  with self.assertRaises(c.CredentialRefused):c.inspect(value(aud='https://synthetic.invalid/api/mcp_http',azp='A'*32))
 def test_expired_refused(self):
  with self.assertRaises(c.CredentialRefused):c.inspect(value(exp=int(time.time())-1))
 def test_insufficient_remaining_refused(self):
  with self.assertRaises(c.CredentialRefused):c.inspect(value(exp=int(time.time())+100))
 def test_excessive_lifetime_refused(self):
  with self.assertRaises(c.CredentialRefused):c.inspect(value(exp=int(time.time())+7200))
 def test_id_token_refused(self):
  with self.assertRaises(c.CredentialRefused):c.inspect(value(token_use='id'))
 def test_other_scopes_refused(self):
  with self.assertRaises(c.CredentialRefused):c.inspect(value(scope='openid profile groups'))
 def test_existing_unrelated_client_name_refused(self):
  v=value();v['client_name']='ChatGPT'
  with self.assertRaises(c.CredentialRefused):c.inspect(v)
 def test_persist_requires_approval_and_drops_refresh_secrets(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);reg={k:value()[k] for k in ('client_id','client_name')};response={'access_token':value()['access_token'],'refresh_token':'DO_NOT_STORE_REFRESH','id_token':'DO_NOT_STORE_ID','client_secret':'DO_NOT_STORE_SECRET'}
   with self.assertRaises(c.CredentialRefused):c.persist(p,response,reg,'https://synthetic.invalid')
   target=c.persist(p,response,reg,'https://synthetic.invalid',approved=True)
   text=target.read_text();self.assertNotIn('DO_NOT_STORE',text);self.assertEqual(target.stat().st_mode & 0o777,0o600)
   with self.assertRaises(FileExistsError):c.persist(p,response,reg,'https://synthetic.invalid',approved=True)
 def finalize(self,status=200,denial=401,fail=False):
  class Fake:
   credentials=value();supervisor_token='SYNTHETIC';calls=[]
   def request(self,url,body,headers):
    self.calls.append((url,body))
    if fail:raise TimeoutError()
    return status,[]
   def rpc(self,*args):return denial,{}
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'oauth-probe.json').write_text(json.dumps(Fake.credentials));f=Fake();result=c.finalize(f,p)
   self.assertFalse((p/'oauth-probe.json').exists());self.assertEqual(len(f.calls),1);self.assertEqual(f.calls[0][1],{'client_id':'A'*32})
   return result
 def test_revoke_and_confirm_401(self):self.assertEqual(self.finalize(),'REVOKED_AND_TOKEN_DENIED')
 def test_200_after_revoke_is_not_success(self):self.assertEqual(self.finalize(denial=200),'REVOCATION_UNCONFIRMED_EXPIRY_PENDING')
 def test_failed_revoke_no_retry(self):self.assertEqual(self.finalize(status=503),'REVOCATION_UNCONFIRMED_EXPIRY_PENDING')
 def test_disconnection_during_revoke_no_retry(self):self.assertEqual(self.finalize(fail=True),'REVOCATION_UNCONFIRMED_EXPIRY_PENDING')

if __name__=='__main__':unittest.main(verbosity=2)
