"""Deterministic ingestion admission helpers. No storage, models, or network."""

import ast
import json
import re
import unicodedata
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


_omissions = ContextVar("ingestion_omissions", default=None)
_spellcheck = ContextVar("ingestion_spellcheck", default=True)


def spellcheck_enabled() -> bool:
    return _spellcheck.get()


def note_omission(reason: str, count: int = 1) -> None:
    """Record fixed reason codes/counts, never raw keys or payload values."""
    report = _omissions.get()
    if report is not None:
        report[reason] = report.get(reason, 0) + count


@contextmanager
def omission_report():
    """Share metadata through formatting; annotations are rendered only at exits."""
    report = _omissions.get()
    standalone = report is None
    token = _omissions.set({}) if standalone else None
    try:
        yield _omissions.get(), standalone
    finally:
        if token is not None:
            _omissions.reset(token)


def annotate_omissions(text: str, omissions: dict, *, tool: bool = False) -> str:
    """Legacy display output only. Admission and writers use selected text.

    Render after joins and byte cuts so annotations cannot be split into
    indexable fragments. Never infer provenance from a source string's syntax.
    """
    if not text.strip() or not omissions:
        return text

    def suffix():
        return (" " if "\n" not in text else "\n") + "\n".join(
            f"[ingestion omitted: {reason}"
            + ("" if reason in ("tool_line_bytes", "tool_total_bytes") else f"; count={count}")
            + "]"
            for reason, count in sorted(omissions.items())
        )

    annotation = suffix()
    if tool:
        limit = TOOL_TOTAL_BYTES if "\n" in text else TOOL_LINE_BYTES
        if len((text + annotation).encode("utf-8", errors="replace")) > limit:
            omissions = dict(omissions)
            reason = "tool_total_bytes" if "\n" in text else "tool_line_bytes"
            omissions.setdefault(reason, 1)
            annotation = suffix()
            text = _utf8_ends(
                text, limit - len(annotation.encode("utf-8")), "\n" if "\n" in text else " "
            )
    return text + annotation


_OPAQUE_TYPES = {
    "reasoning",
    "thinking",
    "redacted_thinking",
    "image",
    "image_url",
    "input_image",
    "output_image",
    "audio",
    "input_audio",
    "output_audio",
}
_BUFFER_KEYS = {"base64", "bytes", "buffer", "data", "b64_json", "encrypted_content"}
_TRANSPORT_FIELDS = {
    "rawOutput",
    "raw_buffer",
    "rawBuffer",
    "inlineData",
    "inline_data",
    "image",
    "audio",
    "video",
    "image_url",
    "input_audio",
}
_TRANSPORT_METADATA = {"type", "encoding", "format", "mime_type", "mimeType", "size", "length"}
MAX_TOOL_INPUT_BYTES = 256 * 1024
TOOL_LINE_BYTES = 512
TOOL_TOTAL_BYTES = 2048
_OPAQUE_LINE = re.compile(r"[A-Za-z0-9+/]{2048,}={0,2}\Z")
_TRANSPORT_PREFIX = re.compile(
    r'"(?:rawOutput|raw_buffer|rawBuffer|inlineData|inline_data)"\s*:'
    r'|"type"\s*:\s*"(?:reasoning|thinking|Buffer|input_audio|input_image)"'
)
# Quote/comment starts consume one whole lexeme, including an incomplete EOF
# tail. Disjoint body alternatives and an EOF match prevent suffix retries
# when closing delimiters are missing, in both tokenization consumers.
_LITERAL_TOKENS = re.compile(
    r'(?i:br|rb|r|u|b)?(?:"""(?:[^"\\]+|\\.|"(?!""))*(?:"""|\\?\Z)'
    r"|'''(?:[^'\\]+|\\.|'(?!''))*(?:'''|\\?\Z)"
    r'|"(?:[^"\\]+|\\.)*(?:"|\\?\Z)|\'(?:[^\'\\]+|\\.)*(?:\'|\\?\Z))'
    r"|//[^\r\n]*|/\*(?:[^*]+|\*(?!/))*(?:\*/|\Z)|\#[^\r\n]*|\s+"
    r"|[A-Za-z_][A-Za-z_0-9]*"
    r"|[-+]?(?:0[xX][\da-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+"
    r"|(?:\d[\d_]*(?:\.[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?[\d_]+)?[jJ]?)|.",
    re.DOTALL,
)
_RAW_OPAQUE_PREFIX = re.compile(
    r'"(?:rawOutput|raw_buffer|rawBuffer|inlineData|inline_data)"\s*:\s*"([A-Za-z0-9+/]{2048,})'
)
MAX_STRUCTURE_TOKENS = 16384
MAX_STRUCTURE_DEPTH = 32
_IDENTIFIER_ESCAPE = re.compile(r"\\u(?:[\da-fA-F]{4}|\{[\da-fA-F]{1,6}\})")
_TEMPLATE_MARKER = re.compile(r"[\\`$]")
_REGEX_MARKER = re.compile(r"[/\\\[\]\r\n]")
_FENCE_LINE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)\Z")
_OTHER_ID_START = "\u1885\u1886\u2118\u212e\u309b\u309c"
_OTHER_ID_CONTINUE = "\u00b7\u0387\u1369\u136a\u136b\u136c\u136d\u136e\u136f\u1370\u1371\u19da"


