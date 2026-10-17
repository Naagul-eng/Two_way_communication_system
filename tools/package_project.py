"""Build a clean handoff ZIP without user history or machine-specific binaries."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def build():
    files=[ROOT/name for name in ('.gitignore','README.md','START_HERE_NEW_PERSON.md','setup.sh','assets/pixel-pulse.svg','run_app.sh','run_radio.sh',
        'run_node_a_radio.sh','run_node_a_chat.sh','run_node_b_radio.sh','run_node_b_chat.sh',
        'flowgraphs/Working1.0_csma.grc','sdrchat/REEDSOLO_LICENSE.txt','sdrchat/native/nlms.cpp')]
    for folder in ('sdrchat','tools','tests'):
        files.extend((ROOT/folder).glob('*.py'))
    files.append(ROOT/'configs/node_a.example.json')
    output=ROOT/'dist/Pixel_Pulse_Share.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(set(files)):
            archive.write(path,Path('Pixel_Pulse')/path.relative_to(ROOT))
        assert archive.testzip() is None
    print(f'Created {output} ({output.stat().st_size:,} bytes; {len(set(files))} files)')
    return output


if __name__=='__main__':
    build()
