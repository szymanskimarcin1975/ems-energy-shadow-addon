"""Real adapter guards using synthetic complete polls; no hardware or network."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'ems_shadow/tests'))
import test_actuation_candidate as f

class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture=f.AdapterTests('test_successful_poll_uses_raw_bms_not_unchanged_entity_time')
        await self.fixture.asyncSetUp()
        self.a=self.fixture.adapter
        self.a.clock=lambda:self.fixture.now
        self.req=f.request(option='Discharge to Minimize Import')
    async def test_residual_import_does_not_false_stop_discharge(self):
        self.a.sample.update(m1_w=-20,b1_w=-1000)
        sample=await self.a.monitor_preflight(self.req)
        self.assertEqual(sample['direction_limit_w'],5000)
        self.assertEqual(self.fixture.calls,[])
    async def test_admission_still_requires_import_margin(self):
        self.a.sample.update(m1_w=-20,b1_w=-1000)
        with self.assertRaisesRegex(ValueError,'IMPORT_HEADROOM'):
            await self.a.preflight(self.req)
    async def test_monitor_rejects_actual_export(self):
        self.a.sample.update(m1_w=1,b1_w=-1000)
        with self.assertRaisesRegex(ValueError,'OBSERVED_GRID_EXPORT_DURING_DISCHARGE'):
            await self.a.monitor_preflight(self.req)
    async def test_monitor_still_rejects_zero_bms(self):
        self.a.sample.update(m1_w=-20,b1_w=-1000,peak_discharge=0)
        with self.assertRaisesRegex(ValueError,'BMS_DIRECTION_LIMIT_ZERO'):
            await self.a.monitor_preflight(self.req)
    async def test_short_stop_evidence_refuses_admission_before_write(self):
        self.a.config['verified_evidence']['stop_procedure']['valid_until']=self.fixture.now+400
        with self.assertRaisesRegex(ValueError,'STOP_EVIDENCE_EXPIRES'):
            await self.a.preflight(self.req)
        self.assertEqual(self.fixture.calls,[])
    async def test_short_fence_evidence_refuses_admission(self):
        self.a.config['verified_evidence']['external_writer_fence']['valid_until']=self.fixture.now+400
        with self.assertRaisesRegex(ValueError,'STOP_EVIDENCE_EXPIRES'):
            await self.a.preflight(self.req)
    async def test_stop_evidence_covers_transport_lease_and_two_polls(self):
        await self.a.preflight(self.req)
        self.fixture.now+=30+self.a.config['command_timeout_s']+389
        await self.a.verify_stop_procedure('test_request')
        self.assertEqual(self.fixture.calls,[])
    async def test_short_plan_does_not_shorten_physical_lease_runway(self):
        async def short_plan(req, monitoring=False): return self.fixture.now+1
        self.a.validate_plan=short_plan
        self.a.config['command_timeout_s']=3600
        with self.assertRaisesRegex(ValueError,'STOP_EVIDENCE_EXPIRES'):
            await self.a.preflight(self.req)
        self.assertEqual(self.fixture.calls,[])
    async def test_invalid_command_timeout_refuses_before_write(self):
        self.a.config['command_timeout_s']=0
        with self.assertRaisesRegex(ValueError,'COMMAND_LEASE_UNCONFIRMED'):
            await self.a.preflight(self.req)
        self.assertEqual(self.fixture.calls,[])

if __name__=='__main__':unittest.main()
