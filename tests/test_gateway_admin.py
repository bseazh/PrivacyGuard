import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from privacyguard.gateway.app import Config, create_app
from privacyguard.gateway.state import State
from privacyguard.rules import detect_with_rules


class Echo:
    def __init__(self):
        self.calls = []
    async def complete(self, messages):
        self.calls.append(messages)
        return '请明确付款期限。'


@pytest.fixture
def admin(tmp_path):
    state = State(tmp_path / 'state.db')
    password = state.create_admin()
    adapter = Echo()
    with TestClient(create_app(state, Config('openai/local'), detect_with_rules, adapter)) as client:
        login = client.post('/admin/api/login', headers={'Origin': 'http://127.0.0.1:8787'}, json={'password': password})
        assert login.status_code == 200
        headers = {'Origin': 'http://127.0.0.1:8787', 'X-CSRF-Token': login.json()['csrf']}
        yield client, state, adapter, headers


def change(admin, action, data):
    r = admin[0].post('/admin/api/' + action, headers=admin[3], json=data)
    assert r.status_code == 200, r.text
    return r.json()


def setup_user_channel(admin):
    user = change(admin, 'user_create', {'name': '测试用户'})['id']
    channel = change(admin, 'channel_create', {'name': '测试通道', 'model': 'test-model'})['id']
    change(admin, 'channel_status', {'id': channel, 'enabled': True})
    change(admin, 'grant', {'user_id': user, 'channel_id': channel})
    key = change(admin, 'issue_key', {'user_id': user, 'channel_id': channel})['api_key']
    return user, channel, key


def call(admin, key, model='test-model'):
    return admin[0].post('/v1/chat/completions', headers={'Authorization': 'Bearer ' + key}, json={
        'model': model, 'messages': [{'role': 'user', 'content': '请分析付款期限。'}]})


def test_admin_end_to_end_and_revocation(admin):
    user, channel, key = setup_user_channel(admin)
    assert call(admin, key).status_code == 200
    assert call(admin, key, 'privacyguard-local').status_code == 403
    snapshot = admin[0].get('/admin/api/snapshot').json()
    assert key not in json.dumps(snapshot)
    assert State.digest(key) not in json.dumps(snapshot)
    event = snapshot['events'][0]
    assert event['channel_id'] == channel
    keyid = next(k['id'] for k in snapshot['keys'] if k['user_id'] == user)
    change(admin, 'revoke_key', {'id': str(keyid)})
    assert call(admin, key).status_code == 401
    assert len(admin[2].calls) == 1


@pytest.mark.parametrize('action', ['user_status', 'channel_status', 'ungrant'])
def test_disabled_authority_invalidates_old_key(admin, action):
    user, channel, key = setup_user_channel(admin)
    if action == 'ungrant':
        data = {'user_id': user, 'channel_id': channel}
    else:
        data = {'id': user if action == 'user_status' else channel, 'enabled': False}
    change(admin, action, data)
    assert call(admin, key).status_code == 401
    assert not admin[2].calls


def test_grant_and_enable_required_before_key(admin):
    user = change(admin, 'user_create', {'name': '用户'})['id']
    channel = change(admin, 'channel_create', {'name': '通道', 'model': 'test-model'})['id']
    data = {'user_id': user, 'channel_id': channel}
    assert admin[0].post('/admin/api/issue_key', headers=admin[3], json=data).status_code == 403
    change(admin, 'grant', data)
    assert admin[0].post('/admin/api/issue_key', headers=admin[3], json=data).status_code == 403


def test_cross_tenant_admin_and_data_access_denied(admin):
    state = admin[1]
    with state.connect() as db:
        db.execute("INSERT INTO users VALUES ('foreign','other','其他组织',1)")
        db.execute("INSERT INTO channels VALUES ('foreign-channel','other','其他通道',?,1)", (json.dumps(Config('openai/local').__dict__),))
    for action, data in [('user_status', {'id': 'foreign', 'enabled': False}),
                          ('channel_status', {'id': 'foreign-channel', 'enabled': True}),
                          ('grant', {'user_id': 'foreign', 'channel_id': 'default'})]:
        assert admin[0].post('/admin/api/' + action, headers=admin[3], json=data).status_code == 403
    snapshot = admin[0].get('/admin/api/snapshot').text
    assert 'foreign' not in snapshot


def test_session_csrf_origin_and_gateway_key_separation(admin):
    client, state, _, headers = admin
    assert client.post('/admin/api/user_create', json={'name': 'x'}).status_code == 403
    assert client.post('/admin/api/user_create', headers={'Origin': headers['Origin']}, json={'name': 'x'}).status_code == 403
    assert client.post('/admin/api/user_create', headers={**headers, 'Origin': 'https://evil.example'}, json={'name': 'x'}).status_code == 403
    key = state.issue('local-owner')
    change(admin, 'logout', {})
    assert client.get('/admin/api/snapshot', headers={'Authorization': 'Bearer ' + key}).status_code == 401


def test_login_rate_limit_and_expired_session(admin):
    client, state, _, headers = admin
    with state.connect() as db:
        db.execute('UPDATE sessions SET expires=0')
    assert client.get('/admin/api/snapshot').status_code == 401
    for _ in range(4):
        assert client.post('/admin/api/login', headers={'Origin': headers['Origin']}, json={'password': 'bad'}).status_code == 403
    assert client.post('/admin/api/login', headers={'Origin': headers['Origin']}, json={'password': 'bad'}).status_code == 429


def test_v1_migration_retains_keys_and_grants(tmp_path):
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE schema_version (version INTEGER PRIMARY KEY); INSERT INTO schema_version VALUES (1);
          CREATE TABLE keys (digest TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires REAL NOT NULL,revoked INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE events (request_id TEXT PRIMARY KEY,created REAL NOT NULL,user_id TEXT,revision TEXT NOT NULL,action TEXT NOT NULL,code TEXT NOT NULL,entity_count INTEGER NOT NULL DEFAULT 0);''')
        db.execute('INSERT INTO keys VALUES (?,?,?,0)', (State.digest('test-key'), 'old-user', time.time()+1000))
    state = State(path)
    state = State(path)  # Reopening an upgraded database must not reinsert version 1.
    state.configure_default(Config('openai/local').__dict__)
    assert state.authenticate('test-key') == 'old-user'
    state.manage('local','channel_status',{'id':'default','enabled':False})
    state.configure_default(Config('openai/changed').__dict__)
    assert state.authenticate('test-key') is None


def test_channel_disabled_while_upstream_runs_blocks_answer(admin):
    user, channel, key = setup_user_channel(admin)
    async def disable(messages):
        admin[1].manage('local', 'channel_status', {'id': channel, 'enabled': False})
        return '模型回答'
    admin[2].complete = disable
    response = call(admin, key)
    assert response.status_code == 401
    assert '模型回答' not in response.text