def _identifier_char(char: str, *, start: bool) -> bool:
    # JavaScript uses Unicode ID_Start/ID_Continue, rather than Python's
    # normalization-restricted XID sets (e.g. U+309B is a valid JS start).
    category = unicodedata.category(char)
    return (
        char in "$_" + _OTHER_ID_START
        or category in ("Lu", "Ll", "Lt", "Lm", "Lo", "Nl")
        or (
            not start
            and (
                category in ("Mn", "Mc", "Nd", "Pc") or char in _OTHER_ID_CONTINUE + "\u200c\u200d"
            )
        )
    )


def _identifier_end(text: str, start: int) -> int:
    """JS identifier spelling, including Unicode, combining marks and escapes."""
    position = start
    while position < len(text):
        char, end = text[position], position + 1
        if char == "\\":
            match = _IDENTIFIER_ESCAPE.match(text, position)
            if not match:
                break
            codepoint = int(match[0][2:].strip("{}"), 16)
            if codepoint > 0x10FFFF:
                break
            char, end = chr(codepoint), match.end()
        if not _identifier_char(char, start=position == start):
            break
        position = end
    return position


def _identifier_name(token: str):
    if not token or _identifier_end(token, 0) != len(token):
        return None
    return _IDENTIFIER_ESCAPE.sub(lambda match: chr(int(match[0][2:].strip("{}"), 16)), token)


def _regex_end(text: str, start: int):
    """Skip a JS regex atom, including escaped delimiters and character classes."""
    position, in_class = start + 1, False
    while position < len(text):
        match = _REGEX_MARKER.search(text, position)
        if not match:
            break
        char, position = match[0], match.end()
        if char in ("\r", "\n"):
            break
        if char == "\\":
            position += 1
        elif char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            return max(position, _identifier_end(text, position))
    return None


_EXPRESSION_STARTERS = frozenset(
    (
        "(",
        "[",
        "{",
        ",",
        ":",
        "?",
        ";",
        "=",
        "!",
        "~",
        "+",
        "-",
        "*",
        "/",
        "%",
        "^",
        "&",
        "|",
        "<",
        ">",
        "return",
        "throw",
        "yield",
        "await",
        "typeof",
        "void",
        "delete",
        "new",
        "in",
        "instanceof",
        "case",
    )
)


