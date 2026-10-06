"""Independent integer audit and small-group control for Q1443."""

from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value: bool, explanation: str) -> None:
    if not value:
        raise ValueError(explanation)


def ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def small_group_control() -> dict:
    modulus = 101
    base = {1, 3, 7, 13}
    residuals = {(a + b) % modulus for a in base for b in base}
    for first_pairs in ((5,), (5, 11), (5, 11, 19, 23)):
        hits = sum(any((target - first) % modulus in residuals
                       for first in first_pairs)
                   for target in range(1, modulus))
        require(hits <= len(first_pairs) * len(base) * (len(base) + 1) // 2,
                "small-group union bound failed")
    return {"modulus": modulus, "base_size": len(base),
            "tested_first_pair_list_lengths": [1, 2, 4],
            "status": "passed"}


def audit() -> dict:
    protocol_path = HERE / "protocol.json"
    result_path = HERE / "result.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    require(protocol["source_sha256"] == sha(HERE / "screen.py"), "frozen source changed")
    require(result["source_sha256"] == sha(HERE / "screen.py"), "result source mismatch")
    require(result["protocol_sha256"] == sha(protocol_path), "protocol mismatch")
    for relative, expected in protocol["input_sha256"].items():
        require(sha(ROOT / relative) == expected, f"input changed: {relative}")
    require(protocol["proposal_id"] == result["proposal_id"] == "Q1443", "proposal mismatch")
    require(protocol["candidate_id"] is result["candidate_id"] is None, "candidate ID present")
    require(protocol["isogeny"] == result["isogeny"] == "none", "isogeny mismatch")
    require(result["complete_solve_work_log2"] is None, "complete-solve estimate present")
    require(result["challenge_dispatch_allowed"] is False, "challenge wrongly allowed")
    require(result["ordinary_N83_relation_measured"] is False, "ordinary N83 claim present")
    require(len(result["rows"]) == 4, "row count changed")
    for record in result["rows"]:
        b = int(record["B_used_in_bound"])
        k = int(record["K_used_in_rank_bound"])
        r = int(record["subgroup_order_r"])
        pairs = b * (b + 1) // 2
        p = Fraction(pairs, r - 1)
        single = ceil_fraction(Fraction(19 * (r - 1), 20 * pairs))
        rank = ceil_fraction(Fraction(19 * k * (r - 1), 20 * pairs))
        require(str(pairs) == record["maximum_unordered_pair_count"], "pair count mismatch")
        require(str(single) == record["minimum_first_pair_trials_for_one_relation_95pct"],
                "single relation threshold mismatch")
        require(str(rank) == record["minimum_total_first_pair_trials_for_K_rows_95pct_one_row_policy"],
                "K-row threshold mismatch")
        require((rank > 2**61) is record["K_row_trial_bound_exceeds_2pow61"],
                "budget gate mismatch")
        if record["conditional_base_model"]:
            require(record["actual_B"] is record["actual_K"] is
                    record["base_set_sha256"] is None, "model row promoted")
        else:
            require(record["actual_B"] == b and record["actual_K"] == k,
                    "exact row lost actual geometry")
            require(bool(record["base_set_sha256"]), "exact base digest missing")
        if record["label"].startswith("N131"):
            require(single > 2**61, "N131 one-relation gate changed")
            require(p < Fraction(1, 2**61), "N131 residual support changed")
    return {
        "kind": "q1443_independent_integer_audit",
        "status": "passed",
        "proposal_id": "Q1443",
        "protocol_sha256": sha(protocol_path),
        "result_sha256": sha(result_path),
        "verification_source_sha256": sha(Path(__file__)),
        "small_group_control": small_group_control(),
        "N131_complete_solve_work_log2": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.emit == args.check:
        parser.error("choose --emit or --check")
    receipt = audit()
    output = HERE / "verification.json"
    if args.emit:
        if output.exists():
            raise FileExistsError(f"refusing to overwrite {output}")
        output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    elif json.loads(output.read_text()) != receipt:
        raise ValueError("verification receipt changed")
    else:
        print("Q1443 exact pair-support audit passed")


if __name__ == "__main__":
    main()
