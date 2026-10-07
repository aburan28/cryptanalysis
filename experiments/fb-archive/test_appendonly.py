"""appendonly.py: removed or rewritten archive entries fail, additions pass."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import appendonly  # noqa: E402


def fake_base(extra_rows: dict[str, bytes], files: dict[str, bytes]):
    """at_base: the working tree, with `extra_rows` appended to ledgers and `files` overriding bytes."""
    def at_base(base, rel):
        if rel in files:
            return files[rel]
        path = HERE / rel
        if not path.exists():
            return None
        data = path.read_bytes()
        return data + extra_rows.get(rel, b"")

    def base_files(base, pattern):
        return sorted(str(p.relative_to(HERE)) for p in (HERE / pattern).glob("*"))

    return mock.patch.multiple(appendonly, at_base=at_base, base_files=base_files)


class AppendOnlyTest(unittest.TestCase):
    def test_unchanged_archive_passes(self):
        with fake_base({}, {}):
            self.assertEqual(appendonly.check("BASE"), [])

    def test_removed_row_fails(self):
        row = b"f" * 64 + b",ca-ic sorted-xy-hex-lines," + b"e" * 64 + b",experiments/x\n"
        with fake_base({"aliases.csv": row}, {}):
            errors = appendonly.check("BASE")
        self.assertEqual(len(errors), 1)
        self.assertIn("aliases.csv: row " + "f" * 64 + " removed", errors[0])

    def test_rewritten_file_fails(self):
        with fake_base({}, {"sweeps/volcano-ic.json.gz": b"older bytes"}):
            errors = appendonly.check("BASE")
        self.assertEqual(errors, ["sweeps/volcano-ic.json.gz: archive file rewritten"])

    def test_changed_row_fails(self):
        index = (HERE / "index.csv").read_bytes().decode().split("\n")
        index[1] = index[1].replace(",git,", ",s3,")
        with fake_base({}, {"index.csv": "\n".join(index).encode()}):
            errors = appendonly.check("BASE")
        self.assertTrue(any(e.startswith("index.csv: row ") and e.endswith(" changed") for e in errors), errors)

    def test_rows_added_on_the_base_after_forking_are_not_removals(self):
        # the failure mode of PR #352: the base gained archives after the branch forked,
        # so a base-tip comparison read them as deletions; main() must use the merge-base
        calls = []
        real_git = appendonly.git

        def git(*args):
            calls.append(args)
            if args[0] == "merge-base":
                return mock.Mock(returncode=0, stdout=b"MERGEBASE\n")
            return real_git(*args)

        with mock.patch.object(appendonly, "git", git), \
                mock.patch.object(appendonly, "check", return_value=[]) as chk, \
                mock.patch.object(sys, "argv", ["appendonly.py", "--base", "HEAD"]):
            self.assertEqual(appendonly.main(), 0)
        chk.assert_called_once_with("MERGEBASE")
        self.assertIn(("merge-base", "HEAD", "HEAD"), calls)

    def test_new_branch_is_skipped(self):
        with mock.patch.object(sys, "argv", ["appendonly.py", "--base", "0" * 40]):
            self.assertEqual(appendonly.main(), 0)


if __name__ == "__main__":
    unittest.main()
