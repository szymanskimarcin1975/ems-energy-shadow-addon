import builtins,io,json,sqlite3,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from disabled_stdin import receive
from test_controller import request
import test_isolation
class Tests(unittest.TestCase):
 def collect(self,text):
  result=[]
  with patch.object(sqlite3,'connect',side_effect=AssertionError('database_forbidden')),patch.object(builtins,'open',side_effect=AssertionError('files_forbidden')):
   receive(io.StringIO(text),result.append,'synthetic')
  return result
 def test_valid_correlation(self):
  r=request();out=self.collect(json.dumps(r)+'\n');self.assertEqual(out[0]['reason'],'export_disabled');self.assertEqual(out[0]['request_id'],r['request_id']);self.assertTrue(out[0]['received'])
 def test_duplicate_no_export(self):
  r=request();out=self.collect((json.dumps(r)+'\n')*2)
  self.assertEqual(len(out),2);self.assertFalse(out[0]['repeated']);self.assertTrue(out[1]['repeated']);self.assertTrue(all(x['reason']=='export_disabled' for x in out))
 def test_malformed(self):self.assertEqual(self.collect('{broken\n')[0]['reason'],'invalid_json')
 def test_incomplete_with_correlation(self):
  r=request();out=self.collect(json.dumps(r));self.assertEqual(out[0]['reason'],'incomplete_message');self.assertEqual(out[0]['request_id'],r['request_id'])
 def test_duplicate_json_field(self):self.assertEqual(self.collect('{"request_id":"synthetic_id","request_id":"synthetic_id"}\n')[0]['reason'],'invalid_json')
 def test_oversized_and_recovery(self):
  out=self.collect('x'*10000+'\n'+json.dumps(request())+'\n');self.assertEqual([x['reason'] for x in out],['message_too_large','export_disabled'])
 def test_wrong_ledger(self):
  r=request();r['ledger_id']='other';self.assertEqual(self.collect(json.dumps(r)+'\n')[0]['reason'],'ledger_mismatch')
 def test_expired(self):
  r=request();r['expires_at']='2020-01-01T00:00:00+00:00';self.assertEqual(self.collect(json.dumps(r)+'\n')[0]['reason'],'invalid_expiry')
 def test_nan_rejected(self):self.assertEqual(self.collect('{"x":NaN}\n')[0]['reason'],'invalid_json')
 def test_receiver_read_failure(self):
  class Broken:
   def readline(self,*_):raise OSError()
  with self.assertRaises(OSError):receive(Broken(),lambda _:None,'synthetic')
 def test_receiver_write_failure(self):
  with self.assertRaises(BrokenPipeError):receive(io.StringIO(json.dumps(request())+'\n'),lambda _:(_ for _ in ()).throw(BrokenPipeError()),'synthetic')
 def test_receiver_failure_observer_continues(self):
  test_isolation.Tests.scenario(self,[sys.executable,'-c','raise OSError("synthetic stdin failure")'])
