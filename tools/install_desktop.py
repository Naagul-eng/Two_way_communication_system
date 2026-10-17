"""Install a per-user application-menu entry and optional desktop shortcut."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def quoted(value):
    value = str(value).replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\'+char)
    return '"'+value+'"'


def entry():
    return '\n'.join([
        '[Desktop Entry]', 'Version=1.0', 'Type=Application',
        'Name=Pixel Pulse', 'Comment=Chat over SDR with automatic radio startup',
        'Exec='+quoted(sys.executable)+' '+quoted(ROOT/'tools/desktop_launch.py'),
        'Icon='+str(ROOT/'assets/pixel-pulse.svg'),
        'Terminal=false', 'Categories=Network;Chat;',
        'StartupNotify=true', 'StartupWMClass=Pixel Pulse', '',
    ])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desktop', action='store_true')
    parser.add_argument('--output-dir', type=Path, help='Generate a launcher in this directory only')
    args=parser.parse_args()
    directory=args.output_dir or Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))/'applications'
    directory.mkdir(parents=True, exist_ok=True)
    target=directory/'pixel-pulse.desktop'
    target.write_text(entry());target.chmod(0o755)
    if shutil.which('desktop-file-validate'):
        subprocess.run(['desktop-file-validate', str(target)], check=True)
    print('Created:', target)
    if args.output_dir:
        return
    if shutil.which('update-desktop-database'):
        subprocess.run(['update-desktop-database', str(directory)], check=False)
    if args.desktop:
        desktop=Path.home()/'Desktop'
        if shutil.which('xdg-user-dir'):
            found=subprocess.run(['xdg-user-dir','DESKTOP'],capture_output=True,text=True,check=True).stdout.strip()
            if found:desktop=Path(found)
        desktop.mkdir(parents=True,exist_ok=True)
        shortcut=desktop/'Pixel Pulse.desktop'
        shutil.copy2(target,shortcut)
        if shutil.which('gio'):
            subprocess.run(['gio','set',str(shortcut),'metadata::trusted','true'],capture_output=True)
        print('Created:',shortcut)
    print('Open Pixel Pulse from your applications menu. Keep the project folder in this location.')


if __name__=='__main__':main()
