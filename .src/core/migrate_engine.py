from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Tuple

from hook_runtime import write_json_atomic_if_changed, write_text_atomic_if_changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely migrate Pensieve project data.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--skill-root", type=Path, required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--actions", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--timestamp", required=True)
    parser.add_argument("--client", required=True)
    parser.add_argument("--cleanup-legacy", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve(strict=False) == right.resolve(strict=False)
    except OSError:
        return False


def copy_file_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(
        prefix=destination.name + ".",
        suffix=".tmp",
        dir=str(destination.parent),
    )
    os.close(fd)
    tmp = Path(raw_tmp)
    try:
        shutil.copy2(str(source), str(tmp))
        os.replace(str(tmp), str(destination))
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def is_readme(path: Path, pattern: re.Pattern[str]) -> bool:
    return bool(pattern.match(path.name))


def iter_category_files(base: Path, category: str, readme_pattern: re.Pattern[str]) -> Iterator[Tuple[Path, Path]]:
    category_root = base / category
    if not category_root.is_dir():
        return
    for source in sorted(category_root.rglob("*")):
        if not source.is_file() or is_readme(source, readme_pattern):
            continue
        if category != "knowledge" and source.suffix.lower() != ".md":
            continue
        relative = source.relative_to(category_root)
        if category == "pipelines":
            if relative.name == "review.md":
                relative = relative.with_name("run-when-reviewing-code.md")
            elif relative.name.startswith("pipeline.run-when-"):
                relative = relative.with_name(relative.name[len("pipeline.") :])
        yield source, relative


def iter_seed_files(skill_root: Path) -> Iterator[Tuple[Path, Path]]:
    template_root = skill_root / ".src" / "templates"
    for source in sorted((template_root / "maxims").glob("*.md")):
        if source.is_file():
            yield source, Path("maxims") / source.name
    for source in sorted((template_root / "pipelines").glob("run-when-*.md")):
        if source.is_file():
            yield source, Path("pipelines") / source.name
    knowledge_root = template_root / "knowledge"
    if knowledge_root.is_dir():
        for source in sorted(knowledge_root.rglob("*")):
            if source.is_file():
                yield source, Path("knowledge") / source.relative_to(knowledge_root)


def path_inventory(path: Path) -> List[Tuple[str, str, str]]:
    if path.is_symlink():
        return [(".", "symlink", os.readlink(str(path)))]
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return [(".", "file", digest)]
    inventory: List[Tuple[str, str, str]] = []
    for item in sorted(path.rglob("*")):
        relative = item.relative_to(path).as_posix()
        if item.is_symlink():
            inventory.append((relative, "symlink", os.readlink(str(item))))
        elif item.is_file():
            inventory.append((relative, "file", hashlib.sha256(item.read_bytes()).hexdigest()))
        elif item.is_dir():
            inventory.append((relative, "dir", ""))
    return inventory


def backup_all(candidates: Iterable[Path], backup_dir: Path) -> List[Dict[str, str]]:
    paths = list(candidates)
    if not paths:
        return []
    backup_dir.mkdir(parents=True, exist_ok=False)
    records: List[Dict[str, str]] = []
    for index, source in enumerate(paths, start=1):
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", source.name or "root")
        destination = backup_dir / f"legacy-{index:02d}-{safe_name}"
        try:
            destination.resolve(strict=False).relative_to(source.resolve(strict=False))
        except ValueError:
            pass
        else:
            raise RuntimeError(f"backup destination is inside legacy source: {source}")

        if source.is_symlink():
            destination.symlink_to(os.readlink(str(source)))
        elif source.is_dir():
            shutil.copytree(str(source), str(destination), symlinks=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(destination), follow_symlinks=False)

        if path_inventory(source) != path_inventory(destination):
            raise RuntimeError(f"backup verification failed: {source}")
        records.append({"source": str(source), "backup": str(destination)})
    return records


def render_report(summary: Dict[str, Any]) -> str:
    counts = summary["counts"]
    lines = [
        "# Pensieve Migrate Report",
        "",
        "## Result",
        f"- Status: {summary['status']}",
        f"- Client: {summary['client']}",
        f"- Dry-run: {'yes' if summary['dry_run'] else 'no'}",
        f"- Cleanup legacy: {'yes' if summary['cleanup_legacy'] else 'no'}",
        f"- Data root: `{summary['user_data_root']}`",
        "",
        "## Changes",
        f"- Directories created/planned: {counts['created_dirs']}",
        f"- Legacy files copied/identical: {counts['migrated_files']}",
        f"- Conflict copies created/planned: {counts['conflict_files']}",
        f"- Missing seed files created/planned: {counts['created_seed_files']}",
        f"- Legacy locations backed up: {counts['backed_up_legacy_paths']}",
        f"- Legacy locations removed: {counts['removed_legacy_paths']}",
        "",
        "Customized pipeline, maxim, and knowledge seed content is project-owned and was not replaced.",
        "Legacy locations are retained unless `--cleanup-legacy` is explicit and every full backup verifies.",
        "",
        "## Next step",
        "Run `pensieve doctor` for the selected client.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def run(args: argparse.Namespace) -> int:
    root = args.root.resolve(strict=False)
    project_root = args.project_root.resolve(strict=False)
    skill_root = args.skill_root.resolve(strict=False)
    state_dir = args.state_dir.resolve(strict=False)
    schema = load_json(skill_root / ".src" / "core" / "schema.json")
    required_dirs = [str(value) for value in schema.get("required_dirs", [])]
    optional_dirs = [str(value) for value in schema.get("optional_dirs", [])]
    categories = required_dirs + optional_dirs
    legacy_cfg = schema.get("legacy_paths", {}) if isinstance(schema.get("legacy_paths"), dict) else {}
    legacy_paths = [project_root / str(value) for value in legacy_cfg.get("project", [])]
    legacy_paths.extend(args.home.resolve(strict=False) / str(value) for value in legacy_cfg.get("user", []))
    readme_pattern = re.compile(str(schema.get("legacy_readme_regex", r"(?i)^readme(?:.*\.md)?$")))

    actions: Dict[str, Any] = {
        "dry_run": args.dry_run,
        "cleanup_legacy": args.cleanup_legacy,
        "created_dirs": [],
        "migrated_files": [],
        "conflict_files": [],
        "created_seed_files": [],
        "backed_up_legacy_paths": [],
        "removed_legacy_paths": [],
        "warnings": [],
    }

    def ensure_dir(path: Path) -> None:
        if path.is_dir():
            return
        actions["created_dirs"].append(str(path))
        if not args.dry_run:
            path.mkdir(parents=True, exist_ok=True)

    ensure_dir(root)
    for directory in required_dirs:
        ensure_dir(root / directory)
    for directory in optional_dirs:
        ensure_dir(root / directory)
        for child in required_dirs:
            ensure_dir(root / directory / child)

    active_legacy = []
    for legacy in legacy_paths:
        if same_path(legacy, root) or same_path(legacy, skill_root) or not legacy.exists():
            if same_path(legacy, skill_root) and legacy.exists():
                actions["warnings"].append(f"current skill root is not a cleanup target: {legacy}")
            continue
        active_legacy.append(legacy)
        for category in categories:
            for source, relative in iter_category_files(legacy, category, readme_pattern):
                destination = root / category / relative
                if not destination.exists():
                    actions["migrated_files"].append({"from": str(source), "to": str(destination), "mode": "copied"})
                    if not args.dry_run:
                        copy_file_atomic(source, destination)
                elif source.read_bytes() == destination.read_bytes():
                    actions["migrated_files"].append({"from": str(source), "to": str(destination), "mode": "identical-skip"})
                else:
                    conflict = destination.with_name(f"{destination.stem}.migrated.{args.timestamp}{destination.suffix}")
                    actions["conflict_files"].append({"from": str(source), "target": str(destination), "written": str(conflict)})
                    if not args.dry_run:
                        copy_file_atomic(source, conflict)

    legacy_state = project_root / ".state"
    if legacy_state.exists() and not same_path(legacy_state, state_dir):
        active_legacy.append(legacy_state)
        for source in sorted(legacy_state.rglob("*")):
            if not source.is_file():
                continue
            destination = state_dir / source.relative_to(legacy_state)
            if not destination.exists():
                actions["migrated_files"].append({"from": str(source), "to": str(destination), "mode": "state-copied"})
                if not args.dry_run:
                    copy_file_atomic(source, destination)

    for source, relative in iter_seed_files(skill_root):
        destination = root / relative
        if destination.exists():
            continue
        actions["created_seed_files"].append(str(destination))
        if not args.dry_run:
            copy_file_atomic(source, destination)

    gitignore = root / ".gitignore"
    if not gitignore.exists():
        actions["created_seed_files"].append(str(gitignore))
        if not args.dry_run:
            write_text_atomic_if_changed(
                gitignore,
                "# Runtime state (reports, markers, caches, graph snapshots)\n.state/\n",
            )

    cleanup_candidates = list(dict.fromkeys(path.resolve(strict=False) for path in active_legacy))
    if args.cleanup_legacy and cleanup_candidates:
        if args.dry_run:
            actions["backed_up_legacy_paths"] = [
                {"source": str(path), "backup": str(args.backup_dir / "<verified-copy>")}
                for path in cleanup_candidates
            ]
            actions["removed_legacy_paths"] = [str(path) for path in cleanup_candidates]
        else:
            # No source is removed until every complete backup has been copied
            # and independently inventoried.
            actions["backed_up_legacy_paths"] = backup_all(cleanup_candidates, args.backup_dir)
            for path in cleanup_candidates:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(str(path))
                else:
                    path.unlink()
                actions["removed_legacy_paths"].append(str(path))

    status = "PLANNED" if args.dry_run else ("DONE_WITH_CONFLICTS" if actions["conflict_files"] else "DONE")
    counts = {
        key: len(actions[key])
        for key in (
            "created_dirs",
            "migrated_files",
            "conflict_files",
            "created_seed_files",
            "backed_up_legacy_paths",
            "removed_legacy_paths",
            "warnings",
        )
    }
    summary: Dict[str, Any] = {
        "status": status,
        "client": args.client,
        "dry_run": args.dry_run,
        "cleanup_legacy": args.cleanup_legacy,
        "user_data_root": str(root),
        "backup_dir": str(args.backup_dir),
        "counts": counts,
        "next_action": "run doctor",
    }

    if args.dry_run:
        print(json.dumps({"summary": summary, "actions": actions}, ensure_ascii=False, indent=2))
        return 0

    state_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic_if_changed(args.actions, actions)
    write_json_atomic_if_changed(args.summary, summary)
    write_text_atomic_if_changed(args.report, render_report(summary))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run(parse_args()))
    except Exception as exc:  # noqa: BLE001
        print(
            f"Migration stopped safely: {exc}. Legacy cleanup was not started unless every backup had verified.",
            file=sys.stderr,
        )
        raise SystemExit(1)
