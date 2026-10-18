"""Verified chat-list navigation for agents that can read OCR but not icons."""
import auth
import desktop
import time


# Monochrome silhouette of the official client's chat-tab icon (26.8.2.5324).
# Match a fresh screenshot rather than reusing screen coordinates.
CHAT_ICON = (
    '000000000000000000000000000',
    '000000000000000000000000000',
    '000000000011111110000000000',
    '000000001111111111100000000',
    '000000111111111111111000000',
    '000001111111111111111100000',
    '000001111111111111111100000',
    '000011111111111111111110000',
    '000111111111111111111111000',
    '000111111111111111111111000',
    '000111111111111111111111000',
    '000111111111111111111111000',
    '000111111111111111111111000',
    '000111111111111111111111000',
    '000011111111111111111110000',
    '000011111111111111111110000',
    '000001111111111111111100000',
    '000000111111111111111000000',
    '000000011111111111100000000',
    '000000011111111110000000000',
    '000000011111000000000000000',
    '000000011100000000000000000',
    '000000010000000000000000000',
    '000000000000000000000000000',
    '000000000000000000000000000',
)


def find_chat_tab(picture, box):
    x, y, width, height = box
    region = picture.crop((x + 4, y + 30, min(x + 65, picture.width),
                           min(y + 220, y + height, picture.height))).convert('RGB')
    rows = []
    pixels = region.load()
    for cy in range(region.height):
        rows.append(''.join('1' if max(pixels[cx, cy]) < 200 and
                            max(pixels[cx, cy]) - min(pixels[cx, cy]) < 12 else '0'
                            for cx in range(region.width)))
    pattern = ''.join(CHAT_ICON)
    pw, ph = len(CHAT_ICON[0]), len(CHAT_ICON)
    matches = []
    for cy in range(len(rows) - ph + 1):
        for cx in range(region.width - pw + 1):
            candidate = ''.join(row[cx:cx + pw] for row in rows[cy:cy + ph])
            errors = sum(a != b for a, b in zip(candidate, pattern))
            if errors <= 6:
                matches.append((x + 4 + cx + pw // 2, y + 30 + cy + ph // 2))
    return matches[0] if len(matches) == 1 else None


def chats_header(words, box):
    x, y, width, _ = box
    return any(w['text'] in ('Chats', '채팅') and x + 65 <= w['x'] < x + width
               and y + 25 <= w['y'] <= y + 90 for w in words)


def show_chats():
    state = auth.ensure_logged_in()
    if state['status'] not in ('ready', 'logged_in'):
        return state
    windows = [wid for wid in desktop.status()['windows']
               if desktop.xdo('getwindowname', wid).strip() in ('KakaoTalk', '카카오톡')]
    if len(windows) != 1:
        return {'status': 'needs_inspection', 'message': 'Main KakaoTalk window is ambiguous.'}
    window = windows[0]
    geometry = dict(line.split('=', 1) for line in
                    desktop.xdo('getwindowgeometry', '--shell', window).splitlines() if '=' in line)
    box = tuple(int(geometry[name]) for name in ('X', 'Y', 'WIDTH', 'HEIGHT'))
    desktop.xdo('windowactivate', '--sync', window)
    picture, words = auth.observe()
    if not chats_header(words, box):
        point = find_chat_tab(picture, box)
        if point is None:
            return {'status': 'needs_inspection', 'message': 'Chat-tab icon did not match; no click made.'}
        desktop.click(*point)
        picture, words = auth.observe()
    if not chats_header(words, box):
        return {'status': 'needs_inspection', 'message': 'Chat list was not verified after navigation.'}
    return {'status': 'ready', 'view': 'chats', 'window': dict(zip(('x', 'y', 'width', 'height'), box)),
            'words': [{key: value for key, value in word.items() if key != 'pass'}
                      for word in words if word['pass'] == 200
                      and box[0] <= word['x'] < box[0] + box[2]
                      and box[1] <= word['y'] < box[1] + box[3]],
            'message': 'Chat list only. No room opened and no message sent. Select rows using these current coordinates.'}


def read_chat():
    """Read the active room, annotating the observed yellow outgoing bubbles."""
    active = desktop.xdo('getactivewindow').strip()
    title = desktop.xdo('getwindowname', active).strip()
    if title in ('KakaoTalk', '카카오톡', 'Open', 'Save As') or not title:
        return {'status': 'needs_inspection', 'message': 'The active window is not a verified chat room.'}
    geometry = dict(line.split('=', 1) for line in
                    desktop.xdo('getwindowgeometry', '--shell', active).splitlines() if '=' in line)
    box = {name.lower(): int(geometry[name]) for name in ('X', 'Y', 'WIDTH', 'HEIGHT')}
    picture, words = auth.observe()
    result = []
    for word in words:
        if word['pass'] != 200 or not (box['x'] <= word['x'] < box['x'] + box['width']
                                      and box['y'] <= word['y'] < box['y'] + box['height']):
            continue
        region = picture.crop((max(0, word['x'] - 2), max(0, word['y'] - 2),
                               min(picture.width, word['x'] + word['width'] + 2),
                               min(picture.height, word['y'] + word['height'] + 2))).convert('RGB')
        yellow = sum(count for count, (r, g, b) in
                     region.getcolors(maxcolors=region.width * region.height)
                     if r > 220 and g > 190 and b < 160)
        item = {key: value for key, value in word.items() if key != 'pass'}
        item['bubble'] = 'outgoing' if yellow > region.width * region.height * 0.4 else 'other'
        result.append(item)
    return {'status': 'ready', 'room_title': title, 'window': box, 'words': result,
            'message': 'Outgoing labels use the default yellow bubble background. Other text includes incoming messages and UI; do not infer outgoing from it. Only the visible PC-synced range was read.'}


def open_chat(x, y):
    """Open a currently observed chat-list row with a double click, then read it."""
    state = show_chats()
    if state['status'] != 'ready':
        return state
    box = state['window']
    if not (box['x'] + 65 <= x < box['x'] + box['width'] - 15
            and box['y'] + 90 <= y < box['y'] + box['height'] - 100):
        return {'status': 'needs_inspection', 'message': 'Coordinates are outside the verified chat-list rows; no click made.'}
    desktop.click(x, y, clicks=2)
    time.sleep(0.4)
    return read_chat()
