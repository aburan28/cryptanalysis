import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tree  # noqa: E402


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def make_repo(root):
    root = Path(root)
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    (root / ".gitignore").write_text("build/\n*.o\n")
    (root / "src").mkdir()
    (root / "src" / "a.c").write_text("int a;\n")
    (root / "README").write_text("readme\n")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    (root / "src" / "a.c").write_text("int a = 1;\n")      # edited, uncommitted
    (root / "notes.txt").write_text("untracked\n")          # untracked, not ignored
    (root / "build").mkdir()
    (root / "build" / "big.bin").write_bytes(b"x" * 10)     # ignored
    (root / "src" / "a.o").write_bytes(b"obj")              # ignored
    return root


def names(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        return {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}


class PackTest(unittest.TestCase):
    def test_ships_the_working_tree_without_ignored_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            data, summary = tree.pack(root)
            files = names(data)
            self.assertEqual(set(files), {".gitignore", "README", "notes.txt", "src/a.c"})
            self.assertEqual(files["src/a.c"], b"int a = 1;\n")
            self.assertEqual(summary["files"], 4)

    def test_include_ships_an_ignored_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            data, _ = tree.pack(root, include=["build"])
            self.assertIn("build/big.bin", names(data))

    def test_include_outside_the_checkout_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            with self.assertRaises(ValueError):
                tree.pack(root, include=["../elsewhere"])

    def test_large_files_are_skipped_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            (root / "huge.dat").write_bytes(b"y" * 2048)
            data, summary = tree.pack(root, max_file_bytes=1024)
            self.assertNotIn("huge.dat", names(data))
            self.assertEqual(summary["skipped"], ["huge.dat"])

    def test_git_state_reports_uncommitted_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = tree.git_state(make_repo(tmp))
            self.assertTrue(state["dirty"])
            self.assertEqual(len(state["commit"]), 40)


def tarball(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


class MergeTest(unittest.TestCase):
    def test_conflicting_shards_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as dest:
            seen = {}
            tree.merge_outputs(tarball({"r/out.csv": b"a", "r/0.csv": b"zero"}), dest, "shard0", seen)
            written = tree.merge_outputs(tarball({"r/out.csv": b"b", "r/1.csv": b"one"}), dest,
                                         "shard1", seen)
            self.assertEqual(sorted(written), ["r/1.csv", "r/out.csv.shard1"])
            self.assertEqual(Path(dest, "r/out.csv").read_bytes(), b"a")
            self.assertEqual(Path(dest, "r/out.csv.shard1").read_bytes(), b"b")

    def test_identical_outputs_merge_silently(self):
        with tempfile.TemporaryDirectory() as dest:
            seen = {}
            tree.merge_outputs(tarball({"same.txt": b"x"}), dest, "shard0", seen)
            self.assertEqual(tree.merge_outputs(tarball({"same.txt": b"x"}), dest, "shard1", seen),
                             ["same.txt"])
            self.assertFalse(Path(dest, "same.txt.shard1").exists())

    def test_paths_that_escape_dest_are_dropped(self):
        with tempfile.TemporaryDirectory() as outer:
            dest = Path(outer, "dest")
            dest.mkdir()
            written = tree.merge_outputs(tarball({"../evil": b"e", "/abs": b"a", "ok": b"k"}),
                                         dest, "shard0", {})
            self.assertEqual(written, ["ok"])
            self.assertFalse(Path(outer, "evil").exists())
            self.assertEqual(sorted(os.listdir(dest)), ["ok"])


if __name__ == "__main__":
    unittest.main()
