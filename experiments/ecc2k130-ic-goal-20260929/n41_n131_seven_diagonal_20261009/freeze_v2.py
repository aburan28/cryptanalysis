#!/usr/bin/env python3
"""Freeze a solver-seed correction while retaining the rejected v1 query."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    destination = HERE / "protocol_v2.json"
    if destination.exists():
        raise FileExistsError(destination)
    prior_path = HERE / "protocol.json"
    failure_path = HERE / "public_v1/result.json"
    prior = json.loads(prior_path.read_text())
    failure = json.loads(failure_path.read_text())
    stderr = (HERE / "public_v1/solver.stderr.txt").read_text()
    if (prior["status"] != "FROZEN_BEFORE_MEASUREMENT" or
            failure["proposal_id"] != prior["proposal_id"] or
            failure["status"] != "PRODUCER_OR_SOLVER_FAILURE" or
            failure["solver_exit_code"] != 255 or
            not stderr.startswith("not an integer: 20261009172341") or
            failure["source_sha256"]["protocol"] != sha(prior_path)):
        raise ValueError("first producer failure or original freeze changed")
    corrected = dict(prior)
    corrected["proposal_id"] = "Q20261009173200"
    corrected["solver_flags"] = [
        "--random=20261009" if flag == "--random=20261009172341" else flag
        for flag in prior["solver_flags"]]
    if corrected["solver_flags"] == prior["solver_flags"]:
        raise ValueError("solver seed was not corrected")
    corrected["correction"] = {
        "reason": "CryptoMiniSat rejected the v1 random seed before search",
        "prior_protocol_sha256": sha(prior_path),
        "prior_failure_sha256": sha(failure_path),
        "prior_stderr_sha256": sha(HERE / "public_v1/solver.stderr.txt"),
        "freeze_v2_sha256": sha(Path(__file__)),
        "run_v2_sha256": sha(HERE / "run_v2.py"),
    }
    destination.write_text(json.dumps(corrected, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": corrected["status"],
                      "seed": corrected["solver_flags"][3]}))


if __name__ == "__main__":
    main()
