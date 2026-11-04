"""python -m privacyguard.gateway {init,serve,revoke}. Never print keys."""
import argparse
import json
import os
from pathlib import Path

from .app import Config, create_app
from .state import State


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'serve', 'revoke', 'init-admin'])
    parser.add_argument('--directory', type=Path, default=Path.home() / '.privacyguard/gateway')
    parser.add_argument('--model', help='Explicit local upstream model, with openai/ prefix')
    args = parser.parse_args()
    root = args.directory.expanduser().resolve()
    if args.action == 'init':
        if root.exists():
            parser.error('State directory already exists; refusing to overwrite')
        config = Config(args.model or '')
        config.validate()
        root.mkdir(parents=True, mode=0o700)
        state = State(root / 'state.sqlite3')
        key = state.issue('local-owner')
        (root / 'config.json').write_text(json.dumps(config.__dict__, indent=2))
        (root / 'client.json').write_text(json.dumps({'base_url': 'http://127.0.0.1:8787/v1',
            'api_key': key, 'model': config.public_model}, indent=2))
        print(f'Local configuration created: {root}; client.json contains a 24-hour key. Keep private.')
    else:
        if not (root / 'config.json').is_file():
            parser.error('Initialize a new state directory first')
        state = State(root / 'state.sqlite3')
        if args.action == 'init-admin':
            credential = root / 'admin-login.txt'
            if credential.exists():
                parser.error('Administrator credential already exists; refusing to overwrite')
            password = state.create_admin()
            with credential.open('x') as handle:
                handle.write(password + '\n')
            print(f'Administrator password created: {credential}; open http://127.0.0.1:8787/admin')
            return
        if args.action == 'revoke':
            state.revoke_all()
            print('All gateway keys revoked')
            return
        config = Config(**json.loads((root / 'config.json').read_text()))
        import uvicorn
        uvicorn.run(create_app(state, config), host='127.0.0.1', port=8787, access_log=False,
                    log_level='warning', limit_concurrency=8, timeout_keep_alive=5)


if __name__ == '__main__':
    main()
