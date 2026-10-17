"""Create the first local profile for a new Pixel Pulse radio network."""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def create_coordinator(root=ROOT, name='User 1', uri='ip:192.168.1.10'):
    root = Path(root)
    name, uri = name.strip(), uri.strip()
    if not name or len(name) > 100:
        raise ValueError('Enter a name of 1 to 100 characters.')
    if not uri:
        raise ValueError('Enter the URI of your own SDR.')
    target = root / 'configs/node_a.json'
    marker = root / '.coordinator'
    state = root / 'data/node_a'
    if (target.exists() or marker.exists() or
            (root / 'configs/my_node.json').exists() or
            (state.exists() and any(state.iterdir()))):
        raise FileExistsError('A local profile or coordinator history already exists. '
                              'Keep it and launch the app using the README instructions.')
    config = json.loads((root / 'configs/node_a.example.json').read_text())
    config.update(name=name, uri=uri,
                  shared_key=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
                  local_radio_configured=False)
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
        output.write(json.dumps(config, indent=2) + '\n')
    marker.write_text('Use configs/node_a.json for this coordinator.\n')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='User 1', help='Your display name')
    parser.add_argument('--uri', default='ip:192.168.1.10', help='Your own SDR URI')
    args = parser.parse_args()
    try:
        target = create_coordinator(name=args.name, uri=args.uri)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')
    print(f'Created {target} with a new network key. Run bash start.sh.')


if __name__ == '__main__':
    main()
