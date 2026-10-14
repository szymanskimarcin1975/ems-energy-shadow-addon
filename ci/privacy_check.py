"""Fail publication checks without printing sensitive matches or file contents."""
import hashlib,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
for folder in (root/'ems_shadow',root/'ci'):
 for p in folder.rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts:continue
  if p.suffix in ('.sqlite','.db','.log') or p.name.endswith(('-wal','-shm')):raise SystemExit('forbidden_data_file')
  if p.suffix not in ('.py','.md','.yaml','.yml','.json','.test') and p.name!='Dockerfile':continue
  text=p.read_text()
  patterns=(r'0x[0-9a-fA-F]{16}',r'(?:sensor|binary_sensor)\.(?!example_)[a-z][a-z0-9_]+',r'https?://[^\s]+\.ui\.nabu\.casa',r'-{5}BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-{5}',r'gh[pousr]_[A-Za-z0-9]{20,}',r'github_pat_[A-Za-z0-9_]{20,}',r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
  if any(re.search(pattern,text) for pattern in patterns):raise SystemExit('privacy_pattern_detected')
manifest=json.loads((root/'ci/stdin/observer_manifest.json').read_text())
for name,digest in manifest.items():
 if hashlib.sha256((root/'ems_shadow/app'/name).read_bytes()).hexdigest()!=digest:raise SystemExit('observer_code_changed')
print('privacy_patterns_clear; observer_hashes_match; manual_review_still_required')
