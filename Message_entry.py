import pmt
from gnuradio import gr
from PyQt5 import QtWidgets


class blk(gr.sync_block, QtWidgets.QWidget):
    """
    Small floating text-entry window.
    Type a message, press Enter or click Send, and it publishes
    the text as a PMT message on the 'msg' output port.

    Wire this block's 'msg' output directly into
    Message Strobe's 'set_msg' input port. Message Strobe will
    then keep transmitting whatever text you last sent, at its
    configured Period (ms) interval.
    """

    def __init__(self, label='Enter message'):
        gr.sync_block.__init__(
            self,
            name='Message Entry',
            in_sig=None,
            out_sig=None
        )
        QtWidgets.QWidget.__init__(self)

        # Message output port -> connect to Message Strobe's set_msg
        self.message_port_register_out(pmt.intern('msg'))

        # --- Build the floating window ---
        self.setWindowTitle('Message Entry')

        self.layout = QtWidgets.QHBoxLayout(self)
        self.label = QtWidgets.QLabel(label)
        self.edit = QtWidgets.QLineEdit()
        self.button = QtWidgets.QPushButton('Send')

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.edit)
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.button.clicked.connect(self.send_message)
        self.edit.returnPressed.connect(self.send_message)

        # Show as its own standalone window
        self.resize(400, 60)
        self.show()

    def send_message(self):
        text = self.edit.text()
        if text:
            self.message_port_pub(pmt.intern('msg'), pmt.intern(text))

    def work(self, input_items, output_items):
        return 0
