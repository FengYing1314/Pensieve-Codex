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


def find_pensieve_project(cwd: Path) -> Optional[Path]:
    try:
        current = cwd.expanduser().resolve()
    except OSError:
        return None
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        if (directory / ".pensieve").is_dir():
            return directory
    return None


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def validate_project_state_paths(project_root: Path, data_root: Path, state_root: Path) -> None:
    """Reject redirected automatic outputs before creating directories or locks."""
    project = project_root.resolve(strict=True)
    if not project.is_dir():
        raise ValueError("project root must be an existing directory")
    expected_data = project / ".pensieve"
    expected_state = expected_data / ".state"
    for path, expected in ((data_root, expected_data), (state_root, expected_state)):
        if path.resolve(strict=True) != expected or not path.is_dir():
            raise ValueError(f"project-only refresh requires an existing, unredirected {expected}")
    outputs = (
        expected_data / "state.md",
        expected_state / "pensieve-user-data-graph.md",
        expected_state / ".gitignore",
        expected_state / ".maintain.lock",
    )
    for path in outputs:
        if path.resolve(strict=False) != path or path.is_symlink():
            raise ValueError(f"project-only output is redirected: {path}")
        if path.exists() and not path.is_file():
            raise ValueError(f"project-only output must be a regular file: {path}")
        if path.name in {".gitignore", ".maintain.lock"} and path.exists() and path.stat().st_nlink > 1:
            raise ValueError(f"project-only in-place output must not share a hard link: {path}")
    lock_dir = expected_state / ".maintain.lock.d"
    if lock_dir.is_symlink() or (lock_dir.exists() and not lock_dir.is_dir()):
        raise ValueError(f"project-only lock directory is redirected or invalid: {lock_dir}")


def write_text_atomic_if_changed(path: Path, content: str) -> bool:
    if path.is_symlink():
        path = path.resolve(strict=True)
    try:
        if path.read_bytes() == content.encode("utf-8"):
            return False
    except FileNotFoundError:
        pass
    try:
        target_mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        current_umask = os.umask(0)
        os.umask(current_umask)
        target_mode = 0o666 & ~current_umask

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, target_mode)
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
                "Continue the current task using original entries and source. Run init/doctor only when setup or maintenance is authorized; read-only tasks must not refresh state."
            ),
            system_message="Pensieve project memory needs init and doctor.",
        )

    if checked_version != skill_version:
        recorded = checked_version or "none"
        return HookSemantics(
            event="session-start",
            additional_context=(
                f"[Pensieve] Health check is stale for version {skill_version} (recorded: {recorded}). "
                "Continue from original entries and source. Run Doctor only for authorized maintenance, never to unblock a read-only task."
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
        "Reuse relevant knowledge for file locations and call chains; verify facts and keep decisions within scope. Current requests and authorization prevail over any matching "
        "pipeline. Recall is read-only, including stale indexes; short-term originals need verification. Read at most five likely entries, then use at most two "
        "targeted searches and ten total recall operations before returning to source inspection. Cite the entry paths in "
        "the briefing."
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
    normalize_client(client)
    if semantics.event == "session-start":
        event_name = "SessionStart"
    elif semantics.event == "subagent-start":
        event_name = "SubagentStart"
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
            "updatedInput": updated_input,
        }
    }
