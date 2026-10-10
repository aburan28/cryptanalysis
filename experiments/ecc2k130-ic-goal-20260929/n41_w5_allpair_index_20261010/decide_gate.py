#!/usr/bin/env python3
"""Record the frozen control gate before any less-constrained SAT query."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    preflight = json.loads((HERE / "preflight.json").read_text())
    fixed = json.loads((HERE / "all_fixed_query/result.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_ALL_PAIR_FORMULA_AND_QUERIES"
    assert preflight["status"] == "PASS_FULL_FIVE_PAIR_INDEX_CONTROLS"
    assert preflight["known_relation"]["valid"]
    assert fixed["source_sha256"]["formula"] == preflight["formulas"]["all_fixed"]["sha256"]
    if fixed["status"] == "CENSORED_TIME" and \
            fixed["stop_reason"] == "SOLVER_WALL_CAP":
        decision = "GATE_CLOSED_UPPER_S3_FIXED_CONTROL_CENSORED"
        four_fixed = public = "NOT_RUN_GATE_CLOSED"
    elif fixed["status"] == "SAT_MODEL_PENDING_INDEPENDENT_SAGE":
        decision = "AWAIT_INDEPENDENT_MODEL_AUDIT"
        four_fixed = public = "PENDING"
    else:
        raise ValueError("unexpected all-five-fixed control status")
    receipt = {"status": decision,
               "candidate_id": None, "curve_id": protocol["curve_id"],
               "public_target_q": protocol["public_target_q"],
               "target_count": 1,
               "all_fixed_status": fixed["status"],
               "four_fixed_status": four_fixed,
               "public_status": public,
               "reason": "The completely known pair-output control did not clear its 20-second SAT cap; the upper four S3 links are the measured search gate for this encoding.",
               "source_sha256": {"script": sha(Path(__file__)),
                                 "protocol": sha(HERE / "protocol.json"),
                                 "preflight": sha(HERE / "preflight.json"),
                                 "all_fixed_result": sha(HERE / "all_fixed_query/result.json"),
                                 "failure_v1": sha(HERE / "failure_v1.json")}}
    with (HERE / "gate_result.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": decision,
                      "four_fixed": four_fixed,
                      "public": public}))


if __name__ == "__main__":
    main()
