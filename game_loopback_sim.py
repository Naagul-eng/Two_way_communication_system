#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Among Us Lite - laptop loopback simulation
# Author: naagul
# Description: Game-mode QPSK link: same PHY chain, small packets, light MAC+keystream instead of Fernet, no file/ARQ layer, TDMA uplink slots.
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import analog
from gnuradio import blocks
from gnuradio import channels
from gnuradio.filter import firdes
from gnuradio import digital
from gnuradio import filter
from gnuradio import gr, pdu
import game_loopback_sim_epy_block_3 as epy_block_3  # embedded python block
import game_loopback_sim_epy_rs_decoder as epy_rs_decoder  # embedded python block
import game_loopback_sim_epy_rs_encoder as epy_rs_encoder  # embedded python block
import game_loopback_sim_game_client_1 as game_client_1  # embedded python block
import game_loopback_sim_game_client_2 as game_client_2  # embedded python block
import game_loopback_sim_game_client_3 as game_client_3  # embedded python block
import game_loopback_sim_game_host as game_host  # embedded python block
import threading
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation




class game_loopback_sim(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Among Us Lite - laptop loopback simulation", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Among Us Lite - laptop loopback simulation")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "game_loopback_sim")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.sps = sps = 4
        self.qpsk = qpsk = digital.constellation_rect([0.707+0.707j, -0.707+0.707j, -0.707-0.707j, 0.707-0.707j] , [0, 1, 3, 2],
        4, 2, 2, 1, 1).base()
        self.nfilts = nfilts = 32
        self.access_key = access_key = "1110000101011010111010001001001111100001010110101110100010010011"
        self.tick_ms = tick_ms = 250
        self.slot_ms = slot_ms = 45
        self.samp_rate = samp_rate = 2400000
        self.rrc_taps = rrc_taps = filter.firdes.root_raised_cosine(nfilts, nfilts, 1.0/sps, 0.35, 11*sps*nfilts)
        self.phase_bw = phase_bw = 62.8e-3
        self.node_id = node_id = 1
        self.n_players = n_players = 4
        self.max_dev_0 = max_dev_0 = 0.05
        self.max_dev = max_dev = 0.05
        self.hdr_format = hdr_format = digital.header_format_default(access_key, 0)
        self.guard_ms = guard_ms = 70
        self.game_key = game_key = 'change-this-game-key'
        self.freq = freq = 2.4e9
        self.fec_verbose = fec_verbose = False
        self.fec_nsym = fec_nsym = 16
        self.fec_log_every = fec_log_every = 50
        self.fec_enabled = fec_enabled = True
        self.excess_bw = excess_bw = 0.35
        self.damp_fac = damp_fac = 0.707
        self.cma_alg = cma_alg = digital.adaptive_algorithm_cma( qpsk, .001, 1).base()
        self.burst_tail = burst_tail = 384
        self.burst_prefix = burst_prefix = 640

        ##################################################
        # Blocks
        ##################################################

        self.pdu_tagged_stream_to_pdu_0_0_0 = pdu.tagged_stream_to_pdu(gr.types.byte_t, 'packet_len')
        self.pdu_tagged_stream_to_pdu_0 = pdu.tagged_stream_to_pdu(gr.types.byte_t, 'packet_len')
        self.pdu_pdu_to_tagged_stream_2 = pdu.pdu_to_tagged_stream(gr.types.byte_t, 'packet_len')
        self.pdu_pdu_to_tagged_stream_1 = pdu.pdu_to_tagged_stream(gr.types.byte_t, 'packet_len')
        self.pdu_pdu_to_tagged_stream_0 = pdu.pdu_to_tagged_stream(gr.types.byte_t, 'packet_len')
        self.game_host = game_host.blk(node_id=0, n_players=n_players, tick_ms=tick_ms, slot_ms=slot_ms, guard_ms=guard_ms, key=game_key, show_gui=1, bot=0, min_players=3, title='Among Us Lite')
        self.game_client_3 = game_client_3.blk(node_id=3, n_players=n_players, tick_ms=tick_ms, slot_ms=slot_ms, guard_ms=guard_ms, key=game_key, show_gui=1, bot=1, min_players=3, title='Among Us Lite')
        self.game_client_2 = game_client_2.blk(node_id=2, n_players=n_players, tick_ms=tick_ms, slot_ms=slot_ms, guard_ms=guard_ms, key=game_key, show_gui=1, bot=1, min_players=3, title='Among Us Lite')
        self.game_client_1 = game_client_1.blk(node_id=1, n_players=n_players, tick_ms=tick_ms, slot_ms=slot_ms, guard_ms=guard_ms, key=game_key, show_gui=1, bot=1, min_players=3, title='Among Us Lite')
        self.filter_fft_rrc_filter_0 = filter.fft_filter_ccc(1, firdes.root_raised_cosine(1, samp_rate, (samp_rate/sps), excess_bw, (11*sps)), 1)
        self.epy_rs_encoder = epy_rs_encoder.blk(nsym=fec_nsym, enabled=fec_enabled, verbose=fec_verbose, log_every=fec_log_every)
        self.epy_rs_decoder = epy_rs_decoder.blk(nsym=fec_nsym, enabled=fec_enabled, verbose=fec_verbose, log_every=fec_log_every)
        self.epy_block_3 = epy_block_3.blk(num_dummy_bytes=burst_prefix, num_tail_bytes=burst_tail)
        self.digital_symbol_sync_xx_0_1_0 = digital.symbol_sync_cc(
            digital.TED_GARDNER,
            sps,
            phase_bw,
            damp_fac,
            1.0,
            max_dev,
            2,
            digital.constellation_qpsk().base(),
            digital.IR_MMSE_8TAP,
            32,
            rrc_taps)
        self.digital_protocol_formatter_async_0 = digital.protocol_formatter_async(hdr_format)
        self.digital_map_bb_0_0 = digital.map_bb([0, 1, 3, 2])
        self.digital_linear_equalizer_0 = digital.linear_equalizer(5, 2, cma_alg, True, [ ], "")
        self.digital_diff_decoder_bb_0_0 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.digital_crc_check_0_0 = digital.crc_check(32, 0x4C11DB7, 0xFFFFFFFF, 0xFFFFFFFF, True, True, False, True, 0)
        self.digital_crc_append_0 = digital.crc_append(32, 0x4C11DB7, 0xFFFFFFFF, 0xFFFFFFFF, True, True, False, 0)
        self.digital_costas_loop_cc_0_0 = digital.costas_loop_cc(phase_bw, 4, False)
        self.digital_correlate_access_code_xx_ts_0_0 = digital.correlate_access_code_bb_ts("1110000101011010111010001001001111100001010110101110100010010011",
          2, 'packet_len')
        self.digital_constellation_modulator_0 = digital.generic_mod(
            constellation=qpsk,
            differential=True,
            samples_per_symbol=sps,
            pre_diff_code=True,
            excess_bw=excess_bw,
            verbose=False,
            log=False,
            truncate=False)
        self.digital_constellation_decoder_cb_0_0 = digital.constellation_decoder_cb(qpsk)
        self.channel_model_0 = channels.channel_model(
            noise_voltage=0.03,
            frequency_offset=0.0,
            epsilon=1.0,
            taps=[1.0],
            noise_seed=0,
            block_tags=False)
        self.blocks_unpack_k_bits_bb_0_0 = blocks.unpack_k_bits_bb(2)
        self.blocks_throttle_0 = blocks.throttle(gr.sizeof_gr_complex*1, samp_rate,True)
        self.blocks_tagged_stream_mux_0 = blocks.tagged_stream_mux(gr.sizeof_char*1, 'packet_len', 0)
        self.blocks_repack_bits_bb_1_0_0_0 = blocks.repack_bits_bb(1, 8, "packet_len", False, gr.GR_MSB_FIRST)
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_cc(0.8)
        self.analog_agc_xx_0 = analog.agc_cc((1e-2), 1.0, 1.0, 100)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.digital_crc_append_0, 'out'), (self.epy_rs_encoder, 'pdu_in'))
        self.msg_connect((self.digital_crc_check_0_0, 'ok'), (self.game_client_1, 'rx_in'))
        self.msg_connect((self.digital_crc_check_0_0, 'ok'), (self.game_client_2, 'rx_in'))
        self.msg_connect((self.digital_crc_check_0_0, 'ok'), (self.game_client_3, 'rx_in'))
        self.msg_connect((self.digital_crc_check_0_0, 'ok'), (self.game_host, 'rx_in'))
        self.msg_connect((self.digital_protocol_formatter_async_0, 'header'), (self.pdu_pdu_to_tagged_stream_0, 'pdus'))
        self.msg_connect((self.digital_protocol_formatter_async_0, 'payload'), (self.pdu_pdu_to_tagged_stream_1, 'pdus'))
        self.msg_connect((self.epy_block_3, 'pdu_out'), (self.pdu_pdu_to_tagged_stream_2, 'pdus'))
        self.msg_connect((self.epy_rs_decoder, 'pdu_out'), (self.digital_crc_check_0_0, 'in'))
        self.msg_connect((self.epy_rs_encoder, 'pdu_out'), (self.digital_protocol_formatter_async_0, 'in'))
        self.msg_connect((self.game_client_1, 'tx_out'), (self.digital_crc_append_0, 'in'))
        self.msg_connect((self.game_client_2, 'tx_out'), (self.digital_crc_append_0, 'in'))
        self.msg_connect((self.game_client_3, 'tx_out'), (self.digital_crc_append_0, 'in'))
        self.msg_connect((self.game_host, 'tx_out'), (self.digital_crc_append_0, 'in'))
        self.msg_connect((self.pdu_tagged_stream_to_pdu_0, 'pdus'), (self.epy_block_3, 'pdu_in'))
        self.msg_connect((self.pdu_tagged_stream_to_pdu_0_0_0, 'pdus'), (self.epy_rs_decoder, 'pdu_in'))
        self.connect((self.analog_agc_xx_0, 0), (self.filter_fft_rrc_filter_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.channel_model_0, 0))
        self.connect((self.blocks_repack_bits_bb_1_0_0_0, 0), (self.pdu_tagged_stream_to_pdu_0_0_0, 0))
        self.connect((self.blocks_tagged_stream_mux_0, 0), (self.pdu_tagged_stream_to_pdu_0, 0))
        self.connect((self.blocks_throttle_0, 0), (self.analog_agc_xx_0, 0))
        self.connect((self.blocks_unpack_k_bits_bb_0_0, 0), (self.digital_correlate_access_code_xx_ts_0_0, 0))
        self.connect((self.channel_model_0, 0), (self.blocks_throttle_0, 0))
        self.connect((self.digital_constellation_decoder_cb_0_0, 0), (self.digital_diff_decoder_bb_0_0, 0))
        self.connect((self.digital_constellation_modulator_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        self.connect((self.digital_correlate_access_code_xx_ts_0_0, 0), (self.blocks_repack_bits_bb_1_0_0_0, 0))
        self.connect((self.digital_costas_loop_cc_0_0, 0), (self.digital_constellation_decoder_cb_0_0, 0))
        self.connect((self.digital_diff_decoder_bb_0_0, 0), (self.digital_map_bb_0_0, 0))
        self.connect((self.digital_linear_equalizer_0, 0), (self.digital_costas_loop_cc_0_0, 0))
        self.connect((self.digital_map_bb_0_0, 0), (self.blocks_unpack_k_bits_bb_0_0, 0))
        self.connect((self.digital_symbol_sync_xx_0_1_0, 0), (self.digital_linear_equalizer_0, 0))
        self.connect((self.filter_fft_rrc_filter_0, 0), (self.digital_symbol_sync_xx_0_1_0, 0))
        self.connect((self.pdu_pdu_to_tagged_stream_0, 0), (self.blocks_tagged_stream_mux_0, 0))
        self.connect((self.pdu_pdu_to_tagged_stream_1, 0), (self.blocks_tagged_stream_mux_0, 1))
        self.connect((self.pdu_pdu_to_tagged_stream_2, 0), (self.digital_constellation_modulator_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "game_loopback_sim")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_rrc_taps(filter.firdes.root_raised_cosine(self.nfilts, self.nfilts, 1.0/self.sps, 0.35, 11*self.sps*self.nfilts))
        self.digital_symbol_sync_xx_0_1_0.set_sps(self.sps)
        self.filter_fft_rrc_filter_0.set_taps(firdes.root_raised_cosine(1, self.samp_rate, (self.samp_rate/self.sps), self.excess_bw, (11*self.sps)))

    def get_qpsk(self):
        return self.qpsk

    def set_qpsk(self, qpsk):
        self.qpsk = qpsk
        self.digital_constellation_decoder_cb_0_0.set_constellation(self.qpsk)

    def get_nfilts(self):
        return self.nfilts

    def set_nfilts(self, nfilts):
        self.nfilts = nfilts
        self.set_rrc_taps(filter.firdes.root_raised_cosine(self.nfilts, self.nfilts, 1.0/self.sps, 0.35, 11*self.sps*self.nfilts))

    def get_access_key(self):
        return self.access_key

    def set_access_key(self, access_key):
        self.access_key = access_key
        self.set_hdr_format(digital.header_format_default(self.access_key, 0))

    def get_tick_ms(self):
        return self.tick_ms

    def set_tick_ms(self, tick_ms):
        self.tick_ms = tick_ms

    def get_slot_ms(self):
        return self.slot_ms

    def set_slot_ms(self, slot_ms):
        self.slot_ms = slot_ms

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.filter_fft_rrc_filter_0.set_taps(firdes.root_raised_cosine(1, self.samp_rate, (self.samp_rate/self.sps), self.excess_bw, (11*self.sps)))
        self.blocks_throttle_0.set_sample_rate(self.samp_rate)

    def get_rrc_taps(self):
        return self.rrc_taps

    def set_rrc_taps(self, rrc_taps):
        self.rrc_taps = rrc_taps

    def get_phase_bw(self):
        return self.phase_bw

    def set_phase_bw(self, phase_bw):
        self.phase_bw = phase_bw
        self.digital_costas_loop_cc_0_0.set_loop_bandwidth(self.phase_bw)
        self.digital_symbol_sync_xx_0_1_0.set_loop_bandwidth(self.phase_bw)

    def get_node_id(self):
        return self.node_id

    def set_node_id(self, node_id):
        self.node_id = node_id

    def get_n_players(self):
        return self.n_players

    def set_n_players(self, n_players):
        self.n_players = n_players

    def get_max_dev_0(self):
        return self.max_dev_0

    def set_max_dev_0(self, max_dev_0):
        self.max_dev_0 = max_dev_0

    def get_max_dev(self):
        return self.max_dev

    def set_max_dev(self, max_dev):
        self.max_dev = max_dev

    def get_hdr_format(self):
        return self.hdr_format

    def set_hdr_format(self, hdr_format):
        self.hdr_format = hdr_format

    def get_guard_ms(self):
        return self.guard_ms

    def set_guard_ms(self, guard_ms):
        self.guard_ms = guard_ms

    def get_game_key(self):
        return self.game_key

    def set_game_key(self, game_key):
        self.game_key = game_key
        self.game_host.key = self.game_key
        self.game_client_1.key = self.game_key
        self.game_client_2.key = self.game_key
        self.game_client_3.key = self.game_key

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq

    def get_fec_verbose(self):
        return self.fec_verbose

    def set_fec_verbose(self, fec_verbose):
        self.fec_verbose = fec_verbose
        self.epy_rs_decoder.verbose = self.fec_verbose
        self.epy_rs_encoder.verbose = self.fec_verbose

    def get_fec_nsym(self):
        return self.fec_nsym

    def set_fec_nsym(self, fec_nsym):
        self.fec_nsym = fec_nsym
        self.epy_rs_decoder.nsym = self.fec_nsym
        self.epy_rs_encoder.nsym = self.fec_nsym

    def get_fec_log_every(self):
        return self.fec_log_every

    def set_fec_log_every(self, fec_log_every):
        self.fec_log_every = fec_log_every
        self.epy_rs_decoder.log_every = self.fec_log_every
        self.epy_rs_encoder.log_every = self.fec_log_every

    def get_fec_enabled(self):
        return self.fec_enabled

    def set_fec_enabled(self, fec_enabled):
        self.fec_enabled = fec_enabled
        self.epy_rs_decoder.enabled = self.fec_enabled
        self.epy_rs_encoder.enabled = self.fec_enabled

    def get_excess_bw(self):
        return self.excess_bw

    def set_excess_bw(self, excess_bw):
        self.excess_bw = excess_bw
        self.filter_fft_rrc_filter_0.set_taps(firdes.root_raised_cosine(1, self.samp_rate, (self.samp_rate/self.sps), self.excess_bw, (11*self.sps)))

    def get_damp_fac(self):
        return self.damp_fac

    def set_damp_fac(self, damp_fac):
        self.damp_fac = damp_fac
        self.digital_symbol_sync_xx_0_1_0.set_damping_factor(self.damp_fac)

    def get_cma_alg(self):
        return self.cma_alg

    def set_cma_alg(self, cma_alg):
        self.cma_alg = cma_alg

    def get_burst_tail(self):
        return self.burst_tail

    def set_burst_tail(self, burst_tail):
        self.burst_tail = burst_tail

    def get_burst_prefix(self):
        return self.burst_prefix

    def set_burst_prefix(self, burst_prefix):
        self.burst_prefix = burst_prefix




def main(top_block_cls=game_loopback_sim, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
