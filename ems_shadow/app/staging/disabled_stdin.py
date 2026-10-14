"""Bounded, export-disabled STDIN acknowledgments. No SQLite or controller imports."""
import collections,json,re,sys
from datetime import datetime,timezone
KEYS={'operation','request_id','ledger_id','expires_at','start','end'}
ID=re.compile(r'[a-zA-Z0-9_-]{8,64}\Z')
def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate_field')
        result[key]=value
    return result

def reject_constant(_):raise ValueError('invalid_json_number')
def decode(line):return json.loads(line,object_pairs_hook=unique,parse_constant=reject_constant)
def correlation(value):
    result=value.get('request_id') if isinstance(value,dict) else None
    return result if isinstance(result,str) and ID.fullmatch(result) else None

def validate(value,ledger,now):
    if not isinstance(value,dict) or set(value)!=KEYS:raise ValueError('invalid_fields')
    if value['operation']!='diagnostic_export':raise ValueError('invalid_operation')
    if correlation(value) is None:raise ValueError('invalid_request_id')
    if value['ledger_id']!=ledger:raise ValueError('ledger_mismatch')
    dates=[]
    for name in ('expires_at','start','end'):
        raw=value[name]
        if not isinstance(raw,str):raise ValueError('invalid_timestamp')
        try:stamp=datetime.fromisoformat(raw)
        except ValueError:raise ValueError('invalid_timestamp') from None
        if stamp.tzinfo is None:raise ValueError('timezone_required')
        dates.append(stamp.astimezone(timezone.utc))
    expires,start,end=dates
    if not 0<(expires-now).total_seconds()<=300:raise ValueError('invalid_expiry')
    if (end-start).total_seconds()!=86400 or end>now:raise ValueError('invalid_period')

def receive(stream,emit,ledger,clock=lambda:datetime.now(timezone.utc),capacity=1024):
    seen=collections.OrderedDict()
    while True:
        line=stream.readline(4097)
        if not line:return
        value=None;reason=None
        if len(line.encode('utf-8'))>4096:
            reason='message_too_large'
            while line and not line.endswith('\n'):line=stream.readline(4097)
        else:
            try:value=decode(line)
            except (ValueError,TypeError):reason='invalid_json'
            if not line.endswith('\n'):reason='incomplete_message'
        request_id=correlation(value)
        if reason is None:
            try:validate(value,ledger,clock())
            except ValueError as error:reason=str(error) # Only fixed local codes.
        repeated=False
        if reason is None:
            repeated=request_id in seen
            seen[request_id]=None;seen.move_to_end(request_id)
            if len(seen)>capacity:seen.popitem(last=False)
            reason='export_disabled'
        emit({'component':'diagnostic_stdin','request_id':request_id,
              'status':'REJECTED','reason':reason,'export_enabled':False,
              'received':True,'repeated':repeated})

def main():
    try:
        # Only options read; no ledger, controller database or export directory.
        with open('/data/options.json') as file:ledger=json.load(file).get('ledger_id','')
        if not isinstance(ledger,str):raise ValueError()
        receive(sys.stdin,lambda result:print(json.dumps(result,allow_nan=False),flush=True),ledger)
        print('{"component":"diagnostic_stdin","state":"CLOSED","reason":"stdin_eof"}',flush=True)
        return 0
    except Exception:
        # No exception details, input payload, source IDs or file contents.
        print('{"component":"diagnostic_stdin","state":"ERROR","reason":"receiver_failure"}',flush=True)
        return 70
if __name__=='__main__':raise SystemExit(main())
