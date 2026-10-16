"""Read-only, hypothetical dispatch; no device command capabilities.
The boiler-only scope is not the building load. No PV measurement is inferred.
"""
import hashlib,json,sqlite3,shutil
from datetime import timedelta
from pathlib import Path
from weather_demand import stamp,number
from building_balance import inspect
from dispatch_simulator import simulate
from boiler_offline.g13 import tariff,ZONE

def value(states,entity,unit,at,age=240):
    s=states[entity]
    if s.get('attributes',{}).get('unit_of_measurement')!=unit:raise ValueError('unit_mismatch')
    if not 0<=(stamp(at)-stamp(s['last_reported'])).total_seconds()<=age:raise ValueError('stale_or_future_input')
    return number(s['state'])

def plan(states,prediction,at,config,options):
    solar=options['observation']['solar_sources']; old=options['sources']
    r={'generated_at':at,'valid_until':(stamp(at)+timedelta(seconds=360)).isoformat(),
       'control_enabled':False,'mode':'SIMULATION_ONLY','whole_building_schedule_approved':False,
       'limitations':['Building scope and device synchronisation unconfirmed','Boiler load excludes the rest of the house',
       'All-site PV allocation to boiler is hypothetical','Efficiency and reserve are scenario assumptions',
       'No CWU or CO scheduling; no device commands','No calibrated forecast uncertainty'],
       'balance':inspect(states.get(solar['ac_power'],{}),states.get(old['grid_kw'],{}),at),
       'decisions':[]}
    # Historical direction conventions; actual production PV is intentionally absent.
    try:
        grid=value(states,old['grid_kw'],'kW',at); battery=value(states,solar['b1_power'],'W',at)
        r['flows']={'grid_import_kw':max(-grid,0),'grid_export_kw':max(grid,0),
                    'battery_charge_w':max(battery,0),'battery_discharge_w':max(-battery,0),
                    'actual_pv_production_w':None,'battery_status':states.get(solar['b1_status'],{}).get('state')}
        soc=value(states,solar['b1_soc'],'%',at)
        capacity=value(states,config['capacity_entity'],'kWh',at)
        charge=value(states,config['charge_limit_entity'],'W',at)/1000
        discharge=value(states,config['discharge_limit_entity'],'W',at)/1000
        if not 0<capacity<=30 or not 0<=soc<=100 or not 0<=charge<=15 or not 0<=discharge<=15:raise ValueError('outside_simulation_limits')
        minimum=number(config['simulation_min_soc_percent'])
        ce,de=number(config['simulation_charge_eff']),number(config['simulation_discharge_eff'])
        if not 0<=minimum<=100:raise ValueError('invalid_simulation_floor')
        r['battery']={'soc_percent':soc,'capacity_kwh':capacity,'simulated_min_soc_percent':minimum,
                      'reserve_confirmed_for_control':False,'charge_eff_assumed':ce,'discharge_eff_assumed':de}
        price=config['working_rates_pln_kwh']
        if set(price)!= {'dolina','szczyt_przedpoludniowy','szczyt_popoludniowy'}:raise ValueError('missing_prices')
        price={k:number(v) for k,v in price.items()}
        if min(price.values())<0:raise ValueError('negative_price')
        if stamp(config['rates_effective_from'])>stamp(at):raise ValueError('future_prices')
        r['working_prices']={'rates':price,'version':config['rates_version'],'effective_from':config['rates_effective_from'],'basis':config['rates_basis'],'contract_verified':False}
        issued=stamp(states[config['pv_updated_entity']]['state'])
        if not 0<=(stamp(at)-issued).total_seconds()<=86400:raise ValueError('stale_pv_forecast')
        pv={}
        for entity in config['pv_forecast_entities']:
            for row in states[entity].get('attributes',{}).get('detailedHourly',[]):
                t=stamp(row['period_start']).isoformat()
                vals={k:number(row[k]) for k in ('pv_estimate','pv_estimate10')}
                if min(vals.values())<0:raise ValueError('negative_pv_forecast')
                if t in pv and pv[t]!=vals:raise ValueError('conflicting_pv_forecast')
                pv[t]=vals
        workday=states[options['observation']['boiler_sources']['workday']]['state']
        if workday not in ('on','off'):raise ValueError('missing_workday')
        now=stamp(at).astimezone(ZONE)
        for future_day_type in ('workday','nonworkday'):
            for pv_key in ('pv_estimate','pv_estimate10'):
                slots=[]; times=[]
                for h in prediction['horizon']:
                    t=stamp(h['valid_for']); local=t.astimezone(ZONE)
                    dt=('workday' if workday=='on' else 'nonworkday') if local.date()==now.date() else future_day_type
                    load=h['scenarios'][dt]['prediction_kwh']
                    if load is None:raise ValueError('insufficient_load_forecast')
                    solar_est=pv[t.isoformat()][pv_key] # hourly mean kW x exactly one hour
                    zone=tariff(t,'on' if dt=='workday' else 'off')
                    slots.append(dict(load_kwh=number(load),pv_kwh=solar_est,price_pln_kwh=price[zone],hours=1))
                    times.append(dict(valid_for=t.isoformat(),tariff=zone,load_kwh=load,pv_kwh=solar_est))
                # Input scope is explicitly boiler-only, not approval of site topology.
                result=simulate(slots,capacity,capacity*soc/100,capacity*minimum/100,charge,discharge,ce,de,
                                topology_confirmed=True,step_kwh=.25)
                for entry,meta in zip(result['schedule'],times):entry.update(meta,reason='Minimise hypothetical import cost subject to scenario reserve, power and no battery export')
                r['decisions'].append(dict(result,future_day_type=future_day_type,pv_scenario=pv_key,
                     scope='BOILER_ONLY_HYPOTHETICAL_PV_AND_BATTERY_ALLOCATION',not_full_building_dispatch=True))
        r['status']='HYPOTHETICAL_SCHEDULE_READY'
        r['pv_forecast_issued_at']=issued.isoformat()
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        r['status']='BLOCKED_INPUT';r['reason']=type(exc).__name__+':'+str(exc)[:100];r['decisions']=[]
    return r

class Planner:
    def __init__(self,path):
        self.path=Path(path)
        self.c=sqlite3.connect(path,timeout=.5,isolation_level=None)
        try:
            self.c.execute('PRAGMA journal_mode=WAL');self.c.execute('PRAGMA synchronous=FULL')
            self.c.execute('CREATE TABLE IF NOT EXISTS runs(id PRIMARY KEY,fingerprint,record)')
        except Exception:
            self.c.close();raise
    def run(self,states,prediction,at,config,options):
        sizes=sum(p.stat().st_size for p in (self.path,Path(str(self.path)+'-wal'),Path(str(self.path)+'-shm')) if p.exists())
        if sizes>=256*1024*1024 or shutil.disk_usage(self.path.parent).free<64*1024*1024:raise OSError('planning_storage_limit')
        record=plan(states,prediction,at,config,options)
        digest=hashlib.sha256(json.dumps(dict(planning=config,observation=options['observation'],legacy_sources=options['sources']),sort_keys=True).encode()).hexdigest()
        record['planning_config_fingerprint']=digest
        self.c.execute('BEGIN IMMEDIATE')
        try:
            self.c.execute('INSERT OR IGNORE INTO runs VALUES(?,?,?)',(at,digest,json.dumps(record,allow_nan=False)))
            self.c.execute('COMMIT')
        except Exception:
            if self.c.in_transaction:self.c.execute('ROLLBACK')
            raise
        record['persisted_runs']=self.c.execute('SELECT COUNT(*) FROM runs').fetchone()[0]
        return record
