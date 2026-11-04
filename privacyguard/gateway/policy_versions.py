"""Bounded policy drafts and immutable, tested action snapshots.

Matchers and mandatory safety checks remain code-reviewed. No executable regex
or arbitrary customer sample is accepted through this management API.
"""
import hashlib
import json
import time

from .policies import BUILTINS, VERSION, run_examples

ENGINE = VERSION + ':actions-1'
SUITE = 'policy-workflow-2'
KINDS = sorted({k for k, _, _ in BUILTINS} | {
    'PERSON', 'ORGANIZATION', 'ADDRESS', 'PROJECT', 'DEPARTMENT', 'COURT', 'LAW_FIRM'})
DEFAULT = {'request': {'default': 'REDACT'}, 'response': {'default': 'BLOCK'}}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def validate(value):
    if not isinstance(value, dict) or set(value) != {'request', 'response'}:
        raise ValueError('invalid_policy')
    for rules in value.values():
        if (not isinstance(rules, dict) or 'default' not in rules
                or set(rules) - {'default', *KINDS}
                or any(v not in ('REDACT', 'BLOCK') for v in rules.values())):
            raise ValueError('invalid_policy')
    return json.loads(canonical(value))


def digest(value):
    return hashlib.sha256((ENGINE + canonical(validate(value))).encode()).hexdigest()


BASE = 'pv-' + digest(DEFAULT)


def action(policy, direction, kind):
    return policy[direction].get(kind, policy[direction]['default'])


def exercise(policy):
    """Use the runtime Protection implementation, without calling a model.

    Assertions are independent of actual output and include mandatory failures.
    This is a bounded fixture gate, not an assessment of semantic recall.
    """
    from .app import Protection, Blocked
    from privacyguard.models import Finding
    results = [{'name': r['name'], 'passed': r['passed']} for r in run_examples()['results']]
    for direction in ('request', 'response'):
        samples = [('PHONE', '13800138000'), ('EMAIL', 'alice@example.com')]
        samples += [(kind, '虚构候选') for kind in KINDS]
        for index, (kind, text) in enumerate(samples):
            def detector(content):
                return [Finding(kind, 0, len(content), .99, 'fixture')] if content == '虚构候选' else []
            p = Protection(detector, policy)
            expected = action(policy, direction, kind)
            try:
                output = p.protect(text, direction)
                ok = expected == 'REDACT' and output == f'<{kind}_001>'
            except Blocked:
                ok = expected == 'BLOCK'
            results.append({'name': direction + '.' + kind + '.' + str(index), 'passed': ok})
        for name, text, detector in [
            ('credential', '-----BEGIN PRIVATE KEY-----', lambda _: []),
            ('uncertain', '虚构机构', lambda _: [Finding('ORGANIZATION', 0, 4, .5, 'fixture')]),
        ]:
            try:
                Protection(detector, policy).protect(text, direction)
                ok = False
            except Blocked:
                ok = True
            results.append({'name': direction + '.' + name, 'passed': ok})
    return {'suite': SUITE, 'passed': all(r['passed'] for r in results), 'results': results,
            'calls_upstream': False, 'scope': 'Fixed fictional rule and runtime action fixtures; not semantic recall.'}


