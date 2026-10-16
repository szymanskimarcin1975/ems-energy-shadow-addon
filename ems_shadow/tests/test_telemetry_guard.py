import unittest
from datetime import datetime, timezone, timedelta
from telemetry_guard import evaluate

class Tests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,16,14,0,tzinfo=timezone.utc)
        self.rows={r:{'state':v,'attributes':{'unit_of_measurement':u},
                     'last_reported':self.now.isoformat()}
                   for r,v,u in [('m1_power','-1','kW'),('b1_power','0','W'),('soc','100','%')]}
    def check(self):
        return evaluate(self.rows,self.now,communication_ok=True,inverter_unambiguous=True)
    def test_valid(self): self.assertEqual(self.check(),'HA_TRANSPORT_CHECK_PASSED_NOT_DEVICE_PROOF')
    def test_stale_each(self):
        for role in self.rows:
            old=self.rows[role]['last_reported'];self.rows[role]['last_reported']=(self.now-timedelta(seconds=181)).isoformat()
            self.assertEqual(self.check(),'HA_TELEMETRY_STALE_OR_FUTURE');self.rows[role]['last_reported']=old
    def test_future(self):
        self.rows['m1_power']['last_reported']=(self.now+timedelta(seconds=1)).isoformat()
        self.assertEqual(self.check(),'HA_TELEMETRY_STALE_OR_FUTURE')
    def test_skew(self):
        self.rows['b1_power']['last_reported']=(self.now-timedelta(seconds=6)).isoformat()
        self.assertEqual(self.check(),'HA_SNAPSHOT_SKEW')
    def test_missing(self):
        del self.rows['soc'];self.assertEqual(self.check(),'TELEMETRY_MISSING_OR_INVALID')
    def test_nan(self):
        self.rows['soc']['state']='nan';self.assertEqual(self.check(),'TELEMETRY_VALUE_INVALID')
    def test_bad_soc(self):
        self.rows['soc']['state']='101';self.assertEqual(self.check(),'TELEMETRY_VALUE_INVALID')
    def test_bad_unit(self):
        self.rows['m1_power']['attributes']['unit_of_measurement']='W';self.assertEqual(self.check(),'TELEMETRY_UNIT_INVALID')
    def test_naive(self):
        self.rows['soc']['last_reported']='2026-10-16T14:00:00';self.assertEqual(self.check(),'HA_TELEMETRY_STALE_OR_FUTURE')
    def test_connection(self):
        self.assertEqual(evaluate(self.rows,self.now,communication_ok=False,inverter_unambiguous=True),'COMMUNICATION_UNCONFIRMED')
    def test_unknown_inverter(self):
        self.assertEqual(evaluate(self.rows,self.now,communication_ok=True,inverter_unambiguous=False),'INVERTER_STATE_AMBIGUOUS')
    def test_unavailable(self):
        self.rows['b1_power']['state']='unavailable';self.assertEqual(self.check(),'TELEMETRY_MISSING_OR_INVALID')

if __name__=='__main__': unittest.main()
