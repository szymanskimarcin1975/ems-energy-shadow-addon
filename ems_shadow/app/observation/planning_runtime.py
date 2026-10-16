"""Read-only, hypothetical dispatch; no device command capabilities.
The boiler-only scope is not the building load. No PV measurement is inferred.
"""
import hashlib,json,sqlite3,shutil
from datetime import timedelta
from pathlib import Path
from soc_profile import load_profile,planning_policy
from household_advisory import schedule as household_schedule
from weather_demand import stamp,number
from building_balance import inspect
from balance_quality import Quality
from control_safety import Safety
from dispatch_simulator import simulate
from boiler_offline.g13 import tariff,ZONE

def value(states,entity,unit,at,age=240):
    s=states[entity]
    if s.get('attributes',{}).get('unit_of_measurement')!=unit:raise ValueError('unit_mismatch')
    if not 0<=(stamp(at)-stamp(s['last_reported'])).total_seconds()<=age:raise ValueError('stale_or_future_input:'+entity)
    return number(s['state'])

def plan(states,prediction,at,config,options,building_profile=None,input_safety=None):
    approved_planning=planning_policy(load_profile())
    solar=options['observation']['solar_sources']; old=options['sources']
    evidence=config.get('m1_scope_evidence',{})
    if not isinstance(evidence,dict):evidence={}
    scope_confirmed=(evidence.get('scope')=='whole_building_grid_exchange' and evidence.get('confirmed_by')=='installation_owner' and bool(evidence.get('confirmed_at')))
    if scope_confirmed:
        try: scope_confirmed=stamp(evidence['confirmed_at'])<=stamp(at)
        except (ValueError,TypeError): scope_confirmed=False
    r={'generated_at':at,'valid_until':(stamp(at)+timedelta(seconds=360)).isoformat(),
       'control_enabled':False,'mode':'SIMULATION_ONLY','whole_building_schedule_approved':False,
       'limitations':['Device synchronisation and complete AC source inventory unconfirmed','Boiler load excludes the rest of the house',
       'All-site PV allocation to boiler is hypothetical','Efficiency and reserve are scenario assumptions',
       'No CWU or CO scheduling; no device commands','No calibrated forecast uncertainty'],
       'balance':inspect(states.get(solar['ac_power'],{}),states.get(old['grid_kw'],{}),at),
       'decisions':[],'building_decisions':[],
       'active_control_readiness':{'ready':False,'ownership':'LEGACY_NOT_TOUCHED',
        'blockers':['M1_SCOPE_UNCONFIRMED','DEVICE_TIME_SYNC_UNCONFIRMED','RESERVE_AND_EFFICIENCY_UNVERIFIED','PRICES_NOT_CONTRACT_VERIFIED','FORECAST_UNCALIBRATED','SINGLE_WRITER_HANDOVER_NOT_EXECUTED']}}
    r['planning_soc_policy']=approved_planning
    r['planning_soc_policy']['applied_to_simulation']=False
    r['m1_scope']={'confirmed':scope_confirmed,'evidence':evidence if scope_confirmed else None,'meaning':'Whole-building grid exchange; not total load or pure PV'}
    r['balance']['m1_scope_confirmed']=scope_confirmed
    if scope_confirmed:r['active_control_readiness']['blockers'].remove('M1_SCOPE_UNCONFIRMED')
    r['input_safety']=input_safety or {'status':'UNCONFIRMED','control_enabled':False}
    # Historical direction conventions; actual production PV is intentionally absent.
    try:
        if input_safety is not None and input_safety.get('current_ha_set_valid') is not True:raise ValueError('inconsistent_solar_snapshot')
        grid=value(states,old['grid_kw'],'kW',at); battery=value(states,solar['b1_power'],'W',at)
        r['flows']={'grid_import_kw':max(-grid,0),'grid_export_kw':max(grid,0),
                    'battery_charge_w':max(battery,0),'battery_discharge_w':max(-battery,0),
                    'actual_pv_production_w':None,'battery_status':states.get(solar['b1_status'],{}).get('state')}
        soc=value(states,solar['b1_soc'],'%',at)
        # These are descriptive capacity/power ratings, not live power or SOC.
        # Do not pretend that a constant rating is a fresh device measurement.
        def rating(key,unit):
            raw=states[config[key]]
            if raw.get('attributes',{}).get('unit_of_measurement')!=unit:raise ValueError('rating_unit:'+key)
            return number(raw['state'])
        capacity=rating('capacity_entity','kWh')
        charge=rating('charge_limit_entity','W')/1000
        discharge=rating('discharge_limit_entity','W')/1000
        r['rating_quality']='HA_METADATA_SNAPSHOT_NOT_DYNAMIC_MEASUREMENT'
        r['rating_timestamps']={key:{k:states[config[key]].get(k) for k in ('last_reported','last_updated','last_changed')} for key in ('capacity_entity','charge_limit_entity','discharge_limit_entity')}
        if not 0<capacity<=30 or not 0<=soc<=100 or not 0<=charge<=15 or not 0<=discharge<=15:raise ValueError('outside_simulation_limits')
        minimum=number(config['simulation_min_soc_percent'])
        if approved_planning['owner_approved']:
            if approved_planning['soc_max']!=100:raise ValueError('unsupported_planning_ceiling')
            minimum=approved_planning['soc_min']
            r['planning_soc_policy']['applied_to_simulation']=True
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
        # A separate, conditional whole-building persistence estimate. This is
        # forecasting from an instantaneous observation, never kWh measurement.
        r['balance_quality']=building_profile or {'ready':False,'status':'INSUFFICIENT_QUALIFIED_SNAPSHOTS'}
        candidate=(building_profile or {}).get('power_w')
        r['building_candidate']={'status':'BLOCKED_INVALID_BALANCE',
             'topology_confirmed':False,'m1_scope_confirmed':scope_confirmed,'measurement_energy_kwh':None,
             'method':'rolling_HA_snapshot_median_persistence_uncalibrated',
             'temperature_response_identified':False,'uncertainty_calibrated':False}
        if r['balance'].get('status')=='DIAGNOSTIC_ONLY' and (building_profile or {}).get('ready') is True and candidate is not None and candidate>=0:
            r['building_candidate'].update(status='CONDITIONAL_ESTIMATE_ONLY',power_w=candidate,
                assumption=('M1 whole-building grid scope confirmed by owner; AC source inventory and device synchronisation unconfirmed' if scope_confirmed else 'M1 scope, AC source inventory and device synchronisation unconfirmed'))
            for d in r['decisions']:
                slots=[];times=[]
                for entry in d['schedule']:
                    times.append({'valid_for':entry['valid_for'],'tariff':entry['tariff']})
                    slots.append(dict(load_kwh=candidate/1000,pv_kwh=entry['pv_kwh'],
                          price_pln_kwh=price[entry['tariff']],hours=1))
                result=simulate(slots,capacity,capacity*soc/100,capacity*minimum/100,charge,discharge,ce,de,topology_confirmed=True,step_kwh=.25)
                for entry,meta,slot in zip(result['schedule'],times,slots):
                    entry.update(meta,load_kwh=slot['load_kwh'],pv_kwh=slot['pv_kwh'],
                        reason='Conditional whole-site persistence scenario; not a validated building measurement or command')
                r['building_decisions'].append(dict(result,scope='CONDITIONAL_WHOLE_BUILDING_NOT_APPROVED',future_day_type=d['future_day_type'],pv_scenario=d['pv_scenario']))
        controllers=config.get('legacy_controller_entities',[])
        r['active_control_readiness']['legacy_controllers']={e:states.get(e,{}).get('state','unknown') for e in controllers}
        r['status']='HYPOTHETICAL_SCHEDULE_READY'
        r['pv_forecast_issued_at']=issued.isoformat()
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        r['status']='BLOCKED_INPUT';r['reason']=type(exc).__name__+':'+str(exc)[:100];r['decisions']=[];r['building_decisions']=[]
    # Household advisory scheduling must not depend on boiler model maturity.
    # This is a conditional forecast, never a measurement or actuation approval.
    try:
        if config.get('household_history_enabled') is not True:raise ValueError('household_history_disabled')
        if not scope_confirmed:raise ValueError('m1_scope_unconfirmed')
        house=household_schedule(states,at,config,options,building_profile,input_safety,approved_planning)
        r['household_advisory']=house
        r['building_decisions']=house['decisions']
        r['status']='ADVISORY_HOUSEHOLD_SCHEDULE_READY'
        r['boiler_forecast_blocker']=r.pop('reason',None)
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        if config.get('household_history_enabled') is True:r['building_decisions']=[]
        r['household_advisory']={'status':'BLOCKED','reason':type(exc).__name__+':'+str(exc)[:100],'control_enabled':False}
    r['current_plan_usable_for_simulation']=(r['status'] in ('HYPOTHETICAL_SCHEDULE_READY','ADVISORY_HOUSEHOLD_SCHEDULE_READY') and input_safety is not None and input_safety.get('current_ha_set_valid') is True)
    return r

