"""cloud/ship.py: a checkout rebuilt from its upstream commit plus the differences,
on this machine, against a local bare repository standing in for GitHub."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import ship  # noqa: E402
import tree  # noqa: E402


def setUpModule():
    # A developer's global config (signing, fsmonitor daemons) has no place in
    # throwaway repositories, and can stall them.
    os.environ["GIT_CONFIG_GLOBAL"] = os.devnull


def tearDownModule():
    os.environ.pop("GIT_CONFIG_GLOBAL", None)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


def make_clone(tmp):
    """A clone with an upstream, then edits: modified, deleted, untracked, ignored,
    and a commit that was never pushed."""
    remote, clone = tmp / "remote.git", tmp / "clone"
    git(tmp, "init", "-q", "--bare", str(remote))
    git(remote, "config", "uploadpack.allowAnySHA1InWant", "true")
    git(tmp, "init", "-q", "-b", "main", str(clone))
    for key, value in (("user.email", "t@example.com"), ("user.name", "t")):
        git(clone, "config", key, value)
    (clone / "src").mkdir()
    (clone / "src" / "a.c").write_text("int a = 1;\n")
    (clone / "b.txt").write_text("deleted later\n")
    (clone / "same.txt").write_text("unchanged\n")
    (clone / ".gitignore").write_text("*.o\n")
    git(clone, "add", ".")
    git(clone, "commit", "-q", "-m", "base")
    git(clone, "remote", "add", "origin", str(remote))
    git(clone, "push", "-q", "-u", "origin", "main")
    pushed = git(clone, "rev-parse", "HEAD")
    (clone / "local.txt").write_text("committed, not pushed\n")
    git(clone, "add", "local.txt")
    git(clone, "commit", "-q", "-m", "local")
    (clone / "src" / "a.c").write_text("int a = 2;\n")
    (clone / "b.txt").unlink()
    (clone / "notes.txt").write_text("untracked\n")
    (clone / "x.o").write_text("ignored\n")
    return clone, remote, pushed


def contents(root):
    root = Path(root)
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file()}


class ShipTest(unittest.TestCase):
    def test_the_plan_sends_only_what_upstream_lacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone, remote, pushed = make_clone(Path(tmp))
            plan = ship.plan(clone, url=str(remote))
            self.assertEqual(plan["base"], pushed)
            self.assertEqual(plan["overlay"], ["local.txt", "notes.txt", "src/a.c"])
            self.assertEqual(plan["deleted"], ["b.txt"])
            self.assertEqual(plan["files"], tree.checkout_files(clone))

    def test_github_origins_lose_their_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            git(tmp, "init", "-q")
            git(tmp, "remote", "add", "origin",
                "https://x-access-token:secret@github.com/owner/repo.git")
            self.assertEqual(ship.public_url(tmp), "https://github.com/owner/repo.git")
            git(tmp, "remote", "set-url", "origin", "git@github.com:owner/repo")
            self.assertEqual(ship.public_url(tmp), "https://github.com/owner/repo.git")
            git(tmp, "remote", "set-url", "origin", "https://gitlab.com/owner/repo.git")
            self.assertIsNone(ship.public_url(tmp))

    def test_the_tree_built_over_upstream_is_the_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            clone, remote, pushed = make_clone(tmp)
            env = {**os.environ, "SHIP_CACHE": str(tmp / "cache.git")}
            for dest in (tmp / "first", tmp / "again"):
                summary = ship.ship(None, clone, str(dest), env=env, url=str(remote))
                self.assertEqual(summary["returncode"], 0)
                self.assertEqual((summary["base"], summary["sent_files"]), (pushed, 3))
                self.assertEqual(contents(dest),
                                 {n: (clone / n).read_bytes() for n in tree.checkout_files(clone)})

    def test_an_unreachable_upstream_falls_back_to_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            clone, _, _ = make_clone(tmp)
            env = {**os.environ, "SHIP_CACHE": str(tmp / "cache.git")}
            notes = []
            summary = ship.ship(None, clone, str(tmp / "dest"), env=env,
                                url=str(tmp / "nowhere.git"), log=notes.append)
            self.assertEqual(summary["returncode"], 0)
            self.assertIsNone(summary["base"])
            self.assertTrue(any("sending all of it" in n for n in notes), notes)
            self.assertEqual(contents(tmp / "dest"),
                             {n: (clone / n).read_bytes() for n in tree.checkout_files(clone)})

    def test_a_new_pod_is_told_which_commit_to_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone, _, pushed = make_clone(Path(tmp))
            self.assertEqual(ship.prefetch_env(clone), {})   # origin is not on GitHub
            git(clone, "remote", "set-url", "origin", "https://github.com/owner/repo.git")
            self.assertEqual(ship.prefetch_env(clone),
                             {"SHIP_PREFETCH": f"https://github.com/owner/repo.git {pushed}"})

    def test_a_ship_builds_on_what_the_boot_fetch_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            clone, remote, pushed = make_clone(tmp)
            env = {**os.environ, "SHIP_CACHE": str(tmp / "cache.git")}
            subprocess.run(["bash", "-c", ship.FETCH + '\nfetch_base "$1" "$2"', "prefetch",
                            str(remote), pushed], env=env, check=True, capture_output=True)
            # The remote is gone; the cached commit is enough.
            summary = ship.ship(None, clone, str(tmp / "dest"), env=env,
                                url=str(tmp / "nowhere.git"))
            self.assertEqual((summary["returncode"], summary["base"]), (0, pushed))
            self.assertEqual(contents(tmp / "dest"),
                             {n: (clone / n).read_bytes() for n in tree.checkout_files(clone)})

    def test_a_subset_is_checked_as_a_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            clone, remote, _ = make_clone(tmp)
            env = {**os.environ, "SHIP_CACHE": str(tmp / "cache.git")}
            summary = ship.ship(None, clone, str(tmp / "dest"), files=["src/a.c", "notes.txt"],
                                env=env, url=str(remote))
            self.assertEqual(summary["returncode"], 0)
            self.assertEqual(set(contents(tmp / "dest")), {"src/a.c", "notes.txt"})


if __name__ == "__main__":
    unittest.main()
