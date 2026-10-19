"""Build current proposed deployment: manual ACK, NO extra OAuth client/files."""
import hashlib
from pathlib import Path
import shutil
import sys
import zipfile
ROOT=Path(__file__).parent

def build(package,out):
 out.mkdir(parents=True,exist_ok=False)
 for name in ('mcp-1.18.0-ems.2-prepare.zip','mcp-1.18.0-ems.1-code-recovery.zip','BASE_SHA256SUMS','CANDIDATE_SHA256SUMS','BASE_FILELIST'):
  shutil.copyfile(package/name,out/name)
 for name in ('deployment_core.py','manual_ack_watchdog.py','manual-ack-launch.sh','ack.sh','MANUAL_ACK_PL.md'):
  shutil.copyfile(ROOT/name,out/name)
 shutil.copyfile(ROOT/'prepare_operations.py',out/'diagnostic_verifier.py')
 (out/'install.sh').write_text('#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\n[ "${1:-}" = apply ] || { echo USE_VERIFIED_PREPARE_AND_MANUAL_ACK; exit 1; }\nexec sh manual-ack-launch.sh "${2:-}"\n')
 (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file()))
 with zipfile.ZipFile(out.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(out.iterdir()):z.write(p,out.name+'/'+p.name)

if __name__=='__main__':build(Path(sys.argv[1]),Path(sys.argv[2]))
