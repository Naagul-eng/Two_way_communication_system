import numpy as np
from gnuradio import gr
import pmt
import os
import time
import threading
import sys

class blk(gr.basic_block):
    def __init__(self):
        gr.basic_block.__init__(
            self,
            name='GUI Message Source',
            in_sig=None,
            out_sig=None
        )
        self.message_port_register_out(pmt.intern('out'))
        self.msg_file = "/tmp/sdr_message.bin"
        self.running = True
        print("[GUI Source] Initialized and watching /tmp/sdr_message.bin", flush=True)
        
        # Start a background thread to poll for GUI text files
        self.thread = threading.Thread(target=self.poll_loop)
        self.thread.daemon = True
        self.thread.start()

    def poll_loop(self):
        while self.running:
            if os.path.exists(self.msg_file):
                try:
                    print("[GUI Source] File detected! Reading payload...", flush=True)
                    with open(self.msg_file, "rb") as f:
                        payload_bytes = f.read()
                    os.remove(self.msg_file)
                    
                    if len(payload_bytes) > 0:
                        print(f"[GUI Source] Publishing {len(payload_bytes)} bytes to flowgraph.", flush=True)
                        vector = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
                        msg = pmt.cons(pmt.PMT_NIL, vector)
                        self.message_port_pub(pmt.intern('out'), msg)
                except Exception as e:
                    print(f"[GUI Source Error] {e}", file=sys.stderr, flush=True)
            time.sleep(0.05)

    def stop(self):
        self.running = False
        return True
