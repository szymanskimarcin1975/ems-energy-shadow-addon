"""Non-actuating household forecast from actual archived HA aggregates.
Not billing, measurement integration, calibrated prediction, or device authority.
"""
import json,math
from pathlib import Path
from statistics import median
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
ZONE=ZoneInfo('Europe/Warsaw')
HISTORY_PATH=Path('/ha_config/ems_shadow/household_history_profile_20261016.yaml')
def stamp(v):
 t=datetime.fromisoformat(v)
 if t.tzinfo is None:raise ValueError('naive_time')
 return t.astimezone(timezone.utc)

def load_history():
 try:
  if HISTORY_PATH.stat().st_size>262144:return None
  return json.loads(HISTORY_PATH.read_text())
 except (OSError,ValueError):return None

def finite(v):return type(v) in (float,int) and math.isfinite(v)
def forecast(history,profile,issued_at,targets,allow_current=False):
 now=stamp(issued_at);hours={};rejected={};accepted=0;seen=set()
 provenance={'source_entity':None,'control_approved':False,'device_synchronisation_confirmed':False,'actual_energy_kwh':None}
 if isinstance(history,dict):
  try:
   if history.get('unit')!='W' or not isinstance(history.get('source_entity'),str):raise ValueError('history_metadata')
   retrieved=stamp(history['retrieved_at'])
   if not 0<=(now-retrieved).total_seconds()<=86400:raise ValueError('history_unavailable_at_issue_or_expired')
   provenance.update(source_entity=history['source_entity'],retrieved_at=history['retrieved_at'],method=history.get('method'))
   for row in history.get('rows',[]):
    try:
     start,end=stamp(row['start']),stamp(row['end'])
     if end>retrieved or end>now or (end-start).total_seconds()!=3600:raise ValueError('incomplete_or_future_hour')
     if start in seen:raise ValueError('duplicate_hour')
     seen.add(start)
     lo,mean,hi=(row[k] for k in ('min','mean','max'))
     if not all(finite(v) for v in (lo,mean,hi)) or not 0<=lo<=mean<=hi:raise ValueError('negative_or_invalid_aggregate')
     local=start.astimezone(ZONE);key=(local.hour,local.date())
     hours[key]=mean/1000;accepted+=1
    except (ValueError,TypeError,KeyError):
     rejected['invalid_or_negative_hour']=rejected.get('invalid_or_negative_hour',0)+1
  except (ValueError,TypeError,KeyError):rejected['invalid_history_metadata']=1
 recent=None
 try:
  start,end=stamp(profile['observed_start']),stamp(profile['observed_end'])
  if profile.get('ready') is True and profile.get('control_approved') is False and profile.get('unique_ha_snapshots',0)>=5 and (end-start).total_seconds()>=900 and 0<=(now-end).total_seconds()<=240 and finite(profile['power_w']) and profile['power_w']>=0:recent=profile['power_w']/1000
 except (ValueError,TypeError,KeyError):pass
 out=[]
 for target in targets:
  t=stamp(target)
  if t<now or (t==now and not allow_current):raise ValueError('past_target')
  vals=[v for (hour,day),v in hours.items() if hour==t.astimezone(ZONE).hour]
  if len(vals)>=2:
   pred=median(vals);method='same_local_hour_median_actual_HA_aggregate';sample_range=[min(vals),max(vals)]
  elif recent is not None:
   pred=recent;method='recent_qualified_snapshot_median_persistence';sample_range=None
  else:pred=None;method='insufficient_household_observations';sample_range=None
  out.append({'valid_for':target,'prediction_kwh':pred,'method':method,'historical_days':len(vals),'historical_sample_range_kwh':sample_range,'prediction_interval_kwh':None,'uncertainty_calibrated':False,'control_enabled':False,'temperature_response_identified':False})
 return {'issued_at':issued_at,'scope':'WHOLE_BUILDING_CONDITIONAL_ESTIMATE','status':'ADVISORY_UNCALIBRATED' if all(r['prediction_kwh'] is not None for r in out) else 'INSUFFICIENT_HOUSEHOLD_DATA','accepted_history_hours':accepted,'rejected_history_hours':rejected,'history_reporting_coverage':None,'provenance':provenance,'recent_profile':profile,'horizon':out,'control_enabled':False,'billing_approved':False,'temperature_used':False,'limitations':['Historical AC-minus-M1 is not synchronised physical measurement','No billing energy derived or gaps reconstructed','Hourly mean used as forecast estimate only','Recent snapshot persistence for unsupported hours is uncalibrated','No workday/holiday dependence or temperature response identified']}

