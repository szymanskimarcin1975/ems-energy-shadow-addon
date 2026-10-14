"""Export-only process. Its failures never propagate to the observer."""
import json,signal,sys,threading
from controller import Controller,read_requests
from worker import Worker
from gateway import status

def main():
    controller=None
    try:
        from settings import load_sources,load_ledger_id,fingerprint
        ledger=load_ledger_id('/data/options.json');digest=fingerprint(load_sources('/data/options.json'))
        worker=Worker('/data','/ha_config/ems_shadow/diagnostics',ledger,digest,'/app/diagnostic_export',observer_report='/ha_config/ems_shadow/report.yaml')
        controller=Controller('/data/diagnostic_exports_control',ledger,worker,enabled=True)
        def stopping(*_):
            controller.stop.set()
            raise SystemExit(0)
        signal.signal(signal.SIGTERM,stopping);signal.signal(signal.SIGINT,stopping)
        status('READY','awaiting_request')
        read_requests(sys.stdin,controller.submit)
    except Exception:
        status('ERROR','controller_failure');return 70
    finally:
        if controller is not None:controller.close()
    return 0
if __name__=='__main__':raise SystemExit(main())
