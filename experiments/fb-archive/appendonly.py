#!/usr/bin/env python3
"""The factor-base archive is append-only: nothing that was archived may be removed or rewritten.

    python3 appendonly.py --base origin/<default-branch>     # CI on pull requests
    python3 appendonly.py --base <sha-before-push>            # CI on pushes

Compares the working tree with the archive as of the merge-base of HEAD and
--base (so rows added on the base after the branch forked never read as
removals; a removal of such a row still fails on the base's own push run) and
fails on any:
  - row of index.csv, aliases.csv, sweeps.csv or sweeps/<name>.points.csv that is
    missing or changed (rows are matched by their key column);
  - archive file (bases/... of an index row, sweeps/<name>.json.gz) that is missing
    or whose bytes differ.
New rows and files are always allowed. unarchived.csv, the debt list, is meant to
shrink and is not covered. A correction is a new entry (a new archive or a new sweep
name), never an edit of an old one.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REL = HERE.relative_to(ROOT).as_posix()

# ledger file (relative to fb-archive) -> key column
LEDGERS = {"index.csv": "path", "aliases.csv": "cited_sha256", "sweeps.csv": "name"}
POINTS_KEY = "label"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True)


def at_base(base: str, rel: str) -> bytes | None:
    out = git("show", f"{base}:{REL}/{rel}")
    return out.stdout if out.returncode == 0 else None


def base_files(base: str, pattern: str) -> list[str]:
    out = git("ls-tree", "-r", "--name-only", base, f"{REL}/{pattern}")
    return [p[len(REL) + 1:] for p in out.stdout.decode().split("\n") if p]


def rows(data: bytes, key: str) -> dict[str, dict]:
    return {r[key]: r for r in csv.DictReader(io.StringIO(data.decode()))}


def check(base: str) -> list[str]:
    errors: list[str] = []
    ledgers = dict(LEDGERS)
    for rel in base_files(base, "sweeps/"):
        if rel.endswith(".points.csv"):
            ledgers[rel] = POINTS_KEY
    old_index: dict[str, dict] = {}
    for rel, key in ledgers.items():
        old = at_base(base, rel)
        if old is None:
            continue
        before = rows(old, key)
        if rel == "index.csv":
            old_index = before
        path = HERE / rel
        if not path.exists():
            errors.append(f"{rel}: deleted ({len(before)} archived rows)")
            continue
        after = rows(path.read_bytes(), key)
        gone = [k for k in before if k not in after]
        changed = [k for k in before if k in after and after[k] != before[k]]
        errors += [f"{rel}: row {k} removed" for k in gone[:20]]
        errors += [f"{rel}: row {k} changed" for k in changed[:20]]
        if len(gone) + len(changed) > 40:
            errors.append(f"{rel}: {len(gone)} rows removed, {len(changed)} changed in all")
    files = [r["path"] for r in old_index.values() if r.get("storage") == "git"]
    files += [p for p in base_files(base, "sweeps/") if p.endswith(".json.gz")]
    bad = 0
    for rel in files:
        old = at_base(base, rel)
        if old is None:
            continue
        path = HERE / rel
        if not path.exists():
            msg = f"{rel}: archive file deleted"
        elif hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(old).digest():
            msg = f"{rel}: archive file rewritten"
        else:
            continue
        bad += 1
        if bad <= 20:
            errors.append(msg)
    if bad > 20:
        errors.append(f"{bad} archive files deleted or rewritten in all")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="git revision holding the archive to compare against")
    args = ap.parse_args()
    if set(args.base) <= {"0"} or git("rev-parse", "--verify", "--quiet", f"{args.base}^{{commit}}").returncode:
        print(f"base {args.base!r} is not a commit here (new branch or shallow clone); nothing to compare")
        return 0
    mb = git("merge-base", "HEAD", args.base)
    base = mb.stdout.decode().strip() if mb.returncode == 0 and mb.stdout.strip() else args.base
    errors = check(base)
    for err in errors:
        print(err)
    print(f"append-only check against {base}" + (f" (merge-base with {args.base})" if base != args.base else "")
          + f": {len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
