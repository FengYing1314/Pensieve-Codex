from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = REPO_ROOT / ".src" / "core"
SCRIPTS_ROOT = REPO_ROOT / ".src" / "scripts"
FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(CORE_ROOT))

import hook_runtime  # noqa: E402


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

    def hook(self, client: str, event: str, payload: Mapping[str, Any]) -> subprocess.CompletedProcess:
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
            env=self.env(),
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
    def test_client_detection_and_aliases(self) -> None:
        self.assertEqual(hook_runtime.normalize_client("agent"), "codex")
        self.assertEqual(hook_runtime.normalize_client("agents"), "codex")
        self.assertEqual(hook_runtime.detect_client("auto", env={"PLUGIN_ROOT": "/plugin"}), "codex")
        self.assertEqual(
            hook_runtime.detect_client("auto", env={"CLAUDE_PROJECT_DIR": "/project"}),
            "claude",
        )
        self.assertEqual(hook_runtime.detect_client("auto", env={}, skill_root=Path("/opt/tool")), "generic")
        with self.assertRaises(ValueError):
            hook_runtime.normalize_client("unknown")

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
        semantics = hook_runtime.session_semantics(self.project, REPO_ROOT, "1.4.0")
        self.assertIn("initialization is not recorded", semantics.additional_context)

        # Seed-only and healthy: no injection.
        self.marker()
        write_text(self.project / ".pensieve" / "maxims" / "seed.md", "# seed\n")
        self.assertIsNone(hook_runtime.session_semantics(self.project, REPO_ROOT, "1.4.0"))

        # Existing knowledge and healthy: still no injection.
        write_text(self.project / ".pensieve" / "knowledge" / "api" / "content.md", "# API\n")
        self.assertIsNone(hook_runtime.session_semantics(self.project, REPO_ROOT, "1.4.0"))

        # Due short-term memory: one concise reminder.
        write_text(
            self.project / ".pensieve" / "short-term" / "knowledge" / "old.md",
            "---\ncreated: 2020-01-01\ntags: [knowledge]\n---\n# Old\n",
        )
        due = hook_runtime.session_semantics(
            self.project,
            REPO_ROOT,
            "1.4.0",
            today=dt.date(2020, 1, 9),
        )
        self.assertIn("1 of 1", due.additional_context)

        # A version change invalidates the previous doctor marker.
        changed = hook_runtime.session_semantics(self.project, REPO_ROOT, "1.5.0")
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
        claude_context = claude_agent_json["hookSpecificOutput"]["updatedInput"]["prompt"].split(
            "\n\n---\n\n", 1
        )[0]
        codex_context = codex_agent_json["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(claude_context, codex_context)
        self.assertLess(len(codex_context.split()), 500)

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

    def test_no_project_memory_is_silent(self) -> None:
        shutil.rmtree(str(self.project / ".pensieve"))
        codex = self.hook("codex", "session-start", self.fixture("codex-session-start.json"))
        self.assertEqual(codex.stdout, "")
        claude = self.hook("claude", "subagent-start", self.fixture("claude-subagent-start.json"))
        self.assertEqual(
            json.loads(claude.stdout)["hookSpecificOutput"]["permissionDecision"],
            "allow",
        )


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
        self.git(path, "add", ".")
        self.git(path, "commit", "-m", "initial")

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
    def test_native_plugin_shape_and_default_hook_discovery(self) -> None:
        manifest = json.loads((REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        hooks = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.4.0")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertNotIn("hooks", manifest)
        self.assertEqual(set(hooks["hooks"]), {"SessionStart", "SubagentStart", "PostToolUse"})
        serialized = json.dumps(hooks)
        self.assertIn("$PLUGIN_ROOT", serialized)
        self.assertTrue((REPO_ROOT / "skills" / "pensieve" / "SKILL.md").is_file())
        self.assertTrue((REPO_ROOT / "skills" / "pensieve-wand" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
