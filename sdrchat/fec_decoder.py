"""Inverse of rs_packet_encoder.py. Reassemble a complete PDU before CRC Check.
A failed codeword drops the entire PDU; the existing ARQ retries the packet.
"""
from gnuradio import gr
import pmt
from .reedsolo_bundled import RSCodec, ReedSolomonError

class blk(gr.basic_block):
    """Correct each RS codeword, then emit the original encrypted frame plus CRC."""
    def __init__(self, nsym=16, enabled=True, verbose=True, log_every=50):
        gr.basic_block.__init__(self, name='RS Packet Decoder',
                                in_sig=None, out_sig=None)
        self.nsym = int(nsym)
        if not 2 <= self.nsym <= 128 or self.nsym % 2:
            raise ValueError('nsym must be even, between 2 and 128')
        self.k = 255 - self.nsym
        self.enabled, self.verbose = bool(enabled), bool(verbose)
        self.log_every = max(1, int(log_every))
        self.max_input = 4096
        self.max_coded = self.max_input + self.nsym * ((self.max_input+self.k-1)//self.k)
        self.rs = RSCodec(self.nsym, nsize=255, fcr=0,
                          prim=0x11d, generator=2, c_exp=8)
        self.rx_count = self.fail_count = self.decoded_count = 0
        self.corrected_packets = self.corrected_bytes = 0
        self.message_port_register_in(pmt.intern('pdu_in'))
        self.message_port_register_out(pmt.intern('pdu_out'))
        self.message_port_register_out(pmt.intern('fail'))
        self.set_msg_handler(pmt.intern('pdu_in'), self.handle_msg)

    def handle_msg(self, msg):
        if not pmt.is_pair(msg) or not pmt.is_u8vector(pmt.cdr(msg)):
            if self.verbose:
                print('[RS RX] DROP: expected a packed-byte PDU', flush=True)
            return
        self.rx_count += 1
        raw = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        corrected, corrected_bits, nwords = 0, 0, 0
        try:
            if self.enabled:
                if not self.nsym+4 <= len(raw) <= self.max_coded:
                    raise ValueError('invalid coded packet length')
                tail = len(raw) % 255
                if tail and tail <= self.nsym:
                    raise ValueError('truncated final RS codeword')
                parts = []
                for i in range(0, len(raw), 255):
                    received_word = raw[i:i+255]
                    data, repaired_word, positions = self.rs.decode(received_word)
                    parts.append(bytes(data))
                    corrected += sum(a != b for a, b in zip(received_word, repaired_word))
                    corrected_bits += sum(bin(a ^ b).count('1') for a, b in zip(received_word, repaired_word))
                    nwords += 1
                decoded = b''.join(parts)
            else:
                decoded = raw
            if not 4 <= len(decoded) <= self.max_input:
                raise ValueError('invalid decoded packet length')
        except (ReedSolomonError, ValueError) as exc:
            self.fail_count += 1
            self.message_port_pub(pmt.intern('fail'), msg)
            if self.verbose:
                print(f'[RS RX #{self.rx_count}] DROP: {exc}; '
                      f'RS failures={self.fail_count}; waiting for ARQ retry', flush=True)
            return
        meta = pmt.car(msg)
        if not pmt.is_dict(meta):
            meta = pmt.make_dict()
        meta = pmt.dict_add(meta, pmt.intern('rs_corrected_bytes'), pmt.from_long(corrected))
        meta = pmt.dict_add(meta, pmt.intern('rs_corrected_bits'), pmt.from_long(corrected_bits))
        if pmt.is_dict(meta) and pmt.dict_has_key(meta, pmt.intern('packet_len')):
            meta = pmt.dict_add(meta, pmt.intern('packet_len'), pmt.from_long(len(decoded)))
        out = pmt.cons(meta, pmt.init_u8vector(len(decoded), list(decoded)))
        self.message_port_pub(pmt.intern('pdu_out'), out)
        self.decoded_count += 1
        self.corrected_packets += int(corrected > 0)
        self.corrected_bytes += corrected
        if self.verbose and (corrected or self.rx_count == 1 or
                             self.rx_count % self.log_every == 0):
            print(f'[RS RX #{self.rx_count}] {len(raw)} -> {len(decoded)} bytes; '
                  f'codewords={nwords}; corrected bytes={corrected}; '
                  'CRC/authentication/file verification follow', flush=True)

    def stop(self):
        if self.verbose:
            print(f'[RS RX SUMMARY] received={self.rx_count}; decoded={self.decoded_count}; '
                  f'RS failures={self.fail_count}; corrected packets={self.corrected_packets}; '
                  f'corrected bytes={self.corrected_bytes}', flush=True)
        return True
