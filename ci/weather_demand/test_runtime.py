import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from demand_runtime import Store

C=dict(local_entity='sensor.example_temperature',weather_entity='weather.example',max_ha_age_seconds=900,
       energy='sensor.example_energy',workday='binary_sensor.example_workday')
T=datetime(2026,10,1,tzinfo=timezone.utc)
def at(i):return (T+timedelta(seconds=i*20)).isoformat()
def states(i):
    return {C['local_entity']:dict(entity_id=C['local_entity'],state='10',attributes={'unit_of_measurement':'°C'},last_reported=at(i)),
        C['energy']:dict(state=str(100+i/180),attributes={'unit_of_measurement':'kWh'},last_reported=at(i)),
        C['workday']:dict(state='on')}

class Tests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.path=Path(self.t.name)/'new.sqlite';self.s=Store(self.path,C)
    def tearDown(self):
        self.s.c.close();self.t.cleanup()
    def test_actual_training_and_cold_start_forecast(self):
        for i in range(181):self.s.capture(at(i),states(i),C)
        row=json.loads(self.s.c.execute('SELECT record FROM training').fetchone()[0])
        self.assertAlmostEqual(row['actual_register_delta_kwh'],1)
        self.assertEqual(row['actual_seconds'],3600)
        self.assertEqual(self.s.forecast(at(182),[],C['weather_entity'])['status'],'insufficient_data')
    def test_duplicate(self):
        self.s.capture(at(0),states(0),C)
        self.assertEqual(self.s.capture(at(0),states(0),C),'duplicate')
        self.assertEqual(self.s.c.execute('SELECT COUNT(*) FROM captures').fetchone()[0],1)
    def test_missing_temperature_does_not_crash(self):
        v=states(0);v.pop(C['local_entity'])
        self.assertEqual(self.s.capture(at(0),v,C),'invalid')
        self.assertIsNone(self.s.base)
    def test_register_drop_resets_training_window(self):
        self.s.capture(at(0),states(0),C)
        v=states(1);v[C['energy']]['state']='0'
        self.assertEqual(self.s.capture(at(1),v,C),'interval_discontinuity')
        self.assertIsNone(self.s.base)
    def test_gap_no_bridge(self):
        self.s.capture(at(0),states(0),C)
        self.assertEqual(self.s.capture(at(10),states(10),C),'interval_discontinuity')
    def test_restart_and_independent_reopen(self):
        self.s.capture(at(0),states(0),C);self.s.c.close()
        output=subprocess.check_output([sys.executable,'-c',"import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('pragma integrity_check').fetchone()[0],c.execute('select count(*) from captures').fetchone()[0])",str(self.path)],text=True)
        self.assertEqual(output.strip(),'ok 1')
        self.s=Store(self.path,C)
        self.assertIsNone(self.s.base)
    def test_source_change_refused(self):
        with self.assertRaises(ValueError):Store(self.path,dict(C,energy='sensor.example_other'))
    def test_readonly_failure_no_in_memory_advance(self):
        self.s.c.execute('PRAGMA query_only=ON')
        with self.assertRaises(sqlite3.OperationalError):self.s.capture(at(0),states(0),C)
        self.assertIsNone(self.s.base)

if __name__=='__main__':unittest.main()