def _template_end(text: str, start: int) -> tuple[int, bool]:
    """Consume template text and nested interpolations without evaluating them.

    Interpolation contents are never transformed into AST nodes. Their stack
    is bounded independently; strings/comments keep their delimiters literal.
    """
    stack, position, expect_operand = ["`"], start + 1, True
    while position < len(text):
        if stack[-1] == "`":
            match = _TEMPLATE_MARKER.search(text, position)
            if not match:
                break
            position = match.start()
            char = text[position]
            if char == "\\":
                position += 2
                continue
            position += 1
            if char == "`":
                stack.pop()
                expect_operand = False
                if not stack:
                    return position, True
            elif text[position - 1 : position + 1] == "${":
                stack.append("}")
                expect_operand = True
                position += 1
        else:
            match = _LITERAL_TOKENS.match(text, position)
            token = match[0]
            if token == "/" and expect_operand:
                end = _regex_end(text, position)
                if end is None:
                    break
                token, position = "regex atom", end
            else:
                position = match.end()
            if token.isspace() or token.startswith(("//", "/*", "#")):
                continue
            expect_operand = token in _EXPRESSION_STARTERS
            if token == "`":
                stack.append("`")
            elif token in ("{", "[", "("):
                stack.append({"{": "}", "[": "]", "(": ")"}[token])
            elif token in ("}", "]", ")"):
                if token != stack[-1]:
                    break
                stack.pop()
        if len(stack) > MAX_STRUCTURE_DEPTH:
            raise NonIndexableContentError("structure_depth", decision="unsupported")
    return len(text), False


def _bounded_literal_tokens(text: str) -> list[str]:
    """Bound parser allocations before JSON/AST construction, including flat lists.

    Iterate rather than materializing findall's unbounded result. The source
    byte cap bounds string storage; these limits bound syntax/AST overhead.
    Exhaustion is a refusal, never permission to fall back to raw text.
    """
    if (
        len(text) > MAX_SOURCE_BYTES
        or len(text.encode("utf-8", errors="replace")) > MAX_SOURCE_BYTES
    ):
        raise NonIndexableContentError("source_byte_budget", decision="unsupported")
    tokens, depth = [], 0
    position = 0
    while position < len(text):
        if len(tokens) >= MAX_STRUCTURE_TOKENS:
            raise NonIndexableContentError("structure_token_budget", decision="unsupported")
        match = _LITERAL_TOKENS.match(text, position)
        end = match.end()
        if match[0] == "`":
            end, _ = _template_end(text, position)
        else:
            end = max(end, _identifier_end(text, position))
        token, position = text[position:end], end
        if token in ("{", "[", "("):
            depth += 1
            if depth > MAX_STRUCTURE_DEPTH:
                raise NonIndexableContentError("structure_depth", decision="unsupported")
        elif token in ("}", "]", ")"):
            depth = max(0, depth - 1)
        tokens.append(token)
    return tokens


def _complete_source_literal(text: str) -> bool:
    """Recognize complete JS/Python literal syntax without executing source.

    Comments, trailing commas, and a statement terminator are accepted only
    for this recognition probe. The admitted source is never rewritten.
    """
    tokens = _bounded_literal_tokens(text)
    # Parse only the budgeted, lexically normalized candidate. In particular,
    # JS // comments must never hide Python // operators from an AST budget.
    # Python string delimiters/prefixes remain whole tokens in this pass.
    parts, following = [], ""
    for token in reversed(tokens):
        if token.startswith("/*") and (len(token) < 4 or not token.endswith("*/")):
            return False
        if token.startswith(("//", "/*", "#")):
            parts.append(" ")
        elif token.isspace():
            parts.append(token)
        elif (token == ";" and not following) or (token == "," and following in ("}", "]")):
            continue
        elif token.startswith("`"):
            if not _template_end(token, 0)[1]:
                return False
            # Preserve the entire source, but probe a constant placeholder.
            # Interpolations are source syntax and are never executed.
            parts.append('"template literal"')
            following = token
        elif (name := _identifier_name(token)) is not None:
            # Probe JS keys/constants as Python literals; quoted source
            # strings are whole tokens and never undergo this conversion.
            parts.append(
                json.dumps(name)
                if following == ":"
                else {"true": "True", "false": "False", "null": "None"}.get(name, token)
            )
            following = token
        else:
            parts.append(token)
            following = token
    candidate = "".join(reversed(parts)).strip()
    _bounded_literal_tokens(candidate)
    for parser in (json.loads, ast.literal_eval):
        try:
            value = parser(candidate)
        except (ValueError, SyntaxError, RecursionError):
            continue
        return isinstance(value, (dict, list))
    return False


