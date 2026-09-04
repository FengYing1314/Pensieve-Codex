from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple


VALID_CLIENTS = {"auto", "codex", "claude", "both", "generic"}
CLIENT_ALIASES = {"agent": "codex", "agents": "codex"}
DATA_CATEGORIES = {"maxims", "decisions", "knowledge", "pipelines", "short-term"}
PATCH_PATH_RE = re.compile(
    r"^\*\*\* (?:Add|Update|Delete) File:\s*(.+?)\s*$|^\*\*\* Move to:\s*(.+?)\s*$",
    re.MULTILINE,
)
DIFF_PATH_RE = re.compile(r"^(?:---|\+\+\+)\s+(?:[ab]/)?(.+?)\s*$", re.MULTILINE)
CREATED_RE = re.compile(r"^created:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


@dataclass(frozen=True)
class HookSemantics:
    event: str
    additional_context: str = ""
    system_message: str = ""
    changed_paths: Tuple[str, ...] = ()


def normalize_client(value: Optional[str]) -> str:
    client = (value or "auto").strip().lower()
    client = CLIENT_ALIASES.get(client, client)
    if client not in VALID_CLIENTS:
        allowed = "|".join(sorted(VALID_CLIENTS))
        raise ValueError(f"unsupported client {value!r}; expected {allowed}")
    return client


def detect_client(
    requested: Optional[str] = None,
    *,
    env: Optional[Mapping[str, str]] = None,
    skill_root: Optional[Path] = None,
) -> str:
    env_map = os.environ if env is None else env
    explicit = requested if requested is not None else env_map.get("PENSIEVE_CLIENT", "auto")
    client = normalize_client(explicit)
    if client != "auto":
        return client

    if env_map.get("CLAUDE_PROJECT_DIR") or env_map.get("CLAUDE_PLUGIN_ROOT"):
        return "claude"
    if env_map.get("PLUGIN_ROOT") or env_map.get("CODEX_HOME"):
        return "codex"

    root_text = str(skill_root or "").replace("\\", "/").lower()
    if "/.claude/" in root_text:
        return "claude"
    if "/.codex/" in root_text or "/plugins/cache/" in root_text:
        return "codex"
    return "generic"


def find_pensieve_project(cwd: Path, explicit_root: Optional[Path] = None) -> Optional[Path]:
    candidates = []
    if explicit_root is not None:
        candidates.append(explicit_root)
    candidates.append(cwd)

    seen = set()
    for candidate in candidates:
        try:
            current = candidate.expanduser().resolve()
        except OSError:
            continue
        if current.is_file():
            current = current.parent
        for directory in (current, *current.parents):
            key = str(directory)
            if key in seen:
                continue
            seen.add(key)
            if (directory / ".pensieve").is_dir():
                return directory
    return None


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def write_text_atomic_if_changed(path: Path, content: str) -> bool:
    try:
        if path.read_text(encoding="utf-8") == content:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(tmp), str(path))
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
    return True


def write_json_atomic_if_changed(path: Path, payload: Mapping[str, Any]) -> bool:
    return write_text_atomic_if_changed(
        path,
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
    )


def count_due_short_term(data_root: Path, *, today: Optional[dt.date] = None, ttl_days: int = 7) -> Tuple[int, int]:
    current_day = today or dt.date.today()
    total = 0
    due = 0
    short_term = data_root / "short-term"
    if not short_term.is_dir():
        return total, due

    for note in sorted(short_term.rglob("*.md")):
        try:
            head = note.read_text(encoding="utf-8", errors="replace")[:4096]
        except OSError:
            continue
        end = head.find("\n---", 4)
        if not head.startswith("---") or end < 0:
            continue
        frontmatter = head[:end]
        if re.search(r"^tags:\s*.*\bseed\b", frontmatter, flags=re.MULTILINE | re.IGNORECASE):
            continue
        match = CREATED_RE.search(frontmatter)
        if match is None:
            continue
        try:
            created = dt.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        total += 1
        if (current_day - created).days >= ttl_days:
            due += 1
    return total, due


