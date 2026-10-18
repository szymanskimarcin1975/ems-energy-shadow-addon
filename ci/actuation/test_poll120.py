"""Natural 120s polls, durable pending states and real STOP transport (simulated device).
Virtual clock only; never changes integration cadence or contacts hardware.
"""
import asyncio
import importlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ems_shadow/tests'),str(ROOT/'ems_shadow/app')]
import test_actuation_candidate as fixtures
from battery_executor import SupervisorHA
Store,Engine=fixtures.Store,fixtures.Engine

class SlowDevice(fixtures.Device):
    deferred_confirmation=True
    def __init__(self,clock):
        super().__init__();self.clock=clock;self.config={'command_timeout_s':3600}
        self.poll=0;self.stop_polls=[];self.failed=False
    async def preflight(self,req):
        if self.failed:raise ValueError('COMMUNICATION_LOST')
        return dict(direction_limit_w=getattr(self,'cap',900),poll_completed_at=self.clock(),plan_valid_until=self.clock()+360)
    monitor_preflight=preflight
    async def confirm_effect(self,req,power,*,after=None):
        if self.poll<=after:return dict(pending_confirmation=True)
        return dict(request_id=req['request_id'],plan_id=req['plan_id'],owner_epoch=req['owner_epoch'],
            observed_at=self.poll,physical_effect_confirmed=True)
    async def confirm_termination(self,request_id,*,after=None):
        fresh=[t for t in self.stop_polls if t>after]
        if len(fresh)<2:return dict(pending_confirmation=True)
        return dict(request_id=request_id,active_command_ended=True,safe_local_mode_confirmed=True,observed_at=fresh[-1])

class Poll120Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'journal.sqlite';self.store=Store(self.path);self.store.initialize()
        self.store.transition_owner(0,'EMS2','synthetic-only')
        self.t=1000.;self.device=SlowDevice(lambda:self.t)
        async def db(fn,*args):return await asyncio.to_thread(fn,*args)
        self.engine=Engine(self.store,self.device,db,clock=lambda:self.t);self.db=db
        self.req=fixtures.request(expires_at=1050)
    async def issue(self):return await self.engine.dispatch(self.req)
    async def test_pending_survives_admission_deadline_and_confirms_at_120(self):
        reply=await self.issue();self.assertEqual(reply['status'],'WAITING_CONFIRMATION')
        self.assertEqual(self.store.active('test_request')['state'],'WAITING_EFFECT')
        self.t+=119;await self.engine.monitor_once()
        self.assertEqual(self.store.active('test_request')['state'],'WAITING_EFFECT')
        self.t+=1;self.device.poll=self.t;await self.engine.monitor_once()
        reply=await self.engine.command_status('test_request')
        self.assertEqual(reply['command_state'],'ACK_ACTIVE');self.assertTrue(reply['device_execution_confirmed'])
        self.assertEqual(len(self.device.calls),1)
    async def test_waiting_blocks_other_id_and_owner_change(self):
        await self.issue()
        second=dict(self.req,request_id='second')
        self.assertEqual((await self.engine.dispatch(second))['status'],'UNKNOWN')
        with self.assertRaisesRegex(ValueError,'ACTIVE_OR_UNKNOWN'):
            self.store.transition_owner(1,'LEGACY','not-allowed')
        self.assertEqual(len(self.device.calls),1)
    async def test_stop_sends_immediately_then_waits_two_120s_polls(self):
        await self.issue();reply=await self.engine.stop('test_request')
        self.assertEqual(reply['status'],'WAITING_STOP');self.assertEqual(self.device.calls[-1][0],'STOP')
        self.t+=120;self.device.stop_polls.append(self.t);await self.engine.monitor_once()
        self.assertEqual(self.store.active('test_request')['state'],'WAITING_STOP')
        self.t+=120;self.device.stop_polls.append(self.t);await self.engine.monitor_once()
        self.assertEqual(self.store.active('test_request')['state'],'ENDED')
        self.assertEqual([x[0] for x in self.device.calls].count('STOP'),1)
        self.assertEqual(self.store.transition_owner(1,'LEGACY','confirmed-rollback'),2)
    async def test_stop_timeout_is_unknown_no_retry(self):
        await self.issue();await self.engine.stop('test_request');self.t+=391
        await self.engine.monitor_once()
        self.assertEqual(self.store.active('test_request')['state'],'UNKNOWN')
        await self.engine.monitor_once();await self.engine.stop('test_request')
        self.assertEqual([x[0] for x in self.device.calls].count('STOP'),1)
    async def test_lost_communication_attempts_stop_not_only_waiting(self):
        await self.issue();self.device.failed=True;await self.engine.monitor_once()
        self.assertTrue(self.store.control_status()['emergency_stop']['latched'])
        self.assertEqual(self.store.active('test_request')['state'],'WAITING_STOP')
        self.assertEqual(self.device.calls[-1][0],'STOP')
    async def test_effect_timeout_sends_stop_without_reissuing_command(self):
        await self.issue();self.t+=271;await self.engine.monitor_once()
        self.assertEqual(self.store.active('test_request')['state'],'WAITING_STOP')
        self.assertEqual(len(self.device.calls),2)
    async def test_restart_disarms_waiting_effect_no_replay(self):
        await self.issue();self.store.initialize()
        self.assertEqual(self.store.active('test_request')['state'],'UNKNOWN')
        self.assertFalse(self.store.control_status()['physical_authorized'])
        self.assertEqual((await self.engine.dispatch(self.req))['status'],'UNKNOWN')
        self.assertEqual(len(self.device.calls),1)
    async def test_restart_during_stop_cannot_repeat_it(self):
        await self.issue();await self.engine.stop('test_request');self.store.initialize()
        await self.engine.monitor_once()
        self.assertEqual(self.store.active('test_request')['state'],'UNKNOWN')
        self.assertEqual([x[0] for x in self.device.calls].count('STOP'),1)
    async def test_status_queries_never_send_anything(self):
        await self.issue()
        for _ in range(5):self.assertEqual((await self.engine.command_status('test_request'))['status'],'WAITING_CONFIRMATION')
        self.assertEqual(len(self.device.calls),1)
    async def test_dynamic_bms_cap_drop_stops_existing_command(self):
        await self.issue();self.device.cap=100;self.t+=120;self.device.poll=self.t
        await self.engine.monitor_once()
        self.assertEqual(self.store.active('test_request')['state'],'WAITING_STOP')
        self.assertEqual(self.device.calls[-1][0],'STOP')

    async def test_journal_cas_does_not_revive_stop(self):
        await self.issue();await self.engine.stop('test_request')
        with self.assertRaises(ValueError):self.store.record('test_request','ACK_ACTIVE',True,{},'WAITING_EFFECT')
        self.assertEqual(self.store.active('test_request')['state'],'WAITING_STOP')
    async def test_old_readback_cannot_finish_stop(self):
        await self.issue();await self.engine.stop('test_request')
        self.device.stop_polls=[self.t-240,self.t-120];self.t+=120
        await self.engine.monitor_once();self.assertEqual(self.store.active('test_request')['state'],'WAITING_STOP')
    async def test_integrity_after_wait_stop_and_restart(self):
        await self.issue();await self.engine.stop('test_request');self.store.initialize()
        with sqlite3.connect('file:'+str(self.path)+'?mode=ro',uri=True) as db:
            self.assertEqual(db.execute('pragma integrity_check').fetchone()[0],'ok')