def _malformed_transport(text: str, *, tool_context: bool) -> bool:
    """Require typed payload structure, or an explicitly typed tool context."""
    prefix = text[:8192]
    evidence = tool_context and bool(_TRANSPORT_PREFIX.search(prefix))
    match = _RAW_OPAQUE_PREFIX.search(prefix)
    evidence = evidence or bool(match and _opaque_span(match[1]))
    tokens = [
        token
        for token in _LITERAL_TOKENS.findall(prefix)
        if not token.isspace() and not token.startswith(("//", "/*", "#"))
    ]
    strings = []
    for token in tokens:
        try:
            strings.append(json.loads(token) if token.startswith('"') else None)
        except ValueError:
            strings.append(None)
    frames = []
    for index, token in enumerate(tokens):
        key = strings[index - 2] if index >= 2 and tokens[index - 1] == ":" else None
        if token in ("{", "["):
            frames.append(({} if token == "{" else None, key in _TRANSPORT_FIELDS))
        elif token in ("}", "]"):
            if frames:
                frames.pop()
        elif frames and frames[-1][0] is not None and index + 2 < len(tokens):
            if tokens[index + 1] != ":" or not isinstance(strings[index], str):
                continue
            fields, transport = frames[-1]
            fields[strings[index]] = strings[index + 2]
            typed_buffer = (
                transport
                or fields.get("type") in ("Buffer", "buffer")
                or fields.get("encoding") == "base64"
            )
            if _typed_payload(fields) or (typed_buffer and fields.keys() & _BUFFER_KEYS):
                evidence = True
            if (
                strings[index] in _TRANSPORT_FIELDS
                and tokens[index + 2] == "["
                and index + 3 < len(tokens)
            ):
                evidence = evidence or tokens[index + 3].isdigit()
    return evidence and not _complete_source_literal(text)


def _fits_tool_input(value) -> bool:
    remaining, nodes = MAX_TOOL_INPUT_BYTES, 4096

    def visit(item, depth=0):
        nonlocal remaining, nodes
        nodes -= 1
        if depth > 12 or nodes < 0 or remaining < 0:
            return False
        if isinstance(item, str):
            if len(item) > remaining:
                return False
            remaining -= len(item.encode("utf-8", errors="replace"))
        elif isinstance(item, dict):
            if len(item) > nodes:
                return False
            return all(
                visit(key, depth + 1) and visit(child, depth + 1) for key, child in item.items()
            )
        elif isinstance(item, list):
            if len(item) > nodes:
                return False
            return all(visit(child, depth + 1) for child in item)
        return remaining >= 0

    return visit(value)


def _typed_payload(value) -> bool:
    kind = value.get("type")
    return (
        isinstance(kind, str)
        and kind in _OPAQUE_TYPES
        and any(
            key in value
            for key in (
                "encrypted_content",
                "thinking",
                "data",
                "source",
                "image_url",
                "audio",
                "content",
            )
        )
    )


def _opaque_span(text: str) -> bool:
    return bool(
        _OPAQUE_LINE.fullmatch(text)
        and len(set(text)) >= 16
        and any(c.isupper() for c in text)
        and any(c.islower() for c in text)
        and any(c.isdigit() for c in text)
    )


