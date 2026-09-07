from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


INSTRUCTION_START = "<!-- pensieve:instructions:start -->"
INSTRUCTION_END = "<!-- pensieve:instructions:end -->"
INSTRUCTION_ROUTES = (
    ("run-when-committing.md", "When the user requests executing a Git commit"),
    ("run-when-refactoring.md", "When the user requests implementing a refactor"),
    ("run-when-reviewing-code.md", "When the user requests a code review within the supplied scope"),
)


def instruction_routes(data_root: Path) -> list[str]:
    return [
        f"- {condition}: use `.pensieve/pipelines/{name}`."
        for name, condition in INSTRUCTION_ROUTES
        if (data_root / "pipelines" / name).is_file()
    ]


def instruction_block(routes: list[str], start: str = INSTRUCTION_START, end: str = INSTRUCTION_END) -> str:
    return "\n".join([start, "## How To Use Pensieve", "", *routes, end, ""])


def instruction_block_span(content: bytes, start: str = INSTRUCTION_START, end: str = INSTRUCTION_END) -> tuple[int, int] | None:
    """Locate one ordered pair of standalone markers without normalizing bytes."""
    content.decode("utf-8")
    markers = (start.encode("utf-8"), end.encode("utf-8"))
    counts = tuple(content.count(marker) for marker in markers)
    if counts == (0, 0):
        return None
    if counts != (1, 1):
        raise ValueError("expected one matching pair of Pensieve instruction markers")
    positions = {}
    offset = 0
    for line in content.splitlines(keepends=True):
        bare = line.rstrip(b"\r\n")
        for marker in markers:
            if marker in line:
                if bare != marker:
                    raise ValueError("Pensieve instruction markers must occupy standalone lines")
                if line.endswith(b"\r"):
                    raise ValueError("Pensieve marker lines must use LF or CRLF, not a bare CR")
                positions[marker] = (offset, offset + len(line))
        offset += len(line)
    if len(positions) != 2 or positions[markers[0]][0] >= positions[markers[1]][0]:
        raise ValueError("Pensieve instruction start marker must precede its end marker")
    return positions[markers[0]][0], positions[markers[1]][1]


def replace_instruction_block(content: bytes | None, block: str) -> bytes:
    """Replace only the managed region; preserve the surrounding bytes and EOF style."""
    if not content:
        return block.encode("utf-8")
    span = instruction_block_span(content)
    region = content[span[0]:span[1]] if span is not None else content
    first_lf = region.find(b"\n")
    newline = b"\r\n" if first_lf > 0 and region[first_lf - 1:first_lf] == b"\r" else b"\n"
    replacement = block.encode("utf-8").replace(b"\n", newline)
    if not region.endswith(b"\n"):
        replacement = replacement.rstrip(b"\r\n")
    if span is not None:
        return content[:span[0]] + replacement + content[span[1]:]
    separator = newline if content.endswith(b"\n") else newline * 2
    return content + separator + replacement


