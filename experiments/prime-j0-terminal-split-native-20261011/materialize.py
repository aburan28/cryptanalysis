#!/usr/bin/env python3
"""Rebuild the split-terminal native replay from the pinned budget crate."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
PANEL = HERE.parent / "prime-j0-terminal-split-20261011"
POINT = HERE.parent / "prime-j0-terminal-split-pointcheck-20261011"
PATCH = HERE / "native.patch"
WINDOW = Path("src/bin/eisenstein_fixed/unit_orbit_windows.rs")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def tree_digest(root):
    h = sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or "target" in relative.parts:
            continue
        h.update(relative.as_posix().encode() + b"\0")
        h.update(sha256(path.read_bytes()).digest())
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-crate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = args.base_crate.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("refusing to overwrite native materialization")
    expected_base = (HERE / "base-tree-sha256.txt").read_text().strip()
    actual_base = tree_digest(base)
    assert actual_base == expected_base, (actual_base, expected_base)
    screen = json.loads((PANEL / "holdout-screen.json").read_bytes())
    algebra = json.loads((PANEL / "holdout-check.json").read_bytes())
    points = json.loads((POINT / "point-check.json").read_bytes())
    assert algebra["status"] == points["status"] == "passed"
    assert screen["status"] == "screened"
    inputs = PANEL / "holdout-inputs.json"
    paths = PANEL / "holdout-paths.jsonl"
    assert digest(inputs) == screen["input_sha256"] == points["input_sha256"]
    assert digest(paths) == screen["certificate_sha256"] == \
        algebra["certificate_sha256"] == points["certificate_sha256"]
    shutil.copytree(base, output, ignore=shutil.ignore_patterns("target"))
    subprocess.run(["patch", "-p1", "--forward", "--batch", "-i", str(PATCH)],
                   cwd=output, check=True)
    shutil.copyfile(inputs, output / "split-terminal-inputs.json")
    shutil.copyfile(paths, output / "split-terminal-paths.jsonl")
    receipt = {
        "schema": 1,
        "status": "materialized",
        "base_tree_sha256": actual_base,
        "patch_sha256": digest(PATCH),
        "materializer_sha256": digest(Path(__file__)),
        "window_sha256": digest(output / WINDOW),
        "input_sha256": digest(output / "split-terminal-inputs.json"),
        "certificate_sha256": digest(output / "split-terminal-paths.jsonl"),
    }
    (output / "split-terminal-materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
