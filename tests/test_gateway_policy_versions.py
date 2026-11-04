import copy
import json

import pytest
from fastapi.testclient import TestClient

from privacyguard.gateway.app import Config, Protection, Blocked, create_app
from privacyguard.gateway.state import State
from privacyguard.gateway.policy_versions import PolicyVersions, DEFAULT, BASE, exercise
from privacyguard.models import Finding


@pytest.fixture
def system(tmp_path):
    state = State(tmp_path / 'state.db')
    password = state.create_admin()
    key = state.issue('owner')
    class Adapter:
        calls = 0
        answer = '请明确履行期限。'
        async def complete(self, messages):
            self.calls += 1
            return self.answer
    adapter = Adapter()
    with TestClient(create_app(state, Config('openai/local'), lambda _: [], adapter)) as client:
        login = client.post('/admin/api/login', headers={'Origin': 'http://127.0.0.1:8787'}, json={'password': password})
        headers = {'Origin': 'http://127.0.0.1:8787', 'X-CSRF-Token': login.json()['csrf']}
        yield state, PolicyVersions(state), client, headers, key, adapter


def post(system, operation, data):
    return system[2].post('/admin/api/' + operation, json=data, headers=system[3])


def call(system, text='alice@example.com'):
    return system[2].post('/v1/chat/completions', headers={'Authorization': 'Bearer ' + system[4]}, json={
        'model': 'privacyguard-local', 'messages': [{'role': 'user', 'content': text}]})


def publish(system, request='BLOCK', response='BLOCK'):
    store = system[1]
    content = copy.deepcopy(DEFAULT)
    content['request']['EMAIL'] = request
    content['response']['EMAIL'] = response
    draft = store.snapshot('local')['draft']
    saved = store.save('local', draft['generation'], content)
    assert store.test('local', saved['generation'])['passed']
    return store.publish('local', saved['generation'])['version']


def test_complete_admin_workflow_and_rollback_trace(system):
    version = publish(system)
    # Publishing and saving do not change traffic.
    first = call(system)
    assert first.status_code == 200
    assert first.json()['privacyguard']['revision'].endswith(BASE)
    activated = post(system, 'policy-activate', {'channel': 'default', 'version': version, 'expected': BASE})
    assert activated.status_code == 200
    blocked = call(system)
    assert blocked.status_code == 422
    trace = system[0].read_trace('local', blocked.json()['request_id'])
    assert trace['event']['revision'].endswith(version)
    assert trace['spans'][-1]['details']['action'] == 'BLOCK'
    assert trace['spans'][-1]['details']['policy_version'] == version
    assert not any(s['stage'] == 'upstream.call' for s in trace['spans'])
    assert system[5].calls == 1
    assert post(system, 'policy-activate', {'channel': 'default', 'version': BASE, 'expected': version}).status_code == 200
    assert call(system).status_code == 200
    snapshot = system[1].snapshot('local')
    assert len(snapshot['history']) == 2
    assert b'alice@example.com' not in system[0].path.read_bytes()


def test_no_publish_without_current_passing_test(system):
    assert post(system, 'policy-publish', {'generation': 0}).status_code == 403
    assert post(system, 'policy-check', {'generation': 0}).json()['passed']
    assert post(system, 'policy-save', {'generation': 0, 'content': DEFAULT}).status_code == 200
    for generation in (0, 1):
        assert post(system, 'policy-publish', {'generation': generation}).status_code == 403
    assert post(system, 'policy-save', {'generation': 0, 'content': DEFAULT}).status_code == 403


@pytest.mark.parametrize('value', [None, {}, {'request': {'default': 'ALLOW'}, 'response': {'default': 'BLOCK'}},
    {'request': {'default': 'REDACT', 'CREDENTIAL': 'REDACT'}, 'response': {'default': 'BLOCK'}},
    {'request': {'default': 'REDACT', 'regex': '(a+)+$'}, 'response': {'default': 'BLOCK'}}])
def test_invalid_or_unsafe_policy_rejected(system, value):
    assert post(system, 'policy-save', {'generation': 0, 'content': value}).status_code == 400


def test_failed_or_crashed_test_cannot_publish(system, monkeypatch):
    from privacyguard.gateway import policy_versions as pv
    assert system[1].test('local', 0)['passed']
    monkeypatch.setattr(pv, 'exercise', lambda _: {'passed': False, 'suite': pv.SUITE})
    assert not system[1].test('local', 0)['passed']
    with pytest.raises(PermissionError):
        system[1].publish('local', 0)
    def broken(_):
        raise RuntimeError('fixture crash')
    monkeypatch.setattr(pv, 'exercise', broken)
    with pytest.raises(RuntimeError):
        system[1].test('local', 0)
    with pytest.raises(PermissionError):
        system[1].publish('local', 0)


