"""Local credential storage. Never pass account values in CLI arguments or MCP."""
import argparse
import getpass
import json
import os
from pathlib import Path
import stat
import tempfile

import desktop

PATH = desktop.ROOT / 'login.json'
ATTEMPT = desktop.ROOT / 'login-attempt.json'


def write_private(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.login-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save(account, password):
    if not account.strip() or not password or '\n' in account or '\n' in password:
        raise ValueError('Account and password must be nonempty single-line values.')
    write_private(PATH, {'account': account.strip(), 'password': password})
    ATTEMPT.unlink(missing_ok=True)


def load():
    fd = os.open(PATH, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise PermissionError('Credential file must be owned by this user with mode 600.')
        value = json.load(stream)
    if not all(isinstance(value.get(key), str) and value[key] for key in ('account', 'password')):
        raise ValueError('Invalid local credentials; register them again in the server terminal.')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['set', 'status', 'forget'])
    args = parser.parse_args()
    if args.action == 'set':
        save(getpass.getpass('Kakao account (hidden): '), getpass.getpass('Password (hidden): '))
        print('Saved locally. Account values were not printed.')
    elif args.action == 'forget':
        PATH.unlink(missing_ok=True)
        ATTEMPT.unlink(missing_ok=True)
        print('Local login credentials removed.')
    else:
        print('Configured locally.' if PATH.exists() else 'Not configured.')
