"""Fail-closed, non-streaming local gateway. No configurable remote upstream yet."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from privacyguard.adapters.litellm import LLMSettings, LiteLLMAdapter
from privacyguard.core import PrivacyGuard, UNCERTAIN_SEMANTIC_TYPES
from privacyguard.rules import merge_findings
from .state import State
from .policies import CREDENTIAL, VERSION, detect_builtin
from .trace import Trace

TOKEN = re.compile(r'<[A-Z_]+_[0-9]{3,}>')
MAX_BYTES = 32768


class Blocked(Exception):
    def __init__(self, code: str, status: int = 422):
        self.code, self.status = code, status


@dataclass(frozen=True)
class Config:
    upstream_model: str
    upstream_url: str = 'http://127.0.0.1:8011/v1'
    public_model: str = 'privacyguard-local'

    def validate(self):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', self.public_model):
            raise ValueError('Invalid public model alias')
        address = urlsplit(self.upstream_url)
        # Literal loopback only: no DNS/redirect/public/metadata endpoints.
        if (address.hostname != '127.0.0.1' or address.scheme != 'http'
                or address.path != '/v1' or not address.port or address.port == 8787
                or address.username or address.password or address.query or address.fragment):
            raise ValueError('Prototype upstream must be literal loopback /v1, not gateway port')
        LLMSettings(self.upstream_model, self.upstream_url, 'local-only').validate()

    @property
    def revision(self):
        return hashlib.sha256(json.dumps(self.__dict__, sort_keys=True).encode()).hexdigest()[:16] + ':' + VERSION


class Protection:
    def __init__(self, detector):
        self.detector = detector
        self.mapping = {}
        self.counters = {}
        self.count = 0
        self.hit_counts = {}
        self.matched_rules = set()
        self.last_counts = {}

    def findings(self, text):
        items = self.detector(text)
        builtins = detect_builtin(text)
        self.matched_rules.update('builtin.' + item.entity_type.lower() for item in builtins)
        items = items + builtins
        for item in items:
            if (not 0 <= item.start < item.end <= len(text)
                    or not re.fullmatch(r'[A-Z_]+', item.entity_type)
                    or not math.isfinite(item.score) or not 0 <= item.score <= 1):
                raise Blocked('detector_invalid', 503)
            if item.entity_type in UNCERTAIN_SEMANTIC_TYPES and item.score < .85:
                raise Blocked('review_required')
        merged = merge_findings(items)
        self.last_counts = {}
        for item in merged:
            self.last_counts[item.entity_type] = self.last_counts.get(item.entity_type, 0) + 1
        return merged

    def check_credentials(self, text):
        if CREDENTIAL.search(text):
            self.matched_rules.add('credential.block')
            raise Blocked('credential_blocked')

    def protect(self, text):
        self.check_credentials(text)
        pieces, cursor = [], 0
        for item in self.findings(text):
            key = (item.entity_type, text[item.start:item.end])
            if key not in self.mapping:
                self.counters[item.entity_type] = self.counters.get(item.entity_type, 0) + 1
                self.mapping[key] = f'<{item.entity_type}_{self.counters[item.entity_type]:03d}>'
            pieces.extend((text[cursor:item.start], self.mapping[key]))
            cursor = item.end
            self.count += 1
            self.hit_counts[item.entity_type] = self.hit_counts.get(item.entity_type, 0) + 1
        pieces.append(text[cursor:])
        result = ''.join(pieces)
        self.verify(result)
        return result

    def verify(self, text):
        self.check_credentials(text)
        registered = set(self.mapping.values())
        for token in TOKEN.findall(text):
            if token not in registered:
                raise Blocked('unknown_placeholder')
        masked = TOKEN.sub(lambda m: ' ' * len(m.group()), text)
        if masked.strip() and self.findings(masked):
            raise Blocked('residual_detected')


def parse_body(raw):
    def unique(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError('duplicate')
            output[key] = value
        return output
    try:
        body = json.loads(raw, object_pairs_hook=unique)
        if not isinstance(body, dict) or set(body) - {'model', 'messages', 'stream'}:
            raise ValueError()
        if body.get('stream', False) is not False:
            raise ValueError()
        if not isinstance(body.get('model'), str):
            raise ValueError()
        messages = body.get('messages')
        if not isinstance(messages, list) or not 1 <= len(messages) <= 16:
            raise ValueError()
        for message in messages:
            if (not isinstance(message, dict) or set(message) != {'role', 'content'}
                    or message['role'] not in ('system', 'user', 'assistant')
                    or not isinstance(message['content'], str) or not message['content'].strip()
                    or len(message['content']) > 8000):
                raise ValueError()
        return body
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise Blocked('unsupported_request', 400) from None


def create_app(state: State, config: Config, detector=None, adapter=None):
    config.validate()
    state.configure_default(config.__dict__)
    if detector is None:
        core = PrivacyGuard()
        core.redaction.timeout = 15
        core.presidio.timeout = 5
        detector = core.detect
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    from .admin import install_admin
    install_admin(app, state, config)
    busy = False

    def error(code, status, rid):
        return JSONResponse({'error': {'type': 'privacyguard_blocked', 'code': code,
                                       'message': 'Request stopped; use the code for diagnosis.'},
                             'request_id': rid}, status_code=status,
                            headers={'Cache-Control': 'no-store'})

    @app.middleware('http')
    async def local_boundary(request, call_next):
        # The prototype is local-only, including protection against browser cross-origin requests.
        origin = request.headers.get('origin')
        allowed_origin = origin == 'http://127.0.0.1:8787'
        if (origin and not allowed_origin) or request.headers.get('host') not in ('127.0.0.1:8787', 'testserver'):
            return error('local_client_required', 403, uuid.uuid4().hex)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    def authenticate(request):
        header = request.headers.get('authorization', '')
        if not header.startswith('Bearer ') or len(header) > 256:
            raise Blocked('invalid_key', 401)
        token = header[7:]
        context = state.authorize(token)
        if not context:
            raise Blocked('invalid_key', 401)
        return token, context

    @app.get('/health')
    async def health():
        return {'status': 'alive', 'mode': 'local-prototype', 'ready': 'not_probed'}

    @app.get('/v1/models')
    async def models(request: Request):
        rid = uuid.uuid4().hex
        try:
            _, context = authenticate(request)
            selected = Config(**json.loads(context['config']))
            selected.validate()
            return {'object': 'list', 'data': [{'id': selected.public_model, 'object': 'model', 'owned_by': 'privacyguard'}]}
        except Blocked as exc:
            return error(exc.code, exc.status, rid)
        except Exception:
            return error('state_unavailable', 503, rid)

    @app.post('/v1/chat/completions')
    async def chat(request: Request):
        nonlocal busy
        rid, admitted, acquired = uuid.uuid4().hex, False, False
        try:
            token, context = authenticate(request)
            selected = Config(**json.loads(context['config']))
            selected.validate()
            revision = context['channel_id'] + ':' + selected.revision
            if not state.admit(rid, context['user_id'], revision, context['channel_id']):
                raise Blocked('rate_limited', 429)
            admitted = True
            trace = Trace(state, rid)
            with trace.stage('authorization', {'channel_id': context['channel_id'], 'policy_version': VERSION}):
                if not state.authenticate(token):
                    raise Blocked('invalid_key', 401)
            if busy:
                raise Blocked('gateway_busy', 429)
            busy = acquired = True
            with trace.stage('request.validation') as meta:
                if request.headers.get('content-encoding') or request.headers.get('content-type', '').split(';')[0] != 'application/json':
                    raise Blocked('unsupported_request', 400)
                raw = bytearray()
                async with asyncio.timeout(10):
                    async for chunk in request.stream():
                        raw.extend(chunk)
                        if len(raw) > MAX_BYTES:
                            raise Blocked('request_too_large', 413)
                body = parse_body(raw)
                if body['model'] != selected.public_model:
                    raise Blocked('model_not_allowed', 403)
                meta.update(bytes=len(raw), messages=[{'role': m['role'], 'characters': len(m['content'])} for m in body['messages']], stream=False)
            deadline = time.monotonic() + 120
            def bounded_detector(text):
                if time.monotonic() > deadline:
                    raise Blocked('inspection_timeout', 503)
                findings = detector(text)
                if time.monotonic() > deadline:
                    raise Blocked('inspection_timeout', 503)
                return findings
            protection = Protection(bounded_detector)

            def prepare():
                return [{'role': m['role'], 'content': protection.protect(m['content'])} for m in body['messages']]

            # The worker is bounded to one request. On cancellation keep the slot until it exits.
            with trace.stage('request.policy') as meta:
                for message in body['messages']:
                    if TOKEN.search(message['content']):
                        raise Blocked('unregistered_placeholder')
                    if CREDENTIAL.search(message['content']):
                        meta.update(matched_rules=['credential.block'], action='BLOCK')
                        raise Blocked('credential_blocked')
                try:
                    safe_messages = await anyio.to_thread.run_sync(prepare)
                finally:
                    meta.update(entity_counts=protection.hit_counts, matched_rules=sorted(protection.matched_rules))
                meta.update(action='REDACT' if protection.count else 'ALLOW', recheck='passed',
                            output_messages=[{'role': m['role'], 'characters': len(m['content'])} for m in safe_messages])
            with trace.stage('upstream.authorization'):
                if not state.authenticate(token):
                    raise Blocked('invalid_key', 401)
                state.finish(rid, 'PENDING', 'pre_send', protection.count)
            selected_adapter = adapter or LiteLLMAdapter(LLMSettings(selected.upstream_model, selected.upstream_url, 'local-only'))
            with trace.stage('upstream.call', {'route': selected.upstream_url, 'model': selected.public_model,
                                               'upstream_model': selected.upstream_model.rsplit('/', 1)[-1],
                                               'attempt': 1, 'stream': False}) as meta:
                async with asyncio.timeout(95):
                    answer = await selected_adapter.complete(safe_messages)
                if not isinstance(answer, str) or not answer.strip() or len(answer) > 20000:
                    raise Blocked('invalid_response', 502)
                meta['response_characters'] = len(answer)
                # The production adapter supplies only validated finish status and numeric usage.
                metadata = getattr(selected_adapter, 'last_metadata', {})
                if metadata.get('finish_reason') == 'stop':
                    meta['finish_reason'] = 'stop'
                meta['usage'] = {k: metadata.get(k) for k in ('prompt_tokens','completion_tokens','total_tokens')
                                 if type(metadata.get(k)) is int and 0 <= metadata[k] <= 1_000_000_000}
            with trace.stage('response.policy', {'action_on_sensitive': 'BLOCK'}) as meta:
                protection.matched_rules.clear()
                protection.last_counts = {}
                try:
                    await anyio.to_thread.run_sync(protection.verify, answer)
                finally:
                    meta.update(matched_rules=sorted(protection.matched_rules), detected_entity_counts=protection.last_counts)
                meta['result'] = 'no_detected_residual'
            with trace.stage('response.release', {'object': 'chat.completion', 'role': 'assistant', 'content_retained': False}):
                if not state.authenticate(token):
                    raise Blocked('invalid_key', 401)
                state.finish(rid, 'REDACT' if protection.count else 'ALLOW', 'approved', protection.count)
            return JSONResponse({'id': 'chatcmpl-' + rid, 'object': 'chat.completion',
                'created': int(time.time()), 'model': selected.public_model,
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': answer}, 'finish_reason': 'stop'}],
                'privacyguard': {'status': 'approved', 'revision': revision,
                                 'entity_count': protection.count, 'request_id': rid}}, headers={'Cache-Control': 'no-store'})
        except Blocked as exc:
            code, status = exc.code, exc.status
        except Exception:
            code, status = 'dependency_failed', 503
        finally:
            if acquired:
                busy = False
        if admitted:
            try:
                state.finish(rid, 'BLOCK', code)
            except Exception:
                code, status = 'audit_unavailable', 503
        return error(code, status, rid)

    return app