class AddonTransportTests(unittest.TestCase):
    def test_waiting_reply_is_not_ack_and_status_read_is_correlated(self):
        class HA(SupervisorHA):
            def _request(self,path,data=None):
                self.paths.append(path)
                return {'service_response':dict(gateway_contract='EMS2_COMPOUND_V28',request_id='r',plan_id='a'*64,
                    owner_epoch=1,status='WAITING_CONFIRMATION',command_state='WAITING_EFFECT',owner='EMS2',
                    option='Charge from Solar Power',writes_started=True,device_execution_confirmed=False,applied_power_w=100)}
        from datetime import datetime,timezone,timedelta
        ha=HA('synthetic-not-a-real-token');ha.paths=[]
        r=ha.dispatch('ignored','Charge from Solar Power',100,request_id='r',plan_id='a'*64,owner_epoch=1,
                      expires_at=datetime.now(timezone.utc)+timedelta(seconds=30))
        self.assertFalse(r['device_execution_confirmed'])
        self.assertEqual(ha.command_status('r','a'*64,1)['command_state'],'WAITING_EFFECT')
        self.assertEqual(len([p for p in ha.paths if '/dispatch?' in p]),1)
        with self.assertRaises(RuntimeError):ha.command_status('different','a'*64,1)

class AddonReconciliationTests(unittest.TestCase):
    def setUp(self):
        import test_battery_executor as ef
        self.fixture=ef.Tests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.executor=self.fixture.executor();self.ha=self.fixture.ha;self.phase='WAITING_EFFECT'
        def dispatch(e,o,power_w,**kw):
            self.ha.calls.append((e,o))
            return dict(status='WAITING_CONFIRMATION',applied_power_w=power_w)
        def status(*args):
            if self.phase=='FAIL':raise TimeoutError()
            return dict(command_state=self.phase,device_execution_confirmed=self.phase=='ACK_ACTIVE',
                        termination_evidence={'active_command_ended':self.phase=='ENDED'})
        self.ha.dispatch=dispatch;self.ha.command_status=status
    def test_complete_addon_wait_ack_end_without_second_dispatch(self):
        self.assertEqual(self.fixture.run_command(self.executor),'WAITING')
        self.assertEqual(self.fixture.run_command(self.executor),'DUPLICATE_WAITING')
        self.assertEqual(self.executor.reconcile_pending(),[])
        self.phase='ACK_ACTIVE'
        self.assertEqual(self.executor.reconcile_pending()[0]['status'],'ACK')
        self.phase='ENDED'
        self.assertEqual(self.executor.reconcile_pending()[0]['status'],'ENDED')
        self.assertEqual(len(self.ha.calls),1)
        from dispatch_lifecycle import state
        with sqlite3.connect(self.executor.db) as db:self.assertTrue(state(db)['termination_confirmed'])
    def test_failed_outcome_read_latches_unknown_without_resend(self):
        self.assertEqual(self.fixture.run_command(self.executor),'WAITING')
        self.phase='FAIL';self.assertEqual(self.executor.reconcile_pending()[0]['status'],'UNKNOWN')
        self.phase='ACK_ACTIVE';self.assertEqual(self.executor.reconcile_pending(),[])
        self.assertEqual(self.fixture.run_command(self.executor),'DUPLICATE_UNKNOWN')
        self.assertEqual(len(self.ha.calls),1)

if __name__=='__main__':unittest.main()
