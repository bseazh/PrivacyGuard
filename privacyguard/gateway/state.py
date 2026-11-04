"""Single-instance SQLite authorization and body-free audit records."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class State:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO schema_version VALUES (1);
                CREATE TABLE IF NOT EXISTS keys (
                    digest TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS events (
                    request_id TEXT PRIMARY KEY, created REAL NOT NULL,
                    user_id TEXT, revision TEXT NOT NULL, action TEXT NOT NULL,
                    code TEXT NOT NULL, entity_count INTEGER NOT NULL DEFAULT 0);
            ''')
            if db.execute('SELECT version FROM schema_version').fetchall() != [(1,)]:
                raise ValueError('Unsupported gateway schema')
        path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def digest(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def issue(self, user: str, ttl: int = 86400) -> str:
        token = 'pgw_' + secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('INSERT INTO keys VALUES (?, ?, ?, 0)',
                       (self.digest(token), user, time.time() + ttl))
        return token

    def authenticate(self, token: str) -> str | None:
        with self.connect() as db:
            row = db.execute('SELECT user_id FROM keys WHERE digest=? AND revoked=0 AND expires>?',
                             (self.digest(token), time.time())).fetchone()
        return row[0] if row else None

    def revoke_all(self):
        with self.connect() as db:
            db.execute('UPDATE keys SET revoked=1')

    def admit(self, request_id: str, user: str, revision: str) -> bool:
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count = db.execute('SELECT COUNT(*) FROM events WHERE user_id=? AND created>?',
                               (user, time.time() - 60)).fetchone()[0]
            if count >= 10:
                return False
            db.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, 0)',
                       (request_id, time.time(), user, revision, 'PENDING', 'accepted'))
        return True

    def finish(self, request_id: str, action: str, code: str, count: int = 0):
        with self.connect() as db:
            db.execute('UPDATE events SET action=?, code=?, entity_count=? WHERE request_id=?',
                       (action, code, count, request_id))
