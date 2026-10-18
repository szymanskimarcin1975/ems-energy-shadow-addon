"""Build review artifacts OFFLINE; never install, reload, write HA or contact a device.

Requires pristine solaredge_modbus_multi v4.0.4 source supplied by the reviewer.
Output contains exact recovery source, a scoped companion patch, and SHA256SUMS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

HUB_SHA = '512fe7b3f7d58735f210fd7ed6f87c15b3acc6f4c1c4d3a55070d9f9bdefa6c4'
MANIFEST_SHA = '23ba7cc928c79dfaea183b568bfed04160ab4890d28a415071327cbe83b9bdcc'


def companion(source):
    """Entry allowlist; only StorageControl writes skip the integration retry loop."""
    for name, digest in [('hub.py', HUB_SHA), ('manifest.json', MANIFEST_SHA)]:
        if hashlib.sha256((source/name).read_bytes()).hexdigest() != digest:
            raise ValueError('UNREVIEWED_UPSTREAM_SOURCE:' + name)
    hub = (source/'hub.py').read_text()
    anchor = '    async def component_write(self, unit: int, component, field: str, value) -> None:'
    addition = '''    @property
    def ems_storage_single_attempt(self):
        """Explicit per-entry opt-in; no global retry constant mutation."""
        entries = self._yaml_config.get("ems_single_attempt_entries", [])
        return isinstance(entries, list) and self._entry_id in entries

'''
    assert hub.count(anchor) == 1
    hub = hub.replace(anchor, addition + anchor)
    old = '            await async_write_with_retry(component, field, value)'
    new = '''            # Only this entry's exact StorageControl component is single-attempt.
            storage = any(component is inv.storage_control_data for inv in self.inverters)
            if self.ems_storage_single_attempt and storage:
                await component.write(field, value)
            else:
                await async_write_with_retry(component, field, value)'''
    assert hub.count(old) == 1
    hub = hub.replace(old, new)
    manifest = json.loads((source/'manifest.json').read_text())
    manifest['version'] = '4.0.4+ems.1'
    manifest['requirements'] = ['modbus-connection[tmodbus]==4.10.0', 'tmodbus==0.6.1', 'awesomeversion>=25.5.0']
    return {'hub.py': hub.encode(), 'manifest.json': (json.dumps(manifest, indent=2)+'\n').encode()}


def archive(path, files):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as out:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 18, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            out.writestr(info, content)


def build(source, output, root):
    overrides = companion(source)
    output.mkdir(parents=True, exist_ok=False)
    originals = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    prefix = 'custom_components/solaredge_modbus_multi/'
    archive(output/'solaredge-4.0.4-recovery.zip', {prefix+k:v for k,v in originals.items()})
    archive(output/'solaredge-4.0.4-ems.1-review.zip', {prefix+k:v for k,v in (originals|overrides).items()})
    addon = root/'ems_shadow'
    archive(output/'ems-shadow-0.1.4-observation.41-source.zip',
        {'ems_shadow/'+p.relative_to(addon).as_posix():p.read_bytes()
         for p in addon.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'})
    gateway = root/'custom_components/ems_epoch_gateway'
    archive(output/'ems-epoch-gateway-0.2.0-rc.2.zip',
        {'custom_components/ems_epoch_gateway/'+p.relative_to(gateway).as_posix():p.read_bytes()
         for p in gateway.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    (output/'INSTALLATION-STATE.json').write_text(json.dumps(dict(
        addon_version='0.1.4-observation.41', gateway_version='0.2.0-rc.2',
        active_default=False, owner_transition_performed=False, installed=False,
        companion_entry_opt_in_required=True, device_commissioning_required=True), indent=2)+'\n')
    (output/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
        for p in sorted(output.iterdir()) if p.is_file()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--solaredge-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.solaredge_source, args.output, Path(__file__).resolve().parents[2])
