import sys
import os
from PyQt5 import QtWidgets, QtGui, QtCore

RECEIVED_FILE_PATH = "/tmp/received_message.bin"

class ReceiverGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.last_mtime = 0
        
        # Poll the received file every 500ms
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.check_for_received_message)
        self.timer.start(500)

    def initUI(self):
        self.setWindowTitle('SDR Dedicated Receiver Dashboard')
        self.resize(600, 500)
        
        layout = QtWidgets.QVBoxLayout()
        tabs = QtWidgets.QTabWidget()
        
        # --- TAB 1: TEXT ---
        tab_text = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout()
        self.received_text_display = QtWidgets.QTextEdit()
        self.received_text_display.setReadOnly(True)
        text_layout.addWidget(QtWidgets.QLabel("Incoming Decoded Text:"))
        text_layout.addWidget(self.received_text_display)
        tab_text.setLayout(text_layout)
        tabs.addTab(tab_text, "Received Text")

        # --- TAB 2: IMAGE ---
        tab_image = QtWidgets.QWidget()
        image_layout = QtWidgets.QVBoxLayout()
        self.image_display_label = QtWidgets.QLabel("Waiting for image transmission...")
        self.image_display_label.setAlignment(QtCore.Qt.AlignCenter)
        image_layout.addWidget(self.image_display_label)
        tab_image.setLayout(image_layout)
        tabs.addTab(tab_image, "Received Image")

        # --- TAB 3: AUDIO ---
        tab_audio = QtWidgets.QWidget()
        audio_layout = QtWidgets.QVBoxLayout()
        self.audio_status_label = QtWidgets.QLabel("Waiting for audio transmission...")
        self.play_audio_btn = QtWidgets.QPushButton("Play Received Audio (.wav)")
        self.play_audio_btn.setEnabled(False)
        self.play_audio_btn.clicked.connect(self.play_audio)
        audio_layout.addWidget(self.audio_status_label)
        audio_layout.addWidget(self.play_audio_btn)
        tab_audio.setLayout(audio_layout)
        tabs.addTab(tab_audio, "Received Audio")

        layout.addWidget(tabs)
        
        # Receiver Log Console
        self.log_console = QtWidgets.QTextEdit()
        self.log_console.setReadOnly(True)
        layout.addWidget(QtWidgets.QLabel("Receiver System Log:"))
        layout.addWidget(self.log_console)

        self.setLayout(layout)

    def log(self, message):
        self.log_console.append(message)

    def check_for_received_message(self):
        if not os.path.exists(RECEIVED_FILE_PATH):
            return
        try:
            mtime = os.path.getmtime(RECEIVED_FILE_PATH)
            if mtime != self.last_mtime:
                self.last_mtime = mtime
                with open(RECEIVED_FILE_PATH, "rb") as f:
                    data = f.read()
                if len(data) < 2:
                    return
                
                packet_type = data[0]
                payload = data[1:]
                
                if packet_type == 0x01: # Text
                    text_msg = payload.decode('utf-8', errors='ignore')
                    self.received_text_display.append(text_msg)
                    self.log(f"Successfully Decoded Text: {text_msg}")
                elif packet_type == 0x02: # Image
                    img_path = "/tmp/received_image.png"
                    with open(img_path, "wb") as img_f:
                        img_f.write(payload)
                    pixmap = QtGui.QPixmap(img_path)
                    self.image_display_label.setPixmap(pixmap.scaled(450, 450, QtCore.Qt.KeepAspectRatio))
                    self.log(f"Successfully Decoded Image ({len(payload)} bytes)")
                elif packet_type == 0x03: # Audio
                    self.received_audio_path = "/tmp/received_audio.wav"
                    with open(self.received_audio_path, "wb") as aud_f:
                        aud_f.write(payload)
                    self.audio_status_label.setText(f"Audio ready ({len(payload)} bytes)")
                    self.play_audio_btn.setEnabled(True)
                    self.log(f"Successfully Decoded Audio ({len(payload)} bytes)")
        except Exception as e:
            pass

    def play_audio(self):
        if hasattr(self, 'received_audio_path') and os.path.exists(self.received_audio_path):
            os.system(f"aplay {self.received_audio_path} &")
            self.log("Playing received audio file...")

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ex = ReceiverGUI()
    ex.show()
    sys.exit(app.exec_())