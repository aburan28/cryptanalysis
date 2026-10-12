#!/usr/bin/env python3
"""Add the paired one-scalar CLI to the pinned fixed-limb native crate."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
PATCH = HERE / "native.patch"
TOP = Path("src/bin/eisenstein_fixed.rs")
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
        raise SystemExit("refusing to overwrite benchmark materialization")
    expected = (HERE / "base-tree-sha256.txt").read_text().strip()
    assert tree_digest(base) == expected
    parent = json.loads((base / "fixed-limb-materialization.json").read_bytes())
    assert parent["status"] == "materialized"
    assert digest(base / WINDOW) == parent["window_sha256"]
    shutil.copytree(base, output, ignore=shutil.ignore_patterns("target"))
    subprocess.run(["patch", "-p1", "--forward", "--batch", "-i", str(PATCH)],
                   cwd=output, check=True)
    receipt = {
        "schema": 1,
        "status": "materialized",
        "base_tree_sha256": expected,
        "parent_receipt_sha256": digest(base / "fixed-limb-materialization.json"),
        "patch_sha256": digest(PATCH),
        "materializer_sha256": digest(Path(__file__)),
        "top_sha256": digest(output / TOP),
        "window_sha256": digest(output / WINDOW),
        "input_sha256": digest(output / "split-terminal-inputs.json"),
        "certificate_sha256": digest(output / "split-terminal-paths.jsonl"),
    }
    (output / "benchmark-materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
