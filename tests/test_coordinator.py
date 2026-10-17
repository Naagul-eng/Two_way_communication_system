"""Check fresh-network setup and preservation of existing local identities."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from cryptography.fernet import Fernet
from tools.create_coordinator import create_coordinator


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'configs').mkdir()
        source = Path(__file__).resolve().parents[1] / 'configs/node_a.example.json'
        shutil.copy2(source, self.root / 'configs/node_a.example.json')

    def test_fresh_network_uses_new_key_and_local_profile(self):
        target = create_coordinator(self.root, ' Alice ', 'ip:192.168.2.1')
        config = json.loads(target.read_text())
        self.assertEqual(config['name'], 'Alice')
        self.assertEqual(config['uri'], 'ip:192.168.2.1')
        self.assertFalse(config['local_radio_configured'])
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / '.coordinator').exists())
        example = json.loads((self.root / 'configs/node_a.example.json').read_text())
        self.assertNotEqual(config['shared_key'], example['shared_key'])
        cipher = Fernet(config['shared_key'].encode())
        self.assertEqual(cipher.decrypt(cipher.encrypt(b'hello')), b'hello')
        original = target.read_bytes()
        with self.assertRaises(FileExistsError):
            create_coordinator(self.root)
        self.assertEqual(target.read_bytes(), original)

    def test_existing_friend_or_history_is_preserved(self):
        for relative in ('configs/my_node.json', 'data/node_a/chat.sqlite'):
            with self.subTest(relative=relative):
                existing = self.root / relative
                existing.parent.mkdir(parents=True, exist_ok=True)
                existing.write_bytes(b'existing identity')
                with self.assertRaises(FileExistsError):
                    create_coordinator(self.root)
                self.assertEqual(existing.read_bytes(), b'existing identity')
                self.assertFalse((self.root / 'configs/node_a.json').exists())
                existing.unlink()

    def test_invalid_input_creates_no_profile(self):
        for name, uri in (('', 'ip:device'), ('x' * 101, 'ip:device'), ('Alice', ' ')):
            with self.assertRaises(ValueError):
                create_coordinator(self.root, name, uri)
        self.assertFalse((self.root / 'configs/node_a.json').exists())


if __name__ == '__main__':
    unittest.main()
