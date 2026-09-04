#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SKILL_ROOT / ".src" / "core"))

import hook_runtime  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Pensieve lifecycle hook adapter.")
    parser.add_argument("--client", required=True, choices=("codex", "claude"))
    parser.add_argument(
        "--event",
        required=True,
        choices=("session-start", "subagent-start", "post-tool-use"),
    )
    return parser.parse_args()


def read_payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def payload_cwd(payload: Mapping[str, Any]) -> Path:
    raw = payload.get("cwd")
    if isinstance(raw, str) and raw.strip():
        return Path(raw)
    return Path.cwd()


def output_json(payload: Mapping[str, Any]) -> None:
    sys.stdout.write(json.dumps(dict(payload), ensure_ascii=False) + "\n")


def maintain_project(client: str, project_root: Path, paths: tuple[str, ...], tool_name: str) -> None:
    maintain = SKILL_ROOT / ".src" / "scripts" / "maintain-project-state.sh"
    if not maintain.is_file():
        return
    note = f"posttooluse {tool_name or 'unknown'}: {', '.join(paths)}"
    env = os.environ.copy()
    env.update(
        {
            "PENSIEVE_CLIENT": client,
            "PENSIEVE_PROJECT_ROOT": str(project_root),
            "PENSIEVE_SKILL_ROOT": str(SKILL_ROOT),
        }
    )
    subprocess.run(
        ["bash", str(maintain), "--client", client, "--event", "sync", "--note", note],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def main() -> int:
    args = parse_args()
    payload = read_payload()
    cwd = payload_cwd(payload)
    explicit = os.environ.get("PENSIEVE_PROJECT_ROOT")
    project_root = hook_runtime.find_pensieve_project(cwd, Path(explicit) if explicit else None)

    if project_root is None:
        if args.client == "claude" and args.event == "subagent-start":
            output_json(hook_runtime.claude_allow_output())
        return 0

    os.environ["PENSIEVE_PROJECT_ROOT"] = str(project_root)
    os.environ["PENSIEVE_SKILL_ROOT"] = str(SKILL_ROOT)
    os.environ["PENSIEVE_CLIENT"] = args.client

    if args.event == "session-start":
        manifest = hook_runtime.read_json_object(SKILL_ROOT / ".src" / "manifest.json")
        version = str(manifest.get("version") or "unknown")
        semantics = hook_runtime.session_semantics(project_root, SKILL_ROOT, version)
        if semantics is not None:
            output_json(hook_runtime.render_context_output(args.client, semantics))
        return 0

    if args.event == "subagent-start":
        if args.client == "claude":
            tool_input = payload.get("tool_input")
            agent_type = tool_input.get("subagent_type") if isinstance(tool_input, Mapping) else ""
            if agent_type not in {"Explore", "Plan"}:
                output_json(hook_runtime.claude_allow_output())
                return 0
        semantics = hook_runtime.subagent_semantics(project_root)
        if semantics is None:
            if args.client == "claude":
                output_json(hook_runtime.claude_allow_output())
            return 0
        if args.client == "claude":
            output_json(hook_runtime.render_claude_subagent_output(payload, semantics))
        else:
            output_json(hook_runtime.render_context_output(args.client, semantics))
        return 0

    semantics = hook_runtime.post_tool_semantics(
        payload,
        args.client,
        cwd=cwd,
        project_root=project_root,
    )
    if semantics is not None:
        tool_name = payload.get("tool_name")
        maintain_project(
            args.client,
            project_root,
            semantics.changed_paths,
            tool_name if isinstance(tool_name, str) else "",
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # Hooks are optional integration. A malformed payload or local runtime issue
        # must never block the user's editing flow.
        raise SystemExit(0)
