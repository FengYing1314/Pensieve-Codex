from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = REPO_ROOT / ".src" / "core"
SCRIPTS_ROOT = REPO_ROOT / ".src" / "scripts"
FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(CORE_ROOT))

import hook_runtime  # noqa: E402
import pensieve_core  # noqa: E402


TEST_TMP_ROOT = Path(
    os.environ.get("PENSIEVE_TEST_TMPDIR", str(Path.home() / ".cache" / "pensieve-tests"))
)
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    write_text(path, json.dumps(dict(value), ensure_ascii=False, indent=2) + "\n")


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_snapshot(root: Path) -> tuple:
    items = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            items.append((relative, "symlink", os.readlink(str(path))))
        elif path.is_file():
            stat = path.stat()
            items.append((relative, "file", stat.st_mode, stat.st_mtime_ns, file_digest(path)))
        else:
            items.append((relative, "dir"))
    return tuple(items)


class PensieveTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="case-", dir=str(TEST_TMP_ROOT))
        self.case_root = Path(self._temporary.name)
        self.project = self.case_root / "项目"
        self.home = self.case_root / "home"
        self.project.mkdir()
        self.home.mkdir()

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def env(self, project: Optional[Path] = None) -> Dict[str, str]:
        value = os.environ.copy()
        for key in (
            "CLAUDE_PROJECT_DIR",
            "CLAUDE_PLUGIN_ROOT",
            "CLAUDE_CONFIG_DIR",
            "PLUGIN_ROOT",
            "CODEX_HOME",
            "PENSIEVE_CLIENT",
            "PENSIEVE_DATA_ROOT",
            "PENSIEVE_STATE_ROOT",
            "PENSIEVE_SOURCE_ROOT",
        ):
            value.pop(key, None)
        value.update(
            {
                "HOME": str(self.home),
                "PENSIEVE_PROJECT_ROOT": str(project or self.project),
                "PENSIEVE_SKILL_ROOT": str(REPO_ROOT),
                "PYTHONIOENCODING": "utf-8",
            }
        )
        return value

    def run_script(
        self,
        name: str,
        *arguments: str,
        project: Optional[Path] = None,
        check: bool = True,
        input_text: Optional[str] = None,
        extra_env: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        selected_project = project or self.project
        environment = self.env(selected_project)
        if extra_env:
            environment.update(extra_env)
        return subprocess.run(
            ["bash", str(SCRIPTS_ROOT / name), *arguments],
            cwd=str(selected_project),
            env=environment,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def init(self, client: str = "codex", project: Optional[Path] = None) -> None:
        self.run_script("init-project-data.sh", "--client", client, project=project)

    def hook(
        self,
        client: str,
        event: str,
        payload: Mapping[str, Any],
        *,
        extra_env: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        environment = self.env()
        if extra_env:
            environment.update(extra_env)
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_ROOT / "run-client-hook.py"),
                "--client",
                client,
                "--event",
                event,
            ],
            cwd=str(self.project),
            env=environment,
            input=json.dumps(dict(payload), ensure_ascii=False),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def fixture(self, name: str) -> Dict[str, Any]:
        raw = (FIXTURES_ROOT / name).read_text(encoding="utf-8")
        return json.loads(raw.replace("__PROJECT__", str(self.project)))


class ClientAndPathTests(PensieveTestCase):
    def shell_client(self, requested: str = "auto", **extra_env: str) -> str:
        environment = self.env()
        environment.update(extra_env)
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$PENSIEVE_SKILL_ROOT/.src/scripts/lib.sh"; pensieve_client "$1" "$PWD"',
                "pensieve-client-test",
                requested,
            ],
            cwd=str(self.project),
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return result.stdout.strip()

    def test_client_detection_and_aliases(self) -> None:
        self.assertEqual(hook_runtime.normalize_client("agent"), "codex")
        self.assertEqual(hook_runtime.normalize_client("agents"), "codex")
        self.assertEqual(self.shell_client("agents"), "codex")
        self.assertEqual(self.shell_client(PLUGIN_ROOT="/plugin"), "codex")
        self.assertEqual(self.shell_client(CLAUDE_PROJECT_DIR=str(self.project)), "claude")
        self.assertEqual(self.shell_client(CLAUDE_PLUGIN_ROOT="/plugin"), "claude")
        self.assertEqual(self.shell_client(CODEX_HOME=str(self.home / ".codex")), "codex")
        self.assertEqual(self.shell_client(), "generic")
        self.assertEqual(self.shell_client("both", PLUGIN_ROOT="/plugin"), "both")
        with self.assertRaises(ValueError):
            hook_runtime.normalize_client("unknown")

    def test_codex_native_root_wins_compatibility_alias(self) -> None:
        self.assertEqual(
            self.shell_client(
                PLUGIN_ROOT="/codex/plugin",
                CLAUDE_PLUGIN_ROOT="/codex/plugin",
            ),
            "codex",
        )

    def test_unicode_nested_project_prefers_nearest_pensieve(self) -> None:
        outer = self.project
        inner = outer / "服务" / "支付"
        nested = inner / "src" / "模块"
        (outer / ".pensieve").mkdir()
        (inner / ".pensieve").mkdir(parents=True)
        nested.mkdir(parents=True)
        self.assertEqual(hook_runtime.find_pensieve_project(nested), inner.resolve())

    def test_non_git_project_root_falls_back_to_cwd(self) -> None:
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$PENSIEVE_SKILL_ROOT/.src/scripts/lib.sh"; project_root "$PWD"',
            ],
            cwd=str(self.project),
            env=self.env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        self.assertEqual(Path(result.stdout.strip()), self.project)

    def test_hook_launcher_uses_its_own_installation_without_explicit_root(self) -> None:
        decoy = self.home / ".claude" / "skills" / "pensieve" / ".src" / "scripts"
        write_text(decoy / "run-client-hook.py", 'print("WRONG INSTALLATION")\n')
        environment = self.env()
        environment.pop("PENSIEVE_SKILL_ROOT", None)
        result = subprocess.run(
            [
                "bash",
                str(SCRIPTS_ROOT / "run-hook.sh"),
                "run-client-hook.py",
                "--client",
                "codex",
                "--event",
                "session-start",
            ],
            cwd=str(self.project),
            env=environment,
            input=json.dumps({"cwd": str(self.project), "hook_event_name": "SessionStart"}),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        self.assertEqual(result.stdout, "")

    def test_claude_memory_key_uses_canonical_nested_project_root(self) -> None:
        stale = self.case_root / "outer-project"
        stale.mkdir()
        config_root = self.case_root / "claude-config"
        environment = self.env()
        environment.update(
            {
                "CLAUDE_PROJECT_DIR": str(stale),
                "CLAUDE_CONFIG_DIR": str(config_root),
            }
        )
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$PENSIEVE_SKILL_ROOT/.src/scripts/lib.sh"; auto_memory_file "$PWD"',
            ],
            cwd=str(self.project),
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        encoded = str(self.project)
        for character in (":", "/", "\\", "_"):
            encoded = encoded.replace(character, "-")
        self.assertEqual(
            Path(result.stdout.strip()),
            config_root / "projects" / encoded / "memory" / "MEMORY.md",
        )