def refresh_plan_report(planner,at):
    result=dict(planner.last_report,balance_quality=planner.quality.summary(at),input_safety=planner.safety.summary(at),quality_updated_at=at)
    usable=(result['input_safety']['current_ha_set_valid'] and stamp(at)<=stamp(result['valid_until']) and result.get('status') in ('HYPOTHETICAL_SCHEDULE_READY','ADVISORY_HOUSEHOLD_SCHEDULE_READY'))
    result['current_plan_usable_for_simulation']=usable
    if not usable:result.update(status='SUSPENDED_INPUT_QUALITY_OR_EXPIRED',decisions=[],building_decisions=[])
    return result

class Planner:
    def __init__(self,path):
        self.path=Path(path)
        self.c=sqlite3.connect(path,timeout=.5,isolation_level=None)
        try:
            self.c.execute('PRAGMA journal_mode=WAL');self.c.execute('PRAGMA synchronous=FULL')
            self.c.execute('CREATE TABLE IF NOT EXISTS runs(id PRIMARY KEY,fingerprint,record)')
            self.quality=Quality(self.c)
            self.safety=Safety(self.c)
        except Exception:
            self.c.close();raise
    def storage_guard(self):
        sizes=sum(p.stat().st_size for p in (self.path,Path(str(self.path)+'-wal'),Path(str(self.path)+'-shm')) if p.exists())
        if sizes>=256*1024*1024 or shutil.disk_usage(self.path.parent).free<64*1024*1024:raise OSError('planning_storage_limit')
    def observe(self,states,at,options):
        self.storage_guard()
        result=self.quality.observe(states,at,options)
        self.safety.observe(states,at,options)
        return result
    def run(self,states,prediction,at,config,options):
        self.storage_guard()
        record=plan(states,prediction,at,config,options,self.quality.summary(at),self.safety.summary(at))
        digest=hashlib.sha256(json.dumps(dict(planning=config,approved_soc_planning=record['planning_soc_policy'],observation=options['observation'],legacy_sources=options['sources']),sort_keys=True).encode()).hexdigest()
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

