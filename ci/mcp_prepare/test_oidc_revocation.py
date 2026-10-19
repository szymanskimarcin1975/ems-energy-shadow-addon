"""Actual pinned OIDC 1.5.2 JWT verifier + RSA, without a running HA server.
HA core type is a stub; this is not a full HTTP/OAuth consent integration test.
"""
import hashlib
import importlib.util
from pathlib import Path
import sys
import time
import types
import unittest
from types import SimpleNamespace
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

source=Path(sys.argv.pop(1))
raw=source.read_bytes()
assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='1e3e18e00ec1ee8281292912420f1518408337c3'
try:import homeassistant.core
except ImportError:
 package=types.ModuleType('homeassistant');core=types.ModuleType('homeassistant.core');core.HomeAssistant=type('HomeAssistant',(),{});sys.modules['homeassistant']=package;sys.modules['homeassistant.core']=core
spec=importlib.util.spec_from_file_location('oidc_reference',source);oidc=importlib.util.module_from_spec(spec);spec.loader.exec_module(oidc)
KEY=rsa.generate_private_key(public_exponent=65537,key_size=2048)

class Revocation(unittest.TestCase):
 def setUp(self):self.hass=SimpleNamespace(data={'oidc_provider':{'jwt_public_key':KEY.public_key(),'clients':{'synthetic-client':{}}}})
 def token(self,**changes):
  now=int(time.time());p=dict(sub='synthetic-admin',iat=now,exp=now+3600,iss='https://synthetic.invalid/oidc',aud='synthetic-client',scope='openid',token_use='access');p.update(changes)
  return jwt.encode(p,KEY,algorithm='RS256')
 def verify(self,token):return oidc.validate_access_token(self.hass,token,'https://synthetic.invalid','https://synthetic.invalid/api/mcp_http')
 def test_client_bound_accepted(self):self.assertIsNotNone(self.verify(self.token()))
 def test_client_revocation_denies_same_signed_token(self):
  t=self.token();self.assertIsNotNone(self.verify(t));self.hass.data['oidc_provider']['clients'].clear();self.assertIsNone(self.verify(t))
 def test_resource_bound_token_does_not_revoke_with_client(self):
  t=self.token(aud='https://synthetic.invalid/api/mcp_http',azp='synthetic-client');self.hass.data['oidc_provider']['clients'].clear();self.assertIsNotNone(self.verify(t))
 def test_expired_denied(self):self.assertIsNone(self.verify(self.token(exp=int(time.time())-1)))
 def test_wrong_issuer_denied(self):self.assertIsNone(self.verify(self.token(iss='https://other.invalid/oidc')))
 def test_wrong_signature_denied(self):
  t=self.token();self.hass.data['oidc_provider']['jwt_public_key']=rsa.generate_private_key(public_exponent=65537,key_size=2048).public_key();self.assertIsNone(self.verify(t))

if __name__=='__main__':unittest.main(verbosity=2)
