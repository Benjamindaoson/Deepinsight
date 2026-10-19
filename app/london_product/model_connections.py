"""Browser-owned, encrypted provider connections. Never change scheduled-work credentials."""
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlsplit
import base64
import ctypes
import hashlib
import ipaddress
import json
import os
import secrets
import socket

import httpx
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from .store import now, uid

ACTIVE_CONNECTION = ContextVar('market_personal_connection', default=None)
ACTIVE_ATTACHMENTS = ContextVar('market_personal_attachments', default=())
COOKIE = 'deepinsight_owner'


def owner(request: Request, response=None):
    token = request.cookies.get(COOKIE, '')
    if len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
        if response is None: raise HTTPException(401, 'Open model settings first to establish a private browser session.')
        token = secrets.token_hex(32)
        response.set_cookie(COOKIE, token, httponly=True, samesite='strict', max_age=31536000)
    return hashlib.sha256(token.encode()).hexdigest()


def validate_endpoint(value):
    value = value.strip().rstrip('/')
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.port not in (None, 443):
        raise ValueError('A public HTTPS API base URL without credentials or query parameters is required.')
    if p.hostname.lower() in ('localhost', 'metadata.google.internal') or '.' not in p.hostname:
        raise ValueError('Private API destinations are not permitted.')
    try:
        if not ipaddress.ip_address(p.hostname).is_global: raise ValueError('Private API destinations are not permitted.')
    except ValueError as exc:
        if 'Private API' in str(exc): raise
    return value


def check_destination(value):
    p = urlsplit(validate_endpoint(value))
    # The local workstation's TUN uses RFC2544 fake DNS. Known provider hosts
    # are fixed HTTPS destinations; arbitrary custom hosts must resolve public.
    if p.hostname not in ('api.deepseek.com', 'toapis.cn', 'api.openai.com', 'generativelanguage.googleapis.com', 'api.anthropic.com'):
        addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError('Private API destinations are not permitted.')


class _Blob(ctypes.Structure):
    _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data, decrypt=False):
    buffer = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = _Blob()
    if decrypt:
        ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), 'DeepInsight personal connection', None, None, None, 1, ctypes.byref(target))
    if not ok: raise ValueError('Credential encryption is unavailable for this operating-system account.')
    try: return ctypes.string_at(target.data, target.size)
    finally: ctypes.windll.kernel32.LocalFree(target.data)


class Connections:
    def __init__(self, store): self.store = store

    def _crypt(self, value, decrypt=False):
        if os.name == 'nt':
            return _dpapi(base64.b64decode(value) if decrypt else value.encode(), decrypt).decode() if decrypt else base64.b64encode(_dpapi(value.encode())).decode()
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ValueError('Encrypted credential storage needs cryptography in this project environment on non-Windows systems. No key was saved.') from None
        path = self.store.root / '.connection-vault-key'
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as file: file.write(Fernet.generate_key())
        cipher = Fernet(path.read_bytes())
        return cipher.decrypt(value.encode()).decode() if decrypt else cipher.encrypt(value.encode()).decode()

    @staticmethod
    def public(row):
        return {k: row[k] for k in ('id', 'name', 'base_url', 'key_hint', 'models', 'created_at', 'last_checked_at', 'status') if k in row}

    def list(self, browser):
        return [self.public(r) for r in self.store.all('settings') if r.get('kind') == 'model_connection' and r.get('owner') == browser and not r.get('deleted')]

    def resolve(self, browser, identity):
        r = self.store.get('settings', identity)
        if not r or r.get('kind') != 'model_connection' or r.get('owner') != browser or r.get('deleted'): raise KeyError(identity)
        return dict(r, api_key=self._crypt(r['encrypted_key'], True))

    def save(self, browser, name, base_url, api_key):
        if not api_key.strip() or len(api_key) > 4096: raise ValueError('An API key is required.')
        row = self.store.put('settings', uid(), dict(kind='model_connection', owner=browser, name=name.strip()[:80] or 'Personal connection',
            base_url=validate_endpoint(base_url), encrypted_key=self._crypt(api_key.strip()), key_hint='••••' + api_key.strip()[-4:], models=[], status='saved_not_tested'))
        return self.public(row)

    def delete(self, browser, identity):
        self.resolve(browser, identity)
        self.store.update('settings', identity, dict(deleted=True, encrypted_key='', models=[]))

    async def discover(self, browser, identity):
        row = self.resolve(browser, identity)
        check_destination(row['base_url'])
        try:
            async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
                response = await client.get(row['base_url'] + '/models', headers={'Authorization': 'Bearer ' + row['api_key']})
            if response.status_code != 200:
                raise HTTPException(502, f'Provider model discovery failed (HTTP {response.status_code}). Check the endpoint, key or account quota.')
            payload = response.json()
            models = sorted({r['id'] for r in payload.get('data', []) if isinstance(r, dict) and isinstance(r.get('id'), str) and 0 < len(r['id']) <= 180})
            if not models: raise ValueError('The provider returned no model identifiers in an OpenAI-compatible model list.')
        except httpx.HTTPError:
            raise HTTPException(502, 'Provider connection timed out or could not be reached.') from None
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(502, 'The endpoint did not return an OpenAI-compatible model list.') from None
        updated = self.store.update('settings', identity, dict(models=models, status='models_discovered', last_checked_at=now()))
        return self.public(updated)

    def select(self, browser, identity, model, thinking):
        row = self.resolve(browser, identity)
        if model not in row.get('models', []): raise ValueError('Discover models and select an actual model from this connection first.')
        check_destination(row['base_url'])
        return dict(api_key=row['api_key'], base_url=row['base_url'], model=model, connection_id=identity,
                    personal=True, **model_options(row['base_url'], model, thinking))


def model_options(base_url, model, thinking='standard'):
    from agno.models.openai import OpenAIChat
    roles = dict(OpenAIChat.default_role_map, system='system')
    if thinking not in ('standard', 'deep'): raise ValueError('Unsupported thinking mode.')
    official = urlsplit(base_url).hostname == 'api.deepseek.com'
    if official and model in ('deepseek-flash', 'deepseek-v4-pro', 'deepseek-chat', 'deepseek-reasoner'):
        options = dict(extra_body={'thinking': {'type': 'enabled' if thinking == 'deep' else 'disabled'}}, role_map=roles)
        if thinking == 'deep': options['reasoning_effort'] = 'high'
        return options
    # The compatibility relay has not proven provider-specific thinking controls.
    if thinking != 'standard': raise ValueError('Thinking control has not been verified for this endpoint/model. Use Standard.')
    return dict(role_map=roles)


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=8, max_length=400)
    api_key: str = Field(min_length=1, max_length=4096, repr=False)


def register_connections(app, store):
    from fastapi import Response
    vault = Connections(store)

    @app.get('/api/market/model-connections')
    def connections(request: Request, response: Response):
        browser = owner(request, response)
        return dict(items=vault.list(browser), scope='This browser on this local server. Keys are encrypted on the server; scheduled tasks keep their separate connection.')

    @app.post('/api/market/model-connections')
    def save(data: ConnectionInput, request: Request):
        return vault.save(owner(request), data.name, data.base_url, data.api_key)

    @app.post('/api/market/model-connections/{identity}/discover')
    async def discover(identity: str, request: Request):
        return await vault.discover(owner(request), identity)

    @app.delete('/api/market/model-connections/{identity}')
    def delete(identity: str, request: Request):
        vault.delete(owner(request), identity)
        return dict(deleted=True)
