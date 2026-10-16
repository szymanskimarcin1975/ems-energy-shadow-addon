"""Only synthetic HA transport; no device/network access in this regression."""
import copy,sqlite3,subprocess,sys,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from battery_executor import SupervisorHA,GatewayRejected
import test_dispatch_lifecycle as fixture

class TransportTests(unittest.TestCase):
 def reply(self):return {'status':'SERVICE_COMPLETED','gateway_contract':'EMS2_COMPOUND_V28','request_id':'request','plan_id':'a'*64,'owner_epoch':2,'owner':'EMS2','option':'Charge from Solar Power and Grid','applied_power_w':1000,'writes_started':True}
 def send(self,value):
  ha=SupervisorHA('synthetic')
  with patch.object(ha,'_request',return_value=value):return ha.dispatch('select.example_mode','Charge from Solar Power and Grid',1000,request_id='request',expires_at=datetime.now(timezone.utc)+timedelta(seconds=30),plan_id='a'*64,owner_epoch=2)
 def test_success_correlated(self):self.assertEqual(self.send({'service_response':self.reply()})['request_id'],'request')
 def test_only_correlated_explicit_before_write_reject_is_rejected(self):
  r=self.reply();r.update(status='REJECTED',writes_started=False,owner='LEGACY')
  with self.assertRaises(GatewayRejected):self.send({'service_response':r})
 def test_missing_partial_malformed_are_unknown(self):
  for r in (None,{},[],{'service_response':None},{'service_response':[]},{'service_response':{'status':'REJECTED'}}):
   with self.subTest(reply=r):
    with self.assertRaises(RuntimeError) as raised:self.send(r)
    self.assertNotIsInstance(raised.exception,GatewayRejected)
 def test_wrong_identity_unknown_even_negative_reply(self):
  for status in ('REJECTED','SERVICE_COMPLETED'):
   for key,value in (('request_id','other'),('plan_id','b'*64),('owner_epoch',3),('owner_epoch',True),('gateway_contract','EMS2_COMPOUND_V27')):
    r=self.reply();r.update(status=status,writes_started=status!='REJECTED');r[key]=value
    with self.subTest(status=status,key=key):
     with self.assertRaises(RuntimeError) as raised:self.send({'service_response':r})
     self.assertNotIsInstance(raised.exception,GatewayRejected)
 def test_reject_without_false_write_marker_unknown(self):
  for marker in (None,True,0,'false'):
   r=self.reply();r.update(status='REJECTED',writes_started=marker)
   with self.subTest(marker=marker):
    with self.assertRaises(RuntimeError) as raised:self.send({'service_response':r})
    self.assertNotIsInstance(raised.exception,GatewayRejected)
 def test_success_wrong_owner_or_mode_unknown(self):
  for key,value in (('owner','LEGACY'),('owner','UNKNOWN'),('option','other'),('writes_started',False)):
   r=self.reply();r[key]=value
   with self.assertRaises(RuntimeError):self.send({'service_response':r})
 def test_timeout_is_not_clean_rejection(self):
  ha=SupervisorHA('synthetic')
  with patch.object(ha,'_request',side_effect=TimeoutError):
   with self.assertRaises(TimeoutError):ha.dispatch('select.example_mode','Charge from Solar Power',1000,request_id='request',expires_at=datetime.now(timezone.utc),plan_id='a'*64,owner_epoch=2)
 def test_no_alternate_transport(self):self.assertFalse(hasattr(SupervisorHA,'select'))

