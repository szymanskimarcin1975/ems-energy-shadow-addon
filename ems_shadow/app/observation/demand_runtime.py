"""Read-only advisory demand worker. Dedicated SQLite; never opens legacy ledgers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from weather_demand import local_temperature, forecast_temperature, predict, stamp, number
from cold_baseline import baseline
from planning_runtime import Planner
from ha_state_times import refresh
from worker import ReadAPI, states_by_id, atomic
from boiler_offline.g13 import tariff

ZONE = ZoneInfo('Europe/Warsaw')

class Store:
    def __init__(self, path, config):
        self.c = sqlite3.connect(path, timeout=1, isolation_level=None)
        try:
            self.c.execute('PRAGMA journal_mode=WAL')
            self.c.execute('PRAGMA synchronous=FULL')
            self.c.executescript('CREATE TABLE IF NOT EXISTS metadata(key PRIMARY KEY,value);'
                'CREATE TABLE IF NOT EXISTS captures(id PRIMARY KEY,record);'
                'CREATE TABLE IF NOT EXISTS training(id PRIMARY KEY,record);'
                'CREATE TABLE IF NOT EXISTS predictions(id PRIMARY KEY,record);')
            self.fingerprint = hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
            old = self.c.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
            if old and old[0] != self.fingerprint:
                raise ValueError('separate_database_required')
            self.c.execute("INSERT OR IGNORE INTO metadata VALUES('fingerprint',?)", (self.fingerprint,))
            self.base = None  # no interval bridge over restart
        except Exception:
            self.c.close()
            raise

    def capture(self, at, states, config):
        temp = local_temperature(states.get(config['local_entity'],{}),config['local_entity'],at,config['max_ha_age_seconds'])
        workday = states.get(config['workday'],{}).get('state')
        try:
            raw = states[config['energy']]
            if raw.get('attributes',{}).get('unit_of_measurement') != 'kWh':
                raise ValueError('invalid_register_unit')
            energy = number(raw['state'])
            age = (stamp(at)-stamp(raw.get('last_reported'))).total_seconds()
            if energy < 0 or not 0 <= age <= 210:
                raise ValueError('invalid_register_age_or_value')
            if temp['temperature_c'] is None or workday not in ('on','off'):
                raise ValueError('invalid_temperature_or_workday')
            valid = True
        except (ValueError,TypeError,KeyError):
            energy = None
            valid = False
        row = dict(captured_at=at,local=temp,register_kwh=energy,workday=workday,quality='valid' if valid else 'invalid')
        newbase = self.base
        train = None
        if not valid:
            newbase = None
        elif self.base is None:
            newbase = {'start':at,'last':at,'first':energy,'last_energy':energy,'temps':[temp['temperature_c']],'workday':workday}
        else:
            b=self.base
            elapsed=(stamp(at)-stamp(b['start'])).total_seconds()
            gap=(stamp(at)-stamp(b['last'])).total_seconds()
            if not 0 < gap <= 45 or energy < b['last_energy'] or workday != b['workday']:
                newbase=None
                row['quality']='interval_discontinuity'
            else:
                newbase=dict(b,last=at,last_energy=energy,temps=b['temps']+[temp['temperature_c']])
                if elapsed >= 3600:
                    start=stamp(b['start']).astimezone(ZONE)
                    # Training label is a rate normalized to one hour, not billed energy.
                    train=dict(target='boiler',slot=start.hour,day_type='workday' if workday=='on' else 'nonworkday',
                        local_day=start.date().isoformat(),start=b['start'],end=at,available_at=at,
                        temperature_c=sum(newbase['temps'])/len(newbase['temps']),temperature_quality='approved',
                        kwh=(energy-b['first'])*3600/elapsed,actual_register_delta_kwh=energy-b['first'],
                        actual_seconds=elapsed,label_method='observed_interval_hour_equivalent_estimate',
                        quality_approved=True,coverage=1)
                    newbase=None
        self.c.execute('BEGIN IMMEDIATE')
        try:
            if self.c.execute('SELECT 1 FROM captures WHERE id=?',(at,)).fetchone():
                self.c.execute('ROLLBACK')
                return 'duplicate'
            self.c.execute('INSERT INTO captures VALUES(?,?)',(at,json.dumps(row,allow_nan=False)))
            if train:
                key=train['local_day']+':'+str(train['slot'])
                self.c.execute('INSERT OR IGNORE INTO training VALUES(?,?)',(key,json.dumps(train,allow_nan=False)))
            self.c.execute('COMMIT')
            self.base=newbase
        except Exception:
            if self.c.in_transaction:self.c.execute('ROLLBACK')
            raise
        return row['quality']

    def forecast(self, at, forecasts, source):
        rows=[json.loads(r[0]) for r in self.c.execute('SELECT record FROM training ORDER BY id')]
        target=(stamp(at)+timedelta(hours=1)).replace(minute=0,second=0,microsecond=0)
        # No invented future workday/holiday state. Emit both scenarios independently.
        recent=[json.loads(r[0]) for r in self.c.execute('SELECT record FROM captures ORDER BY id DESC LIMIT 181')][::-1]
        persistence=baseline(recent,at)
        result={'issued_at':at,'control_enabled':False,'billing_approved':False,'horizon':[]}
        for i in range(24):
            t=target+timedelta(hours=i)
            value=forecast_temperature(forecasts,at,t.isoformat(),source)
            scenarios={d:predict(rows,at,t.astimezone(ZONE).hour,d,value) for d in ('workday','nonworkday')}
            result['horizon'].append({'valid_for':t.isoformat(),'forecast_temperature_c':value,'scenarios':scenarios,
                'g13_scenarios':{'workday':tariff(t,'on'),'nonworkday':tariff(t,'off')}})
        for h in result['horizon']:
            for d,p in h['scenarios'].items():
                if p['prediction_kwh'] is None and persistence['prediction_kwh'] is not None:
                    h['scenarios'][d]=dict(persistence,forecast_temperature_c=h['forecast_temperature_c'],target='boiler',training_days=p['training_days'])
        result['training_rows']=len(rows)
        result['status']='advisory_uncalibrated' if any(p['temperature_used'] for h in result['horizon'] for p in h['scenarios'].values()) else ('persistence_baseline_uncalibrated' if persistence['prediction_kwh'] is not None else 'insufficient_data')
        self.c.execute('INSERT OR IGNORE INTO predictions VALUES(?,?)',(at,json.dumps(result,allow_nan=False)))
        return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--options',default='/data/options.json')
    p.add_argument('--root',default='/data/observation-v1')
    p.add_argument('--stop-after-cycles',type=int)
    p.add_argument('--planning-config',default='/ha_config/ems_shadow/planning_sources.yaml')
    args=p.parse_args()
    o=json.loads(Path(args.options).read_text())['observation']
    if o.get('enabled') is not True:return 78
    config={**o['weather'],'energy':o['boiler_sources']['energy'],'workday':o['boiler_sources']['workday']}
    root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    # A fresh independent period. No legacy/weather/boiler database is opened.
    store=Store(root/'weather-demand-v1.sqlite',config)
    api=ReadAPI(os.environ['SUPERVISOR_TOKEN'])
    stop=threading.Event()
    for s in (signal.SIGTERM,signal.SIGINT):signal.signal(s,lambda *_:stop.set())
    seq=0;commits=0;forecasts=[];next_forecast=0;planner=None;next_planning=0
    try:
        while not stop.is_set():
            phase={'pid':os.getpid(),'sequence':seq,'phase':'polling'}
            atomic(root/'demand-heartbeat.json',phase)
            at=datetime.now(timezone.utc).isoformat()
            status='COMPLETED'
            try:
                states=states_by_id(api.call('GET','/states'))
                snapshot_config_path=Path(args.planning_config)
                if snapshot_config_path.exists():
                    snapshot_options=json.loads(snapshot_config_path.read_text())
                    if snapshot_options.get('refresh_ha_state_snapshot') is True:
                        raw_options=json.loads(Path(args.options).read_text())
                        solar=raw_options['observation']['solar_sources']
                        ids=[config['local_entity'],config['energy'],raw_options['sources']['grid_kw']]+[solar[k] for k in ('ac_power','b1_power','b1_soc','b1_status')]
                        states=refresh(api,states,ids)
                at=datetime.now(timezone.utc).isoformat()
                atomic(root/'demand-heartbeat.json',dict(phase,phase='writing'))
                quality=store.capture(at,states,config)
                if quality!='duplicate':commits+=1
                if time.monotonic()>=next_forecast:
                    response=api.call('POST','/services/weather/get_forecasts?return_response',{'entity_id':config['weather_entity'],'type':'hourly'})
                    rows=response.get('service_response',{}).get(config['weather_entity'],{}).get('forecast')
                    if not isinstance(rows,list):raise ValueError('missing_forecast')
                    forecasts=[dict(source=config['weather_entity'],retrieved_at=at,valid_for=r['datetime'],temperature_c=r['temperature']) for r in rows]
                    next_forecast=time.monotonic()+3600
                prediction=store.forecast(at,forecasts,config['weather_entity'])
                report={'generated_at':at,'valid_until':(stamp(at)+timedelta(seconds=45)).isoformat(),'status':prediction['status'],'capture_quality':quality,
                    'captures':store.c.execute('SELECT COUNT(*) FROM captures').fetchone()[0],
                    'training_rows':prediction['training_rows'],'predictions':store.c.execute('SELECT COUNT(*) FROM predictions').fetchone()[0],
                    'source_fingerprint':store.fingerprint,'model_version':'weather-neighbours-v1+persistence-v1',
                    'control_enabled':False,'horizon':prediction['horizon']}
                atomic('/ha_config/ems_shadow/demand_report.yaml',report)
                try:
                    planning_path=Path(args.planning_config)
                    if planning_path.exists():
                        if planning_path.stat().st_size>65536:raise ValueError('planning_config_too_large')
                        planning_config=json.loads(planning_path.read_text())
                        if planning_config.get('enabled') is True:
                            if planner is None:planner=Planner(root/'planning-v1.sqlite')
                            planner.observe(states,at,json.loads(Path(args.options).read_text()))
                            if time.monotonic()>=next_planning:
                                result=planner.run(states,prediction,at,planning_config,json.loads(Path(args.options).read_text()))
                                atomic('/ha_config/ems_shadow/planning_report.yaml',result)
                                next_planning=time.monotonic()+300
                                planner.last_report=result
                            elif getattr(planner,'last_report',None):
                                result=dict(planner.last_report,balance_quality=planner.quality.summary(at),input_safety=planner.safety.summary(at),quality_updated_at=at)
                                usable=(result['input_safety']['current_ha_set_valid'] and stamp(at)<=stamp(result['valid_until']) and result.get('status')=='HYPOTHETICAL_SCHEDULE_READY')
                                result['current_plan_usable_for_simulation']=usable
                                if not usable:
                                    result.update(status='SUSPENDED_INPUT_QUALITY_OR_EXPIRED',decisions=[],building_decisions=[])
                                atomic('/ha_config/ems_shadow/planning_report.yaml',result)
                except (OSError,ValueError,KeyError,TypeError,sqlite3.Error):
                    try:
                        atomic('/ha_config/ems_shadow/planning_report.yaml',{'generated_at':at,'valid_until':(stamp(at)+timedelta(seconds=45)).isoformat(),'status':'PLANNING_ERROR','control_enabled':False})
                    except OSError:pass
            except (OSError,ValueError,KeyError,TypeError):
                status='API_OR_DATA_ERROR'
            seq+=1
            atomic(root/'demand-quality.json',{'recorded_at':at,'status':status,'completed_cycles':seq,'metrics':{'captures':store.c.execute('SELECT COUNT(*) FROM captures').fetchone()[0]}})
            atomic(root/'demand-heartbeat.json',{'pid':os.getpid(),'sequence':seq,'phase':'completed','completed_cycles':seq,'committed_cycles':commits,'status':status,'captured_at':datetime.now(timezone.utc).isoformat()})
            if args.stop_after_cycles and seq>=args.stop_after_cycles:break
            stop.wait(20)
    finally:
        if planner is not None:planner.c.close()
        store.c.close()
    return 0

if __name__=='__main__':raise SystemExit(main())
