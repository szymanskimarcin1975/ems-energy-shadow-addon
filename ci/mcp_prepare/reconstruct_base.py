"""Reproduce already-reviewed ems.1; package builder verifies every SHA256."""
import json,shutil,sys
from pathlib import Path
root=Path(__file__).parent
source=Path(sys.argv[1]);dest=Path(sys.argv[2])
shutil.copytree(source,dest)
p=dest/'manifest.json';m=json.loads(p.read_text());m['version']='1.18.0+ems.1';p.write_text(json.dumps(m,indent=2)+'\n')
p=dest/'http.py';s=p.read_text().replace('from .completions import complete','from .admin_context import verified_identity\nfrom .completions import complete')
a='            response_data = await self._handle_message(body)'
b='            identity_token = verified_identity.set(token_payload)\n            try:\n                response_data = await self._handle_message(body)\n            finally:\n                verified_identity.reset(identity_token)'
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s)
p=dest/'tools/__init__.py';s=p.read_text().replace('    appdaemon_files,','    ems_admin,  # noqa: F401\n    appdaemon_files,',1);p.write_text(s)
for n in ['admin_context.py','admin_operations.py']:shutil.copy2(root/'base_extension'/n,dest/n)
shutil.copy2(root/'base_extension/ems_admin.py',dest/'tools/ems_admin.py')
