import unittest,sqlite3,tempfile,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from fault_guard import FaultGuard,READY
SOURCES={'inverter_status':'sensor.example_status','vendor_status':'sensor.example_vendor'}
class HA:
 def __init__(self):self.at=datetime(2026,10,16,tzinfo=timezone.utc);self.status='I_STATUS_MPPT';self.vendor='0x0'
 def current_states(self,ids):return {e:{'state':self.status if e==SOURCES['inverter_status'] else self.vendor,'last_reported':self.at.isoformat()} for e in ids}
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'test.sqlite';self.db=sqlite3.connect(self.path,isolation_level=None);self.addCleanup(lambda:self.db.close());self.g=FaultGuard(self.db);self.ha=HA()
 def observe(self):return self.g.observe(self.ha,SOURCES,self.ha.at+timedelta(seconds=1))
 def ready(self):
  for i in range(3):
   self.result=self.observe()
   if i<2:self.ha.at+=timedelta(seconds=120)
  self.assertEqual(self.result,READY)
 def test_three_distinct_publications_and_240s_required(self):self.ready()
 def test_repeated_reads_do_not_stabilise(self):
  for i in range(30):self.assertNotEqual(self.observe(),READY)
  self.assertEqual(self.g.record['updates'],1)
 def test_fault_resets_ready(self):
  self.ready();self.ha.status='I_STATUS_FAULT';self.assertEqual(self.observe(),'INVERTER_FAULT');self.ha.status='I_STATUS_MPPT';self.assertNotEqual(self.observe(),READY)
 def test_heartbeat_without_fault_status_blocks(self):
  self.ha.vendor='1Dx88';self.assertEqual(self.observe(),'INVERTER_HEARTBEAT_ERROR')
 def test_unknown_return_blocks(self):
  self.ha.status='unavailable';self.assertEqual(self.observe(),'INVERTER_RETURN_AMBIGUOUS')
 def test_gap_resets(self):
  self.ready();self.ha.at+=timedelta(seconds=181);self.assertNotEqual(self.observe(),READY);self.assertEqual(self.g.record['updates'],1)
 def test_stale_blocks(self):
  self.assertEqual(self.g.observe(self.ha,SOURCES,self.ha.at+timedelta(seconds=181)),'FAULT_TELEMETRY_STALE_OR_FUTURE')
 def test_missing_mapping_blocks(self):self.assertEqual(self.g.observe(self.ha,{},self.ha.at),'FAULT_SOURCES_UNCONFIRMED')
 def test_out_of_order_blocks(self):
  self.ready();self.ha.at-=timedelta(seconds=1);self.assertEqual(self.observe(),'FAULT_TELEMETRY_OUT_OF_ORDER')
 def test_restart_never_restores_ready_and_integrity_separate_process(self):
  self.ready();self.db.close();self.db=sqlite3.connect(self.path,isolation_level=None);self.g=FaultGuard(self.db);self.assertFalse(self.g.record['ready'])
  out=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys,json;c=sqlite3.connect(sys.argv[1]);print(c.execute('pragma integrity_check').fetchone()[0]);print(json.loads(c.execute('select record from fault_guard').fetchone()[0])['ready'])",str(self.path)],text=True)
  self.assertEqual(out.strip(),'ok\nFalse')
 def test_write_error_is_not_success(self):
  self.db.execute('PRAGMA query_only=ON')
  with self.assertRaises(sqlite3.Error):self.observe()

class ServiceIntegration(unittest.TestCase):
 def test_readonly_real_service_fault_recovery_and_restart(self):
  from battery_service import BatteryService
  from test_battery_service import TestHA,Local,config,PROFILE
  class API(TestHA):
   def current_states(self,ids):
    ids=list(ids)
    if set(ids)==set(SOURCES.values()):return {e:{'state':self.status if e==SOURCES['inverter_status'] else '0x0','last_reported':self.at.isoformat()} for e in ids}
    return super().current_states(ids)
  with tempfile.TemporaryDirectory() as root:
   api=API();api.at=datetime.now(timezone.utc);api.status='I_STATUS_MPPT'
   cfg=config('READ_ONLY');cfg['fault_sources']=SOURCES
   service=BatteryService(root,Local(),'synthetic',ha=api,clock=lambda:api.at+timedelta(seconds=1))
   try:
    for i in range(3):
     report=service.cycle(cfg,PROFILE)
     if i<2:api.at+=timedelta(seconds=120)
    self.assertEqual(report['fault_quality'],READY)
    api.status='I_STATUS_FAULT';report=service.cycle(cfg,PROFILE)
    self.assertEqual(report['fault_quality'],'INVERTER_FAULT');self.assertEqual(api.calls,[])
   finally:service.close()
   service=BatteryService(root,Local(),'synthetic',ha=api,clock=lambda:api.at+timedelta(seconds=1))
   try:
    api.status='I_STATUS_MPPT';report=service.cycle(cfg,PROFILE)
    self.assertEqual(report['fault_quality'],'FAULT_RECOVERY_STABILISING');self.assertEqual(api.calls,[])
   finally:service.close()
