import unittest
from weather_demand import local_temperature, forecast_temperature, predict

NOW = '2026-10-16T04:00:00+00:00'
TARGET = '2026-10-16T05:00:00+00:00'

def training():
    return [dict(target='boiler', slot=7, day_type='workday', quality_approved=True,
                 coverage=1, temperature_quality='approved', local_day=f'2026-10-{d:02}',
                 start=f'2026-10-{d:02}T04:00:00+00:00', end=f'2026-10-{d:02}T05:00:00+00:00',
                 available_at=f'2026-10-{d:02}T05:01:00+00:00', temperature_c=d, kwh=16-d)
            for d in range(1, 15)]

class Tests(unittest.TestCase):
    def test_cold_start(self):
        self.assertEqual(predict([], NOW, 7, 'workday', 5)['status'], 'insufficient_data')
    def test_temperature_changes_advisory(self):
        a=predict(training(), NOW, 7, 'workday', 3)
        b=predict(training(), NOW, 7, 'workday', 12)
        self.assertGreater(a['prediction_kwh'], b['prediction_kwh'])
        self.assertFalse(a['control_enabled'])
    def test_no_extrapolation(self):
        self.assertIsNone(predict(training(), NOW, 7, 'workday', -10)['prediction_kwh'])
    def test_missing_fallback(self):
        self.assertEqual(predict(training(), NOW, 7, 'workday', None)['status'], 'baseline_without_temperature')
    def test_invalid_fallback(self):
        for temp in ('unavailable', float('nan'), True):
            self.assertFalse(predict(training(), NOW, 7, 'workday', temp)['temperature_used'])
    def test_no_future_training(self):
        rows=training()
        for r in rows:r['available_at']='2026-10-17T00:00:00+00:00'
        self.assertEqual(predict(rows, NOW, 7, 'workday', 5)['training_days'], 0)
    def test_no_incomplete_training(self):
        rows=training()
        for r in rows:r['coverage']=.99
        self.assertIsNone(predict(rows, NOW, 7, 'workday', 5)['prediction_kwh'])
    def test_duplicate_rejected(self):
        rows=training()
        with self.assertRaises(RuntimeError):predict(rows+[rows[0]], NOW, 7, 'workday', 5)
    def test_cwu_not_inferred_from_boiler(self):
        self.assertEqual(predict(training(), NOW, 7, 'workday', 5, target='heatpump_co')['training_days'], 0)
    def test_valid_local(self):
        state=dict(entity_id='sensor.example_outdoor', state='8.5', attributes={'unit_of_measurement':'°C'},last_reported=NOW)
        self.assertEqual(local_temperature(state,'sensor.example_outdoor', NOW)['temperature_c'],8.5)
    def test_bad_local(self):
        for value in ('unknown', 'unavailable', None, True, 'nan'):
            state=dict(entity_id='sensor.example_outdoor', state=value,attributes={'unit_of_measurement':'°C'},last_reported=NOW)
            self.assertIsNone(local_temperature(state,'sensor.example_outdoor', NOW)['temperature_c'])
    def test_stale_local(self):
        state=dict(entity_id='sensor.example_outdoor',state='8',attributes={'unit_of_measurement':'°C'},last_reported='2026-10-15T00:00:00+00:00')
        self.assertIsNone(local_temperature(state,'sensor.example_outdoor', NOW)['temperature_c'])
    def test_forecast_as_issued(self):
        row=dict(source='weather.example',retrieved_at='2026-10-16T03:00:00+00:00',valid_for=TARGET,temperature_c=8)
        future=dict(row,retrieved_at='2026-10-16T04:01:00+00:00',temperature_c=99)
        self.assertEqual(forecast_temperature([row,future],NOW,TARGET,'weather.example'),8)
    def test_forecast_missing(self):
        self.assertIsNone(forecast_temperature([],NOW,TARGET,'weather.example'))

if __name__ == '__main__':unittest.main()
