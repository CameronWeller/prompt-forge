//! Pre-model input transformation shared by desktop, SSH and relay clients.
//! Raw requests are never added to the worker history or returned in diagnostics.
use std::path::PathBuf;
use std::process::Stdio;
use std::time::Duration;

use codex_app_server_protocol::JSONRPCErrorError;
use codex_app_server_protocol::UserInput;
use codex_core::CodexThread;
use serde::Deserialize;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;

use crate::error_code::internal_error;

#[derive(Deserialize)]
struct Settings {
    command: Vec<String>,
}

#[derive(Deserialize)]
struct Reply {
    decision: String,
    prompt: Option<String>,
}

fn failure() -> JSONRPCErrorError {
    internal_error("Prompt Forge preprocessing failed. Nothing was submitted. Check the backend installation and retry.")
}

fn settings_path() -> Result<PathBuf, JSONRPCErrorError> {
    let executable = std::env::current_exe().map_err(|_| failure())?;
    Ok(executable.parent().ok_or_else(failure)?.join("prompt-forge-backend.json"))
}

async fn transform(text: &str, first: bool, goal: bool) -> Result<String, JSONRPCErrorError> {
    let settings: Settings = serde_json::from_slice(
        &tokio::fs::read(settings_path()?).await.map_err(|_| failure())?,
    ).map_err(|_| failure())?;
    let executable = settings.command.first().ok_or_else(failure)?;
    let mut command = Command::new(executable);
    command.args(&settings.command[1..]);
    if first { command.arg("--first"); }
    if goal { command.arg("--goal"); }
    command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null())
        .kill_on_drop(true).env_remove("CODEX_THREAD_ID");
    #[cfg(windows)]
    command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    let payload = serde_json::to_vec(&serde_json::json!({"text": text})).map_err(|_| failure())?;
    let output = tokio::time::timeout(Duration::from_secs(330), async {
        let mut child = command.spawn().map_err(|_| failure())?;
        let mut stdin = child.stdin.take().ok_or_else(failure)?;
        stdin.write_all(&payload).await.map_err(|_| failure())?;
        drop(stdin);
        child.wait_with_output().await.map_err(|_| failure())
    }).await.map_err(|_| failure())??;
    if !output.status.success() || output.stdout.len() > 8_000_000 {
        return Err(failure());
    }
    let reply: Reply = serde_json::from_slice(&output.stdout).map_err(|_| failure())?;
    if !matches!(reply.decision.as_str(), "skipped" | "pass" | "forged") {
        return Err(failure());
    }
    reply.prompt.ok_or_else(failure)
}

fn joined_text(input: &[UserInput]) -> String {
    input.iter().filter_map(|item| match item {
        UserInput::Text { text, .. } => Some(text.as_str()),
        _ => None,
    }).collect::<Vec<_>>().join("\n\n")
}

fn replace_text(input: &mut Vec<UserInput>, original: &str, replacement: String) {
    if replacement == original { return; }
    let position = input.iter().position(|item| matches!(item, UserInput::Text { .. })).unwrap_or(0);
    input.retain(|item| !matches!(item, UserInput::Text { .. }));
    input.insert(position.min(input.len()), UserInput::Text {
        text: replacement,
        // Raw byte ranges no longer refer to the transformed text. Attachments,
        // skills and explicit mentions remain separate, unchanged input items.
        text_elements: Vec::new(),
    });
}

pub(crate) async fn input(
    thread: &CodexThread,
    input: &mut Vec<UserInput>,
    trigger: Option<&str>,
) -> Result<(), JSONRPCErrorError> {
    // Internal continuations and tool results are not human drafts.
    if trigger.is_some_and(|trigger| trigger != "user") { return Ok(()); }
    let original = joined_text(input);
    if original.is_empty() { return Ok(()); }
    let first = thread.conversation_history_snapshot().await.user_message_revision() == 0;
    let replacement = transform(&original, first, false).await?;
    replace_text(input, &original, replacement);
    Ok(())
}

pub(crate) async fn goal(objective: &mut Option<String>) -> Result<(), JSONRPCErrorError> {
    if let Some(text) = objective {
        *text = transform(text, false, true).await?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn replacement_preserves_nontext_inputs_and_removes_raw_text() {
        let mut items = vec![
            UserInput::Text { text: "raw draft".into(), text_elements: Vec::new() },
            UserInput::Mention { name: "repo".into(), path: "repo://one".into() },
            UserInput::Text { text: "more raw".into(), text_elements: Vec::new() },
        ];
        let original = joined_text(&items);
        replace_text(&mut items, &original, "forged brief".into());
        assert_eq!(items.len(), 2);
        assert_eq!(joined_text(&items), "forged brief");
        assert!(matches!(&items[1], UserInput::Mention { path, .. } if path == "repo://one"));
    }

    #[test]
    fn pass_preserves_original_item_boundaries() {
        let mut items = vec![
            UserInput::Text { text: "a\r\n".into(), text_elements: Vec::new() },
            UserInput::Text { text: "b".into(), text_elements: Vec::new() },
        ];
        let before = items.clone();
        let text = joined_text(&items);
        replace_text(&mut items, &text, text.clone());
        assert_eq!(items, before);
    }
}
