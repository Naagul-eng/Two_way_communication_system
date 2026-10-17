"""Copy ONLY the GRC to an isolated folder, compile, and test its embedded radio."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='pixel-pulse-portable-test-') as temp:
        directory = Path(temp)
        graph = directory / 'Pixel_Pulse.grc'
        shutil.copy2(ROOT / 'flowgraphs/Working1.0_csma.grc', graph)
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env.pop('SDRCHAT_CONFIG', None)
        subprocess.run(['grcc', '-o', str(directory), str(graph)], cwd=directory, env=env, check=True, timeout=60)
        protocol_tests = (ROOT / 'tests/test_protocol_mac.py').read_text().replace('from sdrchat.', 'from _pixel_pulse_radio.')
        protocol_tests = protocol_tests.replace("BASE=json.loads((Path(__file__).parents[1]/'configs/node_a.json').read_text())", 'BASE=dict(radio.radio_config)')
        phy_tests = (ROOT / 'tests/test_phy.py').read_text().replace('from sdrchat.equalizer', 'from _pixel_pulse_radio.equalizer')
        phy_tests = phy_tests.replace('from sdrchat.fec_decoder import blk as RSDecoder', 'from csma_transceiver_epy_rs_decoder import blk as RSDecoder')
        phy_tests = phy_tests.replace('from sdrchat.protocol', 'from _pixel_pulse_radio.protocol')
        phy_tests = phy_tests.replace("c=json.loads((Path(__file__).parents[1]/'configs/node_a.json').read_text());codec=Codec(c['shared_key'])", "c=radio.radio_config;codec=Codec(c['shared_key'])")
        driver = '''import importlib.abc
import sys
import types
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
class NoProjectImports(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='sdrchat' or fullname.startswith('sdrchat.'):
            raise ImportError('Portable GRC attempted to import the original project: '+fullname)
sys.meta_path.insert(0,NoProjectImports())
import csma_transceiver as radio
from csma_transceiver_epy_mac_bridge import blk as Bridge
from csma_transceiver_epy_training_correlator import blk as Correlator
from csma_transceiver_epy_nlms import blk as Equalizer
assert Bridge.__module__=='csma_transceiver_epy_mac_bridge'
Correlator();Equalizer()
# Verify the generated Run-button hook attaches both hardware blocks.
attached=[]
fake=types.SimpleNamespace(epy_mac_bridge=types.SimpleNamespace(attach_radio=lambda *args:attached.append(args)),iio_pluto_sink_0=object(),iio_pluto_source_0=object())
radio.snippets_main_after_init(fake)
assert attached==[(fake.iio_pluto_sink_0,fake.iio_pluto_source_0)]
suite=unittest.TestSuite()
'''
        for name, source in [('portable_protocol', protocol_tests), ('portable_phy', phy_tests)]:
            driver += f"module=types.ModuleType({name!r});module.__file__=__file__;module.radio=radio\nexec(compile({source!r},__file__,'exec'),module.__dict__)\nsuite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))\n"
        driver += "result=unittest.TextTestRunner(verbosity=2).run(suite)\nsys.exit(0 if result.wasSuccessful() else 1)\n"
        path = directory / 'check.py'
        path.write_text(driver)
        subprocess.run([sys.executable, '-I', str(path)], cwd=directory, env=env, check=True, timeout=45)
    print('PASS: GRC alone compiles outside the project; embedded native equalizer, FEC/PHY loopback, protocol/MAC and automatic radio attachment pass.')


if __name__ == '__main__':
    main()
