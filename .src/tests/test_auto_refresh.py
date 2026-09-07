from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from test_pensieve import PensieveTestCase, REPO_ROOT, tree_snapshot, write_text


class AutomaticRefreshBoundaryTests(PensieveTestCase):
    def env(self, project=None):
        environment = super().env(project)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["CLAUDE_CONFIG_DIR"] = str(self.case_root / "claude-config")
        return environment

    def memory(self, project: Path) -> Path:
        data = project / ".pensieve"
        (data / ".state").mkdir(parents=True)
        write_text(
            data / "short-term/knowledge/example/content.md",
            "---\nid: example\ntype: knowledge\ntitle: Example\nstatus: draft\n"
            "created: 2026-09-08\nupdated: 2026-09-08\ntags: [fixture]\n---\n"
            "\n# Example\n\nSynthetic project fact.\n",
        )
        return data

    def bindings(self, project: Path) -> dict[str, str]:
        return {
            "PENSIEVE_PROJECT_ROOT": str(project),
            "PENSIEVE_DATA_ROOT": str(project / ".pensieve"),
            "PENSIEVE_STATE_ROOT": str(project / ".pensieve/.state"),
        }

    def refresh(self, project: Path, *, client="codex", overrides=None, project_only=True):
        environment = self.bindings(project)
        environment.update(overrides or {})
        arguments = ["--client", client, "--event", "self-improve", "--note", "Fixture capture"]
        if project_only:
            arguments.append("--project-only")
        return self.run_script(
            "maintain-project-state.sh", *arguments,
            project=project, extra_env=environment, check=False,
        )

    def memory_file(self, project: Path) -> Path:
        key = str(project)
        for character in (":", "/", "\\", "_"):
            key = key.replace(character, "-")
        return self.case_root / "claude-config/projects" / key / "memory/MEMORY.md"

    def payload(self, client: str, project: Path, relative=".pensieve/short-term/knowledge/example/content.md"):
        if client == "claude":
            tool_input = {"file_path": str(project / relative)}
            tool_name = "Write"
        else:
            tool_input = {"command": f"*** Begin Patch\n*** Add File: {project / relative}\n+fixture\n*** End Patch"}
            tool_name = "apply_patch"
        return {
            "cwd": str(project), "tool_name": tool_name,
            "tool_input": tool_input, "tool_response": {"success": True},
        }

    def test_project_only_refresh_preserves_claude_memory_and_missing_categories(self):
        data = self.memory(self.project)
        note = data / "short-term/knowledge/example/content.md"
        note_before = (note.read_bytes(), note.stat().st_mtime_ns)
        write_text(self.memory_file(self.project), "User-maintained Claude memory.\n")
        config = self.case_root / "claude-config"
        config_before = tree_snapshot(config)

        result = self.refresh(self.project, client="claude")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((data / "state.md").is_file())
        self.assertTrue((data / ".state/pensieve-user-data-graph.md").is_file())
        self.assertEqual(tree_snapshot(config), config_before)
        self.assertEqual((note.read_bytes(), note.stat().st_mtime_ns), note_before)
        for category in ("knowledge", "decisions", "maxims", "pipelines",
                         "short-term/decisions", "short-term/maxims", "short-term/pipelines"):
            self.assertFalse((data / category).exists(), category)

    def test_legacy_claude_refresh_still_updates_its_routing_memory(self):
        self.memory(self.project)
        memory_file = self.memory_file(self.project)
        write_text(memory_file, "Keep this user-authored content.\n")

        result = self.refresh(self.project, client="claude", project_only=False)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Keep this user-authored content.", memory_file.read_text())
        self.assertIn("<!-- pensieve:auto-memory:start -->", memory_file.read_text())

    def test_hook_binds_actual_project_and_ignores_other_project_overrides(self):
        for client in ("codex", "claude"):
            with self.subTest(client=client):
                actual = self.case_root / client / "actual"
                other = self.case_root / client / "other"
                actual_data = self.memory(actual)
                self.memory(other)
                other_before = tree_snapshot(other)
                write_text(self.memory_file(actual), "Keep Claude routing unchanged.\n")
                config_before = tree_snapshot(self.case_root / "claude-config")

                result = self.hook(
                    client, "post-tool-use", self.payload(client, actual),
                    extra_env=self.bindings(other),
                )

                self.assertEqual(result.stdout, "", result.stdout)
                self.assertEqual(tree_snapshot(other), other_before)
                self.assertTrue((actual_data / "state.md").is_file())
                self.assertIn(str(actual), (actual_data / "state.md").read_text())
                self.assertTrue((actual_data / ".state/pensieve-user-data-graph.md").is_file())
                self.assertEqual(tree_snapshot(self.case_root / "claude-config"), config_before)
                self.assertFalse((actual_data / "decisions").exists())

    def test_project_only_rejects_wrong_data_or_state_binding_before_writes(self):
        for variable, relative in (("PENSIEVE_DATA_ROOT", ".pensieve"),
                                   ("PENSIEVE_STATE_ROOT", ".pensieve/.state")):
            with self.subTest(variable=variable):
                actual = self.case_root / variable / "actual"
                other = self.case_root / variable / "other"
                self.memory(actual)
                self.memory(other)
                before = tree_snapshot(self.case_root)

                result = self.refresh(actual, overrides={variable: str(other / relative)})

                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(tree_snapshot(self.case_root), before)

    def test_project_only_rejects_redirected_memory_and_output_paths_before_writes(self):
        cases = (
            ("memory", ".pensieve", True),
            ("state-directory", ".pensieve/.state", True),
            ("state-file", ".pensieve/state.md", False),
            ("graph-file", ".pensieve/.state/pensieve-user-data-graph.md", False),
            ("ignore-file", ".pensieve/.state/.gitignore", False),
            ("lock-file", ".pensieve/.state/.maintain.lock", False),
            ("lock-directory", ".pensieve/.state/.maintain.lock.d", True),
        )
        for name, relative, directory in cases:
            with self.subTest(path=relative):
                actual = self.case_root / name / "actual"
                outside = self.case_root / name / "outside"
                self.memory(actual)
                self.memory(outside)
                target = actual / relative
                destination = outside / relative
                if directory:
                    destination.mkdir(parents=True, exist_ok=True)
                    if relative == ".pensieve":
                        target.rename(actual / "original-memory")
                    elif target.exists():
                        target.rmdir()
                else:
                    write_text(destination, "External file must remain unchanged.\n")
                target.symlink_to(destination, target_is_directory=directory)
                before = tree_snapshot(self.case_root)

                result = self.refresh(actual)

                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(tree_snapshot(self.case_root), before)

    def test_hook_rejects_state_link_to_existing_project_knowledge_without_writes(self):
        for client in ("codex", "claude"):
            with self.subTest(client=client):
                actual = self.case_root / client / "actual"
                data = self.memory(actual)
                existing_note = data / "knowledge/existing/content.md"
                write_text(existing_note, "Existing knowledge must not become generated state.\n")
                (data / "state.md").symlink_to(existing_note)
                before = tree_snapshot(self.case_root)

                result = self.hook(client, "post-tool-use", self.payload(client, actual))

                self.assertIn("refresh failed", result.stdout)
                self.assertEqual(tree_snapshot(self.case_root), before)

    def test_project_only_does_not_initialize_missing_memory_root(self):
        before = tree_snapshot(self.case_root)

        result = self.refresh(self.project)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(tree_snapshot(self.case_root), before)
        self.assertFalse((self.project / ".pensieve").exists())

    def test_unavailable_graph_generator_rejects_before_writes_or_placeholder(self):
        plugin = self.case_root / "plugin"
        shutil.copytree(str(REPO_ROOT / ".src"), str(plugin / ".src"))
        generator = plugin / ".src/scripts/generate-user-data-graph.sh"
        data = self.memory(self.project)
        outside = self.case_root / "existing-fact.md"
        write_text(outside, "Existing fact must never become a placeholder.\n")
        os.link(str(outside), str(data / ".state/pensieve-user-data-graph.md"))
        for unavailable in ("not executable", "missing"):
            with self.subTest(unavailable=unavailable):
                if unavailable == "missing":
                    generator.unlink()
                else:
                    generator.chmod(0o644)
                before = tree_snapshot(self.case_root)
                environment = self.env()
                environment.update(self.bindings(self.project))
                result = subprocess.run(
                    ["bash", str(plugin / ".src/scripts/maintain-project-state.sh"),
                     "--project-only", "--client", "codex", "--event", "self-improve"],
                    cwd=str(self.project), env=environment, capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("graph generator", result.stderr)
                self.assertEqual(tree_snapshot(self.case_root), before)

    def test_project_only_rejects_shared_in_place_outputs_before_writes(self):
        for name in (".gitignore", ".maintain.lock"):
            with self.subTest(name=name):
                actual = self.case_root / name / "actual"
                data = self.memory(actual)
                existing_note = data / "knowledge/existing/content.md"
                write_text(existing_note, "Existing knowledge must not be truncated through a hard link.\n")
                os.link(str(existing_note), str(data / ".state" / name))
                before = tree_snapshot(self.case_root)

                result = self.refresh(actual)

                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("hard link", result.stderr)
                self.assertEqual(tree_snapshot(self.case_root), before)

    def test_project_only_does_not_initialize_missing_state_root(self):
        (self.project / ".pensieve").mkdir()
        before = tree_snapshot(self.case_root)

        result = self.refresh(self.project)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(tree_snapshot(self.case_root), before)
        self.assertFalse((self.project / ".pensieve/.state").exists())

    def test_ordinary_code_hook_does_not_refresh_memory_or_other_project(self):
        self.memory(self.project)
        other = self.case_root / "other"
        self.memory(other)
        for client in ("codex", "claude"):
            with self.subTest(client=client):
                before = tree_snapshot(self.case_root)

                result = self.hook(
                    client, "post-tool-use", self.payload(client, self.project, "src/main.py"),
                    extra_env=self.bindings(other),
                )

                self.assertEqual(result.stdout, "")
                self.assertEqual(tree_snapshot(self.case_root), before)
