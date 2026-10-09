#!/usr/bin/env python3
"""Freeze the independent Sage and transposed-rank audit input set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "audit_protocol_v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("preserve first independent audit protocol")
    prior = json.loads((HERE / "protocol_v2.json").read_text())
    result = json.loads((HERE / "result_v2.json").read_text())
    if result["status"] != "FULL_DISTINCT_COLUMN_MIXED_CUBIC_RANK":
        raise ValueError("corrected rank result is not complete")
    inputs = {"protocol_v2": HERE / "protocol_v2.json",
              "result_v2": HERE / "result_v2.json",
              "decoded_rows": Path(prior["inputs"]["decoded_rows"]),
              "holdout_rows": Path(prior["inputs"]["holdout_rows"]),
              "geometry": Path(prior["inputs"]["geometry"]),
              "runtime": HERE / "sage_runtime_info.json"}
    if not all(path.is_file() for path in inputs.values()):
        raise FileNotFoundError("independent audit input missing")
    frozen = {"kind": "n41_two_pair_distinct_column_mixed_cubic_audit_freeze_v2",
              "status": "FROZEN", "curve_id": prior["curve_id"],
              "inputs": {key: str(path) for key, path in inputs.items()},
              "input_sha256": {key: sha(path) for key, path in inputs.items()},
              "audit_source_sha256": sha(HERE / "sage_audit_v2.py"),
              "freeze_source_sha256": sha(Path(__file__)),
              "limits": {"wall_seconds": 300, "rss_bytes": 4294967296,
                         "workers": 1}}
    with OUTPUT.open("x") as stream:
        json.dump(frozen, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": frozen["status"],
                      "audit_source_sha256": frozen["audit_source_sha256"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
