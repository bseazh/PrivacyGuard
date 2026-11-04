"""Start/stop the local gateway with process identity validation (macOS/Linux)."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time


def identity(pid):
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart=', '-o', 'command='], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop'])
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    directory = args.directory.expanduser().resolve()
    if not (directory / 'config.json').is_file():
        parser.error('Initialize gateway state first')
    record = directory / 'process.json'
    if record.exists():
        data = json.loads(record.read_text())
        current = identity(data['pid'])
        if current and current != data['identity']:
            parser.error('Process identity mismatch; retaining record and refusing to stop or start')
        if current and args.action == 'start':
            print('Gateway already running: http://127.0.0.1:8787/admin')
            return
        if current:
            os.kill(data['pid'], signal.SIGTERM)
            for _ in range(100):
                if not identity(data['pid']):
                    break
                time.sleep(.1)
            else:
                parser.error('Stop not confirmed; retaining process identity record')
        record.unlink()
    if args.action == 'stop':
        print('Gateway stopped')
        return
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8787)) == 0:
            parser.error('Port 8787 is occupied; no existing process was stopped')
    os.umask(0o077)
    with (directory / 'gateway.log').open('ab') as log:
        process = subprocess.Popen([sys.executable, '-m', 'privacyguard.gateway', 'serve', '--directory', str(directory)],
            cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(100):
        if process.poll() is not None:
            parser.error('Gateway failed to start; inspect private gateway.log')
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', 8787)) == 0:
                record.write_text(json.dumps({'pid': process.pid, 'identity': identity(process.pid)}))
                print('Gateway running: http://127.0.0.1:8787/admin')
                return
        time.sleep(.1)
    process.terminate()
    process.wait(timeout=10)
    parser.error('Gateway startup timed out')


if __name__ == '__main__':
    main()
