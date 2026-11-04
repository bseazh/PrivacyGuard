"""Single-instance SQLite authorization and body-free audit records."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
import json
import hmac
from contextlib import contextmanager
from pathlib import Path


class State:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
                INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
                CREATE TABLE IF NOT EXISTS keys (
                    digest TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS events (
                    request_id TEXT PRIMARY KEY, created REAL NOT NULL,
                    user_id TEXT, revision TEXT NOT NULL, action TEXT NOT NULL,
                    code TEXT NOT NULL, entity_count INTEGER NOT NULL DEFAULT 0);
            ''')
            version = db.execute('SELECT version FROM schema_version').fetchall()
            if version not in ([(1,)], [(2,)]):
                raise ValueError('Unsupported gateway schema')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, name TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, name TEXT NOT NULL, config TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS grants (user_id TEXT NOT NULL, channel_id TEXT NOT NULL, PRIMARY KEY(user_id, channel_id));
                CREATE TABLE IF NOT EXISTS admins (username TEXT PRIMARY KEY, tenant TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, username TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS login_attempts (created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS admin_events (created REAL NOT NULL, tenant TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL);
            ''')
            if version == [(1,)]:
                db.execute("ALTER TABLE keys ADD COLUMN channel_id TEXT NOT NULL DEFAULT 'default'")
                db.execute("ALTER TABLE events ADD COLUMN channel_id TEXT NOT NULL DEFAULT 'default'")
                db.execute("INSERT OR IGNORE INTO users SELECT DISTINCT user_id, 'local', user_id, 1 FROM keys")
                db.execute("INSERT OR IGNORE INTO grants SELECT DISTINCT user_id, 'default' FROM keys")
                db.execute('UPDATE schema_version SET version=2')
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
            db.execute("INSERT OR IGNORE INTO users VALUES (?, 'local', ?, 1)", (user, user))
            db.execute("INSERT OR IGNORE INTO grants VALUES (?, 'default')", (user,))
            db.execute("INSERT INTO keys (digest,user_id,expires,revoked) VALUES (?, ?, ?, 0)",
                       (self.digest(token), user, time.time() + ttl))
        return token

    def authenticate(self, token: str) -> str | None:
        context = self.authorize(token)
        return context['user_id'] if context else None

    def authorize(self, token: str):
        with self.connect() as db:
            row = db.execute('''SELECT u.id, u.tenant, c.id, c.config FROM keys k
                JOIN users u ON u.id=k.user_id JOIN channels c ON c.id=k.channel_id
                JOIN grants g ON g.user_id=u.id AND g.channel_id=c.id
                WHERE k.digest=? AND k.revoked=0 AND k.expires>?
                AND u.enabled=1 AND c.enabled=1 AND u.tenant=c.tenant''',
                             (self.digest(token), time.time())).fetchone()
        return dict(zip(('user_id', 'tenant', 'channel_id', 'config'), row)) if row else None

    def configure_default(self, config):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO channels VALUES ('default','local','本机默认通道',?,1)", (json.dumps(config),))

    def revoke_all(self):
        with self.connect() as db:
            db.execute('UPDATE keys SET revoked=1')

    def admit(self, request_id: str, user: str, revision: str, channel: str = 'default') -> bool:
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count = db.execute('SELECT COUNT(*) FROM events WHERE user_id=? AND created>?',
                               (user, time.time() - 60)).fetchone()[0]
            if count >= 10:
                return False
            db.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, 0, ?)',
                       (request_id, time.time(), user, revision, 'PENDING', 'accepted', channel))
        return True

    def finish(self, request_id: str, action: str, code: str, count: int = 0):
        with self.connect() as db:
            db.execute('UPDATE events SET action=?, code=?, entity_count=? WHERE request_id=?',
                       (action, code, count, request_id))

    def create_admin(self):
        password, salt = secrets.token_urlsafe(24), secrets.token_hex(16)
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        with self.connect() as db:
            db.execute("INSERT INTO admins VALUES ('admin','local',?,?)", (salt, digest))
        return password

    def login(self, password):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM login_attempts WHERE created<?', (time.time()-60,))
            if db.execute('SELECT COUNT(*) FROM login_attempts').fetchone()[0] >= 5:
                raise PermissionError('login_limited')
            db.execute('INSERT INTO login_attempts VALUES (?)', (time.time(),))
            row = db.execute("SELECT salt,password_hash FROM admins WHERE username='admin'").fetchone()
        if not row or not isinstance(password, str) or len(password) > 256:
            raise PermissionError('invalid_login')
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(row[0]), n=16384, r=8, p=1).hex()
        if not hmac.compare_digest(actual, row[1]):
            raise PermissionError('invalid_login')
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            db.execute("INSERT INTO sessions VALUES (?, 'admin', ?)", (self.digest(token), time.time()+3600))
        return token

    def admin_session(self, token):
        with self.connect() as db:
            row = db.execute('SELECT a.tenant FROM sessions s JOIN admins a ON a.username=s.username WHERE s.digest=? AND s.expires>?', (self.digest(token), time.time())).fetchone()
        return row[0] if row else None

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE digest=?', (self.digest(token),))

    def snapshot(self, tenant):
        with self.connect() as db:
            def rows(sql):
                cursor = db.execute(sql, (tenant,))
                return [dict(zip([x[0] for x in cursor.description], row)) for row in cursor.fetchall()]
            return {
                'users': rows('SELECT id,name,enabled FROM users WHERE tenant=? ORDER BY rowid'),
                'channels': rows('SELECT id,name,config,enabled FROM channels WHERE tenant=? ORDER BY rowid'),
                'grants': rows('SELECT g.user_id,g.channel_id FROM grants g JOIN users u ON u.id=g.user_id WHERE u.tenant=?'),
                'keys': rows('SELECT k.rowid AS id,k.user_id,k.channel_id,k.expires,k.revoked FROM keys k JOIN users u ON u.id=k.user_id WHERE u.tenant=? ORDER BY k.rowid DESC'),
                'events': rows('SELECT e.* FROM events e JOIN users u ON u.id=e.user_id WHERE u.tenant=? ORDER BY created DESC LIMIT 100'),
                'changes': rows('SELECT created,action,target FROM admin_events WHERE tenant=? ORDER BY created DESC LIMIT 50')}

    def manage(self, tenant, action, data):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            result = {}
            def owned(table, identifier):
                # table is only a fixed literal supplied by the action below.
                row = db.execute(f'SELECT id FROM {table} WHERE id=? AND tenant=?', (identifier, tenant)).fetchone()
                if not row:
                    raise PermissionError('not_found_or_forbidden')
            target = data.get('id', '')
            if action == 'user_create':
                target = secrets.token_hex(12)
                db.execute('INSERT INTO users VALUES (?,?,?,1)', (target, tenant, data['name']))
                result = {'id': target}
            elif action == 'user_status':
                owned('users', target)
                db.execute('UPDATE users SET enabled=? WHERE id=?', (data['enabled'], target))
            elif action == 'channel_create':
                target = secrets.token_hex(12)
                db.execute('INSERT INTO channels VALUES (?,?,?,?,0)', (target, tenant, data['name'], json.dumps(data['config'])))
                result = {'id': target}
            elif action == 'channel_status':
                owned('channels', target)
                db.execute('UPDATE channels SET enabled=? WHERE id=?', (data['enabled'], target))
            elif action in ('grant', 'ungrant', 'issue_key'):
                user, channel = data['user_id'], data['channel_id']
                owned('users', user); owned('channels', channel)
                target = user + ':' + channel
                if action == 'grant':
                    db.execute('INSERT OR IGNORE INTO grants VALUES (?,?)', (user, channel))
                elif action == 'ungrant':
                    db.execute('DELETE FROM grants WHERE user_id=? AND channel_id=?', (user, channel))
                else:
                    if not db.execute('SELECT 1 FROM grants WHERE user_id=? AND channel_id=?', (user, channel)).fetchone():
                        raise PermissionError('grant_required')
                    if not db.execute('SELECT 1 FROM users u JOIN channels c ON c.id=? WHERE u.id=? AND u.enabled=1 AND c.enabled=1', (channel, user)).fetchone():
                        raise PermissionError('user_or_channel_disabled')
                    token = 'pgw_' + secrets.token_urlsafe(32)
                    db.execute('INSERT INTO keys VALUES (?,?,?,0,?)', (self.digest(token), user, time.time()+86400, channel))
                    result = {'api_key': token, 'expires_in': 86400}
            elif action == 'revoke_key':
                row = db.execute('SELECT k.rowid FROM keys k JOIN users u ON u.id=k.user_id WHERE k.rowid=? AND u.tenant=?', (target, tenant)).fetchone()
                if not row:
                    raise PermissionError('not_found_or_forbidden')
                db.execute('UPDATE keys SET revoked=1 WHERE rowid=?', (target,))
            else:
                raise ValueError('unsupported_action')
            db.execute('INSERT INTO admin_events VALUES (?,?,?,?)', (time.time(), tenant, action, str(target)))
            return result
