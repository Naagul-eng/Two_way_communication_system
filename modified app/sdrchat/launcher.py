"""Own the hardware subprocess for the lifetime of the desktop application."""
import json
import os
from pathlib import Path
import sys
from PyQt5 import QtCore, QtWidgets as W


def configure_radio(path, parent=None):
    """Ask for this machine's SDR URI once, after invitation import."""
    path = Path(path)
    config = json.loads(path.read_text())
    if config.get('local_radio_configured'):
        return True
    uri, accepted = W.QInputDialog.getText(
        parent, 'Connect your SDR', 'Address of your own SDR:',
        text=config.get('uri', 'ip:192.168.1.10'))
    if not accepted:
        return False
    if not uri.strip():
        W.QMessageBox.warning(parent, 'SDR address', 'Enter the URI of your SDR, for example ip:192.168.1.10.')
        return False
    config.update(uri=uri.strip(), local_radio_configured=True)
    path.write_text(json.dumps(config, indent=2) + '\n')
    return True


class RadioProcess(QtCore.QObject):
    failed = QtCore.pyqtSignal(str)

    def __init__(self, config, parent=None, command=None):
        super().__init__(parent)
        self.config = config
        self.command = command or [sys.executable, '-u', '-m', 'sdrchat.hardware',
                                   '--config', config['config_path']]
        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.process.setWorkingDirectory(str(Path(__file__).resolve().parents[1]))
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self.stopping = False
        self.reported = False
        self.tail = ''
        self.log_path = Path(config['state_dir']) / 'radio.log'
        # Shared across copies, so the same node's ports cannot be launched twice.
        self.lock = QtCore.QLockFile(str(Path('/tmp') / (
            f"pixel-pulse-{os.getuid()}-{config['commands_port']}-{config['events_port']}.lock")))
        self.lock.setStaleLockTime(0)

    def start(self):
        if self.process.state() != QtCore.QProcess.NotRunning:
            return
        self.stopping = False
        self.reported = False
        self.tail = ''
        if not self.lock.tryLock(0):
            self._report('This node is already open. Close its other app/radio window and retry.')
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text('Starting radio\n')
        self.process.start(self.command[0], self.command[1:])

    def _read(self):
        text = bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace')
        self.tail = (self.tail + text)[-6000:]
        with self.log_path.open('a') as output:
            output.write(text)

    def _report(self, message):
        if not self.stopping and not self.reported:
            self.reported = True
            self.failed.emit(message)

    def _error(self, error):
        if error == QtCore.QProcess.FailedToStart:
            self.lock.unlock()
            self._report(self.process.errorString())

    def _finished(self, exit_code, exit_status):
        self._read()
        self.lock.unlock()
        self._report(f'Radio stopped (exit {exit_code}).\n\n{self.tail[-2500:]}')

    def stop(self):
        self.stopping = True
        if self.process.state() != QtCore.QProcess.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(5000):
                self.process.kill()
                self.process.waitForFinished(2000)
        self.lock.unlock()


def attach_radio(app, window, config):
    radio = RadioProcess(config, window)

    def failed(message):
        window.details_note.setText('Radio offline. Check your SDR connection and radio.log.')
        dialog = W.QMessageBox(window)
        dialog.setWindowTitle('Radio could not stay connected')
        dialog.setIcon(W.QMessageBox.Warning)
        dialog.setText('Check that your SDR is connected and powered on. You can retry or keep the app open offline.')
        dialog.setDetailedText(message + '\n\nLog: ' + str(radio.log_path))
        dialog.setStandardButtons(W.QMessageBox.Retry | W.QMessageBox.Close)
        dialog.button(W.QMessageBox.Close).setText('Continue offline')
        if dialog.exec_() == W.QMessageBox.Retry:
            QtCore.QTimer.singleShot(0, radio.start)

    radio.failed.connect(failed)
    app.aboutToQuit.connect(radio.stop)
    window.radio_process = radio
    QtCore.QTimer.singleShot(0, radio.start)
    return radio
