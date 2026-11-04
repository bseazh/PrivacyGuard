"""Local administration with separate password, sessions and CSRF protection."""
import asyncio
import hashlib
import hmac
import json
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from .policies import catalog, run_examples, VERSION

ASSETS = Path(__file__).with_name('web')
ORIGIN = 'http://127.0.0.1:8787'
COOKIE = 'pg_admin_session'


def csrf(token):
    return hashlib.sha256(('csrf:' + token).encode()).hexdigest()


def install_admin(app, state, default_config, policies):
    @app.get('/')
    async def root():
        return RedirectResponse('/admin')

    @app.get('/admin')
    async def index():
        return FileResponse(ASSETS / 'index.html')

    @app.get('/admin/assets/{name}')
    async def asset(name: str):
        if name not in ('admin.js', 'admin.css'):
            return JSONResponse({'error': 'not_found'}, status_code=404)
        return FileResponse(ASSETS / name)

    @app.api_route('/admin/api/{operation}', methods=['GET', 'POST'])
    async def api(operation: str, request: Request):
        try:
            token = request.cookies.get(COOKIE, '')
            if request.method == 'POST':
                if request.headers.get('origin') != ORIGIN:
                    return JSONResponse({'error': 'origin_required'}, status_code=403)
                if request.headers.get('content-type', '').split(';')[0] != 'application/json':
                    raise ValueError()
                raw = bytearray()
                async with asyncio.timeout(5):
                    async for chunk in request.stream():
                        raw.extend(chunk)
                        if len(raw) > 16384:
                            raise ValueError()
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError()
            else:
                data = {}
            if operation == 'login' and request.method == 'POST':
                session = state.login(data.get('password'))
                response = JSONResponse({'csrf': csrf(session)})
                response.set_cookie(COOKIE, session, httponly=True, samesite='strict', max_age=3600, path='/admin')
                return response
            tenant = state.admin_session(token)
            if not tenant:
                return JSONResponse({'error': 'login_required'}, status_code=401)
            if request.method == 'POST' and not hmac.compare_digest(request.headers.get('x-csrf-token', ''), csrf(token)):
                return JSONResponse({'error': 'csrf_required'}, status_code=403)
            if operation == 'session' and request.method == 'GET':
                return {'csrf': csrf(token), 'tenant': tenant}
            if operation == 'snapshot' and request.method == 'GET':
                return {**state.snapshot(tenant), 'upstream': default_config.__dict__, 'policy': VERSION}
            if operation == 'policies' and request.method == 'GET':
                return catalog()
            if operation == 'policy-workflow' and request.method == 'GET':
                return policies.snapshot(tenant)
            if operation in ('policy-save', 'policy-check', 'policy-publish', 'policy-activate') and request.method == 'POST':
                fields = {'policy-save': {'generation', 'content'}, 'policy-check': {'generation'},
                          'policy-publish': {'generation'}, 'policy-activate': {'channel', 'version', 'expected'}}
                if set(data) != fields[operation]:
                    raise ValueError()
                if operation == 'policy-save':
                    return policies.save(tenant, data['generation'], data['content'])
                if operation == 'policy-check':
                    return policies.test(tenant, data['generation'])
                if operation == 'policy-publish':
                    return policies.publish(tenant, data['generation'])
                if any(not isinstance(v, str) or len(v) > 100 for v in data.values()):
                    raise ValueError()
                return policies.activate(tenant, data['channel'], data['version'], data['expected'])
            if operation == 'policy-tests' and request.method == 'POST':
                if data:
                    raise ValueError()
                return run_examples()
            if operation == 'trace' and request.method == 'GET':
                request_id = request.query_params.get('id', '')
                import re
                if not re.fullmatch(r'[a-f0-9]{32}', request_id):
                    raise ValueError()
                return state.read_trace(tenant, request_id)
            if operation == 'logout' and request.method == 'POST':
                state.logout(token)
                response = JSONResponse({'ok': True})
                response.delete_cookie(COOKIE, path='/admin')
                return response
            if request.method != 'POST':
                return JSONResponse({'error': 'not_found'}, status_code=404)
            fields = {
                'user_create': {'name'}, 'user_status': {'id', 'enabled'},
                'channel_create': {'name', 'model'}, 'channel_status': {'id', 'enabled'},
                'grant': {'user_id', 'channel_id'}, 'ungrant': {'user_id', 'channel_id'},
                'issue_key': {'user_id', 'channel_id'}, 'revoke_key': {'id'},
            }
            if operation not in fields or set(data) != fields[operation]:
                raise ValueError()
            if 'name' in data and (not isinstance(data['name'], str) or not 1 <= len(data['name'].strip()) <= 64):
                raise ValueError()
            if 'enabled' in data and type(data['enabled']) is not bool:
                raise ValueError()
            for key in ('id', 'user_id', 'channel_id'):
                if key in data and (not isinstance(data[key], str) or not 1 <= len(data[key]) <= 80):
                    raise ValueError()
            if operation == 'channel_create':
                import re
                if not isinstance(data['model'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', data['model']):
                    raise ValueError()
                from .app import Config
                config = Config(default_config.upstream_model, default_config.upstream_url, data.pop('model'))
                config.validate()
                data['config'] = config.__dict__
            return state.manage(tenant, operation, data)
        except PermissionError as exc:
            code = str(exc)
            return JSONResponse({'error': code}, status_code=429 if code == 'login_limited' else 403)
        except (ValueError, TypeError, KeyError):
            return JSONResponse({'error': 'invalid_input'}, status_code=400)
        except Exception:
            return JSONResponse({'error': 'admin_unavailable'}, status_code=503)