class HookParityTests(PensieveTestCase):
    def setUp(self) -> None:
        super().setUp()
        (self.project / ".pensieve" / ".state").mkdir(parents=True)

    def marker(self, *, initialized: bool = True, checked: str = "1.4.0") -> None:
        write_json(
            self.project / ".pensieve" / ".state" / "pensieve-session-marker.json",
            {
                "schema_version": 1,
                "initialized": initialized,
                "skill_version": "1.4.0",
                "self_check_version": checked,
            },
        )

    def test_session_start_scenarios(self) -> None:
        # Uninitialized project memory.
        semantics = hook_runtime.session_semantics(self.project, "1.4.0")
        self.assertIn("initialization is not recorded", semantics.additional_context)

        # Seed-only and healthy: no injection.
        self.marker()
        write_text(self.project / ".pensieve" / "maxims" / "seed.md", "# seed\n")
        self.assertIsNone(hook_runtime.session_semantics(self.project, "1.4.0"))

        # Existing knowledge and healthy: still no injection.
        write_text(self.project / ".pensieve" / "knowledge" / "api" / "content.md", "# API\n")
        self.assertIsNone(hook_runtime.session_semantics(self.project, "1.4.0"))

        # Due short-term memory: one concise reminder.
        write_text(
            self.project / ".pensieve" / "short-term" / "knowledge" / "old.md",
            "---\ncreated: 2020-01-01\ntags: [knowledge]\n---\n# Old\n",
        )
        due = hook_runtime.session_semantics(
            self.project,
            "1.4.0",
            today=dt.date(2020, 1, 9),
        )
        self.assertIn("1 of 1", due.additional_context)

        # A version change invalidates the previous doctor marker.
        changed = hook_runtime.session_semantics(self.project, "1.5.0")
        self.assertIn("stale for version 1.5.0", changed.additional_context)

    def test_paired_session_and_subagent_contexts_are_equal(self) -> None:
        claude_session = self.hook("claude", "session-start", self.fixture("claude-session-start.json"))
        codex_session = self.hook("codex", "session-start", self.fixture("codex-session-start.json"))
        claude_session_json = json.loads(claude_session.stdout)
        codex_session_json = json.loads(codex_session.stdout)
        self.assertEqual(
            claude_session_json["hookSpecificOutput"]["additionalContext"],
            codex_session_json["hookSpecificOutput"]["additionalContext"],
        )
        self.assertEqual(claude_session_json["systemMessage"], codex_session_json["systemMessage"])

        claude_agent = self.hook("claude", "subagent-start", self.fixture("claude-subagent-start.json"))
        codex_agent = self.hook("codex", "subagent-start", self.fixture("codex-subagent-start.json"))
        claude_agent_json = json.loads(claude_agent.stdout)
        codex_agent_json = json.loads(codex_agent.stdout)
        claude_context = claude_agent_json["hookSpecificOutput"]["additionalContext"]
        codex_context = codex_agent_json["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(claude_context, codex_context)
        self.assertLess(len(codex_context.split()), 500)

        legacy = self.hook(
            "claude",
            "subagent-start",
            self.fixture("claude-legacy-pre-tool-use.json"),
        )
        legacy_output = json.loads(legacy.stdout)["hookSpecificOutput"]
        legacy_context = legacy_output["updatedInput"]["prompt"].split("\n\n---\n\n", 1)[0]
        self.assertEqual(legacy_context, codex_context)
        self.assertNotIn("permissionDecision", legacy_output)

    def test_hook_uses_payload_cwd_and_ignores_stale_project_environment(self) -> None:
        self.marker()
        other = self.case_root / "stale-project"
        write_json(
            other / ".pensieve" / ".state" / "pensieve-session-marker.json",
            {
                "schema_version": 1,
                "initialized": False,
                "skill_version": "1.4.0",
                "self_check_version": "",
            },
        )
        result = self.hook(
            "codex",
            "session-start",
            self.fixture("codex-session-start.json"),
            extra_env={"PENSIEVE_PROJECT_ROOT": str(other)},
        )
        self.assertEqual(result.stdout, "")

    def test_paired_edit_fixtures_resolve_identical_paths(self) -> None:
        claude_payload = self.fixture("claude-post-tool-use.json")
        codex_payload = self.fixture("codex-post-tool-use.json")
        claude = hook_runtime.post_tool_semantics(
            claude_payload,
            "claude",
            cwd=self.project,
            project_root=self.project,
        )
        codex = hook_runtime.post_tool_semantics(
            codex_payload,
            "codex",
            cwd=self.project,
            project_root=self.project,
        )
        self.assertEqual(claude.changed_paths, codex.changed_paths)
        self.assertEqual(
            codex.changed_paths,
            (
                "knowledge/payments/content.md",
                "maxims/stable-api.md",
                "short-term/decisions/retry-policy.md",
            ),
        )

    def test_codex_patch_add_update_delete_move_and_regular_code_filter(self) -> None:
        command = """*** Begin Patch
*** Add File: .pensieve/maxims/新增.md
+new
*** Update File: .pensieve/decisions/current.md
@@
-old
+new
*** Delete File: .pensieve/pipelines/obsolete.md
*** Update File: .pensieve/knowledge/old/content.md
*** Move to: .pensieve/knowledge/new/content.md
*** Update File: src/main.py
@@
-a
+b
*** End Patch"""
        payload = {
            "tool_name": "apply_patch",
            "tool_input": {"command": command},
            "tool_response": {"success": True},
        }
        semantics = hook_runtime.post_tool_semantics(
            payload,
            "codex",
            cwd=self.project,
            project_root=self.project,
        )
        self.assertEqual(
            semantics.changed_paths,
            (
                "decisions/current.md",
                "knowledge/new/content.md",
                "knowledge/old/content.md",
                "maxims/新增.md",
                "pipelines/obsolete.md",
            ),
        )
        regular = dict(payload)
        regular["tool_input"] = {"command": "*** Begin Patch\n*** Update File: src/main.py\n*** End Patch"}
        self.assertIsNone(
            hook_runtime.post_tool_semantics(
                regular,
                "codex",
                cwd=self.project,
                project_root=self.project,
            )
        )

    def test_codex_patch_paths_are_resolved_from_nested_hook_cwd(self) -> None:
        nested = self.project / "backend" / "src"
        nested.mkdir(parents=True)
        payload = {
            "tool_name": "apply_patch",
            "tool_input": {
                "command": "*** Begin Patch\n*** Update File: ../../.pensieve/knowledge/api/content.md\n*** End Patch"
            },
            "tool_response": {"success": True},
        }
        semantics = hook_runtime.post_tool_semantics(
            payload,
            "codex",
            cwd=nested,
            project_root=self.project,
        )
        self.assertIsNotNone(semantics)
        self.assertEqual(semantics.changed_paths, ("knowledge/api/content.md",))

    def test_no_project_memory_is_silent(self) -> None:
        shutil.rmtree(str(self.project / ".pensieve"))
        codex = self.hook("codex", "session-start", self.fixture("codex-session-start.json"))
        self.assertEqual(codex.stdout, "")
        claude = self.hook("claude", "subagent-start", self.fixture("claude-subagent-start.json"))
        self.assertEqual(claude.stdout, "")


class InstructionSyncTests(PensieveTestCase):
    def test_malformed_second_target_prevents_all_writes(self) -> None:
        self.init("codex")
        start = pensieve_core.INSTRUCTION_START
        end = pensieve_core.INSTRUCTION_END
        malformed = [start, end, end + "\n" + start,
                     start + "\n" + start + "\n" + end + "\n" + end,
                     "prefix " + start + "\n" + end,
                     start + "\n" + end + " suffix",
                     start + "\nOLD\n" + end + "\rUSER\n"]
        for content in malformed:
            with self.subTest(content=content):
                write_text(self.project / "CLAUDE.md", "User text\n")
                write_text(self.project / "AGENTS.md", content + "\nKEEP THIS\n")
                before = tree_snapshot(self.project)
                result = self.run_script("sync-instructions.sh", "--client", "both", check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("AGENTS.md", result.stderr)
                self.assertNotIn("sync completed", result.stdout)
                self.assertEqual(tree_snapshot(self.project), before)

    def test_region_bytes_newlines_eof_and_repeat_are_preserved(self) -> None:
        self.init("codex")
        target = self.project / "AGENTS.md"
        for newline in (b"\n", b"\r\n"):
            for trailing in (b"", newline):
                with self.subTest(newline=newline, trailing=trailing):
                    prefix = "用户前言".encode() + newline
                    suffix = newline + b"USER SUFFIX" + trailing
                    original = prefix + pensieve_core.INSTRUCTION_START.encode() + newline + b"OLD" + newline + pensieve_core.INSTRUCTION_END.encode() + newline + suffix
                    target.write_bytes(original)
                    self.run_script("sync-instructions.sh", "--client", "codex")
                    result = target.read_bytes()
                    self.assertTrue(result.startswith(prefix))
                    self.assertTrue(result.endswith(suffix))
                    self.assertEqual(result.count(pensieve_core.INSTRUCTION_START.encode()), 1)
                    if newline == b"\r\n":
                        self.assertNotIn(b"\n", result.replace(b"\r\n", b""))
                    before = tree_snapshot(self.project)
                    self.run_script("sync-instructions.sh", "--client", "codex")
                    self.assertEqual(tree_snapshot(self.project), before)
        target.write_bytes(pensieve_core.INSTRUCTION_START.encode() + b"\nOLD\n" + pensieve_core.INSTRUCTION_END.encode())
        self.run_script("sync-instructions.sh", "--client", "codex")
        self.assertFalse(target.read_bytes().endswith(b"\n"))

    def test_append_preserves_existing_bytes_and_eof(self) -> None:
        self.init("codex")
        target = self.project / "AGENTS.md"
        for original in (b"", b"USER", b"USER\n", b"USER\r\n"):
            target.write_bytes(original)
            self.run_script("sync-instructions.sh", "--client", "codex")
            result = target.read_bytes()
            self.assertTrue(result.startswith(original))
            self.assertEqual(result.endswith(b"\n"), not original or original.endswith(b"\n"))

    def test_invalid_file_targets_fail_before_writing(self) -> None:
        self.init("codex")
        first = self.project / "AGENTS.md"
        write_text(first, "USER\n")
        directory = self.project / "directory"
        directory.mkdir()
        dangling = self.project / "dangling"
        dangling.symlink_to("missing")
        loop = self.project / "loop"
        loop.symlink_to("loop")
        for invalid in (directory, dangling, loop):
            before = tree_snapshot(self.project)
            result = self.run_script("sync-instructions.sh", "--client", "codex", "--file", str(first), "--file", str(invalid), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(tree_snapshot(self.project), before)

    def test_changed_target_is_not_overwritten_after_preflight(self) -> None:
        self.init("codex")
        first, second = self.project / "one.md", self.project / "two.md"
        write_text(first, "ONE\n")
        write_text(second, "TWO\n")
        real_write = hook_runtime.write_text_atomic_if_changed
        def concurrent_edit(path, content):
            result = real_write(path, content)
            if path == first:
                second.write_text("USER EDIT\n", encoding="utf-8")
            return result
        with patch.object(hook_runtime, "write_text_atomic_if_changed", side_effect=concurrent_edit):
            with self.assertRaises(pensieve_core.InstructionSyncError) as error:
                pensieve_core.sync_instruction_targets(self.project / ".pensieve", [first, second])
        self.assertIn("changed after preflight", str(error.exception))
        self.assertIn("Written: " + str(first), str(error.exception))
        self.assertIn("Not written: " + str(second), str(error.exception))
        self.assertEqual(second.read_text(), "USER EDIT\n")

    def test_write_failure_reports_partial_progress(self) -> None:
        self.init("codex")
        first, second = self.project / "one.md", self.project / "two.md"
        write_text(first, "ONE\n")
        write_text(second, "TWO\n")
        real_write = hook_runtime.write_text_atomic_if_changed
        def fail_second(path, content):
            if path == second:
                raise OSError("simulated write failure")
            return real_write(path, content)
        with patch.object(hook_runtime, "write_text_atomic_if_changed", side_effect=fail_second):
            with self.assertRaises(pensieve_core.InstructionSyncError) as error:
                pensieve_core.sync_instruction_targets(self.project / ".pensieve", [first, second])
        self.assertIn("Written: " + str(first), str(error.exception))
        self.assertIn("Not written: " + str(second), str(error.exception))
        self.assertEqual(second.read_text(), "TWO\n")

    def test_existing_routes_match_doctor_without_copying_pipeline_content(self) -> None:
        self.init("codex")
        pipeline_dir = self.project / ".pensieve" / "pipelines"
        for count in (3, 2, 1, 0):
            present = list(pipeline_dir.glob("run-when-*.md"))
            while len(present) > count:
                present.pop().unlink()
            for item in present:
                with item.open("a") as stream:
                    stream.write("\nCUSTOM WORKFLOW BODY\n")
            before = tree_snapshot(self.project)
            result = self.run_script("sync-instructions.sh", "--client", "codex", check=False)
            if count == 0:
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(tree_snapshot(self.project), before)
            else:
                self.assertEqual(result.returncode, 0, result.stderr)
                content = (self.project / "AGENTS.md").read_text()
                self.assertNotIn("CUSTOM WORKFLOW BODY", content)
                self.assertEqual(content.count(".pensieve/pipelines/"), count)
            scan = self.run_script("scan-structure.sh", "--client", "codex", "--format", "json", "--output", "-")
            findings = json.loads(scan.stdout)["findings"]
            self.assertFalse(any(item["id"] in {"STR-702", "STR-703"} for item in findings))

    def test_default_codex_target_preserves_other_client_file_mode_and_mtime(self) -> None:
        self.init("codex")
        agents = self.project / "AGENTS.md"
        claude = self.project / "CLAUDE.md"
        write_text(agents, "# Existing Codex guidance\n")
        write_text(claude, "# Existing Claude guidance\n")
        agents.chmod(0o664)
        claude_before = tree_snapshot(claude.parent)

        first = self.run_script("sync-instructions.sh", "--client", "codex")
        self.assertIn("AGENTS.md: updated", first.stdout)
        self.assertIn("pensieve:instructions:start", agents.read_text(encoding="utf-8"))
        self.assertEqual(agents.stat().st_mode & 0o777, 0o664)
        self.assertEqual(claude.read_text(encoding="utf-8"), "# Existing Claude guidance\n")

        first_mtime = agents.stat().st_mtime_ns
        second = self.run_script("sync-instructions.sh", "--client", "codex")
        self.assertIn("AGENTS.md: unchanged", second.stdout)
        self.assertEqual(agents.stat().st_mtime_ns, first_mtime)
        self.assertEqual(
            [item for item in claude_before if item[0] == "CLAUDE.md"],
            [item for item in tree_snapshot(claude.parent) if item[0] == "CLAUDE.md"],
        )
        self.assertFalse((self.home / ".claude").exists())

    def test_empty_existing_target_keeps_mode(self) -> None:
        self.init("codex")
        agents = self.project / "AGENTS.md"
        write_text(agents, "")
        agents.chmod(0o640)
        self.run_script("sync-instructions.sh", "--client", "codex")
        self.assertEqual(agents.stat().st_mode & 0o777, 0o640)

    def test_generic_auto_does_not_create_both_instruction_files(self) -> None:
        self.init("generic")
        result = self.run_script("sync-instructions.sh", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No instruction targets resolved", result.stderr)
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / "CLAUDE.md").exists())

    def test_atomic_text_update_preserves_existing_permissions(self) -> None:
        target = self.project / "notes.md"
        write_text(target, "before\n")
        target.chmod(0o664)
        self.assertTrue(hook_runtime.write_text_atomic_if_changed(target, "after\n"))
        self.assertEqual(target.stat().st_mode & 0o777, 0o664)
        mtime = target.stat().st_mtime_ns
        self.assertFalse(hook_runtime.write_text_atomic_if_changed(target, "after\n"))
        self.assertEqual(target.stat().st_mtime_ns, mtime)

    def test_atomic_text_update_preserves_symbolic_link(self) -> None:
        target = self.project / "shared" / "AGENTS.md"
        link = self.project / "AGENTS.md"
        write_text(target, "before\n")
        link.symlink_to(target.relative_to(self.project))
        self.assertTrue(hook_runtime.write_text_atomic_if_changed(link, "after\n"))
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_text(encoding="utf-8"), "after\n")


class DoctorIsolationTests(PensieveTestCase):
    def test_codex_checks_only_agents_and_require_integration_changes_severity(self) -> None:
        self.init("codex")
        default = self.run_script(
            "run-doctor.sh",
            "--client",
            "codex",
            "--strict",
            "--skip-maintain-state",
        )
        self.assertEqual(default.returncode, 0)
        scan_path = self.project / ".pensieve" / ".state" / "pensieve-structure-scan.json"
        scan = json.loads(scan_path.read_text(encoding="utf-8"))
        serialized = json.dumps(scan["findings"], ensure_ascii=False)
        self.assertIn("AGENTS.md", serialized)
        self.assertNotIn("CLAUDE.md", serialized)
        self.assertNotIn("MEMORY.md", serialized)
        self.assertEqual(scan["summary"]["must_fix_count"], 0)

        required = self.run_script(
            "run-doctor.sh",
            "--client",
            "codex",
            "--require-integration",
            "--strict",
            "--skip-maintain-state",
            check=False,
        )
        self.assertEqual(required.returncode, 3)
        report = (
            self.project / ".pensieve" / ".state" / "pensieve-doctor-report.md"
        ).read_text(encoding="utf-8")
        self.assertIn("into AGENTS.md", report)
        self.assertNotIn("CLAUDE.md and AGENTS.md", report)
        self.assertNotIn("MEMORY.md missing/drifted", report)
        self.run_script("sync-instructions.sh", "--client", "codex", "--target", "codex")
        repaired = self.run_script(
            "run-doctor.sh",
            "--client",
            "codex",
            "--require-integration",
            "--strict",
            "--skip-maintain-state",
        )
        self.assertEqual(repaired.returncode, 0)
        self.assertFalse((self.home / ".claude").exists())

    def test_claude_does_not_require_agents(self) -> None:
        self.init("claude")
        self.run_script("sync-instructions.sh", "--client", "claude", "--target", "claude")
        result = self.run_script(
            "run-doctor.sh",
            "--client",
            "claude",
            "--require-integration",
            "--strict",
            "--skip-maintain-state",
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.project / "AGENTS.md").exists())
        scan = json.loads(
            (self.project / ".pensieve" / ".state" / "pensieve-structure-scan.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("AGENTS.md", json.dumps(scan["findings"], ensure_ascii=False))

    def test_customized_seed_is_not_doctor_damage(self) -> None:
        self.init("codex")
        seed = self.project / ".pensieve" / "pipelines" / "run-when-committing.md"
        seed.write_text(seed.read_text(encoding="utf-8") + "\nProject-specific rule.\n", encoding="utf-8")
        self.run_script(
            "run-doctor.sh",
            "--client",
            "codex",
            "--skip-maintain-state",
        )
        scan = json.loads(
            (self.project / ".pensieve" / ".state" / "pensieve-structure-scan.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(any(item["id"] == "STR-202" for item in scan["findings"]))


class ClaudeIntegrationTests(PensieveTestCase):
    def test_installer_replaces_legacy_hook_with_native_event_and_is_idempotent(self) -> None:
        settings_file = self.home / ".claude" / "settings.json"
        unrelated = {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": "/usr/local/bin/unrelated-hook"}],
        }
        unrelated_agent = {
            "matcher": "Agent",
            "hooks": [
                {
                    "type": "command",
                    "command": "/opt/another-tool/run-client-hook.py --client claude",
                }
            ],
        }
        legacy = {
            "matcher": "Agent",
            "hooks": [
                {
                    "type": "command",
                    "command": 'bash "/old/pensieve/run-hook.sh" run-client-hook.py --client claude --event subagent-start',
                }
            ],
        }
        legacy_session = {
            "hooks": [
                {
                    "type": "command",
                    "command": 'bash "/old/pensieve/run-hook.sh" pensieve-session-marker.sh --mode session-start',
                }
            ]
        }
        write_json(
            settings_file,
            {
                "hooks": {
                    "PreToolUse": [unrelated, unrelated_agent, legacy],
                    "SessionStart": [legacy_session],
                },
                "theme": "dark",
            },
        )
        settings_file.chmod(0o640)

        self.run_script("install-hooks.sh")
        installed = json.loads(settings_file.read_text(encoding="utf-8"))
        self.assertEqual(installed["theme"], "dark")
        self.assertEqual(installed["hooks"]["PreToolUse"], [unrelated, unrelated_agent])
        self.assertIn("SubagentStart", installed["hooks"])
        self.assertEqual(installed["hooks"]["SubagentStart"][0]["matcher"], "Explore|Plan")
        self.assertEqual(
            installed["hooks"]["SessionStart"][0]["matcher"],
            "startup|resume|clear|compact",
        )
        self.assertEqual(len(installed["hooks"]["SessionStart"]), 1)
        self.assertTrue(installed["hooks"]["PostToolUse"][0]["hooks"][0]["async"])
        self.assertEqual(settings_file.stat().st_mode & 0o777, 0o640)

        mtime = settings_file.stat().st_mtime_ns
        second = self.run_script("install-hooks.sh")
        self.assertIn("already up to date", second.stdout)
        self.assertEqual(settings_file.stat().st_mtime_ns, mtime)

    def test_installer_honors_claude_config_dir(self) -> None:
        config_root = self.case_root / "custom-claude-config"
        self.run_script(
            "install-hooks.sh",
            extra_env={"CLAUDE_CONFIG_DIR": str(config_root)},
        )
        self.assertTrue((config_root / "settings.json").is_file())
        self.assertFalse((self.home / ".claude" / "settings.json").exists())

        self.run_script(
            "init-project-data.sh",
            "--client",
            "claude",
            extra_env={"CLAUDE_CONFIG_DIR": str(config_root)},
        )
        memory_files = list((config_root / "projects").rglob("MEMORY.md"))
        self.assertEqual(len(memory_files), 1)
        self.assertFalse((self.home / ".claude" / "projects").exists())

    def test_invalid_settings_shape_is_preserved(self) -> None:
        settings_file = self.home / ".claude" / "settings.json"
        write_text(settings_file, "[]\n")
        before = tree_snapshot(self.home)
        result = self.run_script("install-hooks.sh", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(tree_snapshot(self.home), before)

    def test_claude_agent_template_is_self_contained_and_has_no_second_memory_authority(self) -> None:
        template = (REPO_ROOT / ".src" / "templates" / "agents" / "pensieve-wand.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("${PENSIEVE_SKILL_ROOT}", template)
        self.assertNotIn("\nmemory:", template)
        self.assertIn("at most five", template)
        self.assertIn("at most two", template)
        self.assertIn("at most ten", template)
        self.assertIn("only knowledge authority", template)


class MigrationSafetyTests(PensieveTestCase):
    def legacy_root(self) -> Path:
        return self.project / ".claude" / "skills" / "pensieve"

    def test_dry_run_zero_writes_and_default_preserves_legacy_and_custom_seed(self) -> None:
        legacy = self.legacy_root()
        write_text(
            legacy / "pipelines" / "run-when-committing.md",
            "---\nname: legacy-custom\ntype: pipeline\nstatus: active\n---\n# Legacy custom\n",
        )
        write_text(legacy / "unknown-user-file.txt", "must survive\n")
        before = tree_snapshot(self.case_root)
        dry = self.run_script("run-migrate.sh", "--client", "codex", "--dry-run")
        self.assertIn('"status": "PLANNED"', dry.stdout)
        self.assertEqual(before, tree_snapshot(self.case_root))
        self.assertFalse((self.project / ".pensieve").exists())

        self.run_script("run-migrate.sh", "--client", "codex")
        target = self.project / ".pensieve" / "pipelines" / "run-when-committing.md"
        self.assertIn("# Legacy custom", target.read_text(encoding="utf-8"))
        self.assertTrue((legacy / "unknown-user-file.txt").is_file())

        customized = target.read_text(encoding="utf-8") + "Project-owned addition.\n"
        target.write_text(customized, encoding="utf-8")
        self.run_script("run-migrate.sh", "--client", "codex")
        self.assertEqual(target.read_text(encoding="utf-8"), customized)
        self.assertTrue(legacy.exists())

    def test_cleanup_requires_verified_full_backup(self) -> None:
        legacy = self.legacy_root()
        write_text(legacy / "knowledge" / "known.md", "known\n")
        write_text(legacy / "unknown.bin", "unknown\n")
        blocker = self.case_root / "backup-blocker"
        write_text(blocker, "not a directory\n")
        failed = self.run_script(
            "run-migrate.sh",
            "--client",
            "codex",
            "--cleanup-legacy",
            "--backup-dir",
            str(blocker / "child"),
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertTrue((legacy / "unknown.bin").is_file())

        backup = self.case_root / "verified-backup"
        self.run_script(
            "run-migrate.sh",
            "--client",
            "codex",
            "--cleanup-legacy",
            "--backup-dir",
            str(backup),
        )
        self.assertFalse(legacy.exists())
        backed_up_unknown = list(backup.rglob("unknown.bin"))
        self.assertEqual(len(backed_up_unknown), 1)
        self.assertEqual(backed_up_unknown[0].read_text(encoding="utf-8"), "unknown\n")

    def test_multiple_legacy_conflicts_get_unique_non_overwriting_files(self) -> None:
        self.init("codex")
        target = self.project / ".pensieve" / "knowledge" / "shared.md"
        write_text(target, "current\n")
        write_text(
            self.project / ".claude" / "skills" / "pensieve" / "knowledge" / "shared.md",
            "from-claude\n",
        )
        write_text(
            self.project / ".agents" / "skills" / "pensieve" / "knowledge" / "shared.md",
            "from-agents\n",
        )

        self.run_script("run-migrate.sh", "--client", "codex")
        conflicts = sorted(target.parent.glob("shared.migrated.*.md"))
        self.assertEqual(len(conflicts), 2)
        self.assertEqual(
            {path.read_text(encoding="utf-8") for path in conflicts},
            {"from-claude\n", "from-agents\n"},
        )
        self.assertEqual(target.read_text(encoding="utf-8"), "current\n")


class UpgradeSafetyTests(PensieveTestCase):
    def git(self, cwd: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *arguments],
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def make_source_repo(self, path: Path) -> None:
        path.mkdir(parents=True)
        self.git(path, "init", "-b", "main")
        self.git(path, "config", "user.name", "Pensieve Tests")
        self.git(path, "config", "user.email", "pensieve-tests@example.invalid")
        write_json(path / ".src" / "manifest.json", {"name": "pensieve", "version": "1.4.0"})
        write_json(path / ".src" / "core" / "schema.json", {"schema_version": 2})
        write_text(path / ".src" / "scripts" / "run-upgrade.sh", "#!/bin/bash\n")
        write_text(path / "SKILL.md", "---\nname: pensieve\n---\n")
        self.git(path, "add", ".")
        self.git(path, "commit", "-m", "initial")

    def test_clean_unrelated_repo_and_nested_checkout_are_rejected(self) -> None:
        unrelated = self.case_root / "unrelated"
        unrelated.mkdir()
        self.git(unrelated, "init", "-b", "main")
        self.git(unrelated, "config", "user.name", "Pensieve Tests")
        self.git(unrelated, "config", "user.email", "pensieve-tests@example.invalid")
        write_json(unrelated / ".src" / "manifest.json", {"name": "another-tool", "version": "1.4.0"})
        self.git(unrelated, "add", ".")
        self.git(unrelated, "commit", "-m", "unrelated")
        result = self.run_script(
            "run-upgrade.sh",
            "--client",
            "codex",
            "--source-root",
            str(unrelated),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized checkout", result.stderr)

        parent = self.case_root / "parent-repo"
        child = parent / "nested-pensieve"
        parent.mkdir()
        self.git(parent, "init", "-b", "main")
        self.git(parent, "config", "user.name", "Pensieve Tests")
        self.git(parent, "config", "user.email", "pensieve-tests@example.invalid")
        write_json(child / ".src" / "manifest.json", {"name": "pensieve", "version": "1.4.0"})
        write_json(child / ".src" / "core" / "schema.json", {"schema_version": 2})
        write_text(child / ".src" / "scripts" / "run-upgrade.sh", "#!/bin/bash\n")
        write_text(child / "SKILL.md", "---\nname: pensieve\n---\n")
        self.git(parent, "add", ".")
        self.git(parent, "commit", "-m", "nested")
        result = self.run_script(
            "run-upgrade.sh",
            "--client",
            "codex",
            "--source-root",
            str(child),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("subdirectory of another Git repository", result.stderr)
        self.assertFalse((self.project / ".pensieve").exists())

    def test_non_git_and_dirty_checkout_stop_before_project_writes(self) -> None:
        non_git = self.case_root / "not-git"
        non_git.mkdir()
        result = self.run_script(
            "run-upgrade.sh",
            "--client",
            "codex",
            "--source-root",
            str(non_git),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / ".pensieve").exists())

        source = self.case_root / "dirty-source"
        self.make_source_repo(source)
        write_text(source / "untracked.txt", "dirty\n")
        result = self.run_script(
            "run-upgrade.sh",
            "--client",
            "codex",
            "--source-root",
            str(source),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dirty", result.stderr.lower())
        self.assertFalse((self.project / ".pensieve").exists())

    def test_git_backed_codex_cache_is_still_an_immutable_snapshot(self) -> None:
        installed = self.case_root / ".codex" / "plugins" / "cache" / "personal" / "pensieve" / "1.4.0"
        for relative in (
            ".src/scripts/run-upgrade.sh",
            ".src/scripts/lib.sh",
            ".src/core/hook_runtime.py",
            ".src/manifest.json",
        ):
            destination = installed / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(REPO_ROOT / relative), str(destination))
        self.git(installed, "init", "-b", "main")
        self.git(installed, "config", "user.name", "Pensieve Tests")
        self.git(installed, "config", "user.email", "pensieve-tests@example.invalid")
        self.git(installed, "add", ".")
        self.git(installed, "commit", "-m", "snapshot")

        environment = self.env()
        environment["PENSIEVE_SKILL_ROOT"] = str(installed)
        environment["PLUGIN_ROOT"] = str(installed)
        result = subprocess.run(
            ["bash", str(installed / ".src" / "scripts" / "run-upgrade.sh"), "--client", "codex"],
            cwd=str(self.project),
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not updated in place", result.stderr)
        self.assertFalse((self.project / ".pensieve").exists())

    def test_non_fast_forward_never_resets_checkout(self) -> None:
        remote = self.case_root / "remote.git"
        seed = self.case_root / "seed"
        self.make_source_repo(seed)
        self.git(self.case_root, "init", "--bare", str(remote))
        self.git(seed, "remote", "add", "origin", str(remote))
        self.git(seed, "push", "-u", "origin", "main")

        local = self.case_root / "local"
        other = self.case_root / "other"
        self.git(self.case_root, "clone", "--branch", "main", str(remote), str(local))
        self.git(self.case_root, "clone", "--branch", "main", str(remote), str(other))
        for repo in (local, other):
            self.git(repo, "config", "user.name", "Pensieve Tests")
            self.git(repo, "config", "user.email", "pensieve-tests@example.invalid")

        write_text(local / "local.txt", "local\n")
        self.git(local, "add", ".")
        self.git(local, "commit", "-m", "local")
        local_head = self.git(local, "rev-parse", "HEAD").stdout.strip()

        write_text(other / "remote.txt", "remote\n")
        self.git(other, "add", ".")
        self.git(other, "commit", "-m", "remote")
        self.git(other, "push", "origin", "main")

        result = self.run_script(
            "run-upgrade.sh",
            "--client",
            "codex",
            "--source-root",
            str(local),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(local, "rev-parse", "HEAD").stdout.strip(), local_head)
        self.assertFalse((self.project / ".pensieve").exists())
        script = (SCRIPTS_ROOT / "run-upgrade.sh").read_text(encoding="utf-8")
        self.assertNotIn("reset --hard", script)


class ConcurrentStateTests(PensieveTestCase):
    def test_concurrent_sync_is_valid_and_unchanged_content_keeps_mtime(self) -> None:
        self.init("codex")
        environment = self.env()
        commands = []
        for index in range(12):
            commands.append(
                subprocess.Popen(
                    [
                        "bash",
                        str(SCRIPTS_ROOT / "maintain-project-state.sh"),
                        "--client",
                        "codex",
                        "--event",
                        "sync",
                        "--note",
                        f"concurrent-{index}",
                    ],
                    cwd=str(self.project),
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        for process in commands:
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stdout + stderr)

        marker_commands = []
        for _ in range(8):
            marker_commands.append(
                subprocess.Popen(
                    [
                        "bash",
                        str(SCRIPTS_ROOT / "pensieve-session-marker.sh"),
                        "--client",
                        "codex",
                        "--mode",
                        "record",
                        "--event",
                        "sync",
                    ],
                    cwd=str(self.project),
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        for process in marker_commands:
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stdout + stderr)

        state = self.project / ".pensieve" / "state.md"
        graph = self.project / ".pensieve" / ".state" / "pensieve-user-data-graph.md"
        marker = self.project / ".pensieve" / ".state" / "pensieve-session-marker.json"
        state_text = state.read_text(encoding="utf-8")
        graph_text = graph.read_text(encoding="utf-8")
        self.assertEqual(state_text.count("## Lifecycle State"), 1)
        self.assertIn("```mermaid", graph_text)
        self.assertIn("### Summary", graph_text)
        json.loads(marker.read_text(encoding="utf-8"))

        self.run_script(
            "maintain-project-state.sh",
            "--client",
            "codex",
            "--event",
            "sync",
            "--note",
            "idempotent",
        )
        state_mtime = state.stat().st_mtime_ns
        graph_mtime = graph.stat().st_mtime_ns
        self.run_script(
            "maintain-project-state.sh",
            "--client",
            "codex",
            "--event",
            "sync",
            "--note",
            "idempotent",
        )
        self.assertEqual(state.stat().st_mtime_ns, state_mtime)
        self.assertEqual(graph.stat().st_mtime_ns, graph_mtime)


class PluginShapeTests(unittest.TestCase):
    def assert_version_contract(self, version: str, shared: str) -> None:
        self.assertEqual(shared, "1.4.0")
        self.assertRegex(version, r"^" + re.escape(shared) + r"(?:\+codex\.[A-Za-z0-9][A-Za-z0-9._-]*)?\Z")

    def test_version_contract_accepts_build_metadata_but_rejects_drift(self) -> None:
        for version in ("1.4.0", "1.4.0+codex.20260908T000000Z"):
            self.assert_version_contract(version, "1.4.0")
        for version in ("1.5.0", "1.4.0+codex.", "1.4.0+codex.a+codex.b", "1.4.0+other.a", "1.4.0+codex.a b", "1.4.0\n"):
            with self.subTest(version=version), self.assertRaises(AssertionError):
                self.assert_version_contract(version, "1.4.0")

    def test_native_plugin_shape_and_default_hook_discovery(self) -> None:
        manifest = json.loads((REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        shared_manifest = json.loads((REPO_ROOT / ".src" / "manifest.json").read_text(encoding="utf-8"))
        hooks = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.assert_version_contract(manifest["version"], shared_manifest["version"])
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertNotIn("hooks", manifest)
        self.assertEqual(set(hooks["hooks"]), {"SessionStart", "SubagentStart", "PostToolUse"})
        self.assertEqual(
            hooks["hooks"]["SessionStart"][0]["matcher"],
            "startup|resume|clear|compact",
        )
        self.assertTrue(hooks["hooks"]["PostToolUse"][0]["hooks"][0]["async"])
        serialized = json.dumps(hooks)
        self.assertIn("$PLUGIN_ROOT", serialized)
        self.assertTrue((REPO_ROOT / "skills" / "pensieve" / "SKILL.md").is_file())
        self.assertTrue((REPO_ROOT / "skills" / "pensieve-wand" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