class SchemaError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        raise SchemaError(f"failed to parse schema: {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise SchemaError(f"schema root must be object: {path}")
    return data


def load_schema(schema_file: Path) -> dict[str, Any]:
    if not schema_file.is_file():
        raise SchemaError(f"schema file missing: {schema_file}")

    schema = _read_json(schema_file)

    required_top = {
        "required_dirs",
        "critical_files",
        "memory",
        "doctor",
    }
    missing = sorted(k for k in required_top if k not in schema)
    if missing:
        raise SchemaError(f"schema missing keys: {', '.join(missing)}")

    version = schema.get("schema_version")
    if version != 2:
        raise SchemaError(f"unsupported schema_version: {version!r} (expected 2)")

    return schema


def classify_state(
    *,
    has_missing_root: bool,
    has_missing_directories: bool,
    has_missing_critical_files: bool,
    must_fix_count: int,
) -> str:
    # Explicit state machine for project data lifecycle.
    if has_missing_root or has_missing_directories:
        return "EMPTY"
    if has_missing_critical_files:
        return "SEEDED"
    if must_fix_count == 0:
        return "ALIGNED"
    return "DRIFTED"


# ---------------------------------------------------------------------------
# SKILL.md frontmatter description extraction (used by scan-structure and
# maintain-auto-memory to read the skill description from SKILL.md).
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", flags=re.MULTILINE | re.DOTALL)


def load_skill_description(path: Path) -> str | None:
    """Extract the ``description`` value from a SKILL.md frontmatter block.

    Returns the description string, or ``None`` if the file is missing,
    has no valid frontmatter, or has no ``description`` field.
    """
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    m = _FRONTMATTER_RE.search(text)
    if not m:
        return None
    lines = m.group(1).splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        value = line.split(":", 1)[1].strip()
        if value in (">-", ">", "|", "|-"):
            parts: list[str] = []
            for cont in lines[i + 1 :]:
                if cont and cont[0] in (" ", "\t"):
                    parts.append(cont.strip())
                else:
                    break
            if parts:
                sep = " " if value.startswith(">") else "\n"
                return sep.join(parts)
            return None
        return value if value else None
    return None


class InstructionSyncError(RuntimeError):
    pass


def instruction_target_snapshot(target: Path):
    # Resolve links without replacing them; never read a FIFO or another special target.
    if target.is_symlink() or target.exists():
        resolved = target.resolve(strict=True)
        if not resolved.is_file():
            raise ValueError("target must resolve to a regular file")
        info = resolved.stat()
        original = resolved.read_bytes()
        fingerprint = (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)
    else:
        resolved = target.resolve(strict=False)
        original = None
        fingerprint = None
    return resolved, original, fingerprint



def sync_instruction_targets(data_root: Path, targets: list[Path]) -> list[tuple[Path, str]]:
    """Preflight every target, then atomically replace each unchanged snapshot."""
    from hook_runtime import write_text_atomic_if_changed

    routes = instruction_routes(data_root)
    if not routes:
        raise InstructionSyncError("No supported pipeline files found; no instruction files were written.")
    block = instruction_block(routes)
    prepared = []
    seen = set()
    for raw in targets:
        target = Path(raw)
        try:
            snapshot = instruction_target_snapshot(target)
            resolved, original, fingerprint = snapshot
            candidate = replace_instruction_block(original, block)
            if resolved in seen:
                continue
            seen.add(resolved)
            prepared.append((target, snapshot, candidate))
        except (OSError, ValueError, RuntimeError) as exc:
            raise InstructionSyncError(f"Preflight failed for {target}: {exc}. No instruction files were written.") from exc

    for target, (resolved, original, _), candidate in prepared:
        try:
            conflicting_parent = next((parent for parent in resolved.parents if parent in seen), None)
            if conflicting_parent is not None:
                raise ValueError(f"another instruction target is required as a parent directory: {conflicting_parent}")
            if candidate != original:
                ancestor = resolved.parent
                while not ancestor.exists():
                    ancestor = ancestor.parent
                if not ancestor.is_dir() or not os.access(ancestor, os.W_OK | os.X_OK):
                    raise ValueError("target parent must be a writable directory")
        except (OSError, ValueError, RuntimeError) as exc:
            raise InstructionSyncError(f"Preflight failed for {target}: {exc}. No instruction files were written.") from exc

    written = []
    results = []
    for index, (target, snapshot, candidate) in enumerate(prepared):
        try:
            if instruction_target_snapshot(target) != snapshot:
                raise ValueError("target changed after preflight; refusing to overwrite it")
            changed = write_text_atomic_if_changed(target, candidate.decode("utf-8"))
            status = "unchanged" if not changed else ("created" if snapshot[1] is None else "updated")
            results.append((target, status))
            if changed:
                written.append(target)
        except (OSError, ValueError, RuntimeError) as exc:
            raise InstructionSyncError(
                f"Instruction sync failed for {target}: {exc}\n"
                + "Written: " + (", ".join(map(str, written)) or "none") + "\n"
                + "Not written: " + ", ".join(str(item[0]) for item in prepared[index:])
            ) from exc
    return results
