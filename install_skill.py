"""Install the shared Korean skill with paths to this checkout and interpreter."""
import argparse
import datetime
import os
from pathlib import Path
import shutil
import sys

import desktop


def install(agent, update=False):
    repo = Path(__file__).resolve().parent
    home = Path.home()
    root = (Path(os.environ.get('HERMES_HOME', home / '.hermes/local-chat')).expanduser() / 'skills'
            if agent == 'local' else home / ('.codex' if agent == 'codex' else '.claude') / 'skills')
    target = root / '카카오톡'
    skill = target / 'SKILL.md'
    if target.is_symlink() or skill.is_symlink():
        raise RuntimeError(f'{target} uses a source-managed symlink; update its source instead.')
    if target.exists() and not update:
        raise RuntimeError(f'{target} exists; preserve your current skill before installing.')
    template = (repo / 'skills/카카오톡/SKILL.md').read_text()
    text = template.replace('{{REPO}}', str(repo)).replace('{{PYTHON}}', sys.executable)
    if skill.exists():
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup = desktop.ROOT / 'skill-backups' / stamp / agent
        backup.mkdir(parents=True, mode=0o700)
        shutil.copy2(skill, backup / 'SKILL.md')
        print(f'{agent}: previous skill preserved at {backup / "SKILL.md"}')
    target.mkdir(parents=True, exist_ok=True)
    skill.write_text(text)
    print(f'{agent}: installed /카카오톡 at {target}; open a new agent session.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('agent', choices=('claude', 'codex', 'local', 'both', 'all'))
    parser.add_argument('--update', action='store_true', help='Back up and update an existing skill.')
    args = parser.parse_args()
    agents = (('claude', 'codex', 'local') if args.agent == 'all' else
              ('claude', 'codex') if args.agent == 'both' else (args.agent,))
    for agent in agents:
        install(agent, update=args.update)
