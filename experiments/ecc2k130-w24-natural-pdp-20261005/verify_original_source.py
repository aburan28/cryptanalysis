#!/usr/bin/env python3
"""Reconstruct the pre-watchdog-fix diagnostic source from the final source."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNS = ("v2-original-both", "v2-inverse-overrun")


def main():
    for name in RUNS:
        receipt = json.loads((HERE / "runs" / name / "receipt.json").read_text())
        for source_name in ("run.py", "witness_diagnostic.py"):
            current = (HERE / source_name).read_bytes()
            assert current.count(b">= wall:") == 1
            original = current.replace(b">= wall:", b"> wall+15:")
            assert hashlib.sha256(original).hexdigest() == receipt[
                "source_sha256"][source_name]
    print(json.dumps({"status": "PASS_ORIGINAL_SOURCE_RECONSTRUCTION",
                      "receipts": list(RUNS)}))


if __name__ == "__main__":
    main()
