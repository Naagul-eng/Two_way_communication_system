"""Embed project radio sources in a GRC so the GRC can be shared on its own.

GNU Radio still generates its normal _epy_*.py files when compiling the GRC.
Those files are generated outputs, not additional source files to distribute.
"""
import argparse
import ast
from pathlib import Path
import pprint
import yaml

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = '_pixel_pulse_radio'


def function_source(path, name):
    source = path.read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(source, node) + '\n'


def embedded_sources():
    sources = {name: (ROOT / 'sdrchat' / (name + '.py')).read_text()
               for name in ('config', 'reedsolo_bundled', 'protocol', 'engine', 'service', 'equalizer', 'radio_blocks')}
    # Embed public example settings only. Runtime profiles remain local and are
    # selected through SDRCHAT_CONFIG by the application.
    default = __import__('json').loads((ROOT / 'configs/node_a.example.json').read_text())
    default['state_dir'] = './data/node_a'
    sources['config'] += '\n\n_DEFAULT_CONFIG = ' + repr(default) + '''
_original_load = load

def load(path):
    import os
    path = Path(path)
    if path.exists():
        return _original_load(path)
    if os.environ.get('SDRCHAT_CONFIG') or str(path) != 'configs/node_a.json':
        raise FileNotFoundError('Node configuration does not exist: ' + str(path))
    c = dict(_DEFAULT_CONFIG)
    c['state_dir'] = str(Path(c['state_dir']).resolve())
    Path(c['state_dir']).mkdir(parents=True, exist_ok=True)
    return c
'''
    # Keep the fast native equalizer. Its source travels inside the GRC and is
    # compiled for the recipient's CPU, rather than distributing a platform .so.
    native = (ROOT / 'sdrchat/native/nlms.cpp').read_text()
    sources['equalizer'] += '\n\n_NATIVE_SOURCE = ' + repr(native) + '''
_native_directory = None

def _embedded_native_library():
    global _native_directory
    import shutil
    import subprocess
    import tempfile
    if _native_directory is None:
        compiler = shutil.which('g++')
        if compiler is None:
            raise RuntimeError('The embedded NLMS source needs g++. Install g++ and run again.')
        directory = tempfile.TemporaryDirectory(prefix='pixel-pulse-nlms-')
        folder = Path(directory.name)
        source = folder / 'nlms.cpp'
        source.write_text(_NATIVE_SOURCE)
        try:
            subprocess.run([compiler, '-O3', '-std=c++17', '-shared', '-fPIC', str(source), '-o', str(folder / 'libnlms.so')], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            directory.cleanup()
            raise RuntimeError('Could not compile embedded NLMS source: ' + exc.stderr) from exc
        _native_directory = directory
    return Path(_native_directory.name) / 'libnlms.so'
'''
    sources['equalizer'] = sources['equalizer'].replace("lib=Path(__file__).parent/'native'/'libnlms.so'", 'lib=_embedded_native_library()')
    sources['radio_blocks'] = sources['radio_blocks'].replace('from .equalizer import TrainingCorrelator, NLMS\n', '')
    return sources


def bootstrap():
    sources = pprint.pformat(embedded_sources(), width=110, sort_dicts=True)
    license_text = (ROOT / 'sdrchat/REEDSOLO_LICENSE.txt').read_text()
    return '''# Pixel Pulse: all project radio modules are embedded below.
# No sdrchat checkout or separately supplied Python blocks are required.
import importlib.abc as _abc
import importlib.util as _util
import sys as _sys
import types as _types

''' + '_RADIO_SOURCES = ' + sources + '\n_REEDSOLO_LICENSE = ' + repr(license_text) + '''

class _EmbeddedRadioLoader(_abc.MetaPathFinder, _abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        prefix = '_pixel_pulse_radio.'
        if fullname.startswith(prefix) and fullname[len(prefix):] in _RADIO_SOURCES:
            return _util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name = module.__name__.split('.')[-1]
        module.__file__ = '<Pixel Pulse GRC>/' + name + '.py'
        exec(compile(_RADIO_SOURCES[name], module.__file__, 'exec'), module.__dict__)

if '_pixel_pulse_radio' not in _sys.modules:
    _package = _types.ModuleType('_pixel_pulse_radio')
    _package.__path__ = []
    _package.__package__ = '_pixel_pulse_radio'
    _sys.modules['_pixel_pulse_radio'] = _package
    _sys.meta_path.insert(0, _EmbeddedRadioLoader())
'''


class LiteralDumper(yaml.SafeDumper):
    pass


def represent_string(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value, style='|' if '\n' in value else None)


LiteralDumper.add_representer(str, represent_string)


def embed(source, output):
    graph = yaml.safe_load(source.read_text())
    boot = bootstrap()
    blocks = {b['name']: b for b in graph['blocks']}
    blocks['import_0']['parameters']['imports'] = (
        'from gnuradio import filter\nimport os\n' + boot +
        '\nfrom _pixel_pulse_radio.config import load\n'
        'radio_config = load(os.environ.get("SDRCHAT_CONFIG", "configs/node_a.json"))\n')
    wrappers = {
        'epy_mac_bridge': ('radio_blocks', 'MacBridge', 'config_path="configs/node_a.json"', 'config_path'),
        'epy_training_correlator': ('equalizer', 'TrainingCorrelator', 'threshold=0.6', 'threshold'),
        'epy_nlms': ('equalizer', 'NLMS', 'taps=7, mu=0.2, dd_mu=0.02, eps=1e-6', 'taps,mu,dd_mu,eps'),
    }
    for block, (module, base, parameters, arguments) in wrappers.items():
        blocks[block]['parameters']['_source_code'] = (
            boot + f'\nfrom {PACKAGE}.{module} import {base}\n'
            f'class blk({base}):\n    def __init__(self, {parameters}):\n        super().__init__({arguments})\n')
    # The normal GRC Run button now supplies the same attachment as hardware.py.
    graph['blocks'] = [b for b in graph['blocks'] if b['name'] != 'pixel_pulse_attach_radio']
    graph['blocks'].append(dict(name='pixel_pulse_attach_radio', id='snippet',
        parameters=dict(section='main_after_init', priority='0',
            code='self.epy_mac_bridge.attach_radio(self.iio_pluto_sink_0, self.iio_pluto_source_0)'),
        states=dict(bus_sink=False, bus_source=False, bus_structure=None, coordinate=[128,800], rotation=0, state='enabled')))
    graph['options']['parameters'].update(title='Pixel Pulse · CSMA/CA QPSK NLMS',
        description='Self-contained radio sources. Requires GNU Radio/IIO, NumPy, pyzmq, cryptography and g++. Set SDRCHAT_CONFIG to use your node JSON; otherwise public demo settings are used.')
    output.write_text(yaml.dump(graph, Dumper=LiteralDumper, sort_keys=False, width=110))
    print(f'Embedded radio Python modules, native source, license, and startup hook in {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'flowgraphs/Working1.0_csma.grc')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    embed(args.source, args.output or args.source)


if __name__ == '__main__':
    main()
