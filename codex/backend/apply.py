"""Apply the narrowly scoped backend patch to the exact tested upstream revision."""
import pathlib
import shutil
import subprocess
import sys

REVISION = "a956835d020762cb2b570053af06f643a11c0ecc"
root = pathlib.Path(sys.argv[1]).resolve()
actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
if actual != REVISION:
    raise SystemExit(f"Expected Codex 0.160.0 ({REVISION}), got {actual}")

def edit(relative, old, new):
    path = root / relative
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"Patch anchor changed or already applied: {relative}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

base = "codex-rs/app-server/src/"
edit(base + "lib.rs", "mod plugin_config_reload;", "mod plugin_config_reload;\nmod prompt_forge;")
for name in ("turn_start_inner", "turn_steer_inner"):
    file = base + "request_processors/turn_processor.rs"
    path = root / file
    text = path.read_text(encoding="utf-8")
    start = text.index("    async fn " + name + "(")
    end = text.index("    ) ->", start)
    signature = text[start:end]
    edit(file, signature, signature.replace("        params:", "        mut params:"))

# Placement follows the existing permission/provider/input-size checks and
# precedes conversion to core turn input, history persistence and model work.
edit(base + "request_processors/turn_processor.rs",
     "        Self::set_app_server_client_info(\n            thread.as_ref(),",
     "        if params.tool_output.is_none() {\n            crate::prompt_forge::input(thread.as_ref(), &mut params.input, params.turn_trigger.as_deref()).await?;\n            Self::validate_v2_input_limit(&params.input)?;\n        }\n        Self::set_app_server_client_info(\n            thread.as_ref(),")
edit(base + "request_processors/turn_processor.rs",
     "        let mapped_items: Vec<CoreInputItem> = params\n            .input",
     "        crate::prompt_forge::input(thread.as_ref(), &mut params.input, None).await?;\n        Self::validate_v2_input_limit(&params.input)?;\n        let mapped_items: Vec<CoreInputItem> = params\n            .input")
file = base + "request_processors/thread_goal_processor.rs"
edit(file,
     "    async fn thread_goal_set_inner(\n        &self,\n        request_id: ConnectionRequestId,\n        params: ThreadGoalSetParams,",
     "    async fn thread_goal_set_inner(\n        &self,\n        request_id: ConnectionRequestId,\n        mut params: ThreadGoalSetParams,")
edit(file, "        let objective = params.objective.as_deref();",
     "        crate::prompt_forge::goal(&mut params.objective).await?;\n        let objective = params.objective.as_deref();")
shutil.copyfile(pathlib.Path(__file__).with_name("prompt_forge.rs"), root / base / "prompt_forge.rs")
print("Applied Prompt Forge at shared turn/start, turn/steer and thread/goal/set handlers.")
