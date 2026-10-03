#!/usr/bin/env python3
"""Check source, solver logs, and gzip XCNF archives against frozen receipts."""

import gzip
import hashlib
import json
from pathlib import Path

from run_probe import HERE, sha


def verify():
    protocol_digest = sha(HERE / "protocol.json")
    rows = []
    for n in (53, 83):
        for kind in ("planted", "ordinary"):
            stem = f"n{n}_{kind}_frozen"
            receipt_path = HERE / "runs" / f"{stem}.json"
            receipt = json.loads(receipt_path.read_text())
            assert receipt["protocol_sha256"] == protocol_digest
            assert receipt["solver_source_sha256"] == sha(HERE / "chain_s3.py")
            assert receipt["runner_source_sha256"] == sha(HERE / "run_probe.py")
            formula_digest = hashlib.sha256()
            formula_bytes = 0
            with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b""):
                    formula_digest.update(chunk)
                    formula_bytes += len(chunk)
            assert formula_digest.hexdigest() == receipt["xcnf_sha256"]
            assert formula_bytes == receipt["xcnf_bytes"]
            for attempt in receipt["attempts"]:
                index = attempt["index"]
                assert sha(HERE / "runs" / f"{stem}.attempt{index}.stdout.txt") == (
                    attempt["solver_stdout_sha256"])
                assert sha(HERE / "runs" / f"{stem}.attempt{index}.stderr.txt") == (
                    attempt["solver_stderr_sha256"])
            rows.append({"n": n, "kind": kind,
                         "receipt_sha256": sha(receipt_path),
                         "formula_sha256": formula_digest.hexdigest(),
                         "formula_bytes": formula_bytes,
                         "attempt_count": len(receipt["attempts"])})
    return rows


if __name__ == "__main__":
    print(json.dumps({"verified": verify()}, indent=2))
