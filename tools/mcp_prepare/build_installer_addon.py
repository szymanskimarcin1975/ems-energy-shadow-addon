"""Build reviewed local-addon source plus verified watchdog payload; no install."""
import hashlib,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def build(payload,output):
 files={str(p.relative_to(ROOT)):p.read_bytes() for p in (ROOT/'mcp_installer').iterdir() if p.is_file()}
 files['mcp-installer-package.zip']=payload.read_bytes()
 files['SHA256SUMS']=''.join(hashlib.sha256(v).hexdigest()+'  '+k+'\n' for k,v in sorted(files.items())).encode()
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for name,value in sorted(files.items()):z.writestr(name,value)
 print('PAYLOAD_SHA256 '+hashlib.sha256(payload.read_bytes()).hexdigest())
 print('DELIVERY_SHA256 '+hashlib.sha256(output.read_bytes()).hexdigest())
if __name__=='__main__':build(Path(sys.argv[1]),Path(sys.argv[2]))