def omit_opaque_lines(text: str) -> str:
    """Only long, standalone transport-like lines, outside literal code fences.

    Do not remove hashes/IDs, code containing base64 literals, or ordinary long
    words. This is a conservative structural rule, not semantic detection.
    """
    kept, omitted, fence = [], 0, None
    for line in text.splitlines():
        stripped = line.strip()
        match = _FENCE_LINE.fullmatch(line)
        if match:
            run, tail = match.groups()
            if fence is None:
                if run[0] != "`" or "`" not in tail:
                    fence = (run[0], len(run))
            elif run[0] == fence[0] and len(run) >= fence[1] and not tail.strip(" \t"):
                fence = None
        candidate = stripped.lstrip(">→ ").strip()
        if fence is None and _opaque_span(candidate):
            omitted += 1
        else:
            kept.append(line)
    if not omitted:
        return text
    note_omission("opaque_line", omitted)
    return "\n".join(kept).strip()


def _utf8_ends(text: str, limit: int, separator: str) -> str:
    raw = text.encode("utf-8", errors="replace")
    budget = max(0, limit - len(separator.encode("utf-8")))
    head_size = budget // 2
    tail_size = budget - head_size
    head = raw[:head_size].decode("utf-8", errors="ignore")
    tail = raw[-tail_size:].decode("utf-8", errors="ignore") if tail_size else ""
    return head + separator + tail


def _byte_ends(text: str, limit: int, reason: str) -> str:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= limit:
        return text
    note_omission(reason)
    # Separate segments for the total limit so no newly joined line exceeds
    # the per-line limit after the byte cut.
    return _utf8_ends(text, limit, "\n" if reason == "tool_total_bytes" else " ")


def bound_tool_result(text: str) -> str:
    limited = "\n".join(
        _byte_ends(line, TOOL_LINE_BYTES, "tool_line_bytes") for line in text.splitlines()
    )
    return _byte_ends(limited, TOOL_TOTAL_BYTES, "tool_total_bytes")


def _select_transport(value, *, transport=False, depth=0, decoded=False):
    """Select typed useful fields without decoding binary data. Work is bounded."""
    if depth > 12:
        raise NonIndexableContentError("structure_depth", decision="unsupported")
    if transport and isinstance(value, str) and _opaque_span(value.strip()):
        return None, 1
    if (
        transport
        and isinstance(value, list)
        and value
        and all(type(item) is int and 0 <= item <= 255 for item in value)
    ):
        return None, 1
    if transport and isinstance(value, str) and value.lstrip().startswith(("{", "[", '"')):
        if decoded:
            return None, 1
        _bounded_literal_tokens(value)
        try:
            nested = json.loads(value)
        except (ValueError, RecursionError):
            return None, 1
        # This single decode is specific to a typed raw-output field. It is
        # not the transcript decoder and never decodes base64/byte buffers.
        return _select_transport(nested, transport=True, depth=depth + 1, decoded=True)
    if isinstance(value, dict):
        kind = value.get("type")
        if _typed_payload(value):
            return None, 1
        transport = transport or kind in ("Buffer", "buffer") or value.get("encoding") == "base64"
        kept, omitted = {}, 0
        for key, child in value.items():
            if transport and key in ("type", "encoding"):
                continue
            if transport and key in _BUFFER_KEYS:
                omitted += 1
                continue
            selected, count = _select_transport(
                child,
                transport=key in _TRANSPORT_FIELDS,
                depth=depth + 1,
                decoded=decoded,
            )
            omitted += count
            if selected is not None:
                kept[key] = selected
        if omitted and set(kept).issubset(_TRANSPORT_METADATA):
            kept = {}
        return (kept if kept else None), omitted
    if isinstance(value, list):
        kept, omitted = [], 0
        for child in value:
            selected, count = _select_transport(
                child, transport=transport, depth=depth + 1, decoded=decoded
            )
            omitted += count
            if selected is not None:
                kept.append(selected)
        return (kept if kept else None), omitted
    return value, 0


