#!/usr/bin/env python3
"""Re-verify B's archived factor-log table before any timing.

Runs the reconcile experiment's `verify_log_table.verify` (every [L_j]G = R_j
in the pinned pure-Python oracle, plus kind, n/a/r, base hash, width and
range) against this experiment's restored snapshot and frozen base, and
checks the table digest against `protocol.json`. Exits nonzero on failure.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "koblitz-n83-reconcile-20261014"))
sys.path.insert(0, str(HERE))
import verify_log_table  # noqa: E402
from verify_receipt import oracle  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    online = json.loads((HERE / "protocol.json").read_text())["online"]
    table = (HERE / online["factor_log_table"]).resolve()
    if hashlib.sha256(table.read_bytes()).hexdigest() != online["factor_log_table_sha256"]:
        raise SystemExit("factor-log table digest differs from the protocol")
    result = verify_log_table.verify(table, HERE / online["base"], oracle())
    args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "table": str(table)}))
    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
