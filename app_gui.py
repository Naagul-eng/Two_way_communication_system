import sys
import os
import subprocess
from PyQt5 import QtWidgets

MSG_FILE_PATH = "/tmp/sdr_message.bin"

class MultimediaTransmitterGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        
        # Launch GNU Radio flowgraph as an independent subprocess with unbuffered output
        self.gr_process = None
        self.start_gnuradio_subprocess()

    def initUI(self):
        self.setWindowTitle('SDR Multimedia Dashboard - Text, Image, Audio')
        self.resize(550, 450)
        
        layout = QtWidgets.QVBoxLayout()
        tabs = QtWidgets.QTabWidget()
        
        # --- TAB 1: TEXT ---
        tab_text = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout()
        self.text_input = QtWidgets.QLineEdit()
        self.text_input.setPlaceholderText("Type your message here...")
        send_text_btn = QtWidgets.QPushButton("Transmit Text")
        send_text_btn.clicked.connect(self.send_text_packet)
        text_layout.addWidget(QtWidgets.QLabel("Enter Text Message:"))
        text_layout.addWidget(self.text_input)
        text_layout.addWidget(send_text_btn)
        tab_text.setLayout(text_layout)
        tabs.addTab(tab_text, "Text")

        # --- TAB 2: IMAGE ---
        tab_image = QtWidgets.QWidget()
        image_layout = QtWidgets.QVBoxLayout()
        self.image_path_label = QtWidgets.QLabel("No image selected")
        browse_img_btn = QtWidgets.QPushButton("Browse Image (.png/.jpg)")
        browse_img_btn.clicked.connect(self.browse_image)
        send_img_btn = QtWidgets.QPushButton("Transmit Image")
        send_img_btn.clicked.connect(self.send_image_packet)
        image_layout.addWidget(self.image_path_label)
        image_layout.addWidget(browse_img_btn)
        image_layout.addWidget(send_img_btn)
        tab_image.setLayout(image_layout)
        tabs.addTab(tab_image, "Image")

        # --- TAB 3: AUDIO ---
        tab_audio = QtWidgets.QWidget()
        audio_layout = QtWidgets.QVBoxLayout()
        self.audio_path_label = QtWidgets.QLabel("No audio selected")
        browse_audio_btn = QtWidgets.QPushButton("Browse Audio (.wav)")
        browse_audio_btn.clicked.connect(self.browse_audio)
        send_audio_btn = QtWidgets.QPushButton("Transmit Audio")
        send_audio_btn.clicked.connect(self.send_audio_packet)
        audio_layout.addWidget(self.audio_path_label)
        audio_layout.addWidget(browse_audio_btn)
        audio_layout.addWidget(send_audio_btn)
        tab_audio.setLayout(audio_layout)
        tabs.addTab(tab_audio, "Audio")

        layout.addWidget(tabs)
        
        # Status Log Console
        self.log_console = QtWidgets.QTextEdit()
        self.log_console.setReadOnly(True)
        layout.addWidget(QtWidgets.QLabel("System Transmission Log:"))
        layout.addWidget(self.log_console)

        self.setLayout(layout)

    def start_gnuradio_subprocess(self):
        try:
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Version_1.py")
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"  # Forces live terminal printing from the subprocess
            self.gr_process = subprocess.Popen(["python3", script_path], env=env)
        except Exception as e:
            self.log(f"Failed to start GNU Radio flowgraph: {e}")

    def log(self, message):
        self.log_console.append(message)

    def send_text_packet(self):
        text_data = self.text_input.text()
        if not text_data:
            return
        payload = b'\x01' + text_data.encode('utf-8')
        with open(MSG_FILE_PATH, "wb") as f:
            f.write(payload)
        self.log(f"Transmitted Text Packet: {text_data}")
        self.text_input.clear()

    def browse_image(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open Image', '', 'Image Files (*.png *.jpg *.jpeg)', 
            options=QtWidgets.QFileDialog.DontUseNativeDialog
        )
        if fname:
            self.selected_image = fname
            self.image_path_label.setText(os.path.basename(fname))

    def send_image_packet(self):
        if hasattr(self, 'selected_image') and os.path.exists(self.selected_image):
            with open(self.selected_image, 'rb') as f:
                img_bytes = f.read()
            payload = b'\x02' + img_bytes
            with open(MSG_FILE_PATH, "wb") as f:
                f.write(payload)
            self.log(f"Transmitted Image: {os.path.basename(self.selected_image)} ({len(img_bytes)} bytes)")

    def browse_audio(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open Audio', '', 'Audio Files (*.wav)', 
            options=QtWidgets.QFileDialog.DontUseNativeDialog
        )
        if fname:
            self.selected_audio = fname
            self.audio_path_label.setText(os.path.basename(fname))

    def send_audio_packet(self):
        if hasattr(self, 'selected_audio') and os.path.exists(self.selected_audio):
            with open(self.selected_audio, 'rb') as f:
                audio_bytes = f.read()
            payload = b'\x03' + audio_bytes
            with open(MSG_FILE_PATH, "wb") as f:
                f.write(payload)
            self.log(f"Transmitted Audio: {os.path.basename(self.selected_audio)} ({len(audio_bytes)} bytes)")

    def closeEvent(self, event):
        if self.gr_process:
            self.gr_process.terminate()
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ex = MultimediaTransmitterGUI()
    ex.show()
    sys.exit(app.exec_())