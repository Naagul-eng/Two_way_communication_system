import sys
import os
import random
import struct
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextBrowser, 
                             QLineEdit, QPushButton, QLabel, QFileDialog, QProgressBar)
from PyQt5.QtCore import QTimer, QUrl

# Configuration Parameters
CHUNK_SIZE = 1024        # 1 KB chunk size
WINDOW_SIZE = 3          # Go-Back-N Window Size (N=3)
ARQ_TIMEOUT_MS = 3500    # 3.5s timeout
FRAME_PACING_MS = 250    # Frame pacing to prevent /tmp write collisions

class TransceiverApp(QMainWindow):
    def __init__(self, node_id):
        super().__init__()
        self.node_id = node_id.upper()
        
        # File IPC paths
        if self.node_id == 'A':
            self.tx_file = "/tmp/nodeA_tx.bin"
            self.rx_file = "/tmp/nodeA_rx.bin"
        else:
            self.tx_file = "/tmp/nodeB_tx.bin"
            self.rx_file = "/tmp/nodeB_rx.bin"

        # Go-Back-N Transmitter State
        self.tx_packets = []        
        self.send_base = 0          
        self.next_seq_num = 0       
        self.file_start_seq = 0     
        self.total_file_chunks = 0  

        # Go-Back-N Receiver State
        self.expected_seq_num = 0   
        self.rx_file_buffers = {}   

        self.initUI()
        
        # Receiver Polling Timer (30ms)
        self.rx_timer = QTimer()
        self.rx_timer.timeout.connect(self.check_rx)
        self.rx_timer.start(30)

        # Transmission Pacing Timer (250ms)
        self.tx_pacer = QTimer()
        self.tx_pacer.timeout.connect(self.gbn_transmit_step)

        # ARQ Retransmission Timeout Timer (3.5s)
        self.arq_timer = QTimer()
        self.arq_timer.setSingleShot(True)
        self.arq_timer.timeout.connect(self.handle_gbn_timeout)

    def initUI(self):
        self.setWindowTitle(f"Transceiver Node {self.node_id} (Go-Back-N ARQ)")
        self.setGeometry(100 if self.node_id == 'A' else 650, 100, 620, 580)

        central_widget = QWidget()
        layout = QVBoxLayout()

        self.log_display = QTextBrowser()
        self.log_display.setReadOnly(True)
        self.log_display.setOpenExternalLinks(False)
        self.log_display.anchorClicked.connect(self.handle_link_click)
        
        layout.addWidget(QLabel(f"<b>Node {self.node_id} Active Terminal (Go-Back-N N={WINDOW_SIZE})</b>"))
        layout.addWidget(self.log_display)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        input_layout = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Type a message to transmit...")
        self.msg_input.returnPressed.connect(self.send_text)
        
        self.send_btn = QPushButton("Send Text")
        self.send_btn.clicked.connect(self.send_text)

        self.file_btn = QPushButton("Attach File (.wav / .png)")
        self.file_btn.clicked.connect(self.send_file)

        self.cancel_btn = QPushButton("Cancel Tx")
        self.cancel_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.cancel_btn.clicked.connect(self.cancel_tx)

        input_layout.addWidget(self.msg_input)
        input_layout.addWidget(self.send_btn)
        input_layout.addWidget(self.file_btn)
        input_layout.addWidget(self.cancel_btn)
        layout.addLayout(input_layout)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def handle_link_click(self, url):
        """Passes local file paths to Windows host to open in default Windows applications."""
        local_path = url.toLocalFile()
        if os.path.exists(local_path):
            try:
                # Use Windows shell via cmd.exe to launch default viewer from WSL
                subprocess.run(["cmd.exe", "/c", "start", "", local_path], check=False)
            except Exception as e:
                self.log_display.append(f"<font color='red'>[Error Opening File]: {e}</font>")

    def cancel_tx(self):
        self.tx_pacer.stop()
        self.arq_timer.stop()
        self.next_seq_num = self.send_base
        self.total_file_chunks = 0
        self.progress_bar.setValue(0)
        
        if os.path.exists(self.tx_file):
            try:
                os.remove(self.tx_file)
            except Exception:
                pass

        self.log_display.append("<font color='red'><b>[TX Cancelled]:</b> Active transmission stopped.</font>")

    def trigger_gbn_transmission(self):
        if not self.tx_pacer.isActive():
            self.tx_pacer.start(FRAME_PACING_MS)

    def gbn_transmit_step(self):
        if self.next_seq_num < (self.send_base + WINDOW_SIZE) and self.next_seq_num < len(self.tx_packets):
            pkt = self.tx_packets[self.next_seq_num]
            self._write_to_tx_file(pkt)

            if self.send_base == self.next_seq_num:
                self.arq_timer.start(ARQ_TIMEOUT_MS)

            self.log_display.append(
                f"<font color='gray'>[GBN TX]: Sent Frame Seq {self.next_seq_num} (Window: [{self.send_base}..{self.send_base + WINDOW_SIZE - 1}])</font>"
            )
            self.next_seq_num += 1
        else:
            if self.next_seq_num >= len(self.tx_packets) or self.next_seq_num >= (self.send_base + WINDOW_SIZE):
                self.tx_pacer.stop()

    def _write_to_tx_file(self, pkt):
        try:
            with open(self.tx_file, "wb") as f:
                f.write(pkt)
        except Exception as e:
            self.log_display.append(f"<font color='red'>[TX Error]: {e}</font>")

    def send_text(self):
        text = self.msg_input.text().strip()
        if not text:
            return
        
        seq = len(self.tx_packets)
        hdr = struct.pack(">BH", 0x01, seq)
        full_pkt = hdr + text.encode('utf-8')
        
        self.tx_packets.append(full_pkt)
        self.log_display.append(f"<font color='black'><b>[Node {self.node_id} TX Text Queued]:</b> '{text}' (Seq {seq})</font>")
        self.msg_input.clear()
        
        self.trigger_gbn_transmission()

    def send_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Send", "", "All Files (*)")
        if not file_path:
            return
        
        filename = os.path.basename(file_path)
        fn_bytes = filename.encode('utf-8')
        if len(fn_bytes) > 255:
            self.log_display.append("<font color='red'>[Error]: Filename too long.</font>")
            return

        with open(file_path, "rb") as f:
            content = f.read()

        file_size = len(content)
        file_id = random.randint(1, 255)
        chunks = [content[i:i+CHUNK_SIZE] for i in range(0, file_size, CHUNK_SIZE)]
        total_chunks = len(chunks)

        self.file_start_seq = len(self.tx_packets)
        self.total_file_chunks = total_chunks
        self.progress_bar.setRange(0, total_chunks)
        self.progress_bar.setValue(0)

        self.log_display.append(
            f"<font color='purple'><b>[TX File Initiated]:</b> {filename} ({file_size} bytes, {total_chunks} chunks)</font>"
        )

        for idx, chunk_data in enumerate(chunks):
            seq = len(self.tx_packets)
            hdr = struct.pack(">BHBHHB", 0x02, seq, file_id, idx, total_chunks, len(fn_bytes)) + fn_bytes
            full_pkt = hdr + chunk_data
            self.tx_packets.append(full_pkt)

        self.trigger_gbn_transmission()

    def handle_gbn_timeout(self):
        self.log_display.append(
            f"<font color='red'><b>[GBN Timeout!]:</b> Retransmitting window starting from Seq {self.send_base} up to {self.next_seq_num - 1}...</font>"
        )
        self.next_seq_num = self.send_base
        self.arq_timer.start(ARQ_TIMEOUT_MS)
        self.trigger_gbn_transmission()

    def check_rx(self):
        if os.path.exists(self.rx_file):
            try:
                with open(self.rx_file, "rb") as f:
                    data = f.read()
                os.remove(self.rx_file)
                
                if len(data) >= 3:
                    pkt_type = data[0]

                    # 1. Received ACK
                    if pkt_type == 0x04:
                        _, ack_seq = struct.unpack(">BH", data[:3])
                        
                        if ack_seq >= self.send_base:
                            self.log_display.append(
                                f"<font color='green'><b>[GBN ACK Received]:</b> Cumulative ACK for Seq {ack_seq}</font>"
                            )
                            self.send_base = ack_seq + 1
                            
                            if hasattr(self, 'total_file_chunks') and self.total_file_chunks > 0:
                                chunks_acked = max(0, self.send_base - self.file_start_seq)
                                self.progress_bar.setValue(min(chunks_acked, self.total_file_chunks))
                                if chunks_acked >= self.total_file_chunks:
                                    self.log_display.append("<font color='gray'><b>[TX Complete]:</b> All file chunks confirmed.</font>")
                                    self.total_file_chunks = 0  

                            if self.send_base == self.next_seq_num:
                                self.arq_timer.stop()
                            else:
                                self.arq_timer.start(ARQ_TIMEOUT_MS)

                            self.trigger_gbn_transmission()
                        return

                    # 2. Received Data Frame
                    if pkt_type in [0x01, 0x02]:
                        _, rx_seq = struct.unpack(">BH", data[:3])

                        if rx_seq == self.expected_seq_num:
                            self.send_ack(rx_seq)
                            self.expected_seq_num += 1

                            if pkt_type == 0x01:
                                text = data[3:].decode('utf-8', errors='ignore')
                                self.log_display.append(f"<font color='blue'><b>[Node {self.node_id} RX Text]:</b> {text}</font>")

                            elif pkt_type == 0x02:
                                hdr_fmt = ">BHBHHB"
                                hdr_size = struct.calcsize(hdr_fmt)
                                _, _, file_id, chunk_idx, total_chunks, fn_len = struct.unpack(hdr_fmt, data[:hdr_size])
                                filename = data[hdr_size : hdr_size + fn_len].decode('utf-8', errors='ignore')
                                chunk_payload = data[hdr_size + fn_len :]

                                if file_id not in self.rx_file_buffers:
                                    self.rx_file_buffers[file_id] = {
                                        'filename': filename,
                                        'total_chunks': total_chunks,
                                        'chunks': {}
                                    }

                                self.rx_file_buffers[file_id]['chunks'][chunk_idx] = chunk_payload
                                received_count = len(self.rx_file_buffers[file_id]['chunks'])

                                if received_count == total_chunks:
                                    file_buf = self.rx_file_buffers[file_id]
                                    full_data = bytearray()
                                    for i in range(total_chunks):
                                        full_data.extend(file_buf['chunks'][i])
                                    
                                    save_dir = f"/tmp/node{self.node_id}_downloads"
                                    os.makedirs(save_dir, exist_ok=True)
                                    out_path = os.path.abspath(os.path.join(save_dir, file_buf['filename']))
                                    
                                    with open(out_path, "wb") as f:
                                        f.write(full_data)

                                    del self.rx_file_buffers[file_id]

                                    ext = os.path.splitext(filename)[1].lower()
                                    file_url = QUrl.fromLocalFile(out_path).toString()

                                    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                                        self.log_display.append(
                                            f"<font color='blue'><b>[Node {self.node_id} RX Image Complete]:</b> {filename} ({len(full_data)} bytes)</font><br/>"
                                            f"<a href='{file_url}'><img src='{out_path}' width='250'></a><br/>"
                                            f"<a href='{file_url}'><b>🔍 Click Here to Open Image Externally</b></a>"
                                        )
                                    elif ext in ['.wav', '.mp3', '.ogg', '.flac']:
                                        self.log_display.append(
                                            f"<font color='blue'><b>[Node {self.node_id} RX Audio Complete]:</b> {filename} ({len(full_data)} bytes)</font><br/>"
                                            f"<a href='{file_url}'><b>▶ Click Here to Play Audio File ({filename})</b></a>"
                                        )
                                    else:
                                        self.log_display.append(
                                            f"<font color='blue'><b>[Node {self.node_id} RX File Complete]:</b> Saved to <i>{out_path}</i> ({len(full_data)} bytes)</font><br/>"
                                            f"<a href='{file_url}'><b>📁 Click Here to Open File</b></a>"
                                        )

                        else:
                            self.log_display.append(
                                f"<font color='orange'><b>[GBN RX Discard]:</b> Expected Seq {self.expected_seq_num}, got Seq {rx_seq}. Re-ACKing last good frame.</font>"
                            )
                            if self.expected_seq_num > 0:
                                self.send_ack(self.expected_seq_num - 1)

            except Exception as e:
                pass

    def send_ack(self, ack_seq):
        ack_pkt = struct.pack(">BH", 0x04, ack_seq)
        self._write_to_tx_file(ack_pkt)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    node_arg = sys.argv[1] if len(sys.argv) > 1 else 'A'
    win = TransceiverApp(node_arg)
    win.show()
    sys.exit(app.exec_())