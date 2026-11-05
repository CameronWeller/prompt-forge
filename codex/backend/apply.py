"""Apply the narrowly scoped backend patch to the exact tested upstream revision."""
import pathlib
import shutil
import subprocess
import sys
import re
import tomllib

REVISION = "4f093f2748667f3b0e6a07e3d4055121cbd3ce64"
root = pathlib.Path(sys.argv[1]).resolve()
actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
if actual != REVISION:
    raise SystemExit(f"Expected Codex 0.166.0-alpha.6 ({REVISION}), got {actual}")

# Upstream release tags stamp the workspace version but leave 0.0.0 for path
# packages in Cargo.lock. Update those exact local packages without resolving or
# changing any registry/git dependency. Cargo --locked checks the result in CI.
workspace = root / "codex-rs"
version = tomllib.loads((workspace / "Cargo.toml").read_text(encoding="utf-8"))["workspace"]["package"]["version"]
local_names = set()
for manifest in workspace.rglob("Cargo.toml"):
    package = tomllib.loads(manifest.read_text(encoding="utf-8")).get("package", {})
    if isinstance(package.get("version"), dict) and package["version"].get("workspace"):
        local_names.add(package["name"])
lock_path = workspace / "Cargo.lock"
lock = lock_path.read_text(encoding="utf-8")
parts = lock.split("[[package]]")
for index, part in enumerate(parts[1:], start=1):
    name = re.search(r'^name = "([^"]+)"', part, re.M)
    if name and name[1] in local_names and not re.search(r"^source =", part, re.M):
        parts[index] = re.sub(r'^version = "[^"]+"', f'version = "{version}"', part, count=1, flags=re.M)
lock_path.write_text("[[package]]".join(parts), encoding="utf-8", newline="\n")

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
edit(file, "        let objective = params.objective.as_deref().map(str::trim);",
     "        if params.origin != Some(ThreadGoalMutationOrigin::Automatic) {\n            crate::prompt_forge::goal(&mut params.objective).await?;\n        }\n        let objective = params.objective.as_deref().map(str::trim);")
file = base + "request_processors/thread_queue_processor.rs"
for kind in ("Add", "Update"):
    edit(file, f"        params: ThreadQueue{kind}Params,", f"        mut params: ThreadQueue{kind}Params,")
for method in ("add", "update"):
    path = root / file
    text = path.read_text(encoding="utf-8")
    start = text.index(f"    pub(crate) async fn {method}(\n")
    end = text.index("\n    pub(crate) async fn ", start + 1)
    section = text[start:end]
    anchor = "        ensure_direct_input_allowed(loaded_thread.as_deref(), &source)?;"
    if section.count(anchor) != 1:
        raise SystemExit("Queue preprocessing anchor changed: " + method)
    edit(file, section, section.replace(anchor, anchor + "\n        let forge_thread = loaded_thread.as_deref().ok_or_else(|| invalid_request(\"Open this chat before queuing a Prompt Forge message\"))?;\n        crate::prompt_forge::input(forge_thread, &mut params.input, None).await?;"))
shutil.copyfile(pathlib.Path(__file__).with_name("prompt_forge.rs"), root / base / "prompt_forge.rs")
print("Applied Prompt Forge at shared turn/start, turn/steer, queue add/update and thread/goal/set handlers.")
