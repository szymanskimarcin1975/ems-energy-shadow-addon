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

def actual_hourly_rows(history,issued_at):
 """Return only complete, unique, non-future hourly HA aggregates."""
 now=stamp(issued_at);accepted=[]
 if not isinstance(history,dict) or history.get('unit')!='W' or not isinstance(history.get('source_entity'),str):return accepted
 try:
  retrieved=stamp(history['retrieved_at'])
  if not 0<=(now-retrieved).total_seconds()<=86400:return accepted
 except (ValueError,TypeError,KeyError):return accepted
 seen=set()
 for row in history.get('rows',[]):
  try:
   start,end=stamp(row['start']),stamp(row['end'])
   lo,mean,hi=(row[k] for k in ('min','mean','max'))
   if end>retrieved or end>now or (end-start).total_seconds()!=3600 or start in seen:continue
   if not all(finite(v) for v in (lo,mean,hi)) or not 0<=lo<=mean<=hi:continue
   seen.add(start)
   local=start.astimezone(ZONE)
   accepted.append({'target_at':start.isoformat(),'actual_kwh':mean/1000,
                    'local_hour':local.hour,'local_day':local.date().isoformat(),
                    'observed_at':end.isoformat()})
  except (ValueError,TypeError,KeyError):continue
 return accepted

def forecast(history,profile,issued_at,targets,allow_current=False,error_biases=None):
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
 recent=None;valid_hour_values=list(hours.values())
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
  elif len(vals)==1:
   pred=vals[0];method='single_actual_same_local_hour_uncalibrated';sample_range=[vals[0],vals[0]]
  elif recent is not None:
   pred=recent;method='recent_qualified_snapshot_persistence_uncalibrated';sample_range=None
  elif valid_hour_values:
   pred=max(valid_hour_values);method='conservative_max_observed_hour_uncalibrated';sample_range=[min(valid_hour_values),max(valid_hour_values)]
  else:pred=None;method='insufficient_household_observations';sample_range=None
  correction=None;bias=(error_biases or {}).get(t.astimezone(ZONE).hour)
  if pred is not None and isinstance(bias,dict) and bias.get('samples',0)>=3 and finite(bias.get('median_error_kwh')):
   limit=pred*.5;correction=max(-limit,min(limit,bias['median_error_kwh']))
   pred=max(0,pred+correction);method+=' + damped_recent_error_bias'
   correction={'applied_kwh':round(correction,6),'samples':bias['samples'],'source':'completed_actual_HA_hours_only'}
  out.append({'valid_for':target,'prediction_kwh':pred,'method':method,'historical_days':len(vals),'historical_sample_range_kwh':sample_range,'prior_error_correction':correction,'prediction_interval_kwh':None,'uncertainty_calibrated':False,'control_enabled':False,'temperature_response_identified':False})
 return {'issued_at':issued_at,'scope':'WHOLE_BUILDING_CONDITIONAL_ESTIMATE','status':'ADVISORY_UNCALIBRATED' if all(r['prediction_kwh'] is not None for r in out) else 'INSUFFICIENT_HOUSEHOLD_DATA','accepted_history_hours':accepted,'rejected_history_hours':rejected,'history_reporting_coverage':None,'provenance':provenance,'recent_profile':profile,'horizon':out,'control_enabled':False,'billing_approved':False,'temperature_used':False,'limitations':['Historical AC-minus-M1 is not synchronised physical measurement','No billing energy derived or gaps reconstructed','Hourly mean used as forecast estimate only','Sparse-history fallbacks are uncalibrated','Daily residual correction requires at least three complete actual-hour matches','No workday/holiday dependence or temperature response identified']}

