import sqlite3

import pytest
from fastapi.testclient import TestClient

from privacyguard.gateway.app import Config, create_app
from privacyguard.gateway.state import State
from privacyguard.rules import detect_with_rules


class Upstream:
    def __init__(self, answer='条款需要约定履行期限。'):
        self.calls = []
        self.answer = answer

    async def complete(self, messages):
        self.calls.append(messages)
        return self.answer


@pytest.fixture
def gateway(tmp_path):
    state = State(tmp_path / 'state.sqlite3')
    token = state.issue('owner')
    upstream = Upstream()
    app = create_app(state, Config('openai/local-test'), detector=detect_with_rules, adapter=upstream)
    with TestClient(app) as client:
        yield client, state, token, upstream


def post(gateway, content='请分析条款。', **extra):
    client, state, key, upstream = gateway
    return client.post('/v1/chat/completions', headers={'Authorization': 'Bearer ' + key},
                       json={'model': 'privacyguard-local', 'messages': [{'role': 'user', 'content': content}], **extra})


def test_redacts_before_send_and_does_not_log_values(gateway):
    raw = '邮箱 alice@example.com，电话 13800138000。'
    response = post(gateway, raw)
    assert response.status_code == 200, response.text
    assert response.json()['privacyguard']['entity_count'] >= 2
    sent = str(gateway[3].calls)
    assert 'alice@example.com' not in sent and '13800138000' not in sent
    assert '<EMAIL_001>' in sent
    assert b'alice@example.com' not in gateway[1].path.read_bytes()


@pytest.mark.parametrize('extra', [{'stream': True}, {'tools': []}, {'temperature': 0}, {'model': 'other'}])
def test_unsupported_or_model_denied_never_sends(gateway, extra):
    assert post(gateway, **extra).status_code in (400, 403)
    assert not gateway[3].calls


@pytest.mark.parametrize('content', ['-----BEGIN PRIVATE KEY-----', 'sk-' + 'x' * 30, '<PERSON_001>'])
def test_block_rules(gateway, content):
    assert post(gateway, content).status_code == 422
    assert not gateway[3].calls


def test_invalid_expired_revoked_keys(gateway):
    client, state, key, upstream = gateway
    for token in ['invalid', state.issue('expired', -1)]:
        assert client.get('/v1/models', headers={'Authorization': 'Bearer ' + token}).status_code == 401
    state.revoke_all()
    assert post(gateway).status_code == 401
    assert not upstream.calls


def test_models_only_authorized_alias(gateway):
    client, state, key, _ = gateway
    response = client.get('/v1/models', headers={'Authorization': 'Bearer ' + key})
    assert response.json()['data'][0]['id'] == 'privacyguard-local'


def test_detector_failure_no_upstream(tmp_path):
    state = State(tmp_path / 's.db')
    key = state.issue('owner')
    upstream = Upstream()
    def broken(_):
        raise RuntimeError('secret must not be returned')
    with TestClient(create_app(state, Config('openai/local'), broken, upstream)) as client:
        response = post((client, state, key, upstream))
    assert response.status_code == 503
    assert 'secret' not in response.text
    assert upstream.calls == []


def test_response_pii_blocked_without_exposure(gateway):
    gateway[3].answer = '新增联系地址 new@example.com'
    response = post(gateway)
    assert response.status_code == 422
    assert 'new@example.com' not in response.text


def test_same_and_different_entities_across_messages(gateway):
    client, state, key, upstream = gateway
    response = client.post('/v1/chat/completions', headers={'Authorization': 'Bearer ' + key}, json={
        'model': 'privacyguard-local', 'messages': [
            {'role': 'system', 'content': '联系人 a@example.com'},
            {'role': 'user', 'content': 'a@example.com 和 b@example.com'}]})
    assert response.status_code == 200, response.text
    assert '<EMAIL_001>' in upstream.calls[0][0]['content']
    assert '<EMAIL_001>' in upstream.calls[0][1]['content']
    assert '<EMAIL_002>' in upstream.calls[0][1]['content']


def test_audit_failure_prevents_send(gateway, monkeypatch):
    def broken(*args):
        raise sqlite3.OperationalError('disk unavailable')
    monkeypatch.setattr(gateway[1], 'admit', broken)
    assert post(gateway).status_code == 503
    assert not gateway[3].calls


def test_final_audit_failure_blocks_response(gateway, monkeypatch):
    original = gateway[1].finish
    def broken(rid, action, code, count=0):
        if code != 'pre_send':
            raise sqlite3.OperationalError()
        original(rid, action, code, count)
    monkeypatch.setattr(gateway[1], 'finish', broken)
    response = post(gateway)
    assert response.status_code == 503
    assert '条款' not in response.text


def test_revocation_during_upstream_blocks_return(gateway):
    client, state, key, upstream = gateway
    async def revoke(messages):
        state.revoke_all()
        return '回答'
    upstream.complete = revoke
    assert post(gateway).status_code == 401


def test_body_size_duplicate_and_multimodal(gateway):
    client, _, key, upstream = gateway
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    assert client.post('/v1/chat/completions', headers=headers, content=b'x' * 32769).status_code == 413
    assert client.post('/v1/chat/completions', headers=headers, content='{"model":"a","model":"b"}').status_code == 400
    assert post(gateway, [{'type': 'image_url', 'image_url': 'https://example.com'}]).status_code == 400
    assert not upstream.calls


def test_rate_limit(gateway):
    for _ in range(10):
        assert post(gateway).status_code == 200
    assert post(gateway).status_code == 429
    assert len(gateway[3].calls) == 10


@pytest.mark.parametrize('url', ['https://example.com/v1', 'http://localhost:8011/v1',
    'http://169.254.169.254/v1', 'http://127.0.0.1:8787/v1', 'http://127.0.0.1:8011/v1?x=1'])
def test_upstream_restrictions(url):
    with pytest.raises(ValueError):
        Config('openai/local', url).validate()


def test_browser_origin_denied(gateway):
    assert gateway[0].get('/health', headers={'Origin': 'https://untrusted.example'}).status_code == 403


def test_real_http_upstream_receives_only_scrubbed_messages(tmp_path):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    received = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            payload = json.dumps({'id': 'test', 'object': 'chat.completion', 'created': 1,
                'model': 'local-test', 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': '请明确履行期限。'}}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        state = State(tmp_path / 'state.db')
        key = state.issue('owner')
        config = Config('openai/local-test', f'http://127.0.0.1:{server.server_port}/v1')
        with TestClient(create_app(state, config, detector=detect_with_rules)) as client:
            fixture = (client, state, key, None)
            assert post(fixture, '-----BEGIN PRIVATE KEY-----').status_code == 422
            assert received == []
            response = post(fixture, '邮箱 alice@example.com，电话13800138000。')
            assert response.status_code == 200, response.text
            assert len(received) == 1
            serialized = json.dumps(received)
            assert 'alice@example.com' not in serialized
            assert '13800138000' not in serialized
            assert '<EMAIL_001>' in serialized
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