def select_visible_text(content, *, tool_context=False) -> str:
    """Filter transport-shaped JSON strings; ordinary prose/code/config stays literal."""
    if isinstance(content, str):
        text = content.strip()
        if not text.startswith(("{", "[")):
            return text
        _bounded_literal_tokens(text)
        try:
            value = json.loads(text)
        except (ValueError, RecursionError):
            if _malformed_transport(text, tool_context=tool_context):
                note_omission("malformed_transport")
                return ""
            return text
    elif isinstance(content, (dict, list)):
        value = content
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        return ""
    if tool_context and not _fits_tool_input(value):
        note_omission("tool_structure_budget")
        return ""
    if (
        not tool_context
        and isinstance(value, dict)
        and not (
            _typed_payload(value)
            or value.get("type") in ("Buffer", "buffer")
            or value.get("encoding") == "base64"
            or any(key in value for key in _TRANSPORT_FIELDS)
        )
    ):
        return text
    selected, omitted = _select_transport(value)
    if not omitted:
        return text
    note_omission("opaque_transport", omitted)
    useful = (
        json.dumps(selected, ensure_ascii=False, separators=(",", ":"))
        if selected is not None
        else ""
    )
    return useful


def select_tool_text(content) -> str:
    # Bound allocation/JSON traversal before interpreting tool data. Oversized
    # results are omitted explicitly, not truncated into opaque fragments.
    if not _fits_tool_input(content):
        note_omission("tool_input_budget")
        return ""
    try:
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(select_visible_text(item, tool_context=True))
                elif isinstance(item, dict) and item.get("type") == "text":
                    parts.append(select_visible_text(item.get("text", ""), tool_context=True))
                else:
                    note_omission("typed_nontext")
            text = "\n".join(part for part in parts if part)
        else:
            text = select_visible_text(content, tool_context=True)
    except NonIndexableContentError as exc:
        note_omission(exc.reason)
        return ""
    except MemoryError:
        note_omission("structure_allocation_budget")
        return ""
    return omit_opaque_lines(text)


class NonIndexableContentError(ValueError):
    """Admission refusal: callers must skip without recording a refresh."""

    def __init__(self, reason: str, *, decision: str = "archive-only"):
        self.reason = reason
        self.decision = decision
        super().__init__(reason)


def unwrap_transcript(content: str) -> str:
    """Unwrap exactly one JSON string layer, only for a recognized format."""
    if content.lstrip().startswith(("{", "[", '"')):
        _bounded_literal_tokens(content)
    if not content.lstrip().startswith('"'):
        return content
    try:
        inner = json.loads(content)
    except (ValueError, RecursionError):
        return content
    if not isinstance(inner, str):
        return content
    if transcript_family(inner):
        return inner
    # One bounded probe diagnoses excess encoding; it is never normalized.
    if inner.lstrip().startswith('"'):
        try:
            probe = json.loads(inner)
        except (ValueError, RecursionError):
            probe = None
        if isinstance(probe, str):
            # Diagnose deeper encodings from a fixed prefix, without decoding
            # recursively. This diagnostic cannot produce indexable text.
            prefix = probe[:4096].replace("\\", "").lstrip('" \t\r\n')
            if transcript_family(probe) or transcript_family(prefix):
                raise NonIndexableContentError("encoding_depth", decision="unsupported")
    return content


class _ProbeObject(dict):
    """Retain ambiguous duplicate-field evidence without copying whole trees."""

    def __init__(self):
        super().__init__()
        self.previous = {}

    def __setitem__(self, key, value):
        if key in self:
            self.previous.setdefault(key, []).append(self[key])
        super().__setitem__(key, value)


def _field_values(value: dict, key: str):
    if key in value:
        yield value[key]
    if isinstance(value, _ProbeObject):
        yield from value.previous.get(key, ())


def _object_values(value: dict):
    for key in value:
        yield from _field_values(value, key)


