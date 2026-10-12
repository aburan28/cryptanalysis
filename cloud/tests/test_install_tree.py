"""cloud/install_tree.py: a checkout that changes only where its tree does."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import install_tree  # noqa: E402

OLD = 1_000_000_000 * 10**9  # 2001, older than any build


def write(root, files):
    for name, text in files.items():
        path = Path(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def files_of(root):
    root = Path(root)
    return {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob("*"))
            if p.is_file() and not p.is_symlink()}


def age_everything(root):
    for path in [*Path(root).rglob("*"), Path(root)]:
        os.utime(path, ns=(OLD, OLD), follow_symlinks=False)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.checkout = self.base / "checkout"
        self.first = {"src/a.c": "int a;\n", "src/b.c": "int b;\n", "suite/Cargo.toml": "[x]\n",
                      "old/gone.txt": "gone\n", "README": "readme\n"}
        write(self.base / "t1", self.first)
        install_tree.install(self.base / "t1", self.checkout)
        write(self.checkout, {"suite/target/release/lib.rlib": "built\n"})
        age_everything(self.checkout)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_first_install_copies_the_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            written, removed = install_tree.install(self.base / "t1", Path(tmp, "fresh"))
            self.assertEqual(files_of(Path(tmp, "fresh")), self.first)
            self.assertEqual((written, removed), (5, 0))

    def test_the_same_content_from_another_copy_changes_nothing(self):
        write(self.base / "t2", self.first)   # new files, so new ages
        self.assertEqual(install_tree.install(self.base / "t2", self.checkout), (0, 0))
        for path in [*self.checkout.rglob("*"), self.checkout]:
            self.assertEqual(path.lstat().st_mtime_ns, OLD, path)

    def test_only_what_changed_is_new_and_the_build_tree_stays(self):
        second = dict(self.first, **{"src/a.c": "int a = 2;\n", "src/new.c": "int n;\n"})
        del second["old/gone.txt"]
        write(self.base / "t2", second)
        self.assertEqual(install_tree.install(self.base / "t2", self.checkout), (2, 1))
        self.assertEqual({k: v for k, v in files_of(self.checkout).items()
                          if not k.startswith("suite/target/")}, second)
        self.assertEqual((self.checkout / "suite/target/release/lib.rlib").read_text(), "built\n")
        self.assertGreater((self.checkout / "src/a.c").stat().st_mtime_ns, OLD)
        self.assertEqual((self.checkout / "src/b.c").stat().st_mtime_ns, OLD)
        self.assertFalse((self.checkout / "old").exists())
        # src gained a file, so a build script watching it reruns; suite did not.
        self.assertGreater((self.checkout / "src").stat().st_mtime_ns, OLD)
        self.assertEqual((self.checkout / "suite").stat().st_mtime_ns, OLD)

    def test_a_mode_change_keeps_the_age(self):
        write(self.base / "t2", self.first)
        os.chmod(self.base / "t2" / "README", 0o700)
        self.assertEqual(install_tree.install(self.base / "t2", self.checkout), (0, 0))
        self.assertEqual((self.checkout / "README").stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.checkout / "README").stat().st_mtime_ns, OLD)

    def test_files_and_directories_trade_places(self):
        second = {k: v for k, v in self.first.items() if k != "README"}
        second["README/part.txt"] = "now a directory\n"
        write(self.base / "t2", second)
        install_tree.install(self.base / "t2", self.checkout)
        self.assertEqual((self.checkout / "README/part.txt").read_text(), "now a directory\n")
        write(self.base / "t3", self.first)
        install_tree.install(self.base / "t3", self.checkout)
        self.assertEqual((self.checkout / "README").read_text(), "readme\n")

    def test_symlinks_are_links(self):
        write(self.base / "t2", self.first)
        os.symlink("src/a.c", self.base / "t2" / "link.c")
        install_tree.install(self.base / "t2", self.checkout)
        self.assertEqual(os.readlink(self.checkout / "link.c"), "src/a.c")
        self.assertEqual(install_tree.install(self.base / "t2", self.checkout), (0, 0))


if __name__ == "__main__":
    unittest.main()
