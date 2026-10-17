import os
import queue
import threading
import time
import numpy as np
import pmt
from gnuradio import gr
from .config import load
from .service import Service
from .equalizer import TrainingCorrelator, NLMS


def airtime(c, raw_length):
    """Estimate a framed RF burst including host delay and turnaround guard."""
    coded=raw_length+4+16*((raw_length+4+238)//239)
    return (2048+12+coded+2570)*16/c['sample_rate']+c['tx_delay_s']+c['tx_guard_s']


class MacBridge(gr.sync_block):
    """Raw RX energy observer + PDU socket/MAC service. No stream output."""
    def __init__(self,config_path='configs/node_a.json'):
        gr.sync_block.__init__(self,name='CSMA/CA + app bridge',in_sig=[np.complex64],out_sig=None)
        self.c=load(config_path);self.incoming=queue.Queue(maxsize=4096)
        self.reading=None;self.read_at=0;self.lock=threading.Lock();self.tx_lock=threading.Lock()
        self.tx_at=0;self.tx_end=0;self.sink=None;self.source=None;self.muted=True
        self.message_port_register_in(pmt.intern('rx_in'));self.set_msg_handler(pmt.intern('rx_in'),self.receive)
        self.message_port_register_out(pmt.intern('tx_out'))
        self.service=Service(self.c,self.send,self.incoming,self.sensor)

    def attach_radio(self,sink,source):
        self.sink=sink;self.source=source

    def start(self):
        if self.sink is None:raise RuntimeError('Launch with python3 -m sdrchat.hardware; radio mute hook is required')
        self.sink.set_attenuation(0,89.75)
        self.service.start();return True

    def stop(self):
        self.service.stop()
        if self.sink:self.sink.set_attenuation(0,89.75)
        return True

    def sensor(self):
        now=time.monotonic()
        if not self.muted and now>=self.tx_end:
            self.sink.set_attenuation(0,89.75);self.muted=True
        with self.lock:
            if now-self.read_at>.1:return None
            return self.reading,None

    def send(self,wire):
        if self.sink is None:raise RuntimeError('Radio sink not attached')
        self.sink.set_attenuation(0,self.c['tx_attenuation_db']);self.muted=False
        duration=airtime(self.c,len(wire))
        self.tx_at=time.monotonic();self.tx_end=self.tx_at+duration
        self.message_port_pub(pmt.intern('tx_out'),pmt.cons(pmt.PMT_NIL,pmt.init_u8vector(len(wire),list(wire))))
        return duration

    def receive(self,msg):
        # Ignore own RF echo during the estimated transmission/turnaround window.
        if time.monotonic()<self.tx_end:return
        if pmt.is_pair(msg) and pmt.is_u8vector(pmt.cdr(msg)):
            try:self.incoming.put_nowait(bytes(pmt.u8vector_elements(pmt.cdr(msg))))
            except queue.Full:pass

    def work(self,inputs,outputs):
        x=inputs[0]
        if len(x):
            power=10*np.log10(max(float(np.mean(np.abs(x)**2)),1e-20))
            with self.lock:self.reading=power;self.read_at=time.monotonic()
        return len(x)
