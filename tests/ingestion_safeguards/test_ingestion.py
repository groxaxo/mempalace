import json
import base64
import time

import pytest

from mempalace.normalize import UnparsedCodexTranscriptError, normalize, normalize_conversations


OPAQUE = "FORBIDDEN_OPAQUE_SENTINEL"


def codex_fragments():
    return "\n".join(
        json.dumps(event)
        for event in [
            {
                "type": "response_item",
                "payload": {"type": "reasoning", "encrypted_content": OPAQUE},
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "output": json.dumps({"rawOutput": {"base64": OPAQUE, "bytes": [1, 2, 3]}}),
                },
            },
        ]
    )


def test_headerless_codex_fragments_never_fall_back_to_raw_text(tmp_path):
    source = tmp_path / "fragment.jsonl"
    source.write_text(codex_fragments())
    with pytest.raises(UnparsedCodexTranscriptError):
        normalize_conversations(str(source))


@pytest.mark.parametrize(
    "payload",
    [
        codex_fragments() + "\n> a\n> b\n> c",
        '  {"type": "response_item", "payload": {"type": "reasoning",',
        json.dumps({"type": "response_item", "payload": {"type": "reasoning"}}, indent=2),
        "\n\t"
        + json.dumps({"type": "session_meta"})
        + "\n\n"
        + json.dumps(
            {"type": "event_msg", "payload": {"type": "user_message", "message": "Only one turn"}}
        ),
    ],
)
@pytest.mark.parametrize("normalizer", [normalize, normalize_conversations])
def test_incomplete_or_malformed_codex_cannot_use_prose_or_quote_fallback(
    tmp_path, payload, normalizer
):
    source = tmp_path / "session.txt"
    source.write_text(payload)
    with pytest.raises(UnparsedCodexTranscriptError):
        normalizer(str(source))


def canonical_codex():
    return (
        "\n\n \t\n".join(
            json.dumps(event)
            for event in [
                {"type": "session_meta", "payload": {"id": "synthetic"}},
                {
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "Remember 東京 uses JST."},
                },
                {
                    "type": "event_msg",
                    "payload": {"type": "agent_message", "message": "JST is UTC+9."},
                },
            ]
        )
        + "\n"
        + codex_fragments()
    )


def test_canonical_codex_keeps_useful_turns_and_skips_transport(tmp_path):
    source = tmp_path / "good.jsonl"
    source.write_text(canonical_codex())
    result = normalize_conversations(str(source))
    assert len(result) == 1
    assert "東京 uses JST" in result[0] and "JST is UTC+9" in result[0]
    assert OPAQUE not in result[0] and "response_item" not in result[0]


@pytest.mark.parametrize(
    "content",
    [
        "Discussion of encrypted_content and response_item is useful prose.",
        'Example:\n```json\n{"type":"response_item","payload":{"type":"reasoning"}}\n```',
        "> quote one\n> quote two\n> quote three\nDiscuss session_meta here.",
        '{"encrypted_content":"a documented config option","retries":3,"bytes":[1,2,3]}',
        'def response_item():\n    return {"type": "session_meta"}',
        "ID: " + "a" * 64 + "\n事实: 東京 is in Japan.\nHe kōrero tēnei.",
    ],
)
def test_legitimate_text_code_and_config_are_preserved(tmp_path, content):
    source = tmp_path / "facts.json"
    source.write_text(content)
    assert normalize_conversations(str(source)) == [content]


def test_json_encoded_supported_transcript_is_unwrapped_once(tmp_path):
    source = tmp_path / "encoded.txt"
    source.write_text(json.dumps(canonical_codex()))
    result = normalize_conversations(str(source))
    assert "東京 uses JST" in result[0] and "JST is UTC+9" in result[0]
    assert OPAQUE not in result[0] and "session_meta" not in result[0]


def test_json_encoded_fragments_still_fail_closed(tmp_path):
    source = tmp_path / "encoded.json"
    source.write_text(json.dumps(codex_fragments()))
    with pytest.raises(UnparsedCodexTranscriptError):
        normalize_conversations(str(source))


def test_excess_encoding_is_explicitly_unsupported(tmp_path):
    source = tmp_path / "too-encoded.json"
    source.write_text(json.dumps(json.dumps(canonical_codex())))
    with pytest.raises(ValueError, match="encoding_depth"):
        normalize_conversations(str(source))


