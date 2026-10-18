import unittest
from unittest.mock import patch

from PIL import Image

import navigation


class NavigationTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
