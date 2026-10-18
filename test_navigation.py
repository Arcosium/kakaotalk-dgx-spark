import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

import navigation


class NavigationTests(unittest.TestCase):
    def test_chat_list_excludes_text_from_other_windows(self):
        words = [{'text': 'Chats', 'pass': 200, 'x': 180, 'y': 150, 'width': 60, 'height': 14},
                 {'text': 'other room', 'pass': 200, 'x': 650, 'y': 250, 'width': 60, 'height': 14}]
        with patch('navigation.auth.ensure_logged_in', return_value={'status': 'ready'}), \
                patch('navigation.desktop.status', return_value={'windows': ['main']}), \
                patch('navigation.desktop.xdo', side_effect=['KakaoTalk',
                                                             'X=100\nY=100\nWIDTH=392\nHEIGHT=642\n', '']), \
                patch('navigation.auth.observe', return_value=(Image.new('RGB', (1000, 800)), words)), \
                patch('navigation.desktop.click') as click:
            result = navigation.show_chats()
            self.assertEqual([w['text'] for w in result['words']], ['Chats'])
            click.assert_not_called()

    def test_icon_is_found_at_current_window_position(self):
        for left, top in ((0, 0), (320, 180)):
            picture = Image.new('RGB', (1000, 800), (238, 238, 238))
            for y, row in enumerate(navigation.CHAT_ICON):
                for x, bit in enumerate(row):
                    if bit == '1':
                        picture.putpixel((left + 19 + x, top + 106 + y), (128, 128, 128))
            self.assertEqual(navigation.find_chat_tab(picture, (left, top, 392, 642)),
                             (left + 32, top + 118))

    def test_unrecognized_or_ambiguous_icon_is_rejected(self):
        picture = Image.new('RGB', (1000, 800), (238, 238, 238))
        self.assertIsNone(navigation.find_chat_tab(picture, (0, 0, 392, 642)))
        for offset in (60, 120):
            for y, row in enumerate(navigation.CHAT_ICON):
                for x, bit in enumerate(row):
                    if bit == '1':
                        picture.putpixel((19 + x, offset + y), (128, 128, 128))
        self.assertIsNone(navigation.find_chat_tab(picture, (0, 0, 392, 642)))

    def test_logged_out_state_does_not_navigate(self):
        with patch('navigation.auth.ensure_logged_in', return_value={'status': 'credentials_missing'}), \
                patch('navigation.desktop.status') as status, patch('navigation.desktop.click') as click:
            self.assertEqual(navigation.show_chats()['status'], 'credentials_missing')
            status.assert_not_called()
            click.assert_not_called()

    def test_room_open_uses_double_click(self):
        state = {'status': 'ready', 'window': {'x': 100, 'y': 100, 'width': 392, 'height': 642}}
        with patch('navigation.show_chats', return_value=state), \
                patch('navigation.desktop.click') as click, patch('navigation.time.sleep'), \
                patch('navigation.read_chat', return_value={'status': 'ready', 'room_title': 'Example room'}):
            self.assertEqual(navigation.open_chat(250, 250)['status'], 'ready')
            click.assert_called_once_with(250, 250, clicks=2)

    def test_coordinates_outside_chat_rows_are_rejected(self):
        state = {'status': 'ready', 'window': {'x': 100, 'y': 100, 'width': 392, 'height': 642}}
        with patch('navigation.show_chats', return_value=state), patch('navigation.desktop.click') as click:
            self.assertEqual(navigation.open_chat(20, 20)['status'], 'needs_inspection')
            click.assert_not_called()

    def test_read_chat_distinguishes_yellow_outgoing_bubbles(self):
        picture = Image.new('RGB', (800, 800), 'white')
        ImageDraw.Draw(picture).rectangle((290, 240, 390, 280), fill=(255, 235, 80))
        words = [{'text': 'sent', 'pass': 200, 'x': 305, 'y': 250, 'width': 40, 'height': 15},
                 {'text': 'received', 'pass': 200, 'x': 125, 'y': 200, 'width': 60, 'height': 15}]
        with patch('navigation.desktop.xdo', side_effect=['room-window', 'Example room',
                                                          'X=100\nY=100\nWIDTH=400\nHEIGHT=400\n']), \
                patch('navigation.auth.observe', return_value=(picture, words)):
            result = navigation.read_chat()
            self.assertEqual(result['room_title'], 'Example room')
            self.assertEqual([w['bubble'] for w in result['words']], ['outgoing', 'other'])


if __name__ == '__main__':
    unittest.main()
