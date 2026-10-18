import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

import auth
import credentials
import mcp_server


def word(text, x, y, threshold=225):
    return {'text': text, 'x': x, 'y': y, 'width': 60, 'height': 12, 'pass': threshold}


PICTURE = Image.new('RGB', (1280, 900), 'white')
FORM = [word('Email or Phone number', 520, 360), word('Password', 520, 400),
        word('QR Code Log In', 590, 530)]
READY = [{**word('Friends', 520, 190), 'height': 14}, word('Q', 750, 190)]


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for target, value in [('auth.desktop.ROOT', self.root),
                              ('credentials.PATH', self.root / 'login.json'),
                              ('credentials.ATTEMPT', self.root / 'attempt.json')]:
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_already_logged_in_does_not_read_credentials(self):
        with patch('auth.observe', return_value=(PICTURE, READY)), \
                patch('credentials.load') as load, patch('auth.desktop.click') as click:
            self.assertEqual(auth.ensure_logged_in()['status'], 'ready')
            load.assert_not_called()
            click.assert_not_called()

    def test_unknown_screen_and_partial_form_never_receive_credentials(self):
        for words in ([], FORM[1:], [word('Password', 520, 400)]):
            with patch('auth.observe', return_value=(PICTURE, words)), \
                    patch('credentials.load') as load, patch('auth.desktop.click') as click:
                auth.ensure_logged_in()
                load.assert_not_called()
                click.assert_not_called()

    def test_missing_credentials_and_previous_attempt_block_input(self):
        with patch('auth.observe', return_value=(PICTURE, FORM)), \
                patch('auth.desktop.type_text') as type_text:
            self.assertEqual(auth.ensure_logged_in()['status'], 'credentials_missing')
            credentials.ATTEMPT.touch()
            self.assertEqual(auth.ensure_logged_in()['status'], 'retry_blocked')
            type_text.assert_not_called()

    def test_single_login_clears_clipboard_and_returns_no_secrets(self):
        credentials.save('test-account', 'test-password')
        with patch('auth.observe', side_effect=[(PICTURE, FORM), (PICTURE, READY)]), \
                patch('auth.desktop.click') as click, patch('auth.desktop.press'), \
                patch('auth.desktop.type_text') as type_text, \
                patch('auth.desktop.set_clipboard') as clipboard, patch('auth.time.sleep'):
            result = auth.ensure_logged_in()
            self.assertEqual(result['status'], 'logged_in')
            self.assertEqual([c.args[0] for c in type_text.call_args_list],
                             ['test-account', 'test-password'])
            self.assertEqual(click.call_count, 3)
            clipboard.assert_called_once_with(' ')
            self.assertFalse(credentials.ATTEMPT.exists())
            self.assertNotIn('test-password', json.dumps(result))
            self.assertNotIn('test-account', json.dumps(result))

    def test_input_error_clears_clipboard_and_blocks_automatic_retry(self):
        credentials.save('test-account', 'test-password')
        with patch('auth.observe', return_value=(PICTURE, FORM)), \
                patch('auth.desktop.click'), patch('auth.desktop.press'), \
                patch('auth.desktop.type_text', side_effect=RuntimeError('input failed')), \
                patch('auth.desktop.set_clipboard') as clipboard:
            with self.assertRaises(RuntimeError):
                auth.ensure_logged_in()
            clipboard.assert_called_once_with(' ')
            self.assertEqual(auth.ensure_logged_in()['status'], 'retry_blocked')

    def test_credentials_are_private_and_reject_insecure_permissions(self):
        credentials.save('test-account', 'test-password')
        self.assertEqual(credentials.PATH.stat().st_mode & 0o777, 0o600)
        self.assertEqual(credentials.load()['account'], 'test-account')
        credentials.PATH.chmod(0o644)
        with self.assertRaises(PermissionError):
            credentials.load()

    def test_additional_authentication_stops_without_retry(self):
        credentials.save('test-account', 'test-password')
        challenge = [word('Verification', 520, 400)]
        with patch('auth.observe', side_effect=[(PICTURE, FORM), (PICTURE, challenge)]), \
                patch('auth.desktop.click') as click, patch('auth.desktop.press'), \
                patch('auth.desktop.type_text'), patch('auth.desktop.set_clipboard'), \
                patch('auth.time.sleep'):
            result = auth.ensure_logged_in()
            self.assertEqual(result['status'], 'authentication_required')
            self.assertEqual(click.call_count, 3)
            self.assertTrue(credentials.ATTEMPT.exists())

    def test_mcp_does_not_type_message_after_fallback_login(self):
        with patch('mcp_server.auth.ensure_logged_in', return_value={'status': 'logged_in'}), \
                patch('mcp_server.desktop.type_text') as type_text:
            result = json.loads(mcp_server.type_text('example message'))
            self.assertFalse(result['typed'])
            type_text.assert_not_called()


if __name__ == '__main__':
    unittest.main()
