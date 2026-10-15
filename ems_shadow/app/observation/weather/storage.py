"""Separate offline weather SQLite; no writes to energy ledgers."""
import json,sqlite3
from .channel import WeatherChannel,stamp
class WeatherStore:
 def __init__(self,path,config):
  self.config=config;validator=WeatherChannel(config);self.fingerprint=validator.fingerprint
  self.c=sqlite3.connect(path,timeout=1,isolation_level=None)
  try:
   self.c.execute('pragma journal_mode=WAL');self.c.execute('pragma synchronous=FULL');self.c.execute('BEGIN IMMEDIATE')
   self.c.execute('create table if not exists weather_meta(key text primary key,value text)')
   old=self.c.execute("select value from weather_meta where key='fingerprint'").fetchone()
   if old and old[0]!=self.fingerprint:raise ValueError('source_change_requires_separate_weather_database')
   self.c.execute("insert or ignore into weather_meta values('fingerprint',?)",(self.fingerprint,))
   self.c.execute('create table if not exists weather_observations(id text primary key,payload text,record text)')
   self.c.execute('create table if not exists weather_baseline(singleton integer primary key,ha_time text,value real)')
   self.c.execute('create table if not exists weather_forecasts(snapshot_id text,valid_for text,record text,primary key(snapshot_id,valid_for))')
   self.c.execute('COMMIT')
  except Exception:self.c.close();raise
 def observe(self,id,captured,state):
  payload=json.dumps([captured,state],sort_keys=True,allow_nan=False)
  self.c.execute('BEGIN IMMEDIATE')
  try:
   old=self.c.execute('select payload from weather_observations where id=?',(id,)).fetchone()
   if old:
    if old[0]!=payload:raise ValueError('id_conflict')
    self.c.execute('ROLLBACK');return 'duplicate'
   v=WeatherChannel(self.config);base=self.c.execute('select ha_time,value from weather_baseline').fetchone()
   if base:v.previous=(stamp(base[0]),base[1])
   v.observe(id,captured,state);record=v.observations[-1]
   self.c.execute('insert into weather_observations values(?,?,?)',(id,payload,json.dumps(record,allow_nan=False)))
   if record['quality']=='valid_ha_observation':
    self.c.execute('insert or replace into weather_baseline values(1,?,?)',(v.previous[0].isoformat(),v.previous[1]))
   self.c.execute('COMMIT');return record['quality']
  except Exception:
   if self.c.in_transaction:self.c.execute('ROLLBACK')
   raise
 def forecast(self,id,retrieved,valid_for,temp,issued_at=None):
  v=WeatherChannel(self.config);v.archive_forecast(id,retrieved,valid_for,temp,issued_at)
  record=v.forecasts[0];raw=json.dumps(record,sort_keys=True,allow_nan=False)
  self.c.execute('BEGIN IMMEDIATE')
  try:
   old=self.c.execute('select record from weather_forecasts where snapshot_id=? and valid_for=?',(id,record['valid_for'])).fetchone()
   if old:
    if old[0]!=raw:raise ValueError('forecast_id_conflict')
    self.c.execute('ROLLBACK');return 'duplicate'
   self.c.execute('insert into weather_forecasts values(?,?,?)',(id,record['valid_for'],raw));self.c.execute('COMMIT');return 'stored'
  except Exception:
   if self.c.in_transaction:self.c.execute('ROLLBACK')
   raise
 def close(self):self.c.close()

 def capture_gaps(self,start,end,max_gap_seconds):
  a,b=stamp(start),stamp(end)
  if a>=b or max_gap_seconds<=0:raise ValueError('invalid_window')
  times=sorted(stamp(json.loads(x[0])['captured_at']) for x in self.c.execute('select record from weather_observations'))
  inside=[t for t in times if a<=t<=b];points=[a]+inside+[b]
  return {'capture_gaps':[(x.isoformat(),y.isoformat()) for x,y in zip(points,points[1:]) if (y-x).total_seconds()>max_gap_seconds],'device_reporting_coverage':None,'note':'gaps in archive captures, not reconstructed device reports'}