def test_ordinary_json_string_remains_literal(tmp_path):
    source = tmp_path / "literal.json"
    text = json.dumps("Examples mention response_item and encrypted_content.")
    source.write_text(text)
    assert normalize_conversations(str(source)) == [text]


@pytest.mark.parametrize(
    "payload",
    [
        json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "thinking", "thinking": OPAQUE}]},
            }
        ),
        json.dumps({"messages": [{"role": "future-role", "content": OPAQUE}]}),
        '{"messages":[{"role":"assistant","content":',
        json.dumps({"history": [{"role": "user", "content": "Incomplete"}]}),
    ],
)
def test_other_recognized_incomplete_envelopes_are_nonindexable(tmp_path, payload):
    from mempalace.ingestion import NonIndexableContentError

    source = tmp_path / "unsupported.json"
    source.write_text(payload)
    with pytest.raises(NonIndexableContentError):
        normalize_conversations(str(source))


def test_nested_schema_example_in_config_is_not_a_transcript(tmp_path):
    text = json.dumps(
        {
            "example": {"type": "response_item", "payload": {"type": "reasoning"}},
            "messages": ["start", "stop"],
        }
    )
    source = tmp_path / "config.json"
    source.write_text(text)
    assert normalize_conversations(str(source)) == [text]


def claude_tool_transcript(output, tool="UnfamiliarTool"):
    return "\n".join(
        json.dumps(event)
        for event in [
            {"type": "user", "message": {"content": "Why did the synthetic build fail?"}},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "The build needs a missing dependency."},
                        {
                            "type": "tool_use",
                            "id": "call-1",
                            "name": tool,
                            "input": {"command": "make test"},
                        },
                        {"type": "thinking", "thinking": OPAQUE},
                        {"type": "image", "source": {"data": OPAQUE}},
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "tool_result", "tool_use_id": "call-1", "content": output},
                    ]
                },
            },
        ]
    )


def test_claude_unknown_tool_keeps_failure_evidence_without_transport(tmp_path):
    source = tmp_path / "claude.jsonl"
    source.write_text(
        claude_tool_transcript(
            json.dumps(
                {
                    "stderr": "ModuleNotFoundError: synthetic_dependency",
                    "exit_code": 1,
                    "rawOutput": {"base64": OPAQUE, "bytes": [91, 92, 93]},
                    "details": {"type": "reasoning", "encrypted_content": OPAQUE},
                }
            )
        )
    )
    text = normalize_conversations(str(source))[0]
    assert OPAQUE not in text and "91,92,93" not in text.replace(" ", "")
    assert "ModuleNotFoundError: synthetic_dependency" in text and '"exit_code":1' in text.replace(
        " ", ""
    )
    assert "omitted" in text and "missing dependency" in text


def test_typed_opaque_only_content_does_not_make_an_omission_memory():
    from mempalace.normalize import _extract_content, _format_tool_result

    raw = json.dumps({"type": "reasoning", "encrypted_content": OPAQUE})
    assert _extract_content(raw) == ""
    assert _format_tool_result(raw, "Unknown") == ""


def test_tool_config_json_and_code_remain_useful():
    from mempalace.normalize import _format_tool_result

    config = '{"bytes":[1,2,3],"encrypted_content":"documented option","retries":3}'
    assert config in _format_tool_result(config, "Unknown")
    code = 'const encrypted_content = "literal example";\nconsole.log("事实");'
    assert code in _format_tool_result(code, "Unknown")


def opaque_line():
    return base64.b64encode(bytes(range(256)) * 12).decode("ascii")


@pytest.mark.parametrize("tool", ["Bash", "Unknown", "Grep", "Glob"])
def test_long_single_line_tool_payload_is_omitted_with_useful_evidence(tool):
    from mempalace.normalize import _format_tool_result

    blob = opaque_line()
    result = _format_tool_result(
        "Build started\n\n \t" + blob + "  \n\nERROR: missing header", tool
    )
    assert blob[:100] not in result
    assert "Build started" in result and "ERROR: missing header" in result
    assert "ingestion omitted" in result
    assert _format_tool_result(blob, tool) == ""


