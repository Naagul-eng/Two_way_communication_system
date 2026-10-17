import json
from pathlib import Path
import struct
import unittest
import numpy as np
import pmt
from gnuradio import gr,blocks,digital,analog,filter,pdu
from sdrchat.equalizer import NLMS,TrainingCorrelator,training_bytes
from sdrchat.fec_decoder import blk as RSDecoder
from sdrchat.protocol import Codec,TEXT


def constellation():
    return digital.constellation_rect([.707+.707j,-.707+.707j,-.707-.707j,.707-.707j],[0,1,3,2],4,2,2,1,1).base()


def waveform(wire,codec):
    coded=codec.protect(wire)
    packet=training_bytes()+bytes.fromhex('e15ae893e15ae893')+struct.pack('!HH',len(coded),len(coded))+coded+bytes([0x55])*2570
    tb=gr.top_block();src=blocks.vector_source_b(list(packet),False);mod=digital.generic_mod(constellation(),True,4,True,.35)
    sink=blocks.vector_sink_c();tb.connect(src,mod,sink);tb.run();return np.asarray(sink.data(),np.complex64)


def decode(samples):
    tb=gr.top_block();q=constellation()
    src=blocks.vector_source_c(samples.tolist(),False)
    agc=analog.agc_cc(.01,1,1);agc.set_max_gain(100)
    rrc=filter.fft_filter_ccc(1,filter.firdes.root_raised_cosine(1,2400000,600000,.35,44),1)
    sync=digital.symbol_sync_cc(digital.TED_GARDNER,4,.0628,.707,1,.05,2,digital.constellation_qpsk().base(),digital.IR_MMSE_8TAP,32,[])
    corr=TrainingCorrelator(.6);eq=NLMS();costas=digital.costas_loop_cc(.0628,4,False)
    slicer=digital.constellation_decoder_cb(q);diff=digital.diff_decoder_bb(4,digital.DIFF_DIFFERENTIAL)
    mapping=digital.map_bb([0,1,3,2]);unpack=blocks.unpack_k_bits_bb(2)
    access=digital.correlate_access_code_bb_ts('1110000101011010111010001001001111100001010110101110100010010011',2,'packet_len')
    repack=blocks.repack_bits_bb(1,8,'packet_len',False,gr.GR_MSB_FIRST)
    to_pdu=pdu.tagged_stream_to_pdu(gr.types.byte_t,'packet_len');rs=RSDecoder(verbose=False)
    crc=digital.crc_check(32,0x04C11DB7,0xFFFFFFFF,0xFFFFFFFF,True,True,False,True,0)
    result=blocks.message_debug()
    tb.connect(src,agc,rrc,sync,corr,eq,costas,slicer,diff,mapping,unpack,access,repack,to_pdu)
    tb.msg_connect(to_pdu,'pdus',rs,'pdu_in');tb.msg_connect(rs,'pdu_out',crc,'in');tb.msg_connect(crc,'ok',result,'store')
    tb.run()
    return [bytes(pmt.u8vector_elements(pmt.cdr(result.get_message(i)))) for i in range(result.num_messages())],corr.count


class PHYTests(unittest.TestCase):
    def test_qpsk_nlms_crc_roundtrip(self):
        c=json.loads((Path(__file__).parents[1]/'configs/node_a.example.json').read_text());codec=Codec(c['shared_key'])
        wire=codec.pack(2,1,123,1,TEXT,b'QPSK NLMS integration')
        samples=waveform(wire,codec)
        rng=np.random.default_rng(1)
        for phase,cfo,multipath in [(0,0,False),(.8,0,False),(.4,500,True)]:
            with self.subTest(phase=phase,cfo=cfo,multipath=multipath):
                noise=(rng.normal(size=len(samples))+1j*rng.normal(size=len(samples)))*.002
                channel=np.convolve(samples,[1,0,.2+.1j])[:len(samples)] if multipath else samples
                impaired=channel*np.exp(1j*(phase+2*np.pi*cfo*np.arange(len(samples))/2400000))+noise
                frames,tags=decode(np.r_[impaired,np.zeros(8192,np.complex64)].astype(np.complex64))
                self.assertGreater(tags,0)
                self.assertIn(wire,frames)


if __name__=='__main__':unittest.main()
