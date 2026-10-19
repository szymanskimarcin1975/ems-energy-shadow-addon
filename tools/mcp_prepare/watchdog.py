"""One-shot CODE-only deployment supervisor. No device services or data restore.

Requires an independently provisioned OAuth probe. Never mints/reuses ChatGPT
credentials, changes OAuth configuration, or accepts an unauthenticated 200.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
import urllib.request
import urllib.error
import zipfile

BACK = Path('/config/mcp_prepare_ems2_recovery')
SRC = Path('/config/custom_components/mcp_server_http_transport')
OLD_TOOLS = {'ems_admin_options_inspect', 'get_state', 'call_service'}
NEW_TOOLS = {'ems_admin_solaredge_prepare', 'ems_admin_solaredge_prepare_status'}

class Blocked(Exception):
    pass

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def manifest(path):
    return {str(Path(line[66:])): line[:64] for line in path.read_text().splitlines() if line}

def verify(root, sums, exact=True):
    expected = manifest(sums)
    for name, sha in expected.items():
        p = Path(name)
        if p.is_absolute() or '..' in p.parts:
            raise Blocked('UNSAFE_MANIFEST')
        target = root / p
        if any(v.is_symlink() for v in [root, *target.parents, target]):
            raise Blocked('SYMLINK_REFUSED')
        if not target.is_file() or digest(target) != sha:
            raise Blocked('HASH_MISMATCH')
    actual = {str(p.relative_to(root)) for p in root.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts}
    if exact and actual != set(expected):
        raise Blocked('FILE_INVENTORY_MISMATCH')

def private_json(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o077 or st.st_size > 16384:
            raise Blocked('PRIVATE_CREDENTIAL_FILE_REQUIRED')
        value = json.loads(os.read(fd, 16385))
    finally:
        os.close(fd)
    from credential_lifecycle import inspect
    host, _ = inspect(value)
    return value, host

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Blocked('REDIRECT_REFUSED')

class Health:
    def __init__(self, backup):
        self.credentials, self.host = private_json(backup / 'oauth-probe.json')
        self.supervisor_token = os.environ.get('SUPERVISOR_TOKEN')
        if not self.supervisor_token:
            raise Blocked('SUPERVISOR_CREDENTIAL_UNAVAILABLE')
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, url, body=None, headers=None):
        req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers or {})
        try:
            with self.http.open(req, timeout=5) as response:
                data = response.read(1048577)
                if len(data) > 1048576:
                    raise Blocked('RESPONSE_TOO_LARGE')
                return response.status, json.loads(data)
        except urllib.error.HTTPError as error:
            return error.code, {}

    def rpc(self, method, token, rid, params=None):
        return self.request('http://homeassistant:8123/api/mcp_http',
            {'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params or {}},
            {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
             'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': self.host})

    def __call__(self, candidate):
        # API proxy authentication is distinct from OAuth MCP authentication.
        status, body = self.request('http://supervisor/core/api/', headers={'Authorization': 'Bearer ' + self.supervisor_token})
        if status != 200 or body.get('message') != 'API running.':
            return False
        # A public or token-ignoring MCP endpoint is not a successful OAuth check.
        status, _ = self.rpc('tools/list', 'deliberately-invalid-probe', 11)
        if status != 401:
            return False
        token = self.credentials['access_token']
        status, body = self.rpc('initialize', token, 12)
        result = body.get('result', {})
        if status != 200 or body.get('id') != 12 or 'error' in body or not result.get('protocolVersion') or not isinstance(result.get('capabilities'), dict):
            return False
        status, body = self.rpc('tools/list', token, 13)
        if status != 200 or body.get('id') != 13 or 'error' in body:
            return False
        names = {t.get('name') for t in body.get('result', {}).get('tools', [])}
        if not (OLD_TOOLS.issubset(names) and (NEW_TOOLS.issubset(names) if candidate else not NEW_TOOLS.intersection(names))):
            return False
        status, body = self.rpc('tools/call', token, 14, {'name': 'ems_admin_options_inspect',
            'arguments': {'entry_id': '01M39WCJ1Y5FQTXXR2FZJBV76K'}})
        result = body.get('result', {})
        if status != 200 or body.get('id') != 14 or 'error' in body or result.get('isError'):
            return False
        # Valid admin-only inspect response, not merely successful tools/list.
        contents = result.get('content', [])
        if not contents or contents[0].get('type') != 'text':
            return False
        inspected = json.loads(contents[0]['text'])
        return inspected.get('status') == 'READ_ONLY' and inspected.get('entry_id') == '01M39WCJ1Y5FQTXXR2FZJBV76K'

class Deployment:
    def __init__(self, root, backup, source, health, core=None, clock=time.monotonic, pause=time.sleep, deadline=300):
        self.root, self.backup, self.source = root, backup, source
        self.health, self.core = health, core or self.run_core
        self.clock, self.pause, self.deadline = clock, pause, deadline
        self.state_path = backup / 'watchdog-state.json'
        self.log_path = backup / 'watchdog-events.jsonl'

    def event(self, phase):
        # Strict allowlisted text only; never include exception text or HTTP bodies.
        record = {'phase': phase, 'time_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        data = json.dumps(record).encode() + b'\n'
        fd = os.open(self.log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, data); os.fsync(fd)
        finally:
            os.close(fd)
        tmp = self.backup / 'watchdog-state.tmp'
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, self.state_path)
        dfd = os.open(self.backup, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    @staticmethod
    def run_core(action):
        try:
            r = subprocess.run(['ha', 'core', action], stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        except subprocess.TimeoutExpired:
            # Unknown Supervisor job completion: do not race it with file swaps.
            raise Blocked('CORE_OPERATION_UNKNOWN') from None
        return r.returncode == 0

    def wait_health(self, candidate):
        until = self.clock() + self.deadline
        while self.clock() < until:
            try:
                if self.core('info') and self.health(candidate):
                    return True
            except (OSError, ValueError, Blocked, urllib.error.URLError):
                pass
            self.pause(5)
        return False

    def prepare_stage(self, candidate):
        stage = self.backup / ('watchdog-candidate' if candidate else 'watchdog-original')
        if stage.exists():
            raise Blocked('EXISTING_STAGE_REFUSED')
        stage.mkdir(mode=0o700)
        if candidate:
            with zipfile.ZipFile(self.root / 'mcp-1.18.0-ems.2-prepare.zip') as archive:
                for item in archive.infolist():
                    p = Path(item.filename)
                    if p.is_absolute() or '..' in p.parts or stat.S_ISLNK(item.external_attr >> 16):
                        raise Blocked('UNSAFE_ARCHIVE')
                archive.extractall(stage)
            component = stage / 'custom_components/mcp_server_http_transport'
            verify(component, self.root / 'CANDIDATE_SHA256SUMS')
            return component
        shutil.copytree(self.backup / 'component', stage / 'component')
        verify(stage / 'component', self.root / 'BASE_SHA256SUMS')
        return stage / 'component'

    def swap_stopped(self, replacement, name):
        if not self.core('stop'):
            raise Blocked('CORE_STOP_NOT_CONFIRMED')
        preserved = self.backup / name
        if preserved.exists():
            raise Blocked('PRESERVED_PATH_EXISTS')
        self.source.rename(preserved)
        try:
            replacement.rename(self.source)
        except OSError:
            preserved.rename(self.source)
            raise Blocked('SWAP_FAILED') from None

    def execute(self):
        self.backup.mkdir(exist_ok=True)
        if self.backup.is_symlink() or self.backup.stat().st_uid != os.geteuid() or self.backup.stat().st_mode & 0o077:
            raise Blocked('UNSAFE_RECOVERY_DIRECTORY')
        fd = os.open(self.backup / 'deploy.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.state_path.exists():
                raise Blocked('ONE_SHOT_ALREADY_USED_REVIEW_STATE')
            verify(self.root, self.root / 'SHA256SUMS', exact=False)
            if not (self.backup / 'PREPARED').is_file():
                raise Blocked('PREPARE_REQUIRED')
            verify(self.backup / 'component', self.root / 'BASE_SHA256SUMS')
            verify(self.source, self.root / 'BASE_SHA256SUMS')
            # Fail before any Core stop if independent authenticated check unavailable.
            if not self.health(False):
                raise Blocked('AUTHENTICATED_BASELINE_REQUIRED')
            self.event('ARMED')
            original = self.prepare_stage(False)
            candidate = self.prepare_stage(True)
            if not self.core('check'):
                self.event('CONFIG_CHECK_FAILED_NO_CHANGE'); return False
            self.event('INSTALLING')
            try:
                self.swap_stopped(candidate, 'watchdog-pre-install')
                started = self.core('start')
                if started and self.wait_health(True):
                    self.event('SUCCESS'); return True
            except Blocked:
                # Unknown core job / failed stop requires manual reconciliation,
                # never an automatic simultaneous rollback.
                self.event('UNKNOWN_REQUIRES_OPERATOR'); return False
            self.event('ROLLBACK_ONCE')
            try:
                verify(self.backup / 'component', self.root / 'BASE_SHA256SUMS')
                verify(original, self.root / 'BASE_SHA256SUMS')
                self.swap_stopped(original, 'watchdog-failed-candidate')
                started = self.core('start')
                ok = started and self.wait_health(False)
            except (OSError, Blocked):
                ok = False
            self.event('ROLLED_BACK' if ok else 'RECOVERY_FAILED_OPERATOR_REQUIRED')
            return False
        finally:
            os.close(fd)


def main():
    import sys
    preflight = sys.argv[1:] == ['preflight']
    if not preflight and sys.argv[1:] != ['deploy', 'CONFIRM_CORE_RESTART']:
        print('EXPLICIT_RESTART_CONFIRMATION_REQUIRED'); return 2
    root = Path(__file__).resolve().parent
    try:
        probe = Health(BACK)
        if preflight:
            ok = probe(False)
            print('AUTHENTICATED_BASELINE_PASS' if ok else 'AUTHENTICATED_BASELINE_FAIL')
            return 0 if ok else 1
        deployment = Deployment(root, BACK, SRC, probe)
        ok = deployment.execute()
        # This runs only after the controller releases its Core/code lock and
        # reaches a terminal state. No credential revoke during health/rollback.
        from credential_lifecycle import finalize
        cleanup = finalize(probe, BACK)
        print(cleanup)
        if cleanup != 'REVOKED_AND_TOKEN_DENIED':
            ok = False
    except (OSError, ValueError, Blocked, BlockingIOError):
        print('WATCHDOG_BLOCKED_NO_SECRET_DETAILS'); return 1
    print('WATCHDOG_SUCCESS' if ok else 'WATCHDOG_NOT_ACCEPTED_CHECK_PRIVATE_EVENT_LOG')
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
