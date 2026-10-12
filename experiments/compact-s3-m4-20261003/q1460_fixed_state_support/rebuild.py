#!/usr/bin/env python3
"""Rebuild Q1460's ignored native binary in any checkout and check its hash."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import build


def main() -> None:
    receipt = json.loads(build.RECEIPT.read_text())
    assert receipt["proposal_id"] == "Q1460"
    assert receipt["build_script_sha256"] == build.sha(Path(build.__file__))
    for name, path in build.SOURCES.items():
        assert build.sha(path) == receipt["source_sha256"][name], name
    subprocess.run(build.command(), check=True)
    assert build.sha(build.BINARY) == receipt["binary_sha256"]
    print("Q1460 portable native rebuild: PASS")


if __name__ == "__main__":
    main()
