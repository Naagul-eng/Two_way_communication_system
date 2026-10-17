"""Coordinator-issued node invitations and non-secret contact cards."""
import base64
import binascii
import hashlib
import json
from pathlib import Path
from cryptography.fernet import Fernet


def network_id(config):
    return hashlib.sha256(config['shared_key'].encode()).hexdigest()[:16]


def contact_card(config):
    return dict(format='pixel-pulse-contact',version=1,name=config['name'],
                address=config['address'],network=network_id(config))


def contact_code(config):
    data=json.dumps(contact_card(config),ensure_ascii=False,separators=(',',':')).encode()
    return 'PP1:'+base64.urlsafe_b64encode(data).decode().rstrip('=')


def make_invitation(config,address,name):
    if type(address) is not int or not 1<=address<=65534 or address==config['address']:
        raise ValueError('An invitation needs a different, non-reserved node address')
    c={k:v for k,v in config.items() if k!='config_path'}
    c.update(invitation_format='pixel-pulse-invitation',invitation_version=1,
             address=address,name=name,state_dir='./data/'+f'{address:04x}',commands_port=5555,events_port=5556,
             contacts=[dict(address=config['address'],name=config['name'],priority=1)])
    return c


def parse_contact(value,config):
    try:
        if isinstance(value,str) and value.strip().startswith('PP1:'):
            encoded=value.strip()[4:]
            if len(encoded)>4096:raise ValueError('Contact code is too long')
            card=json.loads(base64.b64decode(encoded+'='*(-len(encoded)%4),altchars=b'-_',validate=True))
        elif isinstance(value,dict):card=value
        else:raise ValueError('Paste a Pixel Pulse contact code beginning with PP1:')
        if not isinstance(card,dict) or card.get('format')!='pixel-pulse-contact' or card.get('version')!=1:
            raise ValueError('Unsupported contact card')
        address=card['address'];name=card['name']
        if type(address) is not int or not 1<=address<=65534:raise ValueError('Invalid node address')
        if not isinstance(name,str) or not name.strip() or len(name)>100:raise ValueError('Invalid contact name')
        if card.get('network')!=network_id(config):raise ValueError('This contact is on a different radio network. Ask for an invitation to the same network.')
        if address==config['address']:raise ValueError('This is your own address. Each person must use a different invitation.')
        return dict(address=address,name=name.strip())
    except (KeyError,TypeError,json.JSONDecodeError,UnicodeDecodeError) as exc:
        raise ValueError('Invalid Pixel Pulse contact card') from exc
    except binascii.Error as exc:
        raise ValueError('Invalid Pixel Pulse contact code') from exc


def accept_invitation(invitation,name,destination):
    name=name.strip()
    if not name or len(name)>100:raise ValueError('Enter your name (up to 100 characters)')
    c=json.loads(Path(invitation).read_text())
    if not isinstance(c,dict) or c.get('invitation_format')!='pixel-pulse-invitation' or c.get('invitation_version')!=1:
        raise ValueError('Select an invitation created with Invite someone, not another person\'s node profile')
    required=('frequency','sample_rate','uri','commands_port','events_port','state_dir','cs_threshold_db','shared_key','address')
    if any(key not in c for key in required):raise ValueError('Invitation is missing radio settings')
    if type(c['address']) is not int or not 1<=c['address']<=65534:raise ValueError('Invalid assigned address')
    Fernet(c['shared_key'].encode())
    if any(person['address']==c['address'] for person in c.get('contacts',[])):
        raise ValueError('Invitation assigns the same address as an existing contact')
    c.pop('invitation_format',None);c.pop('invitation_version',None)
    c.pop('local_radio_configured',None)
    c.update(name=name,state_dir='../data/my_node')
    target=Path(destination)
    target.parent.mkdir(parents=True,exist_ok=True)
    # Refuse to silently overwrite an established node identity.
    with target.open('x') as output:output.write(json.dumps(c,indent=2)+'\n')
    return target
