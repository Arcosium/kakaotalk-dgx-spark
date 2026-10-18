from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install_skill


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        for helper in (patch.object(Path, 'home', return_value=self.home),
                       patch.object(install_skill.desktop, 'ROOT', self.home / 'data'),
                       patch.dict(os.environ, {'HERMES_HOME': str(self.home / 'local-profile')})):
            helper.start()
            self.addCleanup(helper.stop)

    def install(self, *args, **kwargs):
        with redirect_stdout(io.StringIO()):
            install_skill.install(*args, **kwargs)

    def test_local_profile_install_resolves_template_paths(self):
        self.install('local')
        target = self.home / 'local-profile/skills/카카오톡/SKILL.md'
        text = target.read_text()
        self.assertNotIn('{{REPO}}', text)
        self.assertNotIn('{{PYTHON}}', text)
        self.assertIn('ensure_logged_in', text)

    def test_existing_skill_requires_update_and_is_backed_up(self):
        self.install('codex')
        target = self.home / '.codex/skills/카카오톡/SKILL.md'
        target.write_text('user-edited current skill')
        with self.assertRaises(RuntimeError):
            self.install('codex')
        self.assertEqual(target.read_text(), 'user-edited current skill')
        self.install('codex', update=True)
        backups = list((self.home / 'data/skill-backups').rglob('SKILL.md'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'user-edited current skill')
        self.assertNotEqual(target.read_text(), backups[0].read_text())

    def test_update_preserves_source_managed_symlink(self):
        original = self.home / 'source.md'
        original.write_text('source-managed skill')
        folder = self.home / '.claude/skills/카카오톡'
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').symlink_to(original)
        with self.assertRaises(RuntimeError):
            self.install('claude', update=True)
        self.assertEqual(original.read_text(), 'source-managed skill')


if __name__ == '__main__':
    unittest.main()
