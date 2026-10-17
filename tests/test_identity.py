"""Address provisioning and contact exchange without sharing a node identity."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PyQt5 import QtWidgets as W
from sdrchat.app import Database,ContactDialog,WelcomeDialog
from sdrchat.identity import contact_code,contact_card,parse_contact,make_invitation,accept_invitation


class IdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=W.QApplication.instance() or W.QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.config=json.loads((Path(__file__).resolve().parents[1]/'configs/node_a.example.json').read_text())
        self.config.update(state_dir=self.temp.name,contacts=[])

    def tearDown(self):
        self.temp.cleanup()

    def test_contact_code_roundtrip_excludes_network_key(self):
        peer=dict(self.config,name='Nuwaan',address=2)
        card=contact_card(peer)
        self.assertNotIn('shared_key',card)
        self.assertEqual(parse_contact(contact_code(peer),self.config),dict(address=2,name='Nuwaan'))
        self.assertEqual(parse_contact(card,self.config),dict(address=2,name='Nuwaan'))

    def test_own_address_other_network_and_malformed_codes_rejected(self):
        from cryptography.fernet import Fernet
        peer=dict(self.config,address=2,shared_key=Fernet.generate_key().decode())
        for code in (contact_code(self.config),contact_code(peer),'PP1:!!!','PP1:W10'):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):parse_contact(code,self.config)

    def test_invitation_assigns_address_and_adds_coordinator(self):
        invitation=make_invitation(self.config,2,'New person')
        source=Path(self.temp.name)/'invite.json';source.write_text(json.dumps(invitation))
        target=Path(self.temp.name)/'configs/my_node.json'
        accept_invitation(source,'Nuwaan',target)
        c=json.loads(target.read_text())
        self.assertEqual((c['name'],c['address']),('Nuwaan',2))
        self.assertEqual(c['contacts'][0]['address'],self.config['address'])
        self.assertEqual(c['shared_key'],self.config['shared_key'])
        self.assertNotIn('invitation_format',c)
        with self.assertRaises(ValueError):accept_invitation(target,'Other person',Path(self.temp.name)/'other.json')
        with self.assertRaises(FileExistsError):accept_invitation(source,'Other person',target)
        self.assertEqual(json.loads(target.read_text())['name'],'Nuwaan')

    def test_cannot_use_someone_elses_plain_node_profile_as_invitation(self):
        source=Path(self.temp.name)/'node.json';source.write_text(json.dumps(self.config))
        with self.assertRaises(ValueError):accept_invitation(source,'Nuwaan',Path(self.temp.name)/'new.json')

    def test_first_run_dialog_creates_assigned_profile(self):
        source=Path(self.temp.name)/'invite.json'
        source.write_text(json.dumps(make_invitation(self.config,2,'New person')))
        target=Path(self.temp.name)/'configs/my_node.json'
        dialog=WelcomeDialog(target);dialog.name.setText('Nuwaan');dialog.invitation.setText(str(source));dialog.save()
        self.assertEqual(dialog.result(),W.QDialog.Accepted)
        self.assertEqual(json.loads(target.read_text())['address'],2)

    def test_pasted_contact_code_saves_the_correct_address_and_name(self):
        book=Database(self.config)
        try:
            dialog=ContactDialog(book)
            dialog.code.setText(contact_code(dict(self.config,name='Nuwaan',address=2)))
            self.assertEqual(dialog.name.text(),'Nuwaan')
            dialog.save()
            self.assertEqual(dialog.result(),W.QDialog.Accepted)
            self.assertEqual(book.db.execute('SELECT name FROM contacts WHERE address=2').fetchone()[0],'Nuwaan')
            book.db.execute('DELETE FROM contacts WHERE address=2');book.db.commit()
            # A removed contact may still be using its issued address remotely.
            with patch('sdrchat.app.secrets.randbelow',side_effect=[1,2]):
                self.assertEqual(book.allocate(),3)
        finally:book.db.close()
