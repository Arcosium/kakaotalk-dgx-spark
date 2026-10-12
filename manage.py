"""Start or stop only this project's private desktop processes."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import string
import subprocess
import sys
import time

import desktop

STATE = desktop.ROOT / 'processes.json'
EXPECTED = {'xvfb': 'Xvfb', 'openbox': 'openbox', 'vnc': 'x11vnc',
            'novnc': 'websockify'}


def alive(pid, expected):
    try:
        command = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\x00')
        return any(expected.encode() in item for item in command)
    except (OSError, ValueError):
        return False


def start():
    root = desktop.ROOT
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    (root / 'logs').mkdir(mode=0o700, exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    env = desktop.environment()

    def spawn(name, command, process_env=env):
        if alive(state.get(name, 0), EXPECTED[name]):
            return
        with (root / f'logs/{name}.log').open('ab') as log:
            proc = subprocess.Popen(command, env=process_env, stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
        state[name] = proc.pid
        STATE.write_text(json.dumps(state))

    auth = root / 'Xauthority'
    if not alive(state.get('xvfb', 0), 'Xvfb'):
        if Path('/tmp/.X11-unix/X' + desktop.DISPLAY.lstrip(':')).exists():
            raise RuntimeError('Selected display belongs to another process; refusing to use it.')
        auth.touch(mode=0o600, exist_ok=True)
        result = subprocess.run(['xauth', '-f', str(auth), 'add', desktop.DISPLAY,
                                 '.', secrets.token_hex(16)], capture_output=True)
        if result.returncode:
            raise RuntimeError('Could not initialize X authorization.')
        auth.chmod(0o600)
    spawn('xvfb', ['Xvfb', desktop.DISPLAY, '-screen', '0', '1280x900x24',
                   '-nolisten', 'tcp', '-auth', str(auth)])
    for _ in range(40):
        if Path('/tmp/.X11-unix/X' + desktop.DISPLAY.lstrip(':')).exists():
            break
        time.sleep(0.1)
    else:
        raise RuntimeError('Virtual screen did not start.')
    spawn('openbox', [desktop.native_tool('openbox')])

    passwd = root / 'vnc-passwd'
    if not passwd.exists():
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
        plain = root / 'vnc-password.txt'
        plain.write_text(password + '\n')
        plain.chmod(0o600)
        result = subprocess.run([desktop.native_tool('x11vnc'), '-storepasswd',
                                 password, str(passwd)], env=env, capture_output=True)
        if result.returncode:
            raise RuntimeError('Could not initialize VNC password.')
        passwd.chmod(0o600)
    spawn('vnc', [desktop.native_tool('x11vnc'), '-display', desktop.DISPLAY,
                  '-auth', str(auth), '-localhost', '-rfbport', '5906', '-rfbauth',
                  str(passwd), '-forever', '-shared', '-noxdamage'])
    web_env = env.copy()
    web_env['PYTHONPATH'] = str(desktop.RUNTIME / 'pythondeps')
    webroot = desktop.RUNTIME / 'noVNC'
    spawn('novnc', [sys.executable, '-m', 'websockify', f'--web={webroot}',
                    '127.0.0.1:6086', '127.0.0.1:5906'], web_env)
    if not desktop.status()['windows']:
        exe = next((desktop.PREFIX / 'drive_c').glob('**/KakaoTalk.exe'), None)
        if exe is None:
            return 'Desktop started. Complete setup.py --install-app before launching KakaoTalk.'
        desktop.wine([str(exe)], background=True)
    return 'Dedicated desktop started at http://127.0.0.1:6086/vnc.html; inspect the screen after app startup.'


def stop():
    subprocess.run([str(desktop.WINE / 'wineserver'), '-k'], env=desktop.environment(),
                   check=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    for name in ('novnc', 'vnc', 'openbox', 'xvfb'):
        pid = state.get(name, 0)
        if alive(pid, EXPECTED[name]):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for _ in range(40):
        if not any(alive(state.get(name, 0), command) for name, command in EXPECTED.items()):
            break
        time.sleep(0.1)
    else:
        raise RuntimeError('An owned desktop process did not stop; PID records retained.')
    STATE.write_text('{}')
    print('Stopped only the dedicated KakaoTalk desktop.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop', 'status'])
    args = parser.parse_args()
    if args.action == 'start':
        print(start())
    elif args.action == 'stop':
        stop()
    else:
        print(json.dumps(desktop.status(), ensure_ascii=False))
