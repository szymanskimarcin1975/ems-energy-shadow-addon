"""Shared code-only deployment primitives. No OAuth client or credentials."""
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
        raise Blocked("USE_MANUAL_ACK_CONTROLLER")
