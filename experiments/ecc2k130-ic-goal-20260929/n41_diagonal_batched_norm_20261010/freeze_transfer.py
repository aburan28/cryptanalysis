#!/usr/bin/env python3
"""Freeze N131 W14 support and N41 receipts before the degree audit."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w14_ten_source_gate_20261009"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "transfer_protocol.json"
    if path.exists():
        raise FileExistsError(path)
    sources = {"transfer": HERE / "transfer.py", "freeze": Path(__file__),
               "support_protocol": SUPPORT / "support_protocol.json",
               "support_masks": SUPPORT / "support_w14.tsv",
               "runtime": HERE / "sage_runtime_info.json",
               "n41_positive": HERE / "positive_result.json",
               "n41_public": HERE / "public_result.json"}
    record = {"status": "FROZEN_BEFORE_RUN", "candidate_id": None,
              "purpose": "exact W14 global-left dense representation memory bound",
              "source_sha256": {name: sha(source) for name, source in sources.items()}}
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": record["status"],
                      "support_sha256": record["source_sha256"]["support_masks"]}, indent=2))


if __name__ == "__main__":
    main()