def schedule(states,at,config,options,profile,input_safety,soc_policy,history_override=None,error_biases=None):
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
 # Cover the next costly window whenever the existing today/tomorrow
 # Solcast forecast can support it. Never synthesize hours of PV as zero.
 include_current=config.get('include_current_slot') is True
 last_pv_hour=max(stamp(t) for t in pv)
 horizon_end=min(now+timedelta(hours=48),last_pv_hour+timedelta(hours=1))
 if horizon_end<=now:raise ValueError('no_future_pv_horizon')
 first=(now+timedelta(hours=1)).replace(minute=0,second=0,microsecond=0)
 targets=[now.isoformat()] if include_current else []
 t=first
 while t<horizon_end:
  targets.append(t.isoformat())
  t+=timedelta(hours=1)
 forecast_result=forecast(history_override if history_override is not None else load_history(),profile,at,targets,allow_current=include_current,error_biases=error_biases)
 if forecast_result['status']!='ADVISORY_UNCALIBRATED':raise ValueError('insufficient_household_observations')
 decisions=[]
 for future_type in ('workday','nonworkday'):
  for scenario in ('pv_estimate','pv_estimate10'):
   slots=[];meta=[]
   for h in forecast_result['horizon']:
    t=stamp(h['valid_for']);local=t.astimezone(ZONE)
    workday=day if local.date()==now.astimezone(ZONE).date() else ('on' if future_type=='workday' else 'off')
    zone=tariff(t,workday)
    end=min(t.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1),horizon_end)
    hours=(end-t).total_seconds()/3600
    solar_kwh=pv[t.replace(minute=0,second=0,microsecond=0).isoformat()][scenario]*hours
    # Set a demand-based deadline only after observing the full future
    # 16:00–21:00 costly window (below). Do not force a full battery at 16:00.
    slots.append(dict(load_kwh=h['prediction_kwh']*hours,pv_kwh=solar_kwh,price_pln_kwh=rates[zone],hours=hours,target_after_kwh=None))
    meta.append(dict(valid_for=t.isoformat(),valid_to=end.isoformat(),hours=hours,tariff=zone,load_kwh=h['prediction_kwh']*hours,pv_kwh=solar_kwh,load_method=h['method']))
   eff_discharge=float(config['simulation_discharge_eff'])
   # A 16:00 target is proportional to the forecast net demand over the
   # following five expensive hours, not an unconditional 100% target.
   for i,item in enumerate(meta):
    finish=stamp(item['valid_to']).astimezone(ZONE)
    if finish.hour!=16 or finish.minute!=0:continue
    deficits=[]
    for j in range(5):
     n=i+j+1
     if n>=len(meta):break
     next_item=meta[n]
     begin=stamp(next_item['valid_for']).astimezone(ZONE)
     if (begin.date()!=finish.date() or begin.hour!=16+j or begin.minute!=0 or
         next_item['tariff']!='szczyt_popoludniowy' or abs(next_item['hours']-1)>1e-6):break
     deficits.append(max(slots[n]['load_kwh']-slots[n]['pv_kwh'],0)/eff_discharge)
    if len(deficits)==5:
     slots[i]['target_after_kwh']=min(capacity,capacity*minimum/100+sum(deficits))
   # The energy left at the horizon still has an opportunity value; setting
   # it to zero would reward Sunday off-peak discharge before Monday peak.
   # Price-based value discourages gratuitous off-peak cycles after losses,
   # without rewarding grid charging merely to fill the terminal battery.
   terminal_value=min(rates.values())
   result=simulate_deadlines(slots,capacity,capacity*soc/100,capacity*minimum/100,charge,discharge,float(config['simulation_charge_eff']),eff_discharge,terminal_value_pln_per_kwh=terminal_value)
   for row,m in zip(result['schedule'],meta):row.update(m,reason='Advisory optimisation from actual historical HA aggregates or observed persistence; not device authority')
   decisions.append(dict(result,scope='CONDITIONAL_WHOLE_BUILDING_NOT_APPROVED',future_day_type=future_type,pv_scenario=scenario))
 return {'forecast':forecast_result,'decisions':decisions,'charge_ceiling_kw':charge,'peak_guard':peak_guard,'planning_min_soc_percent':minimum,'planning_max_soc_percent':100,'pv_issued_at':issued.isoformat(),'control_enabled':False,'prices_contract_verified':False,'workday_soc_deadline':{'local_time':'16:00','target_percent':None,'policy':'FORECAST_NET_EXPENSIVE_HOURS_ENERGY_NOT_FIXED_100_PERCENT','partial_current_hour_not_modelled':not include_current,'current_deadline_unmodelled':not include_current and day=='on' and now.astimezone(ZONE).hour==15,'physical_feasibility_confirmed':False}}
