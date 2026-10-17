"""Graphical entry point: prepare radio assets, then open Pixel Pulse."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
try:
    from PyQt5 import QtCore, QtGui, QtWidgets as W
except ImportError:
    message = 'Pixel Pulse needs its Linux dependencies installed first. See README.md in ' + str(ROOT)
    import shutil
    if shutil.which('zenity'):
        subprocess.run(['zenity', '--error', '--text', message])
    else:
        print(message, file=sys.stderr)
    raise SystemExit(1)


def main():
    app = W.QApplication(sys.argv)
    app.setApplicationName('Pixel Pulse')
    app.setDesktopFileName('pixel-pulse')
    app.setWindowIcon(QtGui.QIcon(str(ROOT/'assets/pixel-pulse.svg')))
    dialog = W.QProgressDialog('Preparing your radio…', 'Cancel', 0, 0)
    dialog.setWindowTitle('Pixel Pulse')
    dialog.setMinimumDuration(0)
    dialog.setMinimumWidth(380)
    process = QtCore.QProcess(app)
    process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
    output = []
    result = {'code': 1, 'cancelled': False}

    def read():
        output.append(bytes(process.readAllStandardOutput()).decode('utf-8', errors='replace'))

    def cancel():
        result['cancelled'] = True
        process.terminate()
        if not process.waitForFinished(2000):
            process.kill()
            process.waitForFinished(2000)
        app.quit()

    def finished(code, status):
        read()
        result['code'] = code if status == QtCore.QProcess.NormalExit else 1
        app.quit()

    def error(value):
        if value == QtCore.QProcess.FailedToStart:
            output.append(process.errorString())
            app.quit()

    process.readyReadStandardOutput.connect(read)
    process.finished.connect(finished)
    process.errorOccurred.connect(error)
    dialog.canceled.connect(cancel)
    process.start('/bin/bash', [str(ROOT/'start.sh'), '--prepare-only'])
    dialog.show()
    app.exec_()
    dialog.hide()
    if result['cancelled']:
        return 0
    if result['code']:
        message = W.QMessageBox()
        message.setWindowTitle('Pixel Pulse setup')
        message.setIcon(W.QMessageBox.Critical)
        message.setText('Pixel Pulse could not prepare the radio. See the details below.')
        message.setDetailedText(''.join(output)[-10000:])
        message.exec_()
        return result['code']
    args = [sys.executable, '-m', 'sdrchat.app']
    if (ROOT/'.coordinator').exists():
        args += ['--config', str(ROOT/'configs/node_a.json')]
    os.execv(sys.executable, args)


if __name__ == '__main__':
    sys.exit(main())