def _value_family(value, depth=0) -> str:
    kinds = tuple(_field_values(value, "type")) if isinstance(value, dict) else ()
    if any(is_codex_event({"type": kind}) for kind in kinds):
        return "codex"
    if depth > 4:
        return ""
    if isinstance(value, list):
        return next((family for item in value if (family := _value_family(item, depth + 1))), "")
    if not isinstance(value, dict):
        return ""
    if "session_metadata" in kinds:
        return "gemini"
    if "session" in kinds and "version" in value:
        return "pi"
    if any(kind in ("assistant", "user", "human") for kind in kinds) and "message" in value:
        return "claude-code"
    if any(
        isinstance(role, str) for key in ("role", "sender") for role in _field_values(value, key)
    ) and any(key in value for key in ("content", "text", "parts")):
        return "messages"
    if "message" in kinds and any(key in value for key in ("message", "user", "username")):
        return "messages"
    for key in ("messages", "chat_messages", "contents", "history"):
        for child in _field_values(value, key):
            if isinstance(child, list) and _value_family(child, depth + 1):
                return "messages"
    for mapping in _field_values(value, "mapping"):
        if isinstance(mapping, dict) and any(
            isinstance(node, dict)
            and any(
                isinstance(message, dict) and "author" in message
                for message in _field_values(node, "message")
            )
            for node in _object_values(mapping)
        ):
            return "chatgpt"
    return ""


def _probe_string(token: str):
    """Decode only small string atoms; large values cannot name a schema."""
    if token.startswith("`"):
        return token[1:-1] if _template_end(token, 0)[1] else None
    if len(token) > 256:
        return token if token.startswith(("'", '"')) else None
    for parser in (json.loads, ast.literal_eval):
        try:
            value = parser(token)
        except (ValueError, SyntaxError):
            continue
        return value if isinstance(value, str) else None
    return None


def _partial_literal_roots(tokens: list[str]) -> list:
    """A bounded shape probe, not a decoder or a source-language evaluator.

    Keep keys as soon as their colon is present, including at EOF. Only
    structurally attached containers can supply envelope evidence; comments,
    strings and arbitrary nested configuration cannot create root records.
    Complete and truncated documents use the same family predicates.
    """
    roots, frames = [], []
    for token in tokens:
        if token.isspace() or token.startswith(("//", "/*", "#")):
            continue
        if frames:
            frame = frames[-1]
            value, state, key = frame
            closing = "}" if isinstance(value, dict) else "]"
            if token == closing and state in ("key", "value", "comma"):
                frames.pop()
                continue
            if state == "key":
                key = _probe_string(token)
                if key is None:
                    key = _identifier_name(token)
                if key is None:
                    break
                frame[1:] = ["colon", key]
                continue
            if state == "colon":
                if token != ":":
                    break
                value[key] = None
                frame[1] = "value"
                continue
            if state == "comma":
                if token != ",":
                    break
                frame[1] = "key" if isinstance(value, dict) else "value"
                continue
        elif token not in ("{", "["):
            break

        if token in (":", ",", "}", "]", "(", ")", ";"):
            break
        child = _ProbeObject() if token == "{" else [] if token == "[" else _probe_string(token)
        if frames:
            frame[1] = "comma"
            if isinstance(value, dict):
                value[key] = child
            else:
                value.append(child)
        else:
            roots.append(child)
        if token in ("{", "["):
            frames.append([child, "key" if token == "{" else "value", None])
    return roots


def transcript_family(content: str) -> str:
    """Only inspect root JSON/JSONL, never prose or fenced/quoted examples.

    Inspect bounded lexical structure through EOF, including truncated values
    and late identifying fields. Exhaustion refuses rather than authorizing
    a raw fallback. Literal/comment contents never supply envelope fields.
    """
    stripped = content.lstrip()
    if not stripped.startswith(("{", "[")):
        return ""
    for root in _partial_literal_roots(_bounded_literal_tokens(content)):
        family = _value_family(root)
        if family:
            return family
    return ""


def looks_like_codex(content: str) -> bool:
    return transcript_family(content) == "codex"


MAX_SOURCE_BYTES = 8 * 1024 * 1024


def indexing_text(text: str) -> str:
    """Selected text has no generated annotations; literal markers are content."""
    return text.strip()


