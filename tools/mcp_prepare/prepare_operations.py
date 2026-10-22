"""Bounded code-only backup. No shell, network, HA service or SQLite access."""
from contextlib import ExitStack
import hashlib
import json
import os
import re
import stat
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath

EXPECTED={'hub.py':'512fe7b3f7d58735f210fd7ed6f87c15b3acc6f4c1c4d3a55070d9f9bdefa6c4',
          'manifest.json':'23ba7cc928c79dfaea183b568bfed04160ab4890d28a415071327cbe83b9bdcc'}
MAX_FILE=2*1024*1024
MAX_TOTAL=32*1024*1024
FLAGS=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW

def directory(stack,parent,name,create=False):
    if create:
        try:os.mkdir(name,mode=0o700,dir_fd=parent)
        except FileExistsError:pass
    fd=os.open(name,FLAGS,dir_fd=parent)
    stack.callback(os.close,fd)
    return fd

def read(fd,name):
    handle=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
    with os.fdopen(handle,'rb') as file:
        a=os.fstat(file.fileno())
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_size>MAX_FILE:raise ValueError('UNSAFE_FILE')
        data=file.read(MAX_FILE+1);b=os.fstat(file.fileno())
        if len(data)>MAX_FILE or (a.st_ino,a.st_size,a.st_mtime_ns)!=(b.st_ino,b.st_size,b.st_mtime_ns):raise ValueError('SOURCE_CHANGED')
        return data

def snapshot(fd,prefix='',depth=0,budget=None):
    if budget is None:budget={'nodes':0,'deadline':time.monotonic()+10}
    if depth>8:raise ValueError('TREE_TOO_DEEP')
    result={}
    for name in sorted(os.listdir(fd)):
        budget['nodes']+=1
        if budget['nodes']>1024 or time.monotonic()>budget['deadline']:raise ValueError('BACKUP_WORK_LIMIT')
        if name=='__pycache__':continue
        if name.startswith('.') or '/' in name:raise ValueError('UNEXPECTED_COMPONENT_FILE')
        s=os.stat(name,dir_fd=fd,follow_symlinks=False)
        if stat.S_ISDIR(s.st_mode):
            with ExitStack() as stack:result.update(snapshot(directory(stack,fd,name),prefix+name+'/',depth+1,budget))
        elif stat.S_ISREG(s.st_mode) and PurePosixPath(name).suffix in ('.py','.json','.yaml','.yml','.md','.txt'):
            result[prefix+name]=read(fd,name)
        else:raise ValueError('UNSAFE_COMPONENT_TREE')
        if len(result)>512 or sum(map(len,result.values()))>MAX_TOTAL:raise ValueError('BACKUP_SIZE_LIMIT')
    return result

def write(fd,name,data):
    handle=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
    with os.fdopen(handle,'wb') as file:file.write(data);file.flush();os.fsync(file.fileno())

def relative(stack,fd,path,create=False):
    parts=PurePosixPath(path).parts
    if not parts or any(p in ('.','..','/') for p in parts) or path.startswith('/'):raise ValueError('UNSAFE_MANIFEST_PATH')
    for part in parts[:-1]:fd=directory(stack,fd,part,create)
    return fd,parts[-1]

def verify(op):
    try:
        raw=read(op,'manifest.json');m=json.loads(raw)
        if m['state']!='COMPLETE':raise ValueError('INCOMPLETE')
        files=m['sha256']
        if not isinstance(files,dict) or not 0<len(files)<=512:raise ValueError('INVALID_MANIFEST')
        with ExitStack() as stack:
            original=directory(stack,op,'original')
            for path,h in files.items():
                with ExitStack() as child:
                    parent,name=relative(child,original,path)
                    if hashlib.sha256(read(parent,name)).hexdigest()!=h:raise ValueError('BACKUP_HASH_MISMATCH')
        return dict(status='COMPLETE',file_count=len(files),sha256=files,
                    manifest_sha256=hashlib.sha256(raw).hexdigest(),backup_relative_path='ems_prepare_backups/'+m['operation_id'],
                    source_unchanged_during_prepare=True,independent_off_host_copy=False,restoration_executed=False)
    except (OSError,ValueError,KeyError,TypeError):
        return dict(status='UNKNOWN',reason='BACKUP_INCOMPLETE_OR_INTEGRITY_UNCONFIRMED',automatic_retry=False)

def run(config_root,operation_id,action,expected=None):
    if not isinstance(operation_id,str) or not re.fullmatch('[a-f0-9]{32}',operation_id):raise ValueError('INVALID_OPERATION_ID')
    if action not in ('prepare','status'):raise ValueError('OPERATION_NOT_ALLOWED')
    with ExitStack() as stack:
        root=os.open(config_root,FLAGS);stack.callback(os.close,root)
        if action=='status':
            try:
                base=directory(stack,root,'ems_prepare_backups');op=directory(stack,base,operation_id)
            except FileNotFoundError:return dict(status='NOT_FOUND',automatic_retry=False)
            return verify(op)
        src=directory(stack,directory(stack,root,'custom_components'),'solaredge_modbus_multi')
        data=snapshot(src)
        for name,h in (EXPECTED if expected is None else expected).items():
            if name not in data or hashlib.sha256(data[name]).hexdigest()!=h:return dict(status='REJECTED',reason='INSTALLED_SOURCE_NOT_REVIEWED_404',backup_created=False)
        if data!=snapshot(src):return dict(status='REJECTED',reason='SOURCE_CHANGED',backup_created=False)
        base=directory(stack,root,'ems_prepare_backups',True)
        permissions=os.fstat(base)
        if permissions.st_uid!=os.geteuid() or permissions.st_mode&0o077:raise ValueError('UNSAFE_BACKUP_ROOT_PERMISSIONS')
        try:os.mkdir(operation_id,mode=0o700,dir_fd=base)
        except FileExistsError:return verify(directory(stack,base,operation_id))
        op=directory(stack,base,operation_id)
        try:
            write(op,'intent.json',json.dumps(dict(state='IN_PROGRESS',operation_id=operation_id,at=datetime.now(timezone.utc).isoformat())).encode())
            original=directory(stack,op,'original',True)
            for path,content in data.items():
                with ExitStack() as child:
                    parent,name=relative(child,original,path,True);write(parent,name,content);os.fsync(parent)
            if data!=snapshot(src):raise ValueError('SOURCE_CHANGED_DURING_BACKUP')
            manifest=dict(state='COMPLETE',operation_id=operation_id,at=datetime.now(timezone.utc).isoformat(),sha256={p:hashlib.sha256(b).hexdigest() for p,b in data.items()})
            write(op,'manifest.json',json.dumps(manifest,sort_keys=True).encode());os.fsync(op);os.fsync(base)
            return verify(op)
        except (OSError,ValueError):return dict(status='UNKNOWN',reason='PREPARE_UNCONFIRMED_INSPECT_SAME_ID',automatic_retry=False)
