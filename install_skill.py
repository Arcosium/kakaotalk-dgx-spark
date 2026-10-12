"""Install the shared Korean skill with paths to this checkout and interpreter."""
import argparse
import datetime
from pathlib import Path
import shutil
import sys


def install(agent):
    repo = Path(__file__).resolve().parent
    home = Path.home()
    root = home / ('.codex' if agent == 'codex' else '.claude') / 'skills'
    target = root / '카카오톡'
    if target.exists() or target.is_symlink():
        raise RuntimeError(f'{target} exists; preserve your current skill before installing.')
    template = (repo / 'skills/카카오톡/SKILL.md').read_text()
    text = template.replace('{{REPO}}', str(repo)).replace('{{PYTHON}}', sys.executable)
    target.mkdir(parents=True)
    (target / 'SKILL.md').write_text(text)
    print(f'{agent}: installed /카카오톡 at {target}; open a new agent session.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('agent', choices=('claude', 'codex', 'both'))
    args = parser.parse_args()
    for agent in ('claude', 'codex') if args.agent == 'both' else (args.agent,):
        install(agent)
