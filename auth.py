"""One-shot fallback login using private local credentials and fresh visual anchors."""
import csv
import fcntl
import io
import json
import re
import subprocess
import time

from PIL import Image, ImageOps

import credentials
import desktop


def observe():
    """Threshold low-contrast placeholders locally; never return OCR through MCP."""
    picture = Image.open(io.BytesIO(desktop.screenshot_bytes())).convert('RGB')
    words = []
    for threshold in (200, 225):
        binary = ImageOps.grayscale(picture).point(lambda p: 255 if p > threshold else 0)
        binary = binary.resize((picture.width * 2, picture.height * 2))
        png = io.BytesIO()
        binary.save(png, format='PNG')
        result = subprocess.run(
            ['tesseract', 'stdin', 'stdout', '--tessdata-dir', str(desktop.RUNTIME / 'tessdata'),
             '-l', 'kor+eng', '--psm', '11', '-c', 'tessedit_create_tsv=1'],
            input=png.getvalue(), capture_output=True, check=True, timeout=20)
        for row in csv.DictReader(io.StringIO(result.stdout.decode()), delimiter='\t'):
            if row['text'].strip() and float(row['conf']) >= 30:
                words.append({'text': row['text'], 'pass': threshold, 'x': int(row['left']) // 2,
                              'y': int(row['top']) // 2, 'width': int(row['width']) // 2,
                              'height': int(row['height']) // 2})
    return picture, words


def phrase(words, pattern):
    """Match a visual line without depending on OCR word boundaries."""
    for word in words:
        line = sorted((item for item in words if item.get('pass') == word.get('pass')
                       and abs(item['y'] + item['height'] / 2
                               - word['y'] - word['height'] / 2) <= 8),
                      key=lambda item: item['x'])
        # Two threshold passes can produce duplicates; examine each word sequence too.
        unique = []
        for item in line:
            if not any(abs(item['x'] - old['x']) <= 4 for old in unique):
                unique.append(item)
        normalized = re.sub(r'[^a-z0-9가-힣]', '', ''.join(item['text'] for item in unique).lower())
        if re.search(pattern, normalized):
            return unique
    return None


def center(line):
    return ((min(w['x'] for w in line) + max(w['x'] + w['width'] for w in line)) // 2,
            (min(w['y'] for w in line) + max(w['y'] + w['height'] for w in line)) // 2)


def form(picture, words):
    email = phrase(words, r'emailorphonenumber')
    password = phrase(words, r'^password$')
    qr = phrase(words, r'qrcode')
    if not email or not password or not qr:
        return None
    account_point, password_point, qr_point = map(center, (email, password, qr))
    # Require the observed inputs and QR control in the same visible login panel.
    if not (20 <= password_point[1] - account_point[1] <= 70
            and 80 <= qr_point[1] - password_point[1] <= 230
            and abs(account_point[0] - password_point[0]) < 150):
        return None
    submit = (qr_point[0], (password_point[1] + qr_point[1]) // 2 - 20)
    x, y = submit
    if not (0 <= x < picture.width and 0 <= y < picture.height):
        return None
    if min(picture.getpixel(submit)) < 230:
        return None
    return {'account': account_point, 'password': password_point, 'submit': submit}


def classify(picture, words):
    if phrase(words, r'youhavebeenloggedout'):
        return 'logged_out'
    if form(picture, words):
        return 'login_form'
    if phrase(words, r'certification|verification|인증|securitycode|보안코드'):
        return 'authentication_required'
    # Only a visible application header counts as positive session evidence.
    headers = [w for w in words if w['y'] < picture.height * 0.55]
    if any(re.fullmatch(r'friends|chats|more|친구|채팅|더보기', w['text'].lower())
           and w['height'] >= 13 for w in headers):
        return 'ready'
    if phrase(words, r'qrcode|password|로그인'):
        return 'login_unrecognized'
    return 'unknown'


def ensure_logged_in():
    """No secrets in parameters/results. Login only from a verified blank form."""
    desktop.ROOT.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (desktop.ROOT / 'login.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'busy', 'message': 'Another local login is in progress.'}
        picture, words = observe()
        state = classify(picture, words)
        if state == 'ready':
            credentials.ATTEMPT.unlink(missing_ok=True)
            return {'status': 'ready', 'login_attempted': False}
        if state == 'logged_out':
            ok = phrase(words, r'^ok$')
            if not ok:
                return {'status': 'needs_inspection', 'login_attempted': False}
            desktop.click(*center(ok))
            picture, words = observe()
            state = classify(picture, words)
        if state != 'login_form':
            return {'status': state, 'login_attempted': False,
                    'message': 'Inspect the screen; no credentials were entered.'}
        if credentials.ATTEMPT.exists():
            return {'status': 'retry_blocked', 'login_attempted': False,
                    'message': 'Previous login needs user review. Do not retry automatically.'}
        try:
            secret = credentials.load()
        except FileNotFoundError:
            return {'status': 'credentials_missing', 'login_attempted': False}
        except (OSError, ValueError):
            return {'status': 'credentials_invalid', 'login_attempted': False}
        targets = form(picture, words)
        credentials.write_private(credentials.ATTEMPT, {'started_at': time.time()})
        try:
            for name in ('account', 'password'):
                desktop.click(*targets[name])
                desktop.press('ctrl+a')
                desktop.type_text(secret[name])
            desktop.click(*targets['submit'])
        finally:
            # Replace the shared clipboard even when input or login fails.
            desktop.set_clipboard(' ')
            secret.clear()
        for _ in range(8):
            time.sleep(1)
            picture, words = observe()
            state = classify(picture, words)
            if state in ('ready', 'authentication_required'):
                break
        if state == 'ready':
            credentials.ATTEMPT.unlink(missing_ok=True)
            return {'status': 'logged_in', 'login_attempted': True,
                    'message': 'Inspect and reselect the recipient before entering any message.'}
        return {'status': 'authentication_required' if state == 'authentication_required' else 'needs_user',
                'login_attempted': True,
                'message': 'Login was attempted once. Inspect locally; no automatic retry.'}


if __name__ == '__main__':
    print(json.dumps(ensure_logged_in(), ensure_ascii=False))
