#!/usr/bin/env python3
"""Replay raw hashes and Sage receipt bindings from compressed diagnostic runs."""

import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
NAMES = ("v2-original-both", "v2-inverse-overrun", "v2-strict-both",
         "v2-strict-inverse", "v2-strict-intermediate")


def digest(path, compressed=False):
    hasher = hashlib.sha256()
    size = 0
    opener = gzip.open if compressed else Path.open
    with opener(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def main():
    result = {}
    for name in NAMES:
        folder = HERE / "runs" / name
        receipt_path = folder / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        sage = json.loads((folder / "sage_replay.json").read_text())
        xcnf_sha, xcnf_size = digest(folder / "system.xcnf.gz", True)
        stdout_sha, _ = digest(folder / "solver.stdout.txt.gz", True)
        assert xcnf_sha == receipt["xcnf_sha256"]
        assert xcnf_size == receipt["xcnf_bytes"]
        assert stdout_sha == receipt["solver_stdout_sha256"]
        assert digest(folder / "solver.stderr.txt")[0] == receipt[
            "solver_stderr_sha256"]
        assert digest(folder / "runtime-info.json")[0] == receipt[
            "sage_runtime_info_sha256"]
        assert digest(receipt_path)[0] == sage["receipt_sha256"]
        assert sage["status"] == (
            "PASS_PLANTED_GROUP_REPLAY" if receipt["model"] is not None
            else "NO_MODEL_REPLAYED")
        if name.startswith("v2-strict-"):
            for source_name, claimed in receipt["source_sha256"].items():
                assert digest(HERE / source_name)[0] == claimed
        result[name] = {"status": receipt["status"],
                        "sage_status": sage["status"],
                        "xcnf_sha256": xcnf_sha,
                        "raw_xcnf_bytes": xcnf_size}
    assert result["v2-original-both"]["xcnf_sha256"] == result[
        "v2-strict-both"]["xcnf_sha256"]
    assert result["v2-inverse-overrun"]["xcnf_sha256"] == result[
        "v2-strict-inverse"]["xcnf_sha256"]
    print(json.dumps({"status": "PASS_DIAGNOSTIC_ARCHIVES", "runs": result},
                     sort_keys=True))


if __name__ == "__main__":
    main()
