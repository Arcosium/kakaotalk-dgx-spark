"""Dedicated KakaoTalk desktop; all account data stays in the vault."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from PIL import Image, ImageGrab

ROOT = Path(os.environ.get('KAKAOTALK_DATA_DIR', Path.home() / '.local/share/kakaotalk-dgx-spark')).expanduser().resolve()
RUNTIME = ROOT / 'runtime'
DISPLAY = os.environ.get('KAKAOTALK_DISPLAY', ':119')
WINE = RUNTIME / 'hangover/usr/bin'
PREFIX = ROOT / 'prefix-hangover'
NATIVE = RUNTIME / 'native/usr/bin'


def native_tool(name):
    bundled = NATIVE / name
    return str(bundled) if bundled.is_file() else shutil.which(name) or name


def environment():
    env = os.environ.copy()
    env.update(DISPLAY=DISPLAY, XAUTHORITY=str(ROOT / 'Xauthority'),
               WINEPREFIX=str(PREFIX), WINEARCH='win64',
               WINESERVER=str(WINE / 'wineserver'),
               HODLL='libwow64fex.dll', WINEDLLOVERRIDES='mscoree,mshtml=d',
               WINEDEBUG='-all',
               LD_LIBRARY_PATH=(str(RUNTIME / 'native/usr/lib/aarch64-linux-gnu') + ':' + env.get('LD_LIBRARY_PATH', '') if NATIVE.is_dir() else env.get('LD_LIBRARY_PATH', '')),
               XDG_DATA_DIRS=str(RUNTIME / 'native/usr/share') + ':/usr/share')
    return env


def wine(args, background=False):
    cmd = [str(WINE / 'wine'), *args]
    if background:
        cwd = Path(args[0]).parent if args and Path(args[0]).is_file() else ROOT
        return subprocess.Popen(cmd, env=environment(), cwd=cwd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True).pid
    return subprocess.run(cmd, env=environment(), check=True)


def screenshot_bytes():
    old_auth = os.environ.get('XAUTHORITY')
    os.environ['XAUTHORITY'] = str(ROOT / 'Xauthority')
    try:
        picture = ImageGrab.grab(xdisplay=DISPLAY)
    finally:
        if old_auth is None:
            os.environ.pop('XAUTHORITY', None)
        else:
            os.environ['XAUTHORITY'] = old_auth
    output = io.BytesIO()
    picture.save(output, format='PNG')
    return output.getvalue()


def xdo(*args):
    return subprocess.run([native_tool('xdotool'), *map(str, args)],
                          env=environment(), check=True, capture_output=True).stdout.decode()


def click(x, y, button=1, clicks=1):
    if not 0 <= x < 1280 or not 0 <= y < 900 or button not in (1, 2, 3) or clicks not in (1, 2):
        raise ValueError('Use coordinates inside 1280x900, button 1..3 and clicks 1..2.')
    xdo('mousemove', x, y, 'click', '--repeat', clicks, '--delay', '150', button)
    time.sleep(0.15)


def move_mouse(x, y):
    if not 0 <= x < 1280 or not 0 <= y < 900:
        raise ValueError('Coordinates must be inside the 1280x900 desktop.')
    xdo('mousemove', x, y)
    time.sleep(0.3)


def press(key):
    if not re.fullmatch(r'[A-Za-z0-9_+]+', key):
        raise ValueError('Use an X11 key name or combination such as ctrl+v or Return.')
    xdo('key', '--clearmodifiers', key)
    time.sleep(0.15)


def set_clipboard(text):
    if not text or len(text) > 10000:
        raise ValueError('Text length must be 1..10000 characters.')
    # Unicode clipboard paste avoids the Wine/IBus Korean composition problem.
    subprocess.run([native_tool('xclip'), '-selection', 'clipboard'], input=text,
                   text=True, env=environment(), check=True)


def type_text(text):
    set_clipboard(text)
    press('ctrl+v')


def read_screen():
    """Local Korean/English OCR with coordinates, also usable by text-only models."""
    picture = Image.open(io.BytesIO(screenshot_bytes()))
    enlarged = picture.resize((picture.width * 2, picture.height * 2), Image.Resampling.LANCZOS)
    png = io.BytesIO()
    enlarged.save(png, format='PNG')
    result = subprocess.run(['tesseract', 'stdin', 'stdout', '--tessdata-dir',
                             str(RUNTIME / 'tessdata'), '-l', 'kor+eng', '--psm', '11',
                             '-c', 'tessedit_create_tsv=1'],
                            input=png.getvalue(), capture_output=True, check=True,
                            timeout=30)
    rows = csv.DictReader(io.StringIO(result.stdout.decode()), delimiter='\t')
    return [{'text': row['text'], 'x': int(row['left']) // 2, 'y': int(row['top']) // 2,
             'width': (int(row['width']) + 1) // 2, 'height': (int(row['height']) + 1) // 2,
             'confidence': float(row['conf'])}
            for row in rows if row['text'].strip() and float(row['conf']) >= 30]


def status():
    try:
        windows = xdo('search', '--onlyvisible', '--name', 'KakaoTalk|카카오톡').split()
    except subprocess.CalledProcessError:
        windows = []
    return {'display': DISPLAY, 'size': [1280, 900],
            'backend': 'Hangover 11.16 + FEX',
            'installed': any((PREFIX / 'drive_c').glob('**/KakaoTalk.exe')),
            'windows': windows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['screenshot', 'launch', 'status', 'wine', 'clipboard'])
    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == 'screenshot':
        target = ROOT / 'screen.png'
        target.write_bytes(screenshot_bytes())
        target.chmod(0o600)
        print(target)
    elif args.action == 'launch':
        executable = next((PREFIX / 'drive_c').glob('**/KakaoTalk.exe'))
        print('KakaoTalk PID:', wine([str(executable)], background=True))
    elif args.action == 'status':
        print(json.dumps(status(), ensure_ascii=False))
    elif args.action == 'clipboard':
        import sys
        text = input('붙여넣을 문장: ') if sys.stdin.isatty() else sys.stdin.read()
        set_clipboard(text)
        print('전용 화면 클립보드에 넣었습니다. 입력 칸에서 Ctrl+V로 붙여넣으세요. 전송하지 않았습니다.')
    else:
        wine(args.args)
