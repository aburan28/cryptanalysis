#!/usr/bin/env python3
"""Write or verify the frozen normal4 conflict-gate file inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
TOP = (
    ".gitattributes", "CONFIG.json", "PROTOCOL.md", "RESULT.md", "audit_long.py",
    "launch_R1.stdout.txt", "manifest.py", "preflight_before_R1.json",
    "run_long.py", "trace_compare.py",
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def inventory() -> dict:
    paths = [HERE / item for item in TOP]
    paths.extend(sorted((HERE / "runs" / "R1").iterdir()))
    if any(not path.is_file() for path in paths):
        raise ValueError("evidence inventory contains a missing or non-file entry")
    return {
        "schema": "ecc2k130-equalb-normal4-conflict-manifest-v1",
        "files": {str(path.relative_to(HERE)): digest(path)
                  for path in sorted(paths)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = inventory()
    if args.write:
        MANIFEST.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"WROTE {MANIFEST} ({len(current['files'])} files)")
    else:
        archived = json.loads(MANIFEST.read_text())
        if archived != current:
            raise SystemExit("FAIL file inventory or SHA-256 differs")
        print(f"PASS manifest ({len(current['files'])} files)")


if __name__ == "__main__":
    main()
