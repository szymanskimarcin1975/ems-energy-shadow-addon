"""Persistent advisory-only hourly load forecast feedback; never device authority."""
import sys
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]/"app"
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"observation"))
from household_advisory import actual_hourly_rows,forecast
from planning_runtime import Planner

ZONE=ZoneInfo("Europe/Warsaw")


class HouseholdFeedbackTests(unittest.TestCase):
    def test_sparse_actual_history_produces_uncalibrated_fallback(self):
        now=datetime(2026,10,16,12,tzinfo=ZONE)
        start=datetime(2026,10,15,10,tzinfo=ZONE)
        history={"unit":"W","source_entity":"sensor.example_house_power","retrieved_at":now.isoformat(),
                 "rows":[{"start":start.isoformat(),"end":(start+timedelta(hours=1)).isoformat(),
                          "min":100,"mean":500,"max":900}]}
        result=forecast(history,None,now.isoformat(),[(start+timedelta(days=2)).isoformat()])
        item=result["horizon"][0]
        self.assertEqual(result["status"],"ADVISORY_UNCALIBRATED")
        self.assertAlmostEqual(item["prediction_kwh"],.5)
        self.assertEqual(item["method"],"single_actual_same_local_hour_uncalibrated")
        self.assertFalse(item["uncertainty_calibrated"])
        self.assertFalse(item["control_enabled"])

    def test_daily_bias_is_damped_capped_and_not_marked_calibrated(self):
        now=datetime(2026,10,16,12,tzinfo=ZONE)
        start=datetime(2026,10,15,10,tzinfo=ZONE)
        history={"unit":"W","source_entity":"sensor.example_house_power","retrieved_at":now.isoformat(),
                 "rows":[{"start":start.isoformat(),"end":(start+timedelta(hours=1)).isoformat(),
                          "min":100,"mean":500,"max":900}]}
        bias={10:{"median_error_kwh":4.0,"samples":4}}
        result=forecast(history,None,now.isoformat(),[(start+timedelta(days=2)).isoformat()],
                        error_biases=bias)
        item=result["horizon"][0]
        self.assertAlmostEqual(item["prediction_kwh"],.75)
        self.assertAlmostEqual(item["prior_error_correction"]["applied_kwh"],.25)
        self.assertFalse(item["uncertainty_calibrated"])
        self.assertFalse(item["control_enabled"])

    def test_only_complete_unique_nonfuture_hours_enter_feedback(self):
        now=datetime(2026,10,16,12,tzinfo=ZONE)
        start=datetime(2026,10,16,9,tzinfo=ZONE)
        complete={"start":start.isoformat(),"end":(start+timedelta(hours=1)).isoformat(),
                  "min":100,"mean":500,"max":900}
        history={"unit":"W","source_entity":"sensor.example_house_power","retrieved_at":now.isoformat(),
                 "rows":[complete,complete,
                         {"start":(start+timedelta(hours=2)).isoformat(),
                          "end":(start+timedelta(hours=3)).isoformat(),"min":0,"mean":0,"max":0},
                         {"start":(start-timedelta(hours=1)).isoformat(),
                          "end":start.isoformat(),"min":-1,"mean":0,"max":1}]}
        accepted=actual_hourly_rows(history,now.isoformat())
        self.assertEqual(len(accepted),1)
        self.assertAlmostEqual(accepted[0]["actual_kwh"],.5)

    def test_forecast_errors_deduplicate_and_survive_sqlite_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"planning.sqlite"
            planner=Planner(path)
            base=datetime(2026,10,10,6,tzinfo=ZONE)
            actual_rows=[]
            for day,actual in enumerate((1.2,1.4,1.6)):
                target=(base+timedelta(days=day)).isoformat()
                generated=(base+timedelta(days=day)-timedelta(hours=1)).isoformat()
                planner.record_household_forecasts("sensor.example_house_power",generated,
                    [{"valid_for":target,"prediction_kwh":1.0,"method":"test"}])
                actual_rows.append({"target_at":target,"actual_kwh":actual,"local_hour":6,
                    "local_day":(base+timedelta(days=day)).date().isoformat(),
                    "observed_at":(base+timedelta(days=day,hours=1)).isoformat()})
            self.assertEqual(planner.reconcile_forecast_errors("sensor.example_house_power",actual_rows),3)
            self.assertEqual(planner.reconcile_forecast_errors("sensor.example_house_power",actual_rows),0)
            planner.c.close()

            reopened=Planner(path)
            biases=reopened.error_biases("sensor.example_house_power",(base+timedelta(days=4)).isoformat())
            self.assertEqual(biases[6]["samples"],3)
            self.assertEqual(biases[6]["distinct_days"],3)
            self.assertAlmostEqual(biases[6]["median_error_kwh"],.4)
            reopened.c.close()


if __name__=="__main__":
    unittest.main()
