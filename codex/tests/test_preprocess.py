import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "client"))
from preprocess import classify, preprocess
import forge

BRIEF = "\n".join(s + ": a useful brief" for s in forge.SECTIONS)


class PreprocessingTests(unittest.TestCase):
    def test_override_does_not_trim_verbatim_material(self):
        material = '  café 雪\t  \r\n\r\n//prompt-forge\r\n'
        seen = []
        def model(raw, **kwargs):
            seen.append(raw)
            source, request = forge.split_material(raw)
            return forge.assemble(BRIEF, source, request)
        result = preprocess('forge:\r\n' + material + 'Explain the data.  \r\n', call=model)
        self.assertTrue(seen[0].startswith(material))
        self.assertTrue(result['prompt'].endswith(material))
        exact = '  preserve leading and trailing whitespace  \r\n'
        self.assertEqual(preprocess('raw:\r\n' + exact)['prompt'], exact)

    def test_original_thresholds_and_overrides(self):
        cases = [
            ("one two three", {"first": True}, "skipped", None),
            ("one two three four", {"first": True}, "eligible", "gated"),
            ("one two three four", {}, "skipped", None),
            ("word " * 49, {}, "skipped", None),
            ("word " * 50, {}, "eligible", "gated"),
            ("forge: improve", {}, "eligible", "forced"),
            ("raw: " + "word " * 50, {"first": True}, "skipped", None),
            ("/status check this now", {"first": True}, "skipped", None),
            ("/home/me/file is not working", {"first": True}, "eligible", "gated"),
            ("<bash-input>echo hello world now", {"first": True}, "skipped", None),
            ("forge: improve", {"source": "agent"}, "skipped", None),
            ("forge: " + "x" * 24001, {}, "skipped", None),
            ("//prompt-forge\nfix it", {}, "skipped", None),
            ("/goal ship", {}, "eligible", "goal"),
            ("/goal clear", {}, "skipped", None),
            ("/goal raw: ship", {}, "skipped", None),
        ]
        for text, kwargs, decision, mode in cases:
            with self.subTest(text=text[:40], kwargs=kwargs):
                actual = classify(text, **kwargs)
                self.assertEqual((actual['decision'], actual['mode']), (decision, mode))

    def test_skips_without_model_call_and_pass_keeps_original(self):
        with patch('preprocess.forge'):
            calls = []
            def model(raw, **kwargs):
                calls.append((raw, kwargs))
                return None
            raw = '  Tell me the capital of France.  \r\n'
            result = preprocess(raw, first=True, call=model)
            self.assertEqual(result['decision'], 'pass')
            self.assertEqual(result['prompt'], raw)
            self.assertEqual(calls[0][1]['mode'], 'gated')
            calls.clear()
            self.assertEqual(preprocess('raw: exact words', call=model)['prompt'], 'exact words')
            self.assertEqual(calls, [])

    def test_failed_forge_stops_after_one_retry(self):
        calls = []
        def failed(raw, **kwargs):
            calls.append(raw)
            raise forge.ForgeCallError('secret diagnostics')
        result = preprocess('forge: do the task', call=failed)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['decision'], 'error')
        self.assertNotIn('prompt', result)
        self.assertNotIn('secret diagnostics', json.dumps(result))

    def test_live_adapter_contract_without_network(self):
        material = ' exact café 雪\t  \r\n//prompt-forge\r\n'
        outputs = iter(['PASS', BRIEF, 'A verifiable completion condition.'])
        def model(command, **kwargs):
            payload = json.loads(kwargs['input'])
            self.assertEqual(payload['request'], 'interpret my task')
            self.assertNotIn('café', kwargs['input'].decode())
            instructions = next(x for x in command if x.startswith('model_instructions_file='))
            method = Path(json.loads(instructions.split('=', 1)[1])).read_text(encoding='utf-8')
            self.assertIn('working agent has NOT received', method)
            output = Path(command[command.index('--output-last-message') + 1])
            output.write_bytes(next(outputs).encode())
            return subprocess.CompletedProcess(command, 0, b'', b'')
        with patch.object(forge, 'codex_binary', return_value='codex'), patch.object(forge.subprocess, 'run', side_effect=model):
            self.assertIsNone(forge.forge(material + 'interpret my task', mode='gated'))
            self.assertTrue(forge.forge(material + 'interpret my task', mode='forced').endswith(material))
            self.assertTrue(forge.forge(material + 'interpret my task', mode='goal').endswith(material))


if __name__ == '__main__':
    unittest.main()
