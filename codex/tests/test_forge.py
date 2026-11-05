import argparse
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "prompt-forge/scripts/forge.py"
spec = importlib.util.spec_from_file_location("forge", SCRIPT)
forge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forge)
BRIEF = "\n".join(s + ": an appropriate brief" for s in forge.SECTIONS)


class ForgeTests(unittest.TestCase):
    def test_material_roundtrip_all_markers(self):
        for marker in ("//prompt-forge", "//PROMPT FORGE:", "  //Prompt-Forge: raw data ends here"):
            for newline in ("\n", "\r\n"):
                material = '\ufeff café 雪\t {"x": 2}  ' + newline + marker + newline
                kept, request = forge.split_material(material + "Do the task")
                self.assertEqual(kept.encode(), material.encode())
                self.assertEqual(request, "Do the task")
                result = forge.assemble(BRIEF, kept, request)
                self.assertTrue(result.encode().endswith(material.encode()))

    def test_marker_must_be_a_comment_line(self):
        for raw in ("Explain //prompt-forge please", "//prompt-forgery\nDo work"):
            self.assertEqual(forge.split_material(raw), ("", raw))

    def test_exact_details_recovered(self):
        request = 'Fix `widget.tsx` at C:\\work\\widget.tsx, preserve "literal value", issue #123 and https://example.com/a'
        brief = forge.assemble(BRIEF, "", request)
        for token in forge.anchors(request):
            self.assertIn(token, brief)

    def test_incomplete_brief_rejected(self):
        with self.assertRaises(forge.ForgeError):
            forge.assemble("OUTCOME: inadequate", "", "task")

    def test_strict_raw_prefix_rejected(self):
        with self.assertRaises(forge.ForgeError), patch.object(forge.subprocess, "run") as run:
            forge.forge("raw: secret original")
        run.assert_not_called()

    def test_empty_task_and_oversize_stop(self):
        for raw in (" ", "data\n//prompt-forge\n", "x" * 24001):
            with self.assertRaises(forge.ForgeError):
                forge.forge(raw)

    def test_isolated_call_excludes_raw_material_and_attaches_it_after(self):
        material = "RAW MATERIAL SENTINEL\r\n//prompt-forge\r\n"
        def model(command, **kwargs):
            data = json.loads(kwargs["input"])
            self.assertEqual(data, {"request": "private task wording", "has_verbatim_material": True})
            self.assertNotIn("RAW MATERIAL SENTINEL", str(command) + kwargs["input"].decode())
            self.assertIn("--ephemeral", command)
            self.assertIn("--ignore-user-config", command)
            self.assertIn("read-only", command)
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_bytes(BRIEF.encode())
            return subprocess.CompletedProcess(command, 0, b'', b'')
        with patch.object(forge, "codex_binary", return_value="codex"), patch.object(forge.subprocess, "run", side_effect=model):
            result = forge.forge(material + "private task wording")
        self.assertTrue(result.endswith(material))
        self.assertNotIn("private task wording", result)

    def test_model_failure_does_not_submit(self):
        with patch.object(forge.sys, "stdin", type("Input", (), {"buffer": io.BytesIO(b"secret")})()), patch.object(forge, "forge", side_effect=forge.ForgeError("failed")), patch.object(forge, "submit") as submit:
            self.assertEqual(forge.main(["local"]), 1)
            submit.assert_not_called()

    def test_timeout_fails_closed(self):
        with patch.object(forge, "codex_binary", return_value="codex"), patch.object(forge.subprocess, "run", side_effect=subprocess.TimeoutExpired("codex", 1)):
            with self.assertRaisesRegex(forge.ForgeError, "timed out"):
                forge.forge("private task")

    def test_local_and_cloud_receive_only_finished_brief(self):
        for target in ("local", "cloud"):
            args = argparse.Namespace(target=target, cwd=str(SCRIPT.parent), env="env-test", branch="main", ephemeral=False, sandbox=None)
            with patch.object(forge, "codex_binary", return_value="codex"), patch.object(forge.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertEqual(forge.submit(BRIEF, args), 0)
                command = run.call_args.args[0]
                if target == "local":
                    self.assertEqual(run.call_args.kwargs["input"], BRIEF.encode())
                    self.assertNotIn(BRIEF, command)
                else:
                    self.assertEqual(command[-2:], ["--", BRIEF])


if __name__ == "__main__":
    unittest.main()
