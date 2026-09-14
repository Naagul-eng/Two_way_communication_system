"""
Embedded Python Block: Packet Parser
Strips the SRC/DST/TYPE/SEQ/TOTAL/LEN header, filters on DST address,
and reassembles multi-segment messages before publishing the full payload.
"""
import struct
from gnuradio import gr
import pmt

HEADER_LEN = 7  # B B B B B H
TYPE_NAMES = {0x01: 'TEXT', 0x02: 'IMAGE', 0x03: 'AUDIO'}

class blk(gr.basic_block):
    def __init__(self, my_addr=0x02):
        gr.basic_block.__init__(self, name='Packet Parser', in_sig=None, out_sig=None)
        self.my_addr = my_addr & 0xFF
        self._reassembly = {}
        self.message_port_register_in(pmt.intern('pdu_in'))
        self.message_port_register_out(pmt.intern('pdu_out'))
        self.set_msg_handler(pmt.intern('pdu_in'), self.handle_msg)

    def handle_msg(self, msg):
        if not pmt.is_pair(msg):
            return
        try:
            raw = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        except Exception:
            return
        if len(raw) < HEADER_LEN:
            print("Packet Parser: runt packet, dropping")
            return

        src, dst, mtype, seq, total, plen = struct.unpack('>BBBBBH', raw[:HEADER_LEN])
        payload = raw[HEADER_LEN:HEADER_LEN + plen]

        if dst != self.my_addr and dst != 0xFF:  # 0xFF = broadcast
            print(f"Packet Parser: dropping pkt for {dst:#x} (I'm {self.my_addr:#x})")
            return

        print(f"RX pkt  src={src:#x} dst={dst:#x} type={TYPE_NAMES.get(mtype, mtype)} "
              f"seg={seq+1}/{total} len={plen}")

        key = (src, mtype)
        self._reassembly.setdefault(key, {})[seq] = payload

        if len(self._reassembly[key]) == total:
            full = b''.join(self._reassembly[key][i] for i in range(total))
            del self._reassembly[key]
            out_vec = pmt.init_u8vector(len(full), list(full))
            meta = pmt.cons(pmt.intern("type"), pmt.from_long(mtype))
            self.message_port_pub(pmt.intern('pdu_out'), pmt.cons(meta, out_vec))
