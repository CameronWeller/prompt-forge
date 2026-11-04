"""Documented Codex app-server JSONL transport, using the existing CLI login."""
import json
import os
import queue
import shutil
import subprocess
import threading


class AppServer:
    def __init__(self, on_event):
        binary = shutil.which('codex.exe' if os.name == 'nt' else 'codex')
        if not binary:
            raise RuntimeError('Codex CLI is not installed or is not on PATH.')
        env = os.environ.copy()
        env.pop('CODEX_THREAD_ID', None)
        self.process = subprocess.Popen([binary, 'app-server', '--listen', 'stdio://'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', bufsize=1, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.callback = on_event
        self.pending = {}
        self.lock = threading.RLock()
        self.counter = 0
        threading.Thread(target=self.read, daemon=True).start()
        self.call('initialize', {'clientInfo': {'name': 'prompt_forge_client',
                  'title': 'Prompt Forge', 'version': '0.1.0'},
                  'capabilities': {'experimentalApi': True}})
        self.send({'method': 'initialized', 'params': {}})

    def send(self, data):
        with self.lock:
            self.process.stdin.write(json.dumps(data, ensure_ascii=False) + '\n')
            self.process.stdin.flush()

    def call(self, method, params, timeout=60):
        with self.lock:
            self.counter += 1
            identifier = self.counter
            replies = self.pending[identifier] = queue.Queue()
        try:
            self.send({'id': identifier, 'method': method, 'params': params})
            message = replies.get(timeout=timeout)
            if 'error' in message:
                raise RuntimeError(message['error'].get('message', 'App-server request failed.'))
            return message.get('result', {})
        except queue.Empty:
            raise RuntimeError(f'{method} timed out. Do not resubmit until the chat status is checked.') from None
        finally:
            with self.lock:
                self.pending.pop(identifier, None)

    def read(self):
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if 'method' in message:
                    self.callback(message)
                else:
                    with self.lock:
                        target = self.pending.get(message.get('id'))
                    if target:
                        target.put(message)
        finally:
            with self.lock:
                for target in self.pending.values():
                    target.put({'error': {'message': 'Codex app-server disconnected.'}})
            self.callback({'method': 'client/disconnected', 'params': {}})

    def reply(self, identifier, result):
        self.send({'id': identifier, 'result': result})

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
