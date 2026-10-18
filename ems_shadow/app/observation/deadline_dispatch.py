"""Advisory only: deadline SOC shortfall first, then grid cost. No device IO.
An infeasible target is reported, never filled with fictitious battery energy.
"""
import math

def simulate_deadlines(slots,capacity,initial,minimum,charge_kw,discharge_kw,charge_eff,discharge_eff,step=.25,terminal_value_pln_per_kwh=0.):
 vals=(capacity,initial,minimum,charge_kw,discharge_kw,charge_eff,discharge_eff,step,terminal_value_pln_per_kwh)
 if any(type(v) not in (int,float) or not math.isfinite(v) for v in vals):raise ValueError('invalid_constraints')
 if not 0<=minimum<=capacity or not 0<=initial<=capacity or min(charge_kw,discharge_kw)<0 or not 0<charge_eff<=1 or not 0<discharge_eff<=1 or step<=0 or terminal_value_pln_per_kwh<0:raise ValueError('invalid_constraints')
 grid=sorted(set([initial,capacity,minimum]+[i*step for i in range(math.ceil(capacity/step)) if i*step<=capacity]))
 # The third score term breaks equal-cost ties in favour of fewer cycles.
 states={initial:((0.,0.,0.),[])}
 for slot in slots:
  for key in ('load_kwh','pv_kwh','price_pln_kwh','hours'):
   v=slot.get(key)
   if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('invalid_slot')
  if slot['hours']<=0:raise ValueError('invalid_duration')
  target=slot.get('target_after_kwh')
  if target is not None and (type(target) not in (int,float) or not math.isfinite(target) or not minimum<=target<=capacity):raise ValueError('invalid_target')
  nxt={};residual=slot['load_kwh']-slot['pv_kwh']
  for stored,(score,path) in states.items():
   for after in grid:
    if after<min(minimum,stored)-1e-9:continue
    delta=after-stored;charge=max(delta,0)/charge_eff;discharge=max(-delta,0)*discharge_eff
    if charge>charge_kw*slot['hours']+1e-9 or discharge>discharge_kw*slot['hours']+1e-9 or discharge>max(residual,0)+1e-9:continue
    exchange=residual+charge-discharge;imported=max(exchange,0)
    cost=imported*slot['price_pln_kwh'];shortfall=max(target-after,0) if target is not None else 0.
    newscore=(round(score[0]+shortfall,9),score[1]+cost,score[2]+charge+discharge)
    row=dict(import_kwh=imported,pv_export_kwh=max(-exchange,0),charge_ac_kwh=charge,discharge_ac_kwh=discharge,stored_kwh=after,cost_pln=cost,target_after_kwh=target,deadline_shortfall_kwh=shortfall if target is not None else None)
    if after not in nxt or newscore<nxt[after][0]:nxt[after]=(newscore,path+[row])
  if not nxt:raise ValueError('infeasible_constraints')
  states=nxt
 terminal_soc,(score,path)=min(states.items(),key=lambda item:(item[1][0][0],item[1][0][1]-terminal_value_pln_per_kwh*item[0],item[1][0][2]))
 deadlines=sum(s.get('target_after_kwh') is not None for s in slots)
 return dict(status='SIMULATION_ONLY',control_enabled=False,schedule=path,cost_pln=score[1],deadline_count=deadlines,deadline_shortfall_kwh=score[0],deadline_status=('MET_IN_SIMULATION' if score[0]<1e-8 else 'UNREACHABLE_WITH_CURRENT_CONSTRAINTS') if deadlines else 'NO_DEADLINE_IN_MODELLED_WINDOW',objective='MINIMISE_DEADLINE_SHORTFALL_THEN_NET_IMPORT_COST_WITH_TERMINAL_ENERGY_VALUE',scenario_reserve_kwh=minimum,initial_below_scenario_reserve=initial<minimum,capacity_basis='ADVISORY_SCENARIO_NOT_BMS_SOC_ENVELOPE',step_kwh=step,initial_stored_kwh=initial,terminal_value_assumed_zero=terminal_value_pln_per_kwh==0,terminal_value_pln_per_kwh=terminal_value_pln_per_kwh,terminal_stored_kwh=terminal_soc,objective_cost_pln=score[1]-terminal_value_pln_per_kwh*terminal_soc)
