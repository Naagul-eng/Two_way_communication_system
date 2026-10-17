import argparse
import importlib.util
import os
from pathlib import Path
import signal
import threading
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
    os.environ['SDRCHAT_CONFIG']=str(Path(a.config).resolve())
    path=Path(__file__).resolve().parents[1]/'flowgraphs'/'generated'/'csma_transceiver.py'
    if not path.exists():raise SystemExit('Run bash setup.sh first')
    sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location('csma_transceiver',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    tb=module.csma_transceiver()
    tb.epy_mac_bridge.attach_radio(tb.iio_pluto_sink_0,tb.iio_pluto_source_0)
    stopped=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stopped.set())
    tb.start()
    print('Radio running; Ctrl+C stops it.',flush=True)
    try:
        while not stopped.wait(.5):
            if tb.epy_mac_bridge.service.error:raise RuntimeError(str(tb.epy_mac_bridge.service.error))
    finally:tb.stop();tb.wait()


if __name__=='__main__':main()
