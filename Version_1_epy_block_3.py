"""
Embedded Python Block: PDU Prepend Dummy Bytes
"""

import numpy as np
from gnuradio import gr
import pmt

class blk(gr.basic_block):
    def __init__(self, num_dummy_bytes=64):  # Default to 64 bytes
        """
        Constructor.
        Args:
            num_dummy_bytes: The number of random bytes to prepend.
        """
        gr.basic_block.__init__(
            self,
            name='PDU Prepend Dummy Bytes',
            in_sig=None,
            out_sig=None
        )
        
        # Save the parameter
        self.num_dummy_bytes = num_dummy_bytes

        # Register message ports for PDU handling
        self.message_port_register_in(pmt.intern('pdu_in'))
        self.message_port_register_out(pmt.intern('pdu_out'))
        
        # Set up the message handler
        self.set_msg_handler(pmt.intern('pdu_in'), self.handle_msg)

    def handle_msg(self, msg):
        """
        Message handler that processes incoming PDUs.
        """
        # 1. Validate that the message is a PDU (it should be a pair: meta + data)
        if not pmt.is_pair(msg):
            return

        # 2. Extract metadata and data vector
        meta = pmt.car(msg)
        data_pmt = pmt.cdr(msg)
        
        # Convert PMT vector to a numpy array (uint8)
        # We rely on pmt.u8vector_elements to get the data out
        try:
            input_data = pmt.u8vector_elements(data_pmt)
        except:
            # If data is not a u8vector, ignore or print error
            return

        # 3. Generate dummy bytes for QPSK Costas Loop Sync
        # We use random integers between 0 and 255.
        # Random data ensures White Noise properties, meaning we have an equal 
        # probability of generating 00, 01, 10, and 11 bit pairs.
        # This guarantees that the transitions hit all 4 points of the QPSK 
        # constellation (1+j, 1-j, -1+j, -1-j) to energize the loop.
        dummy_data = np.random.randint(0, 256, self.num_dummy_bytes, dtype=np.uint8)
        
        # 4. Concatenate the dummy bytes with the input data
        # input_data comes out as a tuple or list from pmt, convert to array first
        combined_data = np.concatenate((dummy_data, np.array(input_data, dtype=np.uint8)))

        # 5. Create new output PMT
        # We keep the original metadata (meta)
        out_len = len(combined_data)
        out_vector = pmt.init_u8vector(out_len, combined_data)
        out_msg = pmt.cons(meta, out_vector)

        # 6. Publish the message to the output port
        self.message_port_pub(pmt.intern('pdu_out'), out_msg)
