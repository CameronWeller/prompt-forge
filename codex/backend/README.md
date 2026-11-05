# Native desktop backend

This experimental port changes the open-source Codex backend used by the existing
desktop app. It does not add an interpretation skill or require a separate chat UI.
The current build targets the desktop's Codex `0.166.0-alpha.6` source revision.

The shared app-server handlers run the isolated Forge process before converting
human text into working-agent input. This covers ordinary sends, steering,
edited messages, notification replies, queue additions/edits and human goals.
Desktop, SSH and remote-control transports reach these same handlers.
Nonhuman continuations and tool results retain their original behavior.

The existing gate applies: first message of at least four words, later messages
of at least 50 words, goals, and explicit `forge:` overrides. The semantic gate
can return PASS for a simple, clear request. `raw:` explicitly bypasses forging.
Eligible forge failures stop submission. There is no automatic raw fallback.

## Material boundary

Type normally in the app. Put exact source material above the marker and the task
below it:

```text
Exact logs, code, or other source material
//prompt-forge
Explain the failure and propose a fix with a way to verify it.
```

Everything through the marker line is excluded from the isolated model call and
appended verbatim after the resulting brief. Preservation applies to the string
the app submits; an editor or paste operation may already have normalized newlines.
The marker alone does not force a brief. To force one, put `forge:` on its own line
before the material. `//PROMPT FORGE:` is also accepted.

## Build and verification

The Windows and Linux GitHub workflows fetch the pinned OpenAI source, apply
`apply.py`, build the native executable, and run the Rust input-boundary tests.
The release tag's local workspace versions are repaired in `Cargo.lock` without
changing registry or git dependency pins; compilation uses `--locked`.

`install.py stage` (Windows) and `install_linux.py stage` copy the executable,
matching helper binaries, and isolated processor into a versioned per-user folder.
`smoke.py` performs a real forged turn and checks the worker's stored input,
Unicode/CRLF material preservation, and failure blocking. Activation requires
the smoke proof to match the executable's hash. Restart the desktop app to apply
the backend selection. Both installers retain the previous selection for restore.
`verify_tools.py` separately checks that a worker can read a fresh test file with
its normal tools under read-only permissions.

The forger uses a separate, pinned upstream executable. It receives no worker
history or project instructions and has tools, hooks, plugins, memories and both
multi-agent features disabled. Native app permissions continue to govern the worker.

## Multiple devices

Installing on two hosts protects new submissions on each; it does not merge their
histories. Shared chats require both apps to connect to the same host and runtime.
Use SSH over a private network such as ZeroTier for desktop access. Keep the host
online. Account skill uploads alone do not install this backend or intercept
cloud-hosted conversations.

After Linux staging and smoke verification, `setup_shared_host.py` creates a
per-user service and `codex-forge` SSH command. `install_linux.py activate --shared`
selects its private socket bridge for the Linux desktop. Windows activation selects
the same bare command name: locally it runs the Windows backend, while the desktop's
SSH connection resolves it on the Linux host. Select that host for shared chats.
On Windows, `codex-forge.exe` is the verified native executable itself, next to
its helpers and settings; its directory is added to the user's PATH. No extra
locally compiled launcher is required.
For a Windows update while the app is running, pass the same `--revision` commit
hash to `install.py stage`, `activate`, and `restore`. This keeps the previous
executable available for rollback while the current app finishes its work.
`verify_shared.py` checks that two SSH clients receive the same live completion and
history. Existing chats on separate hosts are not automatically merged.

The private Unix endpoint speaks WebSocket. An SSH desktop runs `app-server proxy`,
which the launcher points at the shared socket. Local JSONL clients use
`socket_bridge.py` to reach that same endpoint. The desktop's one-shot policy
check runs through the native executable. If small SSH commands work
but larger responses stall over ZeroTier, check the tunnel MTU before diagnosing
the app-server; a smaller interface MTU can resolve packet-size black holes.

`install.py restore` and `install_linux.py restore` restore the previous desktop
selection. The Linux shared service is separately stopped with
`systemctl --user disable --now prompt-forge-app-server.service`; stop it only after
connected work has finished. The installers do not stop existing desktop sessions.
Phone relay access is not enabled by this private desktop setup.

The patch currently covers typed task submission. Realtime voice and arbitrary
external history injection are not preprocessing entry points. Existing history
may contain prompts submitted before installation. A desktop/backend upgrade
requires compatibility verification and, when necessary, a new native build.
