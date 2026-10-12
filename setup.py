"""Fetch upstream runtime into private storage; never bundle account data."""
import argparse
import hashlib
import platform
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

import desktop

HANGOVER = 'https://github.com/AndreRH/hangover/releases/download/hangover-11.16/hangover_11.16_ubuntu2404_noble_arm64.tar'
HANGOVER_SHA256 = '94611dad2b23978d35825a018c81b3947caaec174aa04c052849d37bc6a39e72'
NOVNC_COMMIT = 'b17d04c1a1a926a59f4a04bb866332b429f2ce37'


def download(url, target, expected=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + '.part')
    request = urllib.request.Request(url, headers={'User-Agent': 'kakaotalk-dgx-spark'})
    with urllib.request.urlopen(request, timeout=120) as response, part.open('wb') as out:
        shutil.copyfileobj(response, out)
    if expected and hashlib.sha256(part.read_bytes()).hexdigest() != expected:
        part.unlink()
        raise RuntimeError('Upstream download checksum differs; refusing to extract.')
    part.replace(target)
    target.chmod(0o600)


def prepare():
    if platform.machine() not in ('aarch64', 'arm64'):
        raise RuntimeError('This recipe targets Ubuntu 24.04 ARM64.')
    for name in ('dpkg-deb', 'Xvfb', 'xauth', 'openbox', 'x11vnc', 'xdotool', 'xclip', 'tesseract', 'git'):
        if not shutil.which(name):
            raise RuntimeError(f'Missing {name}; install the README system prerequisites first.')
    desktop.ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    desktop.ROOT.chmod(0o700)
    runtime = desktop.RUNTIME
    runtime.mkdir(parents=True, exist_ok=True)
    if not (desktop.WINE / 'wine').exists():
        archive = runtime / 'hangover.tar'
        download(HANGOVER, archive, HANGOVER_SHA256)
        packages = runtime / 'hangover-packages'
        packages.mkdir(exist_ok=True)
        with tarfile.open(archive) as tf:
            tf.extractall(packages, filter='data')
        for deb in sorted(packages.glob('*.deb')):
            subprocess.run(['dpkg-deb', '-x', str(deb), str(runtime / 'hangover')], check=True)
    web = runtime / 'noVNC'
    if not web.exists():
        subprocess.run(['git', 'clone', 'https://github.com/novnc/noVNC.git', str(web)], check=True)
        subprocess.run(['git', '-C', str(web), 'checkout', '--detach', NOVNC_COMMIT], check=True)
    data = runtime / 'tessdata'
    data.mkdir(exist_ok=True)
    for lang in ('kor', 'eng'):
        target = data / (lang + '.traineddata')
        installed = Path('/usr/share/tesseract-ocr/5/tessdata') / target.name
        if not target.exists():
            if not installed.exists():
                raise RuntimeError(f'Missing {lang} OCR data; install tesseract-ocr-{lang}.')
            shutil.copy2(installed, target)
    font = runtime / 'NotoSansCJKkr-Regular.otf'
    if not font.exists():
        download('https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Korean/NotoSansCJKkr-Regular.otf', font)
    print('Runtime prepared. Run setup.py --install-app to open the official installer.')


def install_app():
    import manage
    manage.start()
    existing = next((desktop.PREFIX / 'drive_c').glob('**/KakaoTalk.exe'), None)
    if existing:
        print('KakaoTalk is already installed; existing prefix retained.')
        return
    installer = desktop.RUNTIME / 'KakaoTalk_Setup.exe'
    download('https://app-pc.kakaocdn.net/talk/win32/KakaoTalk_Setup.exe', installer)
    # Disable Wine Mono/Gecko prompts; login remains manual.
    desktop.wine(['wineboot', '-u'])
    fonts = desktop.PREFIX / 'drive_c/windows/Fonts'
    fonts.mkdir(parents=True, exist_ok=True)
    shutil.copy2(desktop.RUNTIME / 'NotoSansCJKkr-Regular.otf', fonts)
    for name in ('Gulim', '굴림', 'Malgun Gothic', '맑은 고딕'):
        desktop.wine(['reg', 'add', r'HKLM\Software\Microsoft\Windows NT\CurrentVersion\FontSubstitutes',
                      '/v', name, '/t', 'REG_SZ', '/d', 'Noto Sans CJK KR', '/f'])
    for name in ('Tahoma', 'Segoe UI', 'Arial', 'Microsoft Sans Serif'):
        desktop.wine(['reg', 'add', r'HKLM\Software\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink',
                      '/v', name, '/t', 'REG_MULTI_SZ', '/d', 'NotoSansCJKkr-Regular.otf,Noto Sans CJK KR', '/f'])
    desktop.wine([str(installer)], background=True)
    print('Official installer opened. Complete it at http://127.0.0.1:6086/vnc.html, then run manage.py start.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-app', action='store_true')
    args = parser.parse_args()
    prepare()
    if args.install_app:
        install_app()
