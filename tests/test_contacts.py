"""Contact identity and persistence regressions; no radio hardware required."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from unittest.mock import patch
from PyQt5 import QtWidgets as W
from sdrchat.app import Database, ContactDialog


class ContactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = W.QApplication.instance() or W.QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = dict(state_dir=self.temp.name, address=1,
                           contacts=[dict(address=2, name='Bob')])
        self.book = Database(self.config)

    def tearDown(self):
        self.book.db.close()
        self.temp.cleanup()

    def test_deleted_config_contact_stays_deleted_after_restart(self):
        self.book.db.execute('DELETE FROM contacts WHERE address=2')
        self.book.db.commit()
        self.book.db.close()
        self.book = Database(self.config)
        self.assertIsNone(self.book.db.execute('SELECT 1 FROM contacts WHERE address=2').fetchone())
        self.assertIsNotNone(self.book.db.execute('SELECT 1 FROM contacts WHERE address=65535').fetchone())

    def test_existing_node_address_and_duplicate_validation(self):
        dialog = ContactDialog(self.book)
        self.assertFalse(dialog.address.isReadOnly())
        dialog.name.setText('Charlie')
        dialog.address.setText('0x003A')
        dialog.save()
        self.assertEqual(dialog.result(), W.QDialog.Accepted)
        duplicate = ContactDialog(self.book)
        duplicate.name.setText('Another Charlie')
        duplicate.address.setText('0x003A')
        with patch.object(W.QMessageBox, 'warning') as warning:
            duplicate.save()
            warning.assert_called_once()
        self.assertEqual(self.book.db.execute('SELECT name FROM contacts WHERE address=58').fetchone()[0], 'Charlie')

    def test_reserved_and_own_addresses_are_rejected(self):
        for value in ('0x0000', '0x0001', '0xFFFF', 'invalid'):
            dialog = ContactDialog(self.book)
            dialog.name.setText('Peer')
            dialog.address.setText(value)
            with patch.object(W.QMessageBox, 'warning') as warning:
                dialog.save()
                warning.assert_called_once()
            self.assertNotEqual(dialog.result(), W.QDialog.Accepted)

    def test_edit_preserves_unique_address(self):
        dialog = ContactDialog(self.book, (2, 'Bob', 1))
        self.assertTrue(dialog.address.isReadOnly())
        dialog.name.setText('Robert')
        dialog.save()
        self.assertEqual(self.book.db.execute('SELECT name FROM contacts WHERE address=2').fetchone()[0], 'Robert')

    def test_allocated_address_is_not_reserved_or_used(self):
        dialog = ContactDialog(self.book)
        dialog.mode.setCurrentIndex(1)
        self.assertTrue(dialog.address.isReadOnly())
        self.assertNotIn(int(dialog.address.text(), 16), (0, 1, 2, 65535))
