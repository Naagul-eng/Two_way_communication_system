"""Unread delivery, activity ordering, and persistent chat pins."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import zmq
from PyQt5 import QtCore, QtWidgets as W
from sdrchat.app import Database, Window


class ChatActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = W.QApplication.instance() or W.QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = json.loads((Path(__file__).resolve().parents[1] / 'configs/node_a.example.json').read_text())
        self.config.update(state_dir=self.temp.name, contacts=[
            dict(address=2, name='Bob'), dict(address=3, name='Charlie')])
        self.book = Database(self.config)

    def tearDown(self):
        self.book.db.close()
        self.temp.cleanup()

    def event(self,ident='first',src=2):
        return dict(event='received', id=ident, src=src, kind='text', text='Hello')

    def state(self,address):
        return self.book.db.execute('SELECT pinned,unread FROM chat_state WHERE address=?',(address,)).fetchone()

    def test_unread_counts_deduplicate_and_survive_restart(self):
        self.assertTrue(self.book.receive(self.event()))
        self.assertFalse(self.book.receive(self.event()))
        self.book.receive(self.event('second'))
        self.book.db.close()
        self.book = Database(self.config)
        self.assertEqual(self.state(2), (0,2))
        self.book.mark_read(2)
        self.assertEqual(self.state(2), (0,0))

    def test_visible_messages_are_read_and_other_contacts_stay_unread(self):
        self.book.receive(self.event(),read=True)
        self.book.receive(self.event('other',src=3))
        self.assertIsNone(self.state(2))
        self.assertEqual(self.state(3), (0,1))
        self.book.mark_read(2)
        self.assertEqual(self.state(3), (0,1))

    def test_latest_message_moves_chat_above_others_but_below_pins(self):
        with patch('sdrchat.app.time.time',return_value=100):
            self.book.receive(self.event())
        with patch('sdrchat.app.time.time',return_value=200):
            self.book.receive(self.event('new',src=3))
        self.assertEqual([r[0] for r in self.book.ordered_contacts()][:2],[3,2])
        self.book.toggle_pin(2)
        self.assertEqual([r[0] for r in self.book.ordered_contacts()][:2],[2,3])
        self.assertEqual(self.state(2), (1,1))
        self.book.db.close()
        self.book = Database(self.config)
        self.assertEqual(self.book.ordered_contacts()[0][0],2)
        self.book.toggle_pin(2)
        self.assertEqual(self.book.ordered_contacts()[0][0],3)

    def test_incoming_event_updates_badge_without_switching_open_chat(self):
        window = Window(self.config)
        window.timer.stop()
        real_rx = window.rx
        try:
            window.selected=3;window.refresh_contacts();window.select_contact(window.contacts.currentItem())
            window.rx=Mock()
            window.rx.recv_json.side_effect=[self.event(),self.event(),self.event('second'),zmq.Again()]
            with patch.object(window,'conversation_visible',return_value=False):
                window.poll()
            self.assertEqual(window.selected,3)
            self.assertEqual(window.contacts.item(0).data(QtCore.Qt.UserRole),2)
            self.assertEqual(window.contacts.item(0).data(QtCore.Qt.UserRole+2),(2,False))
            # Opening the chat clears its badge while retaining the pin.
            window.toggle_pin(address=2)
            with patch.object(window,'conversation_visible',return_value=True):
                window.select_contact(window.contacts.item(0))
            self.assertEqual(window.contacts.item(0).data(QtCore.Qt.UserRole+2),(0,True))
            self.assertEqual(window.pin_action.text(),'Unpin chat')
        finally:
            window.rx=real_rx
            window.close()

    def test_hidden_startup_does_not_clear_persisted_badge(self):
        self.book.receive(self.event())
        window = Window(self.config)
        window.timer.stop()
        try:
            self.assertEqual(window.contacts.item(0).data(QtCore.Qt.UserRole+2),(1,False))
            self.assertFalse(window.conversation_visible(2))
        finally:
            window.close()
