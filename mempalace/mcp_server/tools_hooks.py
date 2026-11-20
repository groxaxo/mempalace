# Loaded into mempalace.mcp_server via exec (see __init__.py).
if __name__ != "mempalace.mcp_server":
    raise ImportError(f"{__name__} is an implementation fragment; import mempalace.mcp_server")


def tool_run_shared_hook(hook: str, harness: str, payload: dict) -> dict:
    """Retain a staged transcript in the existing HTTP writer process."""
    from .. import hooks_cli

    handlers = {
        "stop": hooks_cli.hook_stop,
        "precompact": hooks_cli.hook_precompact,
        "session-end": hooks_cli.hook_session_end,
    }
    if (
        not isinstance(hook, str)
        or hook not in handlers
        or harness not in ("codex", "claude-code")
        or not isinstance(payload, dict)
    ):
        return {"success": False, "error": "Invalid shared hook request"}
    transcript = payload.get("transcript_path")
    if transcript:
        if not isinstance(transcript, str):
            return {"success": False, "error": "Invalid staged transcript path"}
        path = hooks_cli._validate_transcript_path(transcript)
        if path is None or not path.is_file():
            return {"success": False, "error": "Staged transcript is missing or invalid"}

    class SharedHookWriteError(RuntimeError):
        pass

    def mine(**kwargs):
        result = tool_mine(**kwargs)
        if not result.get("success"):
            raise SharedHookWriteError(result.get("error", "Mine failed"))
        return result

    def diary(**kwargs):
        result = tool_diary_write(**kwargs)
        if not result.get("success"):
            raise SharedHookWriteError(result.get("error", "Diary write failed"))
        return result

    output = {}
    token = hooks_cli.SHARED_HOOK_WRITER.set(
        hooks_cli.SharedHookWriter(mine, diary, output, payload.get("source_harness", ""))
    )
    try:
        handlers[hook](payload, harness)
    except SharedHookWriteError as exc:
        return {"success": False, "error": str(exc)}
    finally:
        hooks_cli.SHARED_HOOK_WRITER.reset(token)
    return {"success": True, "hook_output": output}
