#!/usr/bin/env python3
"""Execute the frozen Q1470 cells sequentially in protocol order."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["proposal_id"] == "Q1470"
    for cell in protocol["limits"]["run_order"]:
        degree, kind, mode = cell.split("_", 1)[0], None, None
        rest = cell[len(degree) + 1:]
        kind = "full_lock" if rest.startswith("full_lock_") else "ordinary"
        mode = rest[len(kind) + 1:]
        assert degree in ("n53", "n83")
        assert mode == protocol["selected_mode_by_degree"][degree[1:]]
        print("START", cell, flush=True)
        subprocess.run([sys.executable, str(HERE / "run.py"), degree[1:], kind, mode],
                       check=True)


if __name__ == "__main__":
    main()