def session_semantics(
    project_root: Path,
    skill_root: Path,
    skill_version: str,
    *,
    today: Optional[dt.date] = None,
) -> Optional[HookSemantics]:
    data_root = project_root / ".pensieve"
    if not data_root.is_dir():
        return None

    marker = read_json_object(data_root / ".state" / "pensieve-session-marker.json")
    initialized = bool(marker.get("initialized"))
    checked_version = str(marker.get("self_check_version") or "")

    if not initialized:
        return HookSemantics(
            event="session-start",
            additional_context=(
                "[Pensieve] Project memory exists, but initialization is not recorded. "
                "Continue the current task; run pensieve init and then pensieve doctor before relying on cached routes."
            ),
            system_message="Pensieve project memory needs init and doctor.",
        )

    if checked_version != skill_version:
        recorded = checked_version or "none"
        return HookSemantics(
            event="session-start",
            additional_context=(
                f"[Pensieve] Health check is stale for version {skill_version} (recorded: {recorded}). "
                "Continue the current task; run pensieve doctor before relying on cached routes."
            ),
            system_message="Pensieve project memory needs a doctor check.",
        )

    total, due = count_due_short_term(data_root, today=today)
    if due == 0:
        return None
    return HookSemantics(
        event="session-start",
        additional_context=(
            f"[Pensieve] {due} of {total} short-term item(s) are at least 7 days old. "
            "Use pensieve refine to promote, merge, or delete them; continue the current task unless refinement was requested."
        ),
        system_message=f"Pensieve: {due} short-term item(s) are due for refine.",
    )


def recall_context() -> str:
    return (
        "[Pensieve recall] Before broad exploration, inspect .pensieve/state.md and the generated graph on demand. "
        "Reuse relevant knowledge for file locations and call chains; obey active decisions and maxims; follow a matching "
        "pipeline; treat short-term entries as unpromoted evidence. Read at most five likely entries, then use at most two "
        "targeted searches under .pensieve before returning to source inspection. Cite the entry paths in the briefing."
    )


def subagent_semantics(project_root: Path) -> Optional[HookSemantics]:
    if not (project_root / ".pensieve").is_dir():
        return None
    return HookSemantics(event="subagent-start", additional_context=recall_context())


def _successful_tool_response(payload: Mapping[str, Any]) -> bool:
    response = payload.get("tool_response")
    if not isinstance(response, Mapping):
        return True
    if response.get("success") is False or response.get("isError") is True:
        return False
    return True


def _claude_input_paths(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key == "file_path" and isinstance(nested, str):
                yield nested
            else:
                yield from _claude_input_paths(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            yield from _claude_input_paths(nested)


def _codex_patch_paths(command: str) -> Iterable[str]:
    for match in PATCH_PATH_RE.finditer(command):
        raw = next((group for group in match.groups() if group is not None), "")
        if raw:
            yield raw
    for match in DIFF_PATH_RE.finditer(command):
        raw = match.group(1)
        if raw and raw != "/dev/null":
            yield raw


def extract_changed_paths(payload: Mapping[str, Any], client: str) -> Tuple[str, ...]:
    if not _successful_tool_response(payload):
        return ()
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        return ()

    normalized_client = normalize_client(client)
    if normalized_client == "codex":
        command = tool_input.get("command")
        raw_paths = _codex_patch_paths(command) if isinstance(command, str) else ()
    else:
        raw_paths = _claude_input_paths(tool_input)
    return tuple(dict.fromkeys(path.strip() for path in raw_paths if path.strip()))


def pensieve_changed_paths(
    raw_paths: Iterable[str],
    *,
    cwd: Path,
    project_root: Path,
) -> Tuple[str, ...]:
    data_root = (project_root / ".pensieve").resolve()
    resolved = []
    for raw in raw_paths:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = cwd / candidate
        try:
            candidate = candidate.resolve(strict=False)
            relative = candidate.relative_to(data_root)
        except (OSError, ValueError):
            continue
        if not relative.parts or relative.parts[0] not in DATA_CATEGORIES:
            continue
        resolved.append(relative.as_posix())
    return tuple(sorted(dict.fromkeys(resolved)))


def post_tool_semantics(
    payload: Mapping[str, Any],
    client: str,
    *,
    cwd: Path,
    project_root: Path,
) -> Optional[HookSemantics]:
    changed = pensieve_changed_paths(
        extract_changed_paths(payload, client),
        cwd=cwd,
        project_root=project_root,
    )
    if not changed:
        return None
    return HookSemantics(event="post-tool-use", changed_paths=changed)


def render_context_output(client: str, semantics: HookSemantics) -> dict[str, Any]:
    normalized_client = normalize_client(client)
    if semantics.event == "session-start":
        event_name = "SessionStart"
    elif semantics.event == "subagent-start":
        event_name = "SubagentStart" if normalized_client == "codex" else "PreToolUse"
    else:
        event_name = "PostToolUse"

    output: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": semantics.additional_context,
        }
    }
    if semantics.system_message:
        output["systemMessage"] = semantics.system_message
    return output


def render_claude_subagent_output(payload: Mapping[str, Any], semantics: HookSemantics) -> dict[str, Any]:
    tool_input = payload.get("tool_input")
    updated_input = dict(tool_input) if isinstance(tool_input, Mapping) else {}
    original_prompt = updated_input.get("prompt")
    if not isinstance(original_prompt, str):
        original_prompt = ""
    updated_input["prompt"] = semantics.additional_context + "\n\n---\n\n" + original_prompt
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": updated_input,
        }
    }


def claude_allow_output() -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
