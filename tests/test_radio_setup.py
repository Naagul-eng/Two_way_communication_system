"""Check local SDR configuration without launching radio hardware."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from PyQt5 import QtWidgets as W
from sdrchat.radio_setup import configure_radio
from sdrchat.identity import make_invitation, accept_invitation


class RadioSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = W.QApplication.instance() or W.QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_uri_is_requested_once_and_cancel_keeps_profile(self):
        path=Path(self.temp.name)/'node.json';path.write_text(json.dumps(dict(uri='ip:old')))
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
