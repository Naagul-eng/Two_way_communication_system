"""Multi-codeword RS FEC for encrypted transceiver PDUs, including CRC32.
Each 239-byte segment gets 16 parity bytes at nsym=16. No extra wire header.
"""
from gnuradio import gr
import pmt
from .reedsolo_bundled import RSCodec, ReedSolomonError

class blk(gr.basic_block):
    """Encode all packet types (DATA, metadata, ACK and other controls)."""
    def __init__(self, nsym=16, enabled=True, verbose=True, log_every=50):
        gr.basic_block.__init__(self, name='RS Packet Encoder',
                                in_sig=None, out_sig=None)
        self.nsym = int(nsym)
        if not 2 <= self.nsym <= 128 or self.nsym % 2:
            raise ValueError('nsym must be even, between 2 and 128')
        self.k = 255 - self.nsym
        self.enabled, self.verbose = bool(enabled), bool(verbose)
        self.log_every = max(1, int(log_every))
        self.max_input = 4096  # Existing 4092-byte encrypted PDU budget + CRC32.
        self.rs = RSCodec(self.nsym, nsize=255, fcr=0,
                          prim=0x11d, generator=2, c_exp=8)
        self.tx_count = self.reject_count = 0
        self.message_port_register_in(pmt.intern('pdu_in'))
        self.message_port_register_out(pmt.intern('pdu_out'))
        self.set_msg_handler(pmt.intern('pdu_in'), self.handle_msg)

    def handle_msg(self, msg):
        if not pmt.is_pair(msg) or not pmt.is_u8vector(pmt.cdr(msg)):
            self.reject_count += 1
            if self.verbose:
                print('[RS TX] DROP: expected a packed-byte PDU', flush=True)
            return
        raw = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        if not 4 <= len(raw) <= self.max_input:
            self.reject_count += 1
            if self.verbose:
                print('[RS TX] DROP: packet must be 4..4096 bytes including CRC', flush=True)
            return
        if self.enabled:
            # Explicit boundaries prevent accidental changes to chunking conventions.
            chunks = [bytes(self.rs.encode(raw[i:i+self.k]))
                      for i in range(0, len(raw), self.k)]
            encoded = b''.join(chunks)
            nwords = len(chunks)
        else:
            encoded, nwords = raw, 0
        meta = pmt.car(msg)
        if pmt.is_dict(meta) and pmt.dict_has_key(meta, pmt.intern('packet_len')):
            meta = pmt.dict_add(meta, pmt.intern('packet_len'), pmt.from_long(len(encoded)))
        out = pmt.cons(meta, pmt.init_u8vector(len(encoded), list(encoded)))
        self.message_port_pub(pmt.intern('pdu_out'), out)
        self.tx_count += 1
        if self.verbose and (self.tx_count == 1 or self.tx_count % self.log_every == 0):
            print(f'[RS TX #{self.tx_count}] {len(raw)} -> {len(encoded)} bytes; '
                  f'codewords={nwords}; FEC={self.enabled}', flush=True)

    def stop(self):
        if self.verbose:
            print(f'[RS TX SUMMARY] packets={self.tx_count}; rejected={self.reject_count}', flush=True)
        return True
