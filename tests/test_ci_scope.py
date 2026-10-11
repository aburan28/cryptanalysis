"""Regression cases for CI routing, including real multi-commit Git histories."""

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_scope", REPO / "scripts/ci_scope.py")
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)
SCOPES = json.loads((REPO / ".github/ci/scopes.json").read_text())


class ScopeTests(unittest.TestCase):
    def chosen(self, workflow, *paths):
        return scope.select(SCOPES[workflow], list(paths), workflow)

    def test_root_docs_skip_builds(self):
        for workflow in SCOPES:
            with self.subTest(workflow=workflow):
                self.assertFalse(any(self.chosen(workflow, "README.md", "AGENTS.md", "docs/CONTRIBUTING.md", "papers/draft/paper.pdf").values()))

    def test_c_library_change_reaches_consumers(self):
        self.assertTrue(self.chosen("ci.yml", "src/ffi.c")["build"])
        for job in ("rust", "go", "python", "python-package"):
            self.assertTrue(self.chosen("bindings.yml", "include/cryptanalysis/ca_ffi.h")[job])
        self.assertTrue(self.chosen("suite.yml", "src/ffi.c")["rust"])

    def test_languages_do_not_compile_unrelated_bindings(self):
        go = self.chosen("bindings.yml", "bindings/go/coord.go")
        self.assertTrue(go["go"])
        self.assertFalse(go["rust"])
        self.assertFalse(go["python"])
        engine = self.chosen("suite.yml", "suite/python/indexcalc/requirements-sat.txt")
        self.assertTrue(engine["python-engine"])
        self.assertFalse(engine["f4-kernel"])

    def test_source_dependencies_and_workflow_edits(self):
        self.assertTrue(self.chosen("suite.yml", "suite/Cargo.lock")["rust"])
        self.assertTrue(self.chosen("ci.yml", "CMakeLists.txt")["build"])
        for workflow in SCOPES:
            self.assertTrue(all(self.chosen(workflow, ".github/workflows/" + workflow).values()))
            self.assertTrue(all(self.chosen(workflow, "scripts/ci_scope.py").values()))

    def test_codeql_languages_are_selected_independently(self):
        chosen = self.chosen("codeql.yml", "cloud/fleet.py")
        self.assertTrue(chosen["analyze"])
        self.assertTrue(chosen["python"])
        self.assertFalse(chosen["go"])
        self.assertFalse(chosen["c-cpp"])

    def test_research_proofs_keep_frozen_fixture_dependencies(self):
        self.assertTrue(self.chosen("groebner-early-parity.yml", "experiments/groebner-perf-20260924/round13/results/confirmation.json.gz")["portable"])
        self.assertTrue(self.chosen("groebner-early-parity.yml", "experiments/pdp-scaling/sumpoly.py")["portable"])
        self.assertFalse(self.chosen("reusable-macaulay-layout.yml", "experiments/groebner-perf-20260924/round116/panel.py")["portable"])

    def test_unknown_diff_runs_all_jobs(self):
        for workflow, jobs in SCOPES.items():
            self.assertTrue(all(scope.select(jobs, None, workflow).values()))
        self.assertIsNone(scope.changed_paths("push", {"before": "0" * 40}))
        self.assertIsNone(scope.changed_paths("workflow_dispatch", {}))

    def test_git_globs(self):
        self.assertTrue(scope.matches("src/file.c", "src/**/*.c"))
        self.assertTrue(scope.matches("src/nested/file.c", "src/**/*.c"))
        self.assertFalse(scope.matches("src/nested/file.c", "src/*"))
        self.assertTrue(scope.matches("foo.py", "**/*.py"))

    def test_no_api_changed_file_truncation(self):
        paths = [f"docs/{n}.md" for n in range(3500)] + ["src/ffi.c"]
        self.assertTrue(scope.select(SCOPES["ci.yml"], paths, "ci.yml")["build"])

    def test_scoped_jobs_keep_check_contexts_and_failure_fallback(self):
        for workflow, jobs in SCOPES.items():
            text = (REPO / ".github/workflows" / workflow).read_text()
            self.assertIn("  pull_request:\n", text)
            self.assertIn("  merge_group:\n", text)
            for job in jobs:
                if workflow == "codeql.yml" and job in ("c-cpp", "go", "python"):
                    continue
                start = text.index("  " + job + ":\n")
                rest = text[start:]
                end = re.search(r"\n  [a-zA-Z][a-zA-Z0-9_-]*:\n", rest[1:])
                block = rest[:end.start() + 1] if end else rest
                self.assertIn("    needs: changes\n", block)
                self.assertIn("needs.changes.result != 'success'", block)
                # An absent output is JSON null. Only the exact boolean false
                # permits a skip, while invalid JSON makes the check fail.
                self.assertIn("selected || '{}'", block)
                self.assertIn("!= 'false'", block)
                for line in block.splitlines():
                    if "if:" in line and "needs.changes" in line:
                        self.assertNotIn("always()", line)
                if "      matrix:\n" in block:
                    job_if = re.search(r"^    if: (.+)$", block, re.M).group(1)
                    self.assertNotIn("fromJSON", job_if)


class GitDiffTests(unittest.TestCase):
    def test_multi_commit_push_deleted_paths_and_merge_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
            git("init", "-q")
            git("config", "user.name", "CI fixture")
            git("config", "user.email", "ci@example.invalid")
            (root / "src").mkdir()
            (root / "src/old.c").write_text("int old;\n")
            git("add", ".")
            git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            (root / "src/old.c").unlink()
            (root / "src/new.c").write_text("int newer;\n")
            git("add", "-A")
            git("commit", "-qm", "move source")
            (root / "README.md").write_text("Latest commit is documentation only.\n")
            git("add", ".")
            git("commit", "-qm", "docs")
            with mock.patch.object(scope, "ROOT", root):
                expected = {"README.md", "src/old.c", "src/new.c"}
                self.assertEqual(set(scope.changed_paths("push", {"before": base})), expected)
                self.assertEqual(set(scope.changed_paths("merge_group", {"merge_group": {"base_sha": base}})), expected)


if __name__ == "__main__":
    unittest.main()
