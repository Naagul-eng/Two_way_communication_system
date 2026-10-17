import json
from pathlib import Path


def load(path):
    path = Path(path).resolve()
    c = json.loads(path.read_text())
    if not 1 <= c['address'] <= 65534:
        raise ValueError('Node address must be 0x0001..0xFFFE')
    c['state_dir'] = str((path.parent / c['state_dir']).resolve())
    c['config_path'] = str(path)
    Path(c['state_dir']).mkdir(parents=True, exist_ok=True)
    return c


def addr(value):
    return f'0x{int(value):04X}'
