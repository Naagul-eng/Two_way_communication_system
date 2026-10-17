"""Save this computer's SDR URI before starting the separate radio process."""
import json
from pathlib import Path
from PyQt5 import QtWidgets as W


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
