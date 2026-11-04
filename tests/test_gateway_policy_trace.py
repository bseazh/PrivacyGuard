import json

import pytest
from fastapi.testclient import TestClient

from privacyguard.gateway.app import Config, create_app, Protection
from privacyguard.gateway.policies import EXAMPLES, catalog, detect_builtin, run_examples
from privacyguard.gateway.state import State


@pytest.mark.parametrize('name,kind,sample,expected', EXAMPLES)
def test_builtin_rule_positive_and_negative_examples(name, kind, sample, expected):
    result = next(x for x in run_examples()['results'] if x['name'] == name)
    assert result['passed'], result


def test_builtin_policy_is_executed_even_if_semantic_detector_finds_nothing():
    p = Protection(lambda _: [])
    output = p.protect('联系：+86 138-1001-2345')
    assert '<PHONE_001>' in output and '138' not in output
    assert 'builtin.phone' in p.matched_rules
    assert catalog()['version'] == 'legal-basic-2'


@pytest.fixture
def service(tmp_path):
    state = State(tmp_path / 'state.db')
    password = state.create_admin()
    key = state.issue('owner')
    class Adapter:
        answer = '请明确付款期限。'
        calls = 0
        async def complete(self, messages):
            self.calls += 1
            return self.answer
    adapter = Adapter()
    with TestClient(create_app(state, Config('openai/local'), lambda _: [], adapter)) as client:
        login = client.post('/admin/api/login', headers={'Origin': 'http://127.0.0.1:8787'}, json={'password': password})
        csrf = login.json()['csrf']
        yield state, key, adapter, client, csrf


def send(service, text):
    state, key, adapter, client, csrf = service
    return client.post('/v1/chat/completions', headers={'Authorization':'Bearer '+key}, json={
        'model':'privacyguard-local', 'messages':[{'role':'user','content':text}]})


def test_success_trace_structure_and_no_body_retention(service):
    state, key, adapter, client, _ = service
    response = send(service, '联系邮箱 alice@example.com')
    assert response.status_code == 200
    rid = response.json()['privacyguard']['request_id']
    trace = client.get('/admin/api/trace', params={'id':rid}).json()
    assert [s['stage'] for s in trace['spans']] == ['authorization','request.validation','request.policy',
        'upstream.authorization','upstream.call','response.policy','response.release']
    assert all(s['status']=='PASS' and s['duration_ms']>=0 for s in trace['spans'])
    assert trace['spans'][2]['details']['entity_counts']['EMAIL'] == 1
    serialized=json.dumps(trace,ensure_ascii=False)
    for forbidden in ('alice@example.com', key, adapter.answer):
        assert forbidden not in serialized
        assert forbidden.encode() not in state.path.read_bytes()


def test_block_trace_has_no_upstream_span(service):
    response = send(service, '-----BEGIN PRIVATE KEY-----')
    rid = response.json()['request_id']
    trace = service[3].get('/admin/api/trace',params={'id':rid}).json()
    assert trace['spans'][-1]['stage']=='request.policy'
    assert trace['spans'][-1]['status']=='BLOCK'
    assert trace['spans'][-1]['details']['matched_rules']==['credential.block']
    assert not any(s['stage']=='upstream.call' for s in trace['spans'])
    assert service[2].calls==0


def test_response_block_and_access_isolation(service):
    service[2].answer='new@example.com'
    response=send(service, '说明付款期限。')
    assert response.status_code==422
    rid=response.json()['request_id']
    trace=service[0].read_trace('local',rid)
    assert trace['spans'][-1]['stage']=='response.policy'
    assert trace['spans'][-1]['status']=='BLOCK'
    assert trace['spans'][-1]['details']['detected_entity_counts']=={'EMAIL':1}
    assert 'new@example.com' not in json.dumps(trace)
    with pytest.raises(PermissionError):
        service[0].read_trace('other',rid)
    service[3].cookies.clear()
    assert service[3].get('/admin/api/trace',params={'id':rid}).status_code==401


def test_trace_storage_failure_blocks_before_upstream(service,monkeypatch):
    def broken(*args):
        raise RuntimeError('do not log me')
    monkeypatch.setattr(service[0],'trace_start',broken)
    response=send(service,'正常请求')
    assert response.status_code==503 and service[2].calls==0
    assert 'do not log me' not in response.text


def test_policy_tests_endpoint_has_no_upstream_side_effect(service):
    client, csrf=service[3],service[4]
    response=client.post('/admin/api/policy-tests',headers={'Origin':'http://127.0.0.1:8787','X-CSRF-Token':csrf},json={})
    assert response.status_code==200 and response.json()['passed']
    assert service[2].calls==0