class PersistedTests(unittest.TestCase):
 setUp=fixture.Tests.setUp
 execute=fixture.Tests.execute
 def transport(self,kind):
  ha=SupervisorHA('synthetic')
  def send(path,data):
   self.ha.calls.append((data['request_id'],data['command_value']))
   r={'status':'SERVICE_COMPLETED','gateway_contract':'EMS2_COMPOUND_V28','request_id':data['request_id'],'plan_id':data['plan_id'],'owner_epoch':data['owner_epoch'],'owner':'EMS2','option':data['command_value']['option'],'applied_power_w':data['command_value']['power_w'],'writes_started':True}
   self.ha.power=r['applied_power_w'];self.ha.mode=r['option']
   if kind=='timeout':raise TimeoutError('synthetic')
   if kind=='missing':return {}
   if kind=='partial':r.update(status='PARTIAL_OR_UNKNOWN')
   if kind=='wrong_id':r['request_id']='other'
   if kind=='wrong_plan':r['plan_id']='b'*64
   if kind=='reject':r.update(status='REJECTED',writes_started=False)
   if kind=='late':self.ha.offset=70
   if kind=='owner_change':self.ha.owner='LEGACY'
   return {'service_response':r}
  ha._request=send;self.ha.dispatch=ha.dispatch
 def check_reopen(self,status):
  code="import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select status from commands').fetchone()[0],c.execute('select plan_id,owner_epoch from command_identity').fetchone()[0],c.execute('select count(*) from dispatch_audit').fetchone()[0])"
  result=subprocess.check_output([sys.executable,'-c',code,str(self.path)],text=True).strip()
  self.assertTrue(result.startswith('ok '+status+' '+'a'*64+' '));self.assertEqual(self.ha.calls.__len__(),1)
 def test_partial_unknown_survives_restart_no_replay(self):
  self.transport('partial');self.assertEqual(self.execute(),'UNKNOWN');self.check_reopen('UNKNOWN');self.assertEqual(self.execute(),'DUPLICATE_UNKNOWN');self.assertEqual(self.execute('new'),'UNKNOWN_REQUIRES_RECONCILIATION');self.assertEqual(len(self.ha.calls),1)
 def test_missing_unknown_durable(self):self.transport('missing');self.assertEqual(self.execute(),'UNKNOWN');self.check_reopen('UNKNOWN')
 def test_timeout_unknown_durable(self):self.transport('timeout');self.assertEqual(self.execute(),'UNKNOWN');self.check_reopen('UNKNOWN')
 def test_wrong_request_unknown_durable(self):self.transport('wrong_id');self.assertEqual(self.execute(),'UNKNOWN');self.check_reopen('UNKNOWN')
 def test_wrong_plan_unknown_durable(self):self.transport('wrong_plan');self.assertEqual(self.execute(),'UNKNOWN');self.check_reopen('UNKNOWN')
 def test_delayed_ack_unknown_durable(self):self.transport('late');self.assertEqual(self.execute(),'UNKNOWN');self.check_reopen('UNKNOWN')
 def test_owner_change_after_write_unknown_durable(self):self.transport('owner_change');self.assertEqual(self.execute(),'UNKNOWN');self.check_reopen('UNKNOWN')
 def test_explicit_no_write_rejection_durable(self):self.transport('reject');self.assertEqual(self.execute(),'REJECTED');self.check_reopen('REJECTED')
 def test_duplicate_id_different_plan_conflicts(self):
  self.assertEqual(self.execute(),'ACK')
  result=self.x.execute('request','Charge from Solar Power and Grid',datetime.now(timezone.utc)+timedelta(seconds=30),maximum_power_w=5000,plan_id='b'*64)
  self.assertEqual(result,'REQUEST_CONFLICT');self.assertEqual(len(self.ha.calls),1)
 def test_missing_power_no_transport(self):
  self.assertEqual(self.x.execute('request','Charge from Solar Power',datetime.now(timezone.utc)+timedelta(seconds=30),plan_id='a'*64),'PLAN_POWER_REQUIRED');self.assertEqual(self.ha.calls,[])
 def test_missing_plan_no_transport(self):
  self.assertEqual(self.x.execute('request','Charge from Solar Power',datetime.now(timezone.utc)+timedelta(seconds=30),maximum_power_w=1000),'PLAN_ID_REQUIRED');self.assertEqual(self.ha.calls,[])
