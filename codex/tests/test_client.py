import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'client'))
from server import Client, HTTP


class FakeRPC:
    def __init__(self, event):
        self.event = event
        self.calls = []
        self.replies = []
    def call(self, method, params):
        self.calls.append((method, params))
        if method == 'thread/start':
            return {'thread': {'id': 'worker-123'}}
        if method == 'turn/start':
            return {'turn': {'id': 'turn-123'}}
        return {}
    def reply(self, identifier, result):
        self.replies.append((identifier, result))
    def send(self, data):
        self.replies.append(data)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.client = Client(self.root/'state', rpc_factory=FakeRPC,
            preprocess_fn=lambda raw, **_: {'decision': 'forged', 'reason': 'first prompt', 'mode': 'gated',
                'prompt': 'OUTCOME: refined brief\nMATERIAL café 雪  \r\n//prompt-forge\r\n'})
        self.identifier = self.client.new_chat({'cwd': str(self.root), 'sandbox': 'read-only'})
    def tearDown(self):
        self.temp.cleanup()
    def wait(self):
        self.job.join(timeout=3)
        self.assertFalse(self.job.is_alive())

    def test_raw_draft_never_reaches_worker_or_history(self):
        self.job = self.client.send(self.identifier, 'SECRET_UNFORGED_WORDING', 'unique-send')
        self.wait()
        calls = self.client.rpc.calls
        self.assertNotIn('SECRET_UNFORGED_WORDING', json.dumps(calls))
        turn = next(params for method, params in calls if method == 'turn/start')
        self.assertEqual(turn['input'][0]['text'], 'OUTCOME: refined brief\nMATERIAL café 雪  \r\n//prompt-forge\r\n')
        self.assertNotIn('SECRET_UNFORGED_WORDING', (self.root/'state/chats.json').read_text())
        self.client.send(self.identifier, 'SECRET_UNFORGED_WORDING', 'unique-send')
        self.assertEqual(sum(m=='turn/start' for m,p in calls),1)

    def test_failed_forge_does_not_start_worker(self):
        self.client.preprocess=lambda *a,**k: {'decision':'error','reason':'failed safely'}
        self.job = self.client.send(self.identifier, 'secret draft', 'one')
        self.wait()
        self.assertEqual(self.client.chats[self.identifier]['status'],'failed')
        self.assertFalse(any(m in {'thread/start','turn/start'} for m,p in self.client.rpc.calls))
        self.assertEqual(self.client.chats[self.identifier]['human_turns'],0)

    def test_stop_during_forge_prevents_dispatch(self):
        ready=threading.Event()
        original=self.client.preprocess
        def blocked(*a,**k):
            ready.wait(2)
            return original(*a,**k)
        self.client.preprocess=blocked
        self.job = self.client.send(self.identifier, 'draft', 'one')
        self.client.stop(self.identifier)
        ready.set()
        self.wait()
        self.assertFalse(any(m=='turn/start' for m,p in self.client.rpc.calls))

    def test_approval_requires_explicit_answer_and_stream_is_collected(self):
        chat=self.client.chats[self.identifier]
        chat['thread_id']='worker-123'
        self.client.event({'id':20,'method':'item/commandExecution/requestApproval','params':{'threadId':'worker-123','command':'test'}})
        self.assertEqual(self.client.rpc.replies,[])
        self.client.answer(self.identifier,20,{'decision':'decline'})
        self.assertEqual(self.client.rpc.replies,[(20,{'decision':'decline'})])
        self.client.event({'method':'item/agentMessage/delta','params':{'threadId':'worker-123','itemId':'a','delta':'Hello'}})
        self.client.event({'method':'item/completed','params':{'threadId':'worker-123','item':{'type':'agentMessage','id':'a','text':'Hello world'}}})
        self.client.event({'method':'turn/completed','params':{'threadId':'worker-123','turn':{'status':'completed'}}})
        self.assertEqual(chat['messages'][-1]['text'],'Hello world')
        self.assertEqual(chat['status'],'idle')

    def test_loopback_auth_and_origin_guards(self):
        server=HTTP(self.client)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            for headers,code in [({},403),({'Authorization':'Bearer '+server.token},200),({'Authorization':'Bearer '+server.token,'Origin':'https://untrusted.example'},403),({'Authorization':'Bearer '+server.token,'Host':'evil.example'},403)]:
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                conn.request('GET','/api/state',headers=headers)
                result=conn.getresponse()
                self.assertEqual(result.status,code)
                result.read();conn.close()
        finally:
            server.shutdown();server.server_close()


if __name__=='__main__':
    unittest.main()
