"""Watchdog-owned OAuth credentials only; no registration or issuance on import.
Provisioning requires separately approved new OAuth client/admin consent.
JWT metadata checks below are NOT signature verification: real MCP is verifier.
"""
import base64
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

class CredentialRefused(ValueError):
    pass

def inspect(value, now=None, minimum_remaining=1800):
    now = time.time() if now is None else now
    if not isinstance(value,dict) or set(value) != {'access_token','public_origin','client_id','client_name'}:
        raise CredentialRefused('DEDICATED_CREDENTIAL_REQUIRED')
    if not all(isinstance(v,str) for v in value.values()):
        raise CredentialRefused('STRING_FIELDS_REQUIRED')
    if not re.fullmatch(r'ems-watchdog-[0-9a-f]{32}', value['client_name']):
        raise CredentialRefused('DEDICATED_CLIENT_REQUIRED')
    if not isinstance(value['client_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{20,128}',value['client_id']):
        raise CredentialRefused('INVALID_CLIENT_ID')
    origin = urlsplit(value['public_origin'])
    if origin.scheme!='https' or not origin.hostname or origin.username or origin.password or origin.path not in ('','/') or origin.query or origin.fragment:
        raise CredentialRefused('HTTPS_ORIGIN_REQUIRED')
    try:
        token=value['access_token']
        if not isinstance(token,str) or '\n' in token or '\r' in token or len(token)>12000:
            raise ValueError()
        head,payload,signature=token.split('.')
        h=json.loads(base64.urlsafe_b64decode(head+'='*(-len(head)%4)))
        p=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
        if h.get('alg')!='RS256' or not signature or p.get('token_use')!='access':raise ValueError()
        if p.get('aud')!=value['client_id'] or 'azp' in p:raise ValueError()
        if p.get('iss')!=value['public_origin'].rstrip('/')+'/oidc':raise ValueError()
        if p.get('scope')!='openid':raise ValueError()
        iat,exp=p['iat'],p['exp']
        if isinstance(iat,bool) or isinstance(exp,bool) or not isinstance(iat,(int,float)) or not isinstance(exp,(int,float)):raise ValueError()
        if iat>now+60 or exp-iat>3600 or exp-iat<=0 or exp-now<minimum_remaining:raise ValueError()
    except (KeyError,TypeError,ValueError):
        raise CredentialRefused('INVALID_OR_INSUFFICIENT_LIFETIME') from None
    return origin.netloc, exp

def persist(backup, response, registration, public_origin, *, approved=False, now=None):
    # Registration must be the NEW client response from the approved local flow.
    # Never accept another client's token or store refresh/id/client-secret here.
    if approved is not True:raise CredentialRefused('EXPLICIT_NEW_ADMIN_CLIENT_APPROVAL_REQUIRED')
    value={k:registration[k] for k in ('client_id','client_name')}
    value.update(access_token=response['access_token'],public_origin=public_origin)
    inspect(value,now)
    backup=Path(backup)
    if backup.is_symlink() or backup.stat().st_mode & 0o077 or backup.stat().st_uid!=os.geteuid():
        raise CredentialRefused('PRIVATE_DIRECTORY_REQUIRED')
    target=backup/'oauth-probe.json'
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
    fd=os.open(backup,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return target

def finalize(health, backup):
    """Once only: revoke OUR approved client, verify denial, unlink local copy.
    No retry after ambiguous revoke. Failure leaves JWT expiry as final bound.
    Requires actual Core API; impossible while Core/Supervisor remains down.
    """
    value=health.credentials
    try:
        inspect(value,minimum_remaining=0)
        status,_=health.request('http://supervisor/core/api/services/oidc_provider/revoke_client',
          {'client_id':value['client_id']}, {'Authorization':'Bearer '+health.supervisor_token,'Content-Type':'application/json'})
        if status!=200:
            outcome='REVOCATION_UNCONFIRMED_EXPIRY_PENDING'
        else:
            status,_=health.rpc('tools/list',value['access_token'],91)
            outcome='REVOKED_AND_TOKEN_DENIED' if status==401 else 'REVOCATION_UNCONFIRMED_EXPIRY_PENDING'
    except Exception:
        outcome='REVOCATION_UNCONFIRMED_EXPIRY_PENDING'
    path=Path(backup)/'oauth-probe.json'
    try:
        # Never unlink a replacement credential supplied by another operation.
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:existing=json.load(stream)
        if existing!=value:return 'LOCAL_CREDENTIAL_CHANGED_OPERATOR_REQUIRED'
        path.unlink()
        fd=os.open(backup,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    except (OSError,ValueError):
        return 'LOCAL_CREDENTIAL_CLEANUP_UNCONFIRMED'
    return outcome
