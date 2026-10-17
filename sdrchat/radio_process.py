"""Run the radio alongside the chat window and stop it when the session ends."""
import os
from pathlib import Path
import sys
from PyQt5 import QtCore, QtWidgets as W


class RadioProcess(QtCore.QObject):
    failed = QtCore.pyqtSignal(str)

    def __init__(self, config, parent=None, command=None):
        super().__init__(parent)
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
        if text:
            print(text, end='', flush=True)

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
        dialog.setWindowTitle('Radio connection')
        dialog.setIcon(W.QMessageBox.Warning)
        dialog.setText('The radio could not connect. Check your SDR and retry, or continue offline.')
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