class PolicyVersions:
    def __init__(self, state):
        self.state = state
        with state.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS policy_drafts (
                    tenant TEXT PRIMARY KEY, content TEXT NOT NULL, hash TEXT NOT NULL,
                    generation INTEGER NOT NULL, test TEXT);
                CREATE TABLE IF NOT EXISTS policy_versions (
                    tenant TEXT NOT NULL, id TEXT NOT NULL, content TEXT NOT NULL,
                    engine TEXT NOT NULL, test TEXT NOT NULL, created REAL NOT NULL,
                    PRIMARY KEY(tenant,id));
                CREATE TABLE IF NOT EXISTS policy_bindings (
                    channel_id TEXT PRIMARY KEY, version TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS policy_activations (
                    id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, channel_id TEXT NOT NULL,
                    previous TEXT NOT NULL, version TEXT NOT NULL, created REAL NOT NULL);
            ''')

    def _draft(self, db, tenant):
        db.execute('INSERT OR IGNORE INTO policy_drafts VALUES (?,?,?,0,NULL)',
                   (tenant, canonical(DEFAULT), digest(DEFAULT)))
        row = db.execute('SELECT content,hash,generation,test FROM policy_drafts WHERE tenant=?', (tenant,)).fetchone()
        return {'content': json.loads(row[0]), 'hash': row[1], 'generation': row[2],
                'test': json.loads(row[3]) if row[3] else None}

    def _version(self, db, tenant, identifier):
        if identifier == BASE:
            return validate(DEFAULT)
        row = db.execute('SELECT content,engine FROM policy_versions WHERE tenant=? AND id=?', (tenant, identifier)).fetchone()
        if not row:
            raise PermissionError('version_not_found')
        content = validate(json.loads(row[0]))
        if row[1] != ENGINE or identifier != 'pv-' + digest(content):
            raise ValueError('policy_engine_mismatch')
        return content

    def active(self, tenant, channel):
        with self.state.connect() as db:
            row = db.execute('SELECT b.version FROM channels c LEFT JOIN policy_bindings b ON b.channel_id=c.id WHERE c.id=? AND c.tenant=?', (channel, tenant)).fetchone()
            if row is None:
                raise PermissionError('not_found_or_forbidden')
            identifier = row[0] or BASE
            return identifier, self._version(db, tenant, identifier)

    def snapshot(self, tenant):
        with self.state.connect() as db:
            draft = self._draft(db, tenant)
            versions = [{'id': BASE, 'content': validate(DEFAULT), 'created': None, 'baseline': True}]
            versions += [dict(id=r[0], content=json.loads(r[1]), created=r[2], baseline=False)
                         for r in db.execute('SELECT id,content,created FROM policy_versions WHERE tenant=? AND id!=? ORDER BY created DESC', (tenant, BASE))]
            bindings = [dict(channel_id=r[0], version=r[1] or BASE) for r in db.execute(
                'SELECT c.id,b.version FROM channels c LEFT JOIN policy_bindings b ON b.channel_id=c.id WHERE c.tenant=?', (tenant,))]
            history = [dict(id=r[0], channel_id=r[1], previous=r[2], version=r[3], created=r[4]) for r in db.execute(
                'SELECT id,channel_id,previous,version,created FROM policy_activations WHERE tenant=? ORDER BY id DESC LIMIT 100', (tenant,))]
        return dict(draft=draft, versions=versions, bindings=bindings, history=history, kinds=KINDS,
                    engine=ENGINE, suite=SUITE, baseline=BASE)

    def save(self, tenant, generation, content):
        content = validate(content)
        with self.state.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            draft = self._draft(db, tenant)
            if type(generation) is not int or draft['generation'] != generation:
                raise PermissionError('draft_changed_reload')
            db.execute('UPDATE policy_drafts SET content=?,hash=?,generation=generation+1,test=NULL WHERE tenant=?',
                       (canonical(content), digest(content), tenant))
            self._audit(db, tenant, 'policy_save', digest(content))
            return self._draft(db, tenant)

    def test(self, tenant, generation):
        with self.state.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            draft = self._draft(db, tenant)
            if type(generation) is not int or draft['generation'] != generation:
                raise PermissionError('draft_changed_reload')
            db.execute('UPDATE policy_drafts SET test=NULL WHERE tenant=?', (tenant,))
        result = exercise(validate(draft['content']))
        result.update(hash=draft['hash'], generation=generation)
        with self.state.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = self._draft(db, tenant)
            if current['generation'] != generation:
                raise PermissionError('draft_changed_reload')
            db.execute('UPDATE policy_drafts SET test=? WHERE tenant=?', (canonical(result), tenant))
            self._audit(db, tenant, 'policy_test', draft['hash'])
        return result

    def publish(self, tenant, generation):
        with self.state.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            draft = self._draft(db, tenant)
            test = draft['test'] or {}
            if (type(generation) is not int or draft['generation'] != generation
                    or test.get('generation') != generation or test.get('passed') is not True
                    or test.get('hash') != digest(draft['content']) or test.get('suite') != SUITE):
                raise PermissionError('passing_current_tests_required')
            identifier = 'pv-' + digest(draft['content'])
            db.execute('INSERT OR IGNORE INTO policy_versions VALUES (?,?,?,?,?,?)',
                       (tenant, identifier, canonical(draft['content']), ENGINE, canonical(test), time.time()))
            self._audit(db, tenant, 'policy_publish', identifier)
            return {'version': identifier, 'activated': False}

    def activate(self, tenant, channel, version, expected):
        with self.state.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM channels WHERE id=? AND tenant=?', (channel, tenant)).fetchone():
                raise PermissionError('not_found_or_forbidden')
            self._version(db, tenant, version)
            row = db.execute('SELECT version FROM policy_bindings WHERE channel_id=?', (channel,)).fetchone()
            previous = row[0] if row else BASE
            if previous != expected:
                raise PermissionError('binding_changed_reload')
            db.execute('INSERT INTO policy_bindings VALUES (?,?) ON CONFLICT(channel_id) DO UPDATE SET version=excluded.version', (channel, version))
            db.execute('INSERT INTO policy_activations(tenant,channel_id,previous,version,created) VALUES (?,?,?,?,?)',
                       (tenant, channel, previous, version, time.time()))
            self._audit(db, tenant, 'policy_activate', channel + ':' + version)
            return {'previous': previous, 'version': version}

    @staticmethod
    def _audit(db, tenant, operation, target):
        db.execute('INSERT INTO admin_events VALUES (?,?,?,?)', (time.time(), tenant, operation, target))
