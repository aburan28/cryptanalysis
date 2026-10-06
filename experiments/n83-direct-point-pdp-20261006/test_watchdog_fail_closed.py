#!/usr/bin/env python3
"""Regression control: denied process inspection must kill the child group."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import bounded_direct_point as watchdog


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="direct-point-watchdog-") as directory:
        root = Path(directory)
        dummy = root / "sleep.py"
        dummy.write_text("import time\ntime.sleep(30)\n")
        output = root / "denied"
        with patch.object(watchdog, "RUNNER", dummy), \
             patch.object(watchdog, "sampled_tree",
                          side_effect=PermissionError("injected process denial")):
            assert watchdog.main("pinned_planted", 0, output) == 1
        receipt = json.loads((output / "outer_receipt.json").read_text())
        assert receipt["status"] == "RESOURCE_GUARD"
        assert receipt["guard"] == "process_inspection_error"
        assert receipt["exit_code"] != 0
        assert receipt["inner_receipt_sha256"] is None
        assert receipt["sampled_process_tree_peak_rss_bytes"] == 0
    print("PASS: process-inspection denial kills child and preserves failure receipt")


if __name__ == "__main__":
    main()
