"""Offline only. Refuse any source deviation from reviewed MCP1.18.0+ems.1."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).parent

def build(source,output):
    expected=json.loads((ROOT/'base_sha256.json').read_text())
    files={}
    for p in source.rglob('*'):
        if p.is_symlink():raise ValueError('SYMLINK_SOURCE_REFUSED')
        if p.is_file() and '__pycache__' not in p.parts:
            files[p.relative_to(source).as_posix()]=p.read_bytes()
    if {n:hashlib.sha256(b).hexdigest() for n,b in files.items()}!=expected:raise ValueError('ACTUAL_MCP_SOURCE_NOT_REVIEWED_BASE')
    output.mkdir(exist_ok=False,parents=True)
    changed=dict(files)
    for n in ('prepare_operations.py','tools/ems_prepare.py'):changed[n]=(ROOT/Path(n).name).read_bytes()
    anchor='    ems_admin,  # noqa: F401\n'
    text=files['tools/__init__.py'].decode()
    if text.count(anchor)!=1:raise ValueError('MCP_REGISTRATION_ANCHOR_MISMATCH')
    changed['tools/__init__.py']=text.replace(anchor,anchor+'    ems_prepare,  # noqa: F401\n',1).encode()
    manifest=json.loads(files['manifest.json']);manifest['version']='1.18.0+ems.2'
    changed['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    for name,entries in [('mcp-1.18.0-ems.1-code-recovery.zip',files),('mcp-1.18.0-ems.2-prepare.zip',changed)]:
        with zipfile.ZipFile(output/name,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for path,data in sorted(entries.items()):
                info=zipfile.ZipInfo('custom_components/mcp_server_http_transport/'+path,(2026,10,19,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100600<<16;z.writestr(info,data)
    (output/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(output.glob('*.zip'))))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args();build(a.source,a.output)
