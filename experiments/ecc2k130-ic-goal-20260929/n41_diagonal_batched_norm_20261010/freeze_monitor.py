#!/usr/bin/env python3
"""Bind the process-tree monitor to the already frozen algebraic protocol."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "monitor_protocol.json"
    if path.exists():
        raise FileExistsError(path)
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_RUN"
    record = {"status": "FROZEN_BEFORE_RUN", "candidate_id": None,
              "monitor_sha256": sha(HERE / "monitor.py"),
              "freeze_monitor_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(HERE / "protocol.json"),
              "limits": {"online_wall_seconds": protocol["online_wall_cap_seconds"],
                         "process_wall_seconds": protocol["process_wall_cap_seconds"],
                         "peak_process_tree_rss_bytes": protocol["rss_cap_bytes"],
                         "workers": protocol["workers"]}}
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
