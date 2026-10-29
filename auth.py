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


def remembered_form(picture, words):
    """Remembered-account login form: the account is prefilled and only the password is empty
    (no placeholder text). Anchor on 'QR Code Log In' or 'Keep me logged in', then require the
    yellow login panel, a blank white password field and a light login button."""
    anchors = [(line, lo, hi) for line, lo, hi in ((phrase(words, r'qrcode'), 120, 220),
                                                  (phrase(words, r'keepmeloggedin'), 150, 260)) if line]
    if not anchors:
        return None
    for w in words:
        if '@' not in w['text'] and not re.fullmatch(r'[0-9-]{10,13}', w['text']):
            continue
        ay = w['y'] + w['height'] // 2
        if not any(lo <= center(line)[1] - ay <= hi and abs(min(i['x'] for i in line) - w['x']) < 160
                   for line, lo, hi in anchors):
            continue
        x = w['x'] + 40                      # just right of the account text: inside both fields and the button
        password, submit, panel = (x, ay + 36), (x, ay + 78), (w['x'] - 60, ay)
        if not all(0 <= px < picture.width and 0 <= py < picture.height for px, py in (password, submit, panel)):
            continue
        r, g, b = picture.getpixel(panel)
        if not (r > 230 and g > 200 and b < 90):        # inside the yellow KakaoTalk login panel
            continue
        if min(picture.getpixel(password)) < 245 or min(picture.getpixel(submit)) < 230:
            continue
        return {'shown_account': w['text'], 'password': password, 'submit': submit}
    return None


def other_device_ok(words):
    """OK button of the 'logged in on another device' prompt, only when it sits 50-220px below the text."""
    prompt = phrase(words, r'anotherdevice|다른기기')
    if not prompt:
        return None
    py = center(prompt)[1]
    mid = lambda w: (w['x'] + w['width'] // 2, w['y'] + w['height'] // 2)
    oks = [mid(w) for w in words if w['text'].strip().lower() in ('ok', '확인')]
    cancels = [mid(w) for w in words if w['text'].strip().lower() in ('cancel', '취소')]
    # A real dialog has OK and Cancel side by side on one row below the text; chat text does not.
    for ok in oks:
        if 50 <= ok[1] - py <= 220 and any(abs(ok[1] - c[1]) <= 8 and 60 <= c[0] - ok[0] <= 220 for c in cancels):
            return ok
    return None


def classify(picture, words):
    if phrase(words, r'youhavebeenloggedout'):
        return 'logged_out'
    if form(picture, words) or remembered_form(picture, words):
        return 'login_form'
    if phrase(words, r'certification|verification|인증|securitycode|보안코드'):
        return 'authentication_required'
    # Only a visible application header counts as positive session evidence.
    headers = [w for w in words if w['y'] < picture.height * 0.55]
    if any(re.fullmatch(r'friends|chats|more|친구|채팅|더보기', w['text'].lower())
           and w['height'] >= 13 for w in headers):
        return 'ready'
    if other_device_ok(words) or phrase(words, r'currentlyloggedinonanotherdevice'):
        return 'other_device'        # prompt to force log out the other PC session (checked after ready)
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
        if state == 'other_device':
            point = other_device_ok(words)
            if not point:
                return {'status': 'other_device', 'login_attempted': False,
                        'message': 'Force-logout prompt without a visible OK button. Inspect the screen.'}
            desktop.click(*point)
            for _ in range(8):
                time.sleep(1)
                picture, words = observe()
                if classify(picture, words) == 'ready':
                    credentials.ATTEMPT.unlink(missing_ok=True)
                    return {'status': 'logged_in', 'login_attempted': False,
                            'message': 'Pressed OK on the force-logout prompt. Reselect the recipient before typing.'}
            return {'status': 'needs_user', 'login_attempted': False,
                    'message': 'Pressed OK once; the chat list did not appear. Inspect the screen.'}
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
        fields = ('account', 'password')
        if not targets:
            targets = remembered_form(picture, words)
            # Never type the password into a different remembered account (values are not returned).
            if targets['shown_account'].strip().lower() != secret['account'].strip().lower():
                secret.clear()
                return {'status': 'needs_user', 'login_attempted': False,
                        'message': 'The remembered account differs from the saved one; no credentials were entered.'}
            fields = ('password',)
        credentials.write_private(credentials.ATTEMPT, {'started_at': time.time()})
        try:
            for i, name in enumerate(fields):
                point = targets[name]
                if i:   # clicking a field can move the window (-240px observed 2026-10-29): locate the next field again
                    picture, words = observe()
                    line = phrase(words, r'^password$')
                    if not line:
                        raise RuntimeError('password field not found after account input')
                    point = center(line)
                desktop.click(*point)
                desktop.press('ctrl+a')
                desktop.type_text(secret[name])
            desktop.press('Return')   # submit with Enter from the password field so a moved window cannot be missed
        finally:
            # Replace the shared clipboard even when input or login fails.
            desktop.set_clipboard(' ')
            secret.clear()
        pressed_ok = False
        for _ in range(8):
            time.sleep(1)
            picture, words = observe()
            state = classify(picture, words)
            if state == 'other_device' and not pressed_ok:
                # Standing user instruction (2026-10-29): always confirm the force-logout prompt with OK.
                point = other_device_ok(words)
                if point:
                    desktop.click(*point)
                    pressed_ok = True
                    continue
            if state in ('ready', 'authentication_required', 'other_device'):
                break
        if state == 'ready':
            credentials.ATTEMPT.unlink(missing_ok=True)
            return {'status': 'logged_in', 'login_attempted': True,
                    'message': 'Inspect and reselect the recipient before entering any message.'}
        if state == 'other_device':
            return {'status': 'other_device', 'login_attempted': True,
                    'message': 'The force-logout prompt stayed or its OK button was not found. Inspect the screen.'}
        return {'status': 'authentication_required' if state == 'authentication_required' else 'needs_user',
                'login_attempted': True,
                'message': 'Login was attempted once. Inspect locally; no automatic retry.'}


if __name__ == '__main__':
    print(json.dumps(ensure_logged_in(), ensure_ascii=False))