def schedule(states,at,config,options,profile,input_safety,soc_policy):
 from planning_runtime import value
 from deadline_dispatch import simulate_deadlines
 from boiler_offline.g13 import tariff
 now=stamp(at)
 if not input_safety or not input_safety.get('current_ha_set_valid'):raise ValueError('inconsistent_household_snapshot')
 solar=options['observation']['solar_sources'];day=states[options['observation']['boiler_sources']['workday']]['state']
 if day not in ('on','off'):raise ValueError('missing_workday')
 soc=value(states,solar['b1_soc'],'%',at)
 def rating(key,unit):
  r=states[config[key]]
  if r.get('attributes',{}).get('unit_of_measurement')!=unit:raise ValueError('rating_unit')
  v=float(r['state'])
  if not math.isfinite(v):raise ValueError('rating_value')
  return v
 capacity=rating('capacity_entity','kWh');charge=rating('charge_limit_entity','W')/1000;discharge=rating('discharge_limit_entity','W')/1000
 if not 0<capacity<=30 or not 0<=soc<=100 or not 0<=charge<=5 or not 0<=discharge<=5:raise ValueError('invalid_battery_scenario')
 # A zero exposed peak blocks simulated charging too. Never writes BMS settings.
 peak=config.get('bms_peak_charge_entity');peak_guard='UNCONFIRMED_SIMULATION_ONLY'
 if peak:
  raw=states.get(peak,{})
  if raw.get('attributes',{}).get('unit_of_measurement')!='W':raise ValueError('peak_charge_unit')
  cap=float(raw['state'])
  if not math.isfinite(cap) or cap<0:raise ValueError('peak_charge_value')
  charge=min(charge,cap/1000);peak_guard='EXPOSED_CAP_NOT_DEVICE_AUTHORITY'
 if not soc_policy['owner_approved'] or soc_policy['soc_max']!=100:raise ValueError('approved_planning_range_required')
 minimum=soc_policy['soc_min']
 rates=config['working_rates_pln_kwh']
 if set(rates)!={'dolina','szczyt_przedpoludniowy','szczyt_popoludniowy'} or not all(finite(v) and v>=0 for v in rates.values()):raise ValueError('invalid_prices')
 if stamp(config['rates_effective_from'])>now:raise ValueError('future_prices')
 issued=stamp(states[config['pv_updated_entity']]['state'])
 if not 0<=(now-issued).total_seconds()<=86400:raise ValueError('stale_pv_forecast')
 pv={}
 for entity in config['pv_forecast_entities']:
  for row in states[entity].get('attributes',{}).get('detailedHourly',[]):
   t=stamp(row['period_start']).isoformat();vals={k:row[k] for k in ('pv_estimate','pv_estimate10')}
   if not all(finite(v) and v>=0 for v in vals.values()):raise ValueError('invalid_pv')
   if t in pv and pv[t]!=vals:raise ValueError('conflicting_pv')
   pv[t]=vals
 first=(now+timedelta(hours=1)).replace(minute=0,second=0,microsecond=0)
 targets=[(first+timedelta(hours=i)).isoformat() for i in range(24)]
 include_current=config.get('include_current_slot') is True
 horizon_end=now+timedelta(hours=24)
 if include_current:targets=[now.isoformat()]+[t for t in targets if stamp(t)<horizon_end]
 forecast_result=forecast(load_history(),profile,at,targets,allow_current=include_current)
 if forecast_result['status']!='ADVISORY_UNCALIBRATED':raise ValueError('insufficient_household_observations')
 decisions=[]
 for future_type in ('workday','nonworkday'):
  for scenario in ('pv_estimate','pv_estimate10'):
   slots=[];meta=[]
   for h in forecast_result['horizon']:
    t=stamp(h['valid_for']);local=t.astimezone(ZONE)
    workday=day if local.date()==now.astimezone(ZONE).date() else ('on' if future_type=='workday' else 'off')
    zone=tariff(t,workday)
    end=min(t.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1),horizon_end) if include_current else t+timedelta(hours=1)
    hours=(end-t).total_seconds()/3600
    solar_kwh=pv[t.replace(minute=0,second=0,microsecond=0).isoformat()][scenario]*hours
    # Slot starts at 15:00 and ends at 16:00: target is BEFORE the expensive window.
    deadline=capacity if workday=='on' and end.astimezone(ZONE).hour==16 and end.astimezone(ZONE).minute==0 else None
    slots.append(dict(load_kwh=h['prediction_kwh']*hours,pv_kwh=solar_kwh,price_pln_kwh=rates[zone],hours=hours,target_after_kwh=deadline))
    meta.append(dict(valid_for=t.isoformat(),valid_to=end.isoformat(),hours=hours,tariff=zone,load_kwh=h['prediction_kwh']*hours,pv_kwh=solar_kwh,load_method=h['method']))
   result=simulate_deadlines(slots,capacity,capacity*soc/100,capacity*minimum/100,charge,discharge,float(config['simulation_charge_eff']),float(config['simulation_discharge_eff']))
   for row,m in zip(result['schedule'],meta):row.update(m,reason='Advisory optimisation from actual historical HA aggregates or observed persistence; not device authority')
   decisions.append(dict(result,scope='CONDITIONAL_WHOLE_BUILDING_NOT_APPROVED',future_day_type=future_type,pv_scenario=scenario))
 return {'forecast':forecast_result,'decisions':decisions,'charge_ceiling_kw':charge,'peak_guard':peak_guard,'planning_min_soc_percent':minimum,'planning_max_soc_percent':100,'pv_issued_at':issued.isoformat(),'control_enabled':False,'prices_contract_verified':False,'workday_soc_deadline':{'local_time':'16:00','target_percent':100,'partial_current_hour_not_modelled':not include_current,'current_deadline_unmodelled':not include_current and day=='on' and now.astimezone(ZONE).hour==15,'physical_feasibility_confirmed':False}}
