#!/usr/bin/env python3
"""Local Prompt Forge chat client. Raw drafts never enter worker RPC/history."""
from __future__ import annotations
import argparse
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
import uuid

from preprocess import preprocess
from rpc import AppServer

ROOT = Path(__file__).resolve().parent
STATE = Path.home() / '.codex' / 'prompt-forge-client'


class Client:
    def __init__(self, state=STATE, rpc_factory=AppServer, preprocess_fn=preprocess):
        self.state = state
        self.state.mkdir(parents=True, exist_ok=True)
        self.workspace = self.state / 'workspace'
        self.workspace.mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.chats = {}
        self.loaded = set()
        self.preprocess = preprocess_fn
        self.account = 'Codex'
        self.connected = True
        self.models = []
        path = state / 'chats.json'
        if path.exists():
            self.chats = json.loads(path.read_text(encoding='utf-8'))
            for chat in self.chats.values():
                chat.update(status='idle', requests=[], turn_id=None, cancelled=False)
        self.rpc = rpc_factory(self.event)
        try:
            response = self.rpc.call('account/read', {'refreshToken': False})
            account = response.get('account') or {}
            self.account = account.get('email') or account.get('type') or 'Login required: run codex login once'
            self.models = self.rpc.call('model/list', {}) .get('data', [])
        except RuntimeError:
            self.account = 'Using existing Codex configuration'

    def save(self):
        # Only sent prompts, model output, IDs, and UI state. Never original drafts.
        data = copy.deepcopy(self.chats)
        for chat in data.values():
            chat['requests'] = []
        path = self.state / 'chats.tmp'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        path.replace(self.state / 'chats.json')

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({'chats': list(self.chats.values()), 'account': self.account,
                'connected': self.connected, 'models': self.models, 'default_cwd': str(self.workspace)})

    def new_chat(self, data):
        cwd = Path(data.get('cwd') or self.workspace).expanduser().resolve()
        if not cwd.is_dir():
            raise ValueError('Choose an existing project folder.')
        sandbox = data.get('sandbox', 'workspace-write')
        if sandbox not in {'read-only', 'workspace-write'}:
            raise ValueError('Unsupported workspace mode.')
        identifier = uuid.uuid4().hex
        chat = {'id': identifier, 'title': 'Chat ' + time.strftime('%b %d, %H:%M'),
                'cwd': str(cwd), 'sandbox': sandbox, 'model': data.get('model') or None,
                'thread_id': None, 'turn_id': None, 'status': 'idle', 'messages': [],
                'requests': [], 'human_turns': 0, 'cancelled': False, 'error': None, 'goal': None}
        with self.lock:
            self.chats[identifier] = chat
            self.save()
        return identifier

    def send(self, identifier, raw, request_id):
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError('Write a message first.')
        if len(raw.encode('utf-8')) > 2 * 1024 * 1024:
            raise ValueError('Message exceeds 2 MiB.')
        if not isinstance(request_id, str) or not request_id:
            raise ValueError('A submission ID is required.')
        with self.lock:
            chat = self.chats[identifier]
            if chat.get('request_id') == request_id:
                return  # Network retry must not start a second model turn.
            if chat['status'] not in {'idle', 'failed'}:
                raise ValueError('Wait for the current turn or press Stop.')
            chat.update(status='forging', error=None, cancelled=False, request_id=request_id)
        job = threading.Thread(target=self.submit, args=(identifier, raw), daemon=True)
        job.start()
        return job

    def submit(self, identifier, raw):
        chat = self.chats[identifier]
        dispatch_started = False
        try:
            text = raw.strip()
            if text.lower().startswith('/goal ') and text[6:].lstrip().startswith('-'):
                raise ValueError('Use /goal <condition>, /goal clear, /goal pause, /goal resume, or /goal status.')
            # Native client commands never reach the worker as ordinary instructions.
            goal_control = text.lower().removeprefix('/goal ').strip() if text.lower().startswith('/goal') else None
            if goal_control in {'clear', 'off', 'none', 'pause', 'resume', 'status', 'show', '/goal'}:
                if not chat['thread_id']:
                    raise ValueError('This chat has no goal yet.')
                self.ensure_thread(chat)
                if goal_control in {'clear', 'off', 'none'}:
                    self.rpc.call('thread/goal/clear', {'threadId': chat['thread_id']})
                    chat['goal'] = None
                elif goal_control in {'pause', 'resume'}:
                    self.rpc.call('thread/goal/set', {'threadId': chat['thread_id'], 'status': 'paused' if goal_control == 'pause' else 'active'})
                else:
                    chat['goal'] = self.rpc.call('thread/goal/get', {'threadId': chat['thread_id']})
                with self.lock:
                    chat.update(status='idle')
                    self.save()
                return
            if text.startswith('/') and not text.lower().startswith('/goal ') and '/' not in text.split()[0][1:]:
                raise ValueError('Supported command: /goal. Use New chat for a new conversation.')
            result = self.preprocess(raw, first=chat['human_turns'] == 0, model=chat['model'])
            del raw  # No draft is written to client history, worker RPC, or logs.
            if result['decision'] == 'error':
                raise ValueError(result['reason'])
            prompt = result['prompt']
            with self.lock:
                if chat['cancelled']:
                    chat['status'] = 'idle'
                    return
                chat['status'] = 'starting'
            self.ensure_thread(chat)
            with self.lock:
                if chat['cancelled']:
                    chat['status'] = 'idle'
                    return
                entry = {'id': uuid.uuid4().hex, 'role': 'user', 'text': prompt,
                    'decision': result['decision'], 'reason': result['reason'],
                    'sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest()}
                chat['messages'].append(entry)
                chat['human_turns'] += 1
                chat['status'] = 'working'
                self.save()
            if result.get('is_goal') or result['mode'] == 'goal':
                self.rpc.call('thread/goal/set', {'threadId': chat['thread_id'], 'objective': prompt})
                chat['goal'] = prompt
            dispatch_started = True
            response = self.rpc.call('turn/start', {'threadId': chat['thread_id'],
                'input': [{'type': 'text', 'text': prompt}]})
            with self.lock:
                if chat['status'] == 'working':
                    chat['turn_id'] = response['turn']['id']
                cancelled = chat['cancelled']
            if cancelled:
                self.rpc.call('turn/interrupt', {'threadId': chat['thread_id'], 'turnId': response['turn']['id']})
        except Exception as exc:
            with self.lock:
                # Unknown turn/start outcomes stay blocked to prevent accidental duplication.
                chat.update(status='uncertain' if dispatch_started else 'failed', error=str(exc))
                self.save()

    def ensure_thread(self, chat):
        if not chat['thread_id']:
            params = {'cwd': chat['cwd'], 'sandbox': chat['sandbox'], 'approvalPolicy': 'on-request',
                      'serviceName': 'prompt_forge_client'}
            if chat['model']:
                params['model'] = chat['model']
            result = self.rpc.call('thread/start', params)
            chat['thread_id'] = result['thread']['id']
            self.loaded.add(chat['thread_id'])
        elif chat['thread_id'] not in self.loaded:
            response = self.rpc.call('thread/resume', {'threadId': chat['thread_id'], 'cwd': chat['cwd'],
                'sandbox': chat['sandbox'], 'approvalPolicy': 'on-request'})
            self.hydrate(chat, response.get('thread', {}))
            self.loaded.add(chat['thread_id'])

    def hydrate(self, chat, thread):
        with self.lock:
            for turn in thread.get('turns', []):
                for data in turn.get('items', []):
                    if data.get('type') == 'agentMessage':
                        self.item(chat, data['id'], 'assistant')['text'] = data.get('text', '')

    def recover(self, identifier):
        chat = self.chats[identifier]
        if not chat['thread_id']:
            raise ValueError('No worker was created. Start a new chat.')
        self.ensure_thread(chat)
        response = self.rpc.call('thread/read', {'threadId': chat['thread_id'], 'includeTurns': True})
        thread = response['thread']
        self.hydrate(chat, thread)
        turns = thread.get('turns', [])
        active = next((t for t in reversed(turns) if t.get('status') == 'inProgress'), None)
        with self.lock:
            chat.update(status='working' if active else 'idle', turn_id=active['id'] if active else None, error=None)
            self.save()

    def event(self, event):
        method, params = event.get('method', ''), event.get('params', {})
        with self.lock:
            if method == 'client/disconnected':
                self.connected = False
                for chat in self.chats.values():
                    if chat['status'] in {'starting', 'working'}:
                        chat.update(status='uncertain', error='Codex disconnected. Restart the client before continuing.')
                return
            chat = next((c for c in self.chats.values() if c['thread_id'] == params.get('threadId')), None)
            if chat is None:
                if 'id' in event:
                    self.rpc.send({'id': event['id'], 'error': {'code': -32601, 'message': 'Request has no active chat'}})
                return
            if 'id' in event:
                chat['requests'].append({'id': event['id'], 'method': method, 'params': params})
            elif method == 'serverRequest/resolved':
                chat['requests'] = [r for r in chat['requests'] if r['id'] != params.get('requestId')]
            elif method == 'turn/started':
                chat.update(turn_id=params['turn']['id'], status='working')
            elif method == 'turn/completed':
                turn = params['turn']
                chat.update(turn_id=None, status='failed' if turn['status'] == 'failed' else 'idle', requests=[])
                if turn.get('error'):
                    chat['error'] = turn['error'].get('message', 'Turn failed')
                self.save()
            elif method == 'item/agentMessage/delta':
                item = self.item(chat, params['itemId'], 'assistant')
                item['text'] += params.get('delta', '')
            elif method in {'item/started', 'item/completed'}:
                data = params.get('item', {})
                kind = data.get('type')
                if kind == 'agentMessage':
                    item = self.item(chat, data['id'], 'assistant')
                    item['text'] = data.get('text', item['text'])
                elif kind in {'commandExecution', 'fileChange', 'mcpToolCall', 'webSearch', 'collabAgentToolCall'}:
                    item = self.item(chat, data['id'], 'tool')
                    item.update(text=data.get('command') or kind, detail=json.dumps(data, ensure_ascii=False),
                                status=data.get('status', 'running' if method.endswith('started') else 'done'))
            elif method == 'error':
                chat['error'] = params.get('error', {}).get('message', 'Codex reported an error')

    @staticmethod
    def item(chat, identifier, role):
        existing = next((m for m in chat['messages'] if m['id'] == identifier), None)
        if existing is None:
            existing = {'id': identifier, 'role': role, 'text': ''}
            chat['messages'].append(existing)
        return existing

    def stop(self, identifier):
        with self.lock:
            chat = self.chats[identifier]
            chat['cancelled'] = True
            turn, thread = chat['turn_id'], chat['thread_id']
        if turn:
            self.rpc.call('turn/interrupt', {'threadId': thread, 'turnId': turn})

    def answer(self, identifier, request_id, data):
        with self.lock:
            chat = self.chats[identifier]
            request = next((r for r in chat['requests'] if r['id'] == request_id), None)
            if not request:
                raise ValueError('This request is no longer pending.')
            method = request['method']
            if method in {'item/commandExecution/requestApproval', 'item/fileChange/requestApproval'}:
                decision = data.get('decision')
                if decision not in {'accept', 'decline', 'cancel'}:
                    raise ValueError('Invalid approval decision')
                result = {'decision': decision}
            elif method == 'item/permissions/requestApproval':
                result = {'permissions': request['params'].get('permissions', {}) if data.get('decision') == 'accept' else {}, 'scope': 'turn'}
            elif method == 'item/tool/requestUserInput':
                result = {'answers': data.get('answers', {})}
            elif method == 'mcpServer/elicitation/request':
                result = {'action': 'decline', 'content': None}
            else:
                self.rpc.send({'id': request_id, 'error': {'code': -32601, 'message': 'This client does not support this request'}})
                chat['requests'].remove(request)
                return
            self.rpc.reply(request_id, result)
            chat['requests'].remove(request)


class HTTP(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, client, port=0):
        super().__init__(('127.0.0.1', port), Handler)
        self.client = client
        self.token = secrets.token_urlsafe(32)
        self.origin = f'http://127.0.0.1:{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, value, mime='application/json'):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def allowed(self, auth=True):
        if self.headers.get('Host') != self.server.origin.removeprefix('http://') or self.headers.get('Origin', self.server.origin) != self.server.origin:
            self.reply(403, {'error': 'Invalid origin'})
            return False
        if auth and not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + self.server.token):
            self.reply(403, {'error': 'This session expired. Reopen Prompt Forge.'})
            return False
        return True

    def do_GET(self):
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if not self.allowed(auth=self.path not in assets):
            return
        if self.path in assets:
            name, mime = assets[self.path]
            self.reply(200, (ROOT / 'web' / name).read_bytes(), mime)
        elif self.path == '/api/state':
            self.reply(200, self.server.client.snapshot())
        else:
            self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if not self.allowed():
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if self.headers.get('Content-Type') != 'application/json' or not 0 < size <= 3 * 1024 * 1024:
                raise ValueError('Invalid request')
            data = json.loads(self.rfile.read(size))
            client = self.server.client
            if self.path == '/api/new':
                self.reply(200, {'id': client.new_chat(data)})
            elif self.path == '/api/send':
                client.send(data['id'], data['text'], data['request_id'])
                self.reply(202, {'ok': True})
            elif self.path == '/api/stop':
                client.stop(data['id'])
                self.reply(200, {'ok': True})
            elif self.path == '/api/answer':
                client.answer(data['id'], data['request_id'], data)
                self.reply(200, {'ok': True})
            elif self.path == '/api/recover':
                client.recover(data['id'])
                self.reply(200, {'ok': True})
            else:
                self.reply(404, {'error': 'Not found'})
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            self.reply(400, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--state', type=Path, default=STATE)
    parser.add_argument('--ready-file', type=Path)
    args = parser.parse_args()
    client = Client(args.state)
    http = HTTP(client, args.port)
    ready = {'url': http.origin + '/#' + http.token, 'pid': os.getpid()}
    if args.ready_file:
        args.ready_file.write_text(json.dumps(ready), encoding='utf-8')
    print(json.dumps(ready), flush=True)
    try:
        http.serve_forever()
    finally:
        client.rpc.close()
        http.server_close()


if __name__ == '__main__':
    main()