def test_edit_during_test_prevents_stale_result(system, monkeypatch):
    from privacyguard.gateway import policy_versions as pv
    def edit(policy):
        system[1].save('local', 0, DEFAULT)
        return exercise(policy)
    monkeypatch.setattr(pv, 'exercise', edit)
    with pytest.raises(PermissionError, match='draft_changed'):
        system[1].test('local', 0)
    assert system[1].snapshot('local')['draft']['test'] is None


def test_immutable_publish_restart_and_cas(system):
    version = publish(system)
    original = system[1].snapshot('local')['versions']
    assert system[1].publish('local', 1)['version'] == version
    system[1].activate('local', 'default', version, BASE)
    with pytest.raises(PermissionError, match='binding_changed'):
        system[1].activate('local', 'default', BASE, BASE)
    reopened = PolicyVersions(State(system[0].path))
    assert reopened.active('local', 'default')[0] == version
    assert reopened.snapshot('local')['versions'] == original


def test_tenant_and_channel_isolation_and_unknown_version(system):
    version = publish(system)
    with system[0].connect() as db:
        db.execute('INSERT INTO channels VALUES (?,?,?,?,1)', ('foreign', 'other', 'foreign', '{}'))
    for tenant, channel, chosen in [('local', 'foreign', version), ('other', 'foreign', version),
                                     ('local', 'default', 'pv-missing')]:
        with pytest.raises(PermissionError):
            system[1].activate(tenant, channel, chosen, BASE)
    assert system[1].snapshot('other')['versions'] == [system[1].snapshot('local')['versions'][0]]


def test_inflight_pins_response_policy_and_next_request_changes(system):
    version = publish(system, request='REDACT', response='REDACT')
    async def switch(messages):
        system[1].activate('local', 'default', version, BASE)
        return 'new@example.com'
    system[5].complete = switch
    blocked = call(system)
    assert blocked.status_code == 422  # Old response BLOCK, not the new REDACT.
    trace = system[0].read_trace('local', blocked.json()['request_id'])
    assert trace['spans'][-1]['details']['policy_version'] == BASE
    async def next_answer(messages):
        return 'new@example.com'
    system[5].complete = next_answer
    response = call(system)
    assert response.status_code == 200
    assert response.json()['choices'][0]['message']['content'] == '<EMAIL_002>'
    assert response.json()['privacyguard']['revision'].endswith(version)


def test_block_precedence_over_longer_redact_span():
    policy = copy.deepcopy(DEFAULT)
    policy['request']['PHONE'] = 'BLOCK'
    p = Protection(lambda t: [Finding('PERSON', 0, len(t), .99, 'fixture')], policy)
    with pytest.raises(Blocked) as exc:
        p.protect('联系人13800138000')
    assert exc.value.code == 'policy_blocked'


def test_response_redaction_repeat_and_mandatory_residual():
    policy = {'request': {'default': 'REDACT'}, 'response': {'default': 'REDACT'}}
    p = Protection(lambda _: [], policy)
    assert p.protect('alice@example.com') == '<EMAIL_001>'
    assert p.protect('<EMAIL_001> alice@example.com new@example.com', 'response') == '<EMAIL_001> <EMAIL_001> <EMAIL_002>'
    for text in ('<EMAIL_999>', '-----BEGIN PRIVATE KEY-----'):
        with pytest.raises(Blocked):
            p.protect(text, 'response')
    with pytest.raises(Blocked):
        p.verify('unredacted@example.com')


def test_policy_storage_failure_and_corrupt_version_fail_closed(system, monkeypatch):
    version = publish(system)
    system[1].activate('local', 'default', version, BASE)
    with system[0].connect() as db:
        db.execute("UPDATE policy_versions SET engine='old' WHERE id=?", (version,))
    assert call(system).status_code == 503
    assert system[5].calls == 0


def test_admin_workflow_requires_session_csrf_and_strict_fields(system):
    assert system[2].post('/admin/api/policy-check', json={'generation': 0}).status_code == 403
    assert post(system, 'policy-check', {'generation': True}).status_code == 403
    assert post(system, 'policy-check', {'generation': 0, 'sample': 'private'}).status_code == 400
    system[2].cookies.clear()
    assert system[2].get('/admin/api/policy-workflow').status_code == 401
