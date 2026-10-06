#!/usr/bin/env python3
"""Check that factor bases cited by committed results are archived.

Every `factor_base_sha256` value in a committed JSON / JSONL result file (plain,
.gz or .xz) under experiments/ and ecc2k130/research/, and every point-set digest
(`point_set_sha256`, `enumerated_set_sha256`, `factor_base_point_set_sha256`,
`base_digest`: SHA-256 of the canonical sorted [[x, y], ...] list), must be either
the `factor_base_sha256` or `enumerated_set_sha256` of a row of index.csv, a `cited_sha256` of aliases.csv whose archive is indexed (a digest
cited under another convention; `fbarchive.py verify` recomputes it from the
archived points), or listed in unarchived.csv, the closed list of known, not-yet-archived
bases. The debt list is exact both ways: a new unarchived digest fails, and so
does a debt entry that is now archived or no longer cited, so the list can only
shrink.

    python3 refs.py report          # every cited digest, archived or not
    python3 refs.py check           # CI: fail on any drift from index.csv + unarchived.csv
    python3 refs.py write-debt      # regenerate unarchived.csv from the current tree
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import lzma
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INDEX = HERE / "index.csv"
DEBT = HERE / "unarchived.csv"
ALIASES = HERE / "aliases.csv"
ROOTS = ["experiments", "ecc2k130/research"]
SUFFIXES = (".json", ".jsonl", ".json.gz", ".jsonl.gz", ".json.xz", ".jsonl.xz")
KEY = "factor_base_sha256"
# Keys whose value hashes the point list itself; they match index.csv's enumerated_set_sha256.
POINT_SET_KEYS = ("point_set_sha256", "enumerated_set_sha256", "factor_base_point_set_sha256", "base_digest")
KEYS = (KEY, *POINT_SET_KEYS)
HEX64 = re.compile(r"[0-9a-f]{64}")
# The archive's own records and the debt list are not citations.
SKIP_PREFIX = ("experiments/fb-archive/",)


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", *ROOTS], cwd=ROOT, check=True,
                         capture_output=True).stdout.decode()
    return sorted(p for p in out.split("\0")
                  if p.endswith(SUFFIXES) and not p.startswith(SKIP_PREFIX))


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if path.name.endswith(".gz"):
        data = gzip.decompress(data)
    elif path.name.endswith(".xz"):
        data = lzma.decompress(data)
    return data.decode("utf-8", errors="replace")


def walk(obj, found: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in KEYS and isinstance(v, str) and HEX64.fullmatch(v):
                found.add(v)
            else:
                walk(v, found)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, found)


def digests_in(path: Path) -> set[str]:
    text = read_text(path)
    if not any(k in text for k in KEYS):
        return set()
    found: set[str] = set()
    try:
        walk(json.loads(text), found)
        return found
    except json.JSONDecodeError:
        pass
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            walk(json.loads(line), found)
        except json.JSONDecodeError:
            # not JSON at all: fall back to the key/value pattern
            found.update(re.findall(r'"(?:%s)"\s*:\s*"([0-9a-f]{64})"' % "|".join(KEYS), line))
    return found


def citations() -> dict[str, set[str]]:
    cited: dict[str, set[str]] = {}
    for rel in tracked_files():
        for d in digests_in(ROOT / rel):
            cited.setdefault(d, set()).add(rel)
    return cited


def archived() -> set[str]:
    with open(INDEX, newline="") as fh:
        rows = list(csv.DictReader(fh))
    have = {r["factor_base_sha256"] for r in rows}
    have |= {r["enumerated_set_sha256"] for r in rows if r["enumerated_set_sha256"]}
    if ALIASES.exists():
        with open(ALIASES, newline="") as fh:
            have |= {r["cited_sha256"] for r in csv.DictReader(fh) if r["factor_base_sha256"] in have}
    return have


def owner(rel: str) -> str:
    parts = rel.split("/")
    return "/".join(parts[:2]) if parts[0] == "experiments" else "/".join(parts[:3])


def read_debt() -> dict[str, str]:
    if not DEBT.exists():
        return {}
    with open(DEBT, newline="") as fh:
        return {r["factor_base_sha256"]: r["experiment"] for r in csv.DictReader(fh)}


def write_debt(rows: dict[str, str]) -> None:
    with open(DEBT, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["factor_base_sha256", "experiment"])
        for d, exp in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            w.writerow([d, exp])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["report", "check", "write-debt"])
    args = ap.parse_args()
    cited = citations()
    have = archived()
    missing = {d: files for d, files in cited.items() if d not in have}
    if args.command == "report":
        per: dict[str, list[int]] = {}
        for d, files in cited.items():
            for exp in {owner(f) for f in files}:
                c = per.setdefault(exp, [0, 0])
                c[0 if d in have else 1] += 1
        print(f"{len(cited)} cited digests, {len(cited) - len(missing)} archived, {len(missing)} not")
        for exp, (a, m) in sorted(per.items()):
            print(f"  {exp}: {a} archived, {m} not")
        return 0
    if args.command == "write-debt":
        write_debt({d: min(owner(f) for f in files) for d, files in missing.items()})
        print(f"wrote {len(missing)} rows to {DEBT.name}")
        return 0
    debt = read_debt()
    problems = []
    for d in sorted(set(missing) - set(debt)):
        problems.append(f"not archived and not in {DEBT.name}: {d} cited by {', '.join(sorted(missing[d])[:3])}")
    for d in sorted(set(debt) & have):
        problems.append(f"archived now, remove from {DEBT.name}: {d} ({debt[d]})")
    for d in sorted(set(debt) - set(cited)):
        problems.append(f"no longer cited, remove from {DEBT.name}: {d} ({debt[d]})")
    for p in problems:
        print(p)
    print(f"{len(cited)} cited digests, {len(cited) - len(missing)} archived, {len(debt)} known debt, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
