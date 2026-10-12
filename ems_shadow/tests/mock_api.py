"""Synthetic API, isolated CI Docker network. No user data or credentials."""
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/core/api/states':
            self.send_error(404); return
        IDS=json.loads((Path(__file__).parent/'example_options.json').read_text())['sources']
        stamp=(datetime.now(timezone.utc)-timedelta(seconds=5)).isoformat()
        values=dict(inverter_w='1000',grid_kw='-1',boiler_w='500',heatpump_w='300',
                    boiler_kwh='10',heatpump_kwh='5',workday='on')
        body=json.dumps([dict(entity_id=id,state=values[k],last_updated=stamp)
                         for k,id in IDS.items()]).encode()
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.end_headers(); self.wfile.write(body)
    def log_message(self,*_): pass

if __name__=='__main__': HTTPServer(('0.0.0.0',80),Handler).serve_forever()