@pytest.mark.parametrize("tool", ["Bash", "Unknown", "Grep"])
def test_tool_result_line_and_total_limits_are_utf8_byte_aware(tool):
    from mempalace.normalize import _format_tool_result

    result = _format_tool_result("\n".join("証拠 " + "界" * 1200 for _ in range(70)), tool)
    assert 0 < len(result.encode("utf-8")) <= 2048
    assert all(len(line.encode("utf-8")) <= 512 for line in result.splitlines())
    assert "omitted" in result and "\ufffd" not in result


def test_tool_selection_work_is_bounded_and_code_examples_survive():
    from mempalace.normalize import _format_tool_result

    started = time.monotonic()
    result = _format_tool_result("x" * 2_000_000, "Unknown")
    assert time.monotonic() - started < 5
    assert result == ""
    example = 'const fixture = "' + opaque_line() + '";'
    assert "const fixture" in _format_tool_result(example, "Bash")


def test_normalizer_refuses_opaque_only_sources_and_source_budget(tmp_path):
    from mempalace.ingestion import NonIndexableContentError, MAX_SOURCE_BYTES

    source = tmp_path / "opaque.txt"
    source.write_text(opaque_line())
    with pytest.raises(NonIndexableContentError, match="no_useful_content"):
        normalize_conversations(str(source))
    source.write_text("x" * (MAX_SOURCE_BYTES + 1))
    with pytest.raises(NonIndexableContentError, match="source_byte_budget"):
        normalize_conversations(str(source))


def test_nested_serialized_raw_buffer_and_buffer_only_results_are_not_text():
    from mempalace.normalize import _format_tool_result

    text = json.dumps(
        {
            "stderr": "Permission denied: synthetic path",
            "rawOutput": json.dumps({"base64": OPAQUE, "bytes": [3, 5, 7]}),
        }
    )
    result = _format_tool_result(text, "Unknown")
    assert "Permission denied" in result and OPAQUE not in result
    assert _format_tool_result('{"type":"Buffer","data":[1,2,3]}', "Unknown") == ""


def test_codex_canonical_message_strings_are_selected_before_flattening(tmp_path):
    source = tmp_path / "canonical-with-transport.jsonl"
    source.write_text(
        "\n".join(
            json.dumps(event)
            for event in [
                {"type": "session_meta"},
                {
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "Explain this error"},
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "agent_message",
                        "message": json.dumps(
                            {
                                "stderr": "ERROR: missing synthetic header",
                                "rawOutput": {"base64": OPAQUE},
                            }
                        ),
                    },
                },
            ]
        )
    )
    result = normalize_conversations(str(source))[0]
    assert "missing synthetic header" in result and OPAQUE not in result


def test_oversized_tool_block_list_is_omitted_before_flattening():
    from mempalace.normalize import _format_tool_result

    assert _format_tool_result([{"type": "text", "text": "x" * 2_000_000}], "Unknown") == ""


@pytest.mark.parametrize(
    "content",
    [
        "[" * 2000 + "0" + "]" * 2000,
        '{"type":"assistant","message":{"content":[{"type":[],"text":"malformed"}]}}',
    ],
)
def test_admission_reports_hostile_structure_without_crashing(content):
    from mempalace.ingestion import admit_text

    result = admit_text(content)
    assert result.decision in ("archive-only", "unsupported") and not result.indexable


def test_config_with_type_image_but_no_media_payload_is_preserved():
    from mempalace.ingestion import admit_text

    content = '{"type":"image","description":"image is a valid config choice"}'
    result = admit_text(content)
    assert result.decision == "keep" and result.text == content


def test_more_than_one_extra_encoding_layer_cannot_return_as_prose():
    from mempalace.ingestion import admit_text

    content = canonical_codex()
    for _ in range(4):
        content = json.dumps(content)
    result = admit_text(content)
    assert result.decision == "unsupported" and "encoding_depth" in result.reasons


def test_malformed_typed_transport_does_not_fall_back_to_tool_prose():
    from mempalace.normalize import _format_tool_result

    content = '{"rawOutput":{"base64":"' + OPAQUE
    assert _format_tool_result(content, "Unknown") == ""


