#!/usr/bin/env python3
"""Run the source-identical public query with the frozen valid CMS seed."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as source


def main():
    protocol_v2 = HERE / "protocol_v2.json"
    protocol = json.loads(protocol_v2.read_text())
    correction = protocol["correction"]
    if (correction["run_v2_sha256"] != source.sha(Path(__file__)) or
            correction["prior_protocol_sha256"] != source.sha(HERE / "protocol.json") or
            correction["prior_failure_sha256"] != source.sha(HERE / "public_v1/result.json") or
            correction["prior_stderr_sha256"] != source.sha(HERE / "public_v1/solver.stderr.txt") or
            protocol["solver_flags"][3] != "--random=20261009" or
            protocol["proposal_id"] != "Q20261009173200"):
        raise ValueError("solver-seed correction receipt changed")
    first_preflight = json.loads((HERE / "preflight/receipt.json").read_text())
    if first_preflight["protocol_sha256"] != correction["prior_protocol_sha256"]:
        raise ValueError("full-formula control changed")
    source.PROTOCOL = protocol_v2
    source.verify_freeze()
    source.query()


if __name__ == "__main__":
    main()
