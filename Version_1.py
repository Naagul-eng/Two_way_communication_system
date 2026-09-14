#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: CDP
# Author: Pixel_Pulse
# GNU Radio version: 3.10.9.2

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import analog
from gnuradio import blocks
from gnuradio import blocks, gr
from gnuradio import digital
from gnuradio import filter
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import gr, pdu
from gnuradio import iio
import Version_1_epy_block_0 as epy_block_0  # embedded python block
import Version_1_epy_block_1 as epy_block_1  # embedded python block
import sip



class Version_1(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "CDP", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("CDP")
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

        self.settings = Qt.QSettings("GNU Radio", "Version_1")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Variables
        ##################################################
        self.sps = sps = 4
        self.nfilts = nfilts = 32
        self.bpsk = bpsk = digital.constellation_rect([-1,1] , [0, 1,],
        2, 2, 1, 1, 1).base()
        self.time_offset = time_offset = 1.002
        self.taps = taps = [1.0,0.7,0.4,0.15]
        self.samp_rate = samp_rate = 2400000
        self.rrc_taps = rrc_taps = firdes.root_raised_cosine(nfilts, nfilts, 1.0/float(sps), 0.35, 11*sps*nfilts)
        self.phase_bw = phase_bw = 62.8e-3
        self.noise_volt = noise_volt = 0.3
        self.my_addr = my_addr = 'B1'
        self.max_dev_0 = max_dev_0 = 0.05
        self.max_dev = max_dev = 0.05
        self.freq_offset = freq_offset = 0.01
        self.freq = freq = 2.4e9
        self.excess_bw = excess_bw = 0.35
        self.damp_fac = damp_fac = 0.707
        self.cma_alg = cma_alg = digital.adaptive_algorithm_cma( bpsk, .01, 1).base()

        ##################################################
        # Blocks
        ##################################################

        self.qtgui_const_sink_x_1 = qtgui.const_sink_c(
            1024, #size
            "After linear equilizer", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_const_sink_x_1.set_update_time(0.10)
        self.qtgui_const_sink_x_1.set_y_axis((-2), 2)
        self.qtgui_const_sink_x_1.set_x_axis((-2), 2)
        self.qtgui_const_sink_x_1.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.qtgui_const_sink_x_1.enable_autoscale(False)
        self.qtgui_const_sink_x_1.enable_grid(False)
        self.qtgui_const_sink_x_1.enable_axis_labels(True)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_const_sink_x_1.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_const_sink_x_1.set_line_label(i, labels[i])
            self.qtgui_const_sink_x_1.set_line_width(i, widths[i])
            self.qtgui_const_sink_x_1.set_line_color(i, colors[i])
            self.qtgui_const_sink_x_1.set_line_style(i, styles[i])
            self.qtgui_const_sink_x_1.set_line_marker(i, markers[i])
            self.qtgui_const_sink_x_1.set_line_alpha(i, alphas[i])

        self._qtgui_const_sink_x_1_win = sip.wrapinstance(self.qtgui_const_sink_x_1.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_const_sink_x_1_win)
        self.qtgui_const_sink_x_0_0 = qtgui.const_sink_c(
            2048, #size
            "After syncronization", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_const_sink_x_0_0.set_update_time(0.10)
        self.qtgui_const_sink_x_0_0.set_y_axis((-2), 2)
        self.qtgui_const_sink_x_0_0.set_x_axis((-2), 2)
        self.qtgui_const_sink_x_0_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.qtgui_const_sink_x_0_0.enable_autoscale(False)
        self.qtgui_const_sink_x_0_0.enable_grid(False)
        self.qtgui_const_sink_x_0_0.enable_axis_labels(True)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_const_sink_x_0_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_const_sink_x_0_0.set_line_label(i, labels[i])
            self.qtgui_const_sink_x_0_0.set_line_width(i, widths[i])
            self.qtgui_const_sink_x_0_0.set_line_color(i, colors[i])
            self.qtgui_const_sink_x_0_0.set_line_style(i, styles[i])
            self.qtgui_const_sink_x_0_0.set_line_marker(i, markers[i])
            self.qtgui_const_sink_x_0_0.set_line_alpha(i, alphas[i])

        self._qtgui_const_sink_x_0_0_win = sip.wrapinstance(self.qtgui_const_sink_x_0_0.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_const_sink_x_0_0_win)
        self.pdu_tagged_stream_to_pdu_0_0_0 = pdu.tagged_stream_to_pdu(gr.types.byte_t, 'packet_len')
        self.iio_pluto_source_0 = iio.fmcomms2_source_fc32('ip:192.168.1.10' if 'ip:192.168.1.10' else iio.get_pluto_uri(), [True, True], 32768)
        self.iio_pluto_source_0.set_len_tag_key('packet_len')
        self.iio_pluto_source_0.set_frequency(2400000000)
        self.iio_pluto_source_0.set_samplerate(samp_rate)
        self.iio_pluto_source_0.set_gain_mode(0, 'slow_attack')
        self.iio_pluto_source_0.set_gain(0, 80)
        self.iio_pluto_source_0.set_quadrature(True)
        self.iio_pluto_source_0.set_rfdc(True)
        self.iio_pluto_source_0.set_bbdc(True)
        self.iio_pluto_source_0.set_filter_params('Auto', '', 0, 0)
        self.epy_block_1 = epy_block_1.blk(my_addr=3)
        self.epy_block_0 = epy_block_0.blk()
        self.digital_symbol_sync_xx_0_1_0 = digital.symbol_sync_cc(
            digital.TED_GARDNER,
            sps,
            phase_bw,
            damp_fac,
            1.0,
            max_dev,
            1,
            digital.constellation_bpsk().base(),
            digital.IR_PFB_MF,
            32,
            rrc_taps)
        self.digital_map_bb_0_0 = digital.map_bb([0, 1])
        self.digital_linear_equalizer_0 = digital.linear_equalizer(15, 1, cma_alg, True, [ ], "")
        self.digital_diff_decoder_bb_0_0 = digital.diff_decoder_bb(2, digital.DIFF_DIFFERENTIAL)
        self.digital_crc_check_0_0 = digital.crc_check(32, 0x4C11DB7, 0xFFFFFFFF, 0xFFFFFFFF, True, True, False, False, 0)
        self.digital_costas_loop_cc_0_0 = digital.costas_loop_cc(phase_bw, 2, False)
        self.digital_correlate_access_code_xx_ts_0_0 = digital.correlate_access_code_bb_ts("1110000101011010111010001001001111100001010110101110100010010011",
          4, 'packet_len')
        self.digital_constellation_decoder_cb_0_0 = digital.constellation_decoder_cb(bpsk)
        self.blocks_unpack_k_bits_bb_0_0 = blocks.unpack_k_bits_bb(1)
        self.blocks_repack_bits_bb_1_0_0_0 = blocks.repack_bits_bb(1, 8, "packet_len", False, gr.GR_MSB_FIRST)
        self.blocks_message_debug_3 = blocks.message_debug(True, gr.log_levels.info)
        self.analog_agc_xx_0 = analog.agc_cc((1e-4), 1.0, 1.0, 100)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.digital_crc_check_0_0, 'ok'), (self.epy_block_1, 'pdu_in'))
        self.msg_connect((self.epy_block_1, 'pdu_out'), (self.blocks_message_debug_3, 'print_pdu'))
        self.msg_connect((self.epy_block_1, 'pdu_out'), (self.epy_block_0, 'pdu_in'))
        self.msg_connect((self.pdu_tagged_stream_to_pdu_0_0_0, 'pdus'), (self.digital_crc_check_0_0, 'in'))
        self.connect((self.analog_agc_xx_0, 0), (self.digital_symbol_sync_xx_0_1_0, 0))
        self.connect((self.blocks_repack_bits_bb_1_0_0_0, 0), (self.pdu_tagged_stream_to_pdu_0_0_0, 0))
        self.connect((self.blocks_unpack_k_bits_bb_0_0, 0), (self.digital_correlate_access_code_xx_ts_0_0, 0))
        self.connect((self.digital_constellation_decoder_cb_0_0, 0), (self.digital_diff_decoder_bb_0_0, 0))
        self.connect((self.digital_correlate_access_code_xx_ts_0_0, 0), (self.blocks_repack_bits_bb_1_0_0_0, 0))
        self.connect((self.digital_costas_loop_cc_0_0, 0), (self.digital_constellation_decoder_cb_0_0, 0))
        self.connect((self.digital_costas_loop_cc_0_0, 0), (self.qtgui_const_sink_x_0_0, 0))
        self.connect((self.digital_diff_decoder_bb_0_0, 0), (self.digital_map_bb_0_0, 0))
        self.connect((self.digital_linear_equalizer_0, 0), (self.digital_costas_loop_cc_0_0, 0))
        self.connect((self.digital_linear_equalizer_0, 0), (self.qtgui_const_sink_x_1, 0))
        self.connect((self.digital_map_bb_0_0, 0), (self.blocks_unpack_k_bits_bb_0_0, 0))
        self.connect((self.digital_symbol_sync_xx_0_1_0, 0), (self.digital_linear_equalizer_0, 0))
        self.connect((self.iio_pluto_source_0, 0), (self.analog_agc_xx_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "Version_1")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts, 1.0/float(self.sps), 0.35, 11*self.sps*self.nfilts))
        self.digital_symbol_sync_xx_0_1_0.set_sps(self.sps)

    def get_nfilts(self):
        return self.nfilts

    def set_nfilts(self, nfilts):
        self.nfilts = nfilts
        self.set_rrc_taps(firdes.root_raised_cosine(self.nfilts, self.nfilts, 1.0/float(self.sps), 0.35, 11*self.sps*self.nfilts))

    def get_bpsk(self):
        return self.bpsk

    def set_bpsk(self, bpsk):
        self.bpsk = bpsk
        self.digital_constellation_decoder_cb_0_0.set_constellation(self.bpsk)

    def get_time_offset(self):
        return self.time_offset

    def set_time_offset(self, time_offset):
        self.time_offset = time_offset

    def get_taps(self):
        return self.taps

    def set_taps(self, taps):
        self.taps = taps

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.iio_pluto_source_0.set_samplerate(self.samp_rate)

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

    def get_noise_volt(self):
        return self.noise_volt

    def set_noise_volt(self, noise_volt):
        self.noise_volt = noise_volt

    def get_my_addr(self):
        return self.my_addr

    def set_my_addr(self, my_addr):
        self.my_addr = my_addr

    def get_max_dev_0(self):
        return self.max_dev_0

    def set_max_dev_0(self, max_dev_0):
        self.max_dev_0 = max_dev_0

    def get_max_dev(self):
        return self.max_dev

    def set_max_dev(self, max_dev):
        self.max_dev = max_dev

    def get_freq_offset(self):
        return self.freq_offset

    def set_freq_offset(self, freq_offset):
        self.freq_offset = freq_offset

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq

    def get_excess_bw(self):
        return self.excess_bw

    def set_excess_bw(self, excess_bw):
        self.excess_bw = excess_bw

    def get_damp_fac(self):
        return self.damp_fac

    def set_damp_fac(self, damp_fac):
        self.damp_fac = damp_fac
        self.digital_symbol_sync_xx_0_1_0.set_damping_factor(self.damp_fac)

    def get_cma_alg(self):
        return self.cma_alg

    def set_cma_alg(self, cma_alg):
        self.cma_alg = cma_alg




def main(top_block_cls=Version_1, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

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
