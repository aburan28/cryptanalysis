#!/usr/bin/env python3
"""Write or verify SHA-256 inventory for this frozen two-repeat gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
TOP_LEVEL = (
    "CONFIG.json", "PROTOCOL.md", "R1_RESULT.md", "REPEAT.md",
    "RESULT.md", "audit_count.py", "manifest.py", "run_count.py",
)
RUN_IDS = ("R1", "R2")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def files() -> list[Path]:
    paths = [HERE / name for name in TOP_LEVEL]
    for run_id in RUN_IDS:
        directory = HERE / "runs" / run_id
        paths.extend(sorted(directory.iterdir()))
    if any(not path.is_file() for path in paths):
        raise ValueError("missing or non-file evidence entry")
    return sorted(paths)


def record() -> dict:
    return {
        "schema": "ecc2k130-equalb-gauss-count-manifest-v1",
        "runs": list(RUN_IDS),
        "files": {str(path.relative_to(HERE)): sha256(path) for path in files()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = record()
    if args.write:
        MANIFEST.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"WROTE {MANIFEST} ({len(current['files'])} files)")
    else:
        archived = json.loads(MANIFEST.read_text())
        if archived != current:
            missing = sorted(set(archived.get("files", {})) - set(current["files"]))
            added = sorted(set(current["files"]) - set(archived.get("files", {})))
            changed = sorted(path for path in
                             set(archived.get("files", {})) & set(current["files"])
                             if archived["files"][path] != current["files"][path])
            raise SystemExit(f"FAIL manifest: missing={missing} added={added} changed={changed}")
        print(f"PASS manifest ({len(current['files'])} files)")


if __name__ == "__main__":
    main()
