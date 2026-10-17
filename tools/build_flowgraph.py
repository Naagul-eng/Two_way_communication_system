"""Create a separate headless GRC; leave the supplied original untouched."""
import argparse
from pathlib import Path
import yaml

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True,help='Path to the original Working1.0.grc')
args=parser.parse_args()
d=yaml.safe_load(args.source.read_text())
remove={'cma_alg','my_addr','peer_addr','shared_key','epy_transfer_chat_gui','epy_transfer_protocol',
        'epy_size_profiles','epy_timeout_profiles','epy_interval_profiles','epy_window_profiles',
        'digital_linear_equalizer_0','epy_block_0','blocks_message_debug_0'}
remove.update(b['name'] for b in d['blocks'] if b['id'].startswith('qtgui_'))
d['blocks']=[b for b in d['blocks'] if b['name'] not in remove]
d['connections']=[c for c in d['connections'] if c[0] not in remove and c[2] not in remove]
d['options']['parameters'].update(id='csma_transceiver',title='EN2130 CSMA/CA QPSK NLMS',generate_options='no_gui',
    description='Headless radio. Launch via python3 -m sdrchat.hardware --config configs/node_a.json',run_options='run')
for b in d['blocks']:
    p=b['parameters']
    if b['name']=='import_0':p['imports']='from gnuradio import filter\nimport os\nfrom sdrchat.config import load\nradio_config = load(os.environ.get("SDRCHAT_CONFIG", "configs/node_a.json"))'
    if b['name']=='freq':p['value']='radio_config["frequency"]'
    if b['name']=='samp_rate':p['value']='radio_config["sample_rate"]'
    if b['id'] in ('iio_pluto_source','iio_pluto_sink'):
        p['frequency']='freq';p['uri']='radio_config["uri"]'
    if b['id']=='iio_pluto_source':
        # Fixed gain makes a fixed pre-AGC energy threshold meaningful.
        p['gain1']="'manual'";p['manual_gain1']='radio_config["rx_gain_db"]'
    if b['id']=='iio_pluto_sink':p['attenuation1']='89.75'

def epy(name,source,params,xy):
    return dict(name=name,id='epy_block',parameters=dict(_source_code=source,affinity='',alias='',comment='',maxoutbuf='0',minoutbuf='0',**params),
                states=dict(bus_sink=False,bus_source=False,bus_structure=None,coordinate=xy,rotation=0,state='enabled'))
d['blocks'] += [
epy('epy_mac_bridge','from sdrchat.radio_blocks import MacBridge\nclass blk(MacBridge):\n    def __init__(self, config_path="configs/node_a.json"):\n        super().__init__(config_path)\n',
    dict(config_path='os.environ.get("SDRCHAT_CONFIG", "configs/node_a.json")'),[128,640]),
epy('epy_training_correlator','from sdrchat.equalizer import TrainingCorrelator\nclass blk(TrainingCorrelator):\n    def __init__(self, threshold=0.6):\n        super().__init__(threshold)\n',
    dict(threshold='radio_config["correlation_threshold"]'),[768,1024]),
epy('epy_nlms','from sdrchat.equalizer import NLMS\nclass blk(NLMS):\n    def __init__(self, taps=7, mu=0.2, dd_mu=0.02, eps=1e-6):\n        super().__init__(taps,mu,dd_mu,eps)\n',
    dict(taps='radio_config["nlms_taps"]',mu='radio_config["nlms_mu"]',dd_mu='radio_config["nlms_dd_mu"]',eps='radio_config["nlms_eps"]'),[1040,1024])]
d['connections'] += [
['iio_pluto_source_0','0','epy_mac_bridge','0'],
['epy_mac_bridge','tx_out','digital_crc_append_0','in'],
['digital_crc_check_0_0','ok','epy_mac_bridge','rx_in'],
['digital_symbol_sync_xx_0_1_0','0','epy_training_correlator','0'],
['epy_training_correlator','0','epy_nlms','0'],
['epy_nlms','0','digital_costas_loop_cc_0_0','0']]
(root/'flowgraphs'/'Working1.0_csma.grc').write_text(yaml.safe_dump(d,sort_keys=False,width=100))
print('Created flowgraphs/Working1.0_csma.grc')

# Keep the shareable graph self-contained after rebuilding from the original.
from embed_flowgraph import embed
embed(root/'flowgraphs'/'Working1.0_csma.grc',root/'flowgraphs'/'Working1.0_csma.grc')
