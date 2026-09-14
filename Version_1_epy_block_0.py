import numpy as np
from gnuradio import gr
import pmt

class blk(gr.basic_block):
    """Prints PDU payloads as readable ASCII text"""

    def __init__(self):
        gr.basic_block.__init__(
            self,
            name='Plain Text Printer',
            in_sig=None,
            out_sig=None
        )
        self.message_port_register_in(pmt.intern('pdu_in'))
        self.set_msg_handler(pmt.intern('pdu_in'), self.handle_msg)

    def handle_msg(self, msg):
        if pmt.is_pair(msg):
            data_pmt = pmt.cdr(msg)
            try:
                raw_bytes = bytes(pmt.u8vector_elements(data_pmt))
                text = raw_bytes.decode('utf-8', errors='ignore')
                print(f"\nSUCCESS! RECEIVED MESSAGE: {text}\n")
            except Exception as e:
                print("Could not decode text:", e)