@dataclass(frozen=True)
class Admission:
    decision: str
    conversations: tuple[str, ...]
    reasons: tuple[str, ...]
    omissions: dict[str, int]
    source: str = ""

    @property
    def text(self) -> str:
        return "\n\n".join(self.conversations)

    @property
    def indexable(self) -> bool:
        return self.decision in ("keep", "sanitize") and bool(indexing_text(self.text))

    def metadata(self) -> dict:
        return {
            "ingestion_policy": 1,
            "ingestion_decision": self.decision,
            "ingestion_reasons": ",".join(self.reasons),
            "ingestion_omissions": json.dumps(
                self.omissions, sort_keys=True, separators=(",", ":")
            ),
        }

    def require_conversations(self) -> list[str]:
        if not self.indexable:
            if "unparsed_codex" in self.reasons:
                from .normalize import UnparsedCodexTranscriptError

                raise UnparsedCodexTranscriptError("unparsed_codex")
            raise NonIndexableContentError(",".join(self.reasons), decision=self.decision)
        return list(self.conversations)

    def refusal(self) -> dict:
        return {
            "success": False,
            "error": "ingestion admission refused content",
            "decision": self.decision,
            "reason_codes": list(self.reasons),
            "omission_counts": dict(self.omissions),
        }


def admit_text(content: str, *, source: str = "", spellcheck: bool = True) -> Admission:
    """Classify/select before chunking or writes. Raw input is never archived here.

    Limits are conservative resource budgets, not a semantic relevance score.
    No storage/provider import is needed by this function or the shadow audit.
    """
    if (
        len(content) > MAX_SOURCE_BYTES
        or len(content.encode("utf-8", errors="replace")) > MAX_SOURCE_BYTES
    ):
        return Admission("unsupported", (), ("source_byte_budget",), {}, source)
    omissions = {}
    token = _omissions.set(omissions)
    spellcheck_token = _spellcheck.set(spellcheck)
    try:
        if content.lstrip().startswith(">"):
            lines = content.splitlines()
            quoted = 0
            for index, line in enumerate(lines):
                if line.lstrip().startswith(">"):
                    quoted += 1
                elif line.strip():
                    if quoted >= 3 and transcript_family("\n".join(lines[index:])):
                        return Admission(
                            "archive-only", (), ("mixed_transcript_envelope",), {}, source
                        )
                    break
        from .normalize import _try_normalize_json_split

        split = _try_normalize_json_split(content)
        reasons = ["normalized_transcript"] if split is not None else []
        selected = split if split is not None else [select_visible_text(content)]
        if split is None and not omissions:
            selected = [content]
        selected = tuple(text for item in selected if (text := omit_opaque_lines(item)).strip())
        reasons.extend(sorted(omissions))
        if not any(indexing_text(item) for item in selected):
            return Admission(
                "archive-only", (), tuple(reasons + ["no_useful_content"]), dict(omissions), source
            )
        decision = "sanitize" if reasons else "keep"
        return Admission(
            decision,
            selected,
            tuple(reasons or ["plain_or_structured_text"]),
            dict(omissions),
            source,
        )
    except NonIndexableContentError as exc:
        return Admission(exc.decision, (), (exc.reason,), dict(omissions), source)
    except MemoryError:
        # A last-resort diagnostic; the lexical budget is the primary boundary.
        return Admission(
            "unsupported", (), ("structure_allocation_budget",), dict(omissions), source
        )
    except (ValueError, TypeError, AttributeError, RecursionError):
        # Malformed supported shapes and parser resource failures must never
        # be converted into raw prose. Do not expose exception/payload text.
        return Admission("unsupported", (), ("malformed_structure",), dict(omissions), source)
    finally:
        _spellcheck.reset(spellcheck_token)
        _omissions.reset(token)


def is_codex_event(value) -> bool:
    """Recognize rollout envelopes, including headerless/incomplete fragments."""
    return isinstance(value, dict) and value.get("type") in (
        "session_meta",
        "response_item",
        "event_msg",
        "turn_context",
    )