def test_continue_tool_messages_get_the_same_selection_and_limits(tmp_path):
    source = tmp_path / "continue.json"
    source.write_text(
        json.dumps(
            {
                "history": [
                    {"role": "user", "content": "Why did it fail?"},
                    {"role": "assistant", "content": "The build failed."},
                    {
                        "role": "tool",
                        "content": json.dumps(
                            {"stderr": "ERROR: missing dependency", "rawOutput": {"base64": OPAQUE}}
                        ),
                    },
                ]
            }
        )
    )
    result = normalize_conversations(str(source))[0]
    assert "missing dependency" in result and OPAQUE not in result


def test_structure_limits_have_an_explicit_resource_outcome():
    from mempalace.ingestion import admit_text

    result = admit_text("[" * 2000 + "0" + "]" * 2000)
    assert result.decision == "unsupported"
    assert any("structure" in reason for reason in result.reasons)


def test_wrong_tool_identifier_type_is_reported_instead_of_crashing():
    from mempalace.ingestion import admit_text

    result = admit_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": ["invalid"], "input": {}}]},
            }
        )
    )
    assert result.decision == "unsupported" and "malformed_structure" in result.reasons


def test_quote_preamble_does_not_hide_unquoted_codex_envelopes():
    from mempalace.ingestion import admit_text

    result = admit_text("> injected one\n> injected two\n> injected three\n" + codex_fragments())
    assert not result.indexable and result.decision == "archive-only"


@pytest.mark.parametrize(
    "transport",
    [
        {"rawOutput": opaque_line()},
        {"rawOutput": [11, 22, 33, 44]},
        {"audio": {"data": OPAQUE, "format": "wav"}},
        {"image": {"bytes": [11, 22, 33, 44], "mime_type": "image/png"}},
    ],
)
def test_typed_raw_media_transports_keep_surrounding_tool_evidence(transport):
    from mempalace.normalize import _format_tool_result

    result = _format_tool_result(
        json.dumps({"stderr": "ERROR: synthetic transport failed", **transport}), "Unknown"
    )
    assert "synthetic transport failed" in result
    assert OPAQUE not in result and opaque_line()[:60] not in result
    assert "11,22,33,44" not in result.replace(" ", "")
    assert _format_tool_result(json.dumps(transport), "Unknown") == ""


def test_size_omission_provenance_does_not_leave_indexable_marker_fragments():
    from mempalace.ingestion import admit_text, indexing_text

    for width in range(220, 480, 7):
        evidence = "\n".join(["Evidence: " + "x" * 600] * 7 + ["Evidence: " + "x" * width])
        # Exercise the indexable channel, before chunking. The legacy display
        # formatter deliberately includes complete annotations at its exit.
        admission = admit_text(claude_tool_transcript(evidence, "Bash"), spellcheck=False)
        clean = indexing_text(admission.text).split("→ ", 1)[1]
        assert admission.omissions["tool_line_bytes"] > 0
        assert admission.omissions["tool_total_bytes"] > 0
        assert "ingestion" not in clean and "omitted" not in clean and "tool_" not in clean
        assert "[" not in clean and "]" not in clean


@pytest.mark.parametrize(
    "content",
    [
        '{"type":"session_metadata","sessionId":"synthetic"}',
        '{"type":"session","version":3,"id":"synthetic"}',
        '[{"chat_messages":[{"sender":"human","text":"Only one turn"}]}]',
    ],
)
def test_incomplete_other_supported_sessions_and_bundles_do_not_fall_back(tmp_path, content):
    from mempalace.ingestion import NonIndexableContentError

    source = tmp_path / "incomplete.jsonl"
    source.write_text(content)
    with pytest.raises(NonIndexableContentError):
        normalize_conversations(str(source))


@pytest.mark.parametrize(
    "events",
    [
        [
            {"type": "session_metadata"},
            {"type": "user", "content": [{"text": "東京 uses JST."}]},
            {"type": "gemini", "content": [{"text": "JST is UTC+9."}]},
        ],
        [
            {"type": "session", "version": 3},
            {"type": "message", "message": {"role": "user", "content": "東京 uses JST."}},
            {"type": "message", "message": {"role": "assistant", "content": "JST is UTC+9."}},
        ],
    ],
)
def test_other_canonical_supported_sessions_remain_readable(tmp_path, events):
    source = tmp_path / "supported.jsonl"
    source.write_text("\n".join(json.dumps(event) for event in events))
    result = normalize_conversations(str(source))[0]
    assert "東京 uses JST" in result and "JST is UTC+9" in result
