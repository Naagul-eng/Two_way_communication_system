import numpy as np
from gnuradio import gr
import pmt

class blk(gr.basic_block):
    def __init__(self):
        gr.basic_block.__init__(
            self,
            name='GUI Message Sink',
            in_sig=None,
            out_sig=None
        )
        self.message_port_register_in(pmt.intern('in'))
        self.set_msg_handler(pmt.intern('in'), self.handle_msg)
        self.out_file = "/tmp/received_message.bin"

    def handle_msg(self, msg):
        try:
            if pmt.is_pdu(msg):
                # Unpack the PDU payload
                data = pmt.cdr(msg)
                payload_bytes = bytes(pmt.u8vector_elements(data))
                
                # Strip the 4-byte CRC checksum from the end of the packet
                if len(payload_bytes) > 4:
                    payload_bytes = payload_bytes[:-4]
                
                # Drop the decoded data into the /tmp/ folder for the Receiver App
                with open(self.out_file, "wb") as f:
                    f.write(payload_bytes)
                print(f"[GUI Sink] Exported {len(payload_bytes)} bytes to Receiver App", flush=True)
        except Exception as e:
            print(f"[GUI Sink Error] {e}", flush=True)
