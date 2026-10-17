"""Check radio process ownership without touching SDR hardware."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import json
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from PyQt5 import QtCore, QtWidgets as W
from sdrchat.launcher import RadioProcess, configure_radio
from sdrchat.identity import make_invitation, accept_invitation


class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = W.QApplication.instance() or W.QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = dict(state_dir=self.temp.name, commands_port=29555, events_port=29556,
                           config_path=str(Path(self.temp.name)/'node.json'))
        self.radios = []

    def tearDown(self):
        for radio in self.radios:
            radio.stop()
        self.temp.cleanup()

    def radio(self, code):
        radio = RadioProcess(self.config, command=[sys.executable, '-u', '-c', code])
        self.radios.append(radio)
        return radio

    def until(self, condition):
        end = time.monotonic()+4
        while not condition() and time.monotonic()<end:
            self.app.processEvents()
            time.sleep(.01)
        self.assertTrue(condition())

    def test_start_duplicate_protection_stop_and_restart(self):
        first=self.radio('import time; print("ready", flush=True); time.sleep(30)')
        errors=[];first.failed.connect(errors.append);first.start()
        self.until(lambda:'ready' in first.tail)
        second=self.radio('import time; time.sleep(30)')
        duplicate=[];second.failed.connect(duplicate.append);second.start()
        self.assertTrue(duplicate)
        self.assertEqual(second.process.state(),QtCore.QProcess.NotRunning)
        first.stop()
        self.assertEqual(first.process.state(),QtCore.QProcess.NotRunning)
        self.assertEqual(errors,[])
        second.start()
        self.until(lambda:second.process.state()==QtCore.QProcess.Running)

    def test_failure_reports_log_and_allows_retry(self):
        radio=self.radio('import sys; print("device unavailable"); sys.exit(7)')
        errors=[];radio.failed.connect(errors.append);radio.start()
        self.until(lambda:bool(errors))
        self.assertIn('device unavailable',errors[0])
        self.assertIn('device unavailable',radio.log_path.read_text())
        radio.command=[sys.executable,'-u','-c','import time; print("retry ready"); time.sleep(30)']
        radio.start();self.until(lambda:'retry ready' in radio.tail)

    def test_uri_is_requested_once_and_cancel_keeps_profile(self):
        path=Path(self.config['config_path']);path.write_text(json.dumps(dict(uri='ip:old')))
        with patch.object(W.QInputDialog,'getText',return_value=('ip:new',True)) as prompt:
            self.assertTrue(configure_radio(path))
            self.assertTrue(configure_radio(path))
            self.assertEqual(prompt.call_count,1)
        self.assertEqual(json.loads(path.read_text())['uri'],'ip:new')
        path.write_text(json.dumps(dict(uri='ip:old')))
        with patch.object(W.QInputDialog,'getText',return_value=('',False)):
            self.assertFalse(configure_radio(path))
        self.assertEqual(json.loads(path.read_text()),dict(uri='ip:old'))

    def test_invitation_does_not_skip_recipient_radio_setup(self):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/'configs/node_a.example.json').read_text())
        config['local_radio_configured']=True
        source=Path(self.temp.name)/'invite.json'
        source.write_text(json.dumps(make_invitation(config,1234,'Friend')))
        target=Path(self.temp.name)/'friend.json'
        accept_invitation(source,'Friend',target)
        self.assertNotIn('local_radio_configured',json.loads(target.read_text()))


if __name__=='__main__':unittest.main()
