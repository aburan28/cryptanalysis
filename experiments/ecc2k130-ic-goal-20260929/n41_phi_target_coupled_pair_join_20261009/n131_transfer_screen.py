"""Uniform-target union bound for direct transfer of this sampled join."""

import hashlib
import json
from decimal import Decimal, getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
MANIFEST = (GOAL / "n131_phi_torsion_frobenius_domains_20261005/"
            "m12_d13_full_pipeline/d13_m12_candidate_manifest_v1.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "n131_transfer_screen.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "protocol.json").read_text())
    manifest = json.loads(MANIFEST.read_text())
    r = manifest["candidate_record"]["curve"]["subgroup_order"]
    if (r != 680564733841876926932320129493409985129 or
            protocol["left_samples"] != 1800000 or
            protocol["right_samples"] != 2000000):
        raise ValueError("frozen size or N131 subgroup changed")
    getcontext().prec = 40
    branches = 2
    left = protocol["left_samples"]
    scheduled_right = protocol["right_samples"]
    ideal_right = 600_000_000_000
    ratio = lambda count: str(Decimal(branches * left * count) / Decimal(r))
    receipt = {
        "kind": "n131_sampled_join_uniform_target_transfer_screen",
        "status": "EXACT_UNION_BOUND_SCREEN",
        "candidate_id": None, "run_id": None,
        "n131_subgroup_order": r,
        "fixed_first_root_sign_branches": branches,
        "left_index_draws": left,
        "scheduled_right_draws": scheduled_right,
        "scheduled_uniform_target_success_upper_bound": ratio(scheduled_right),
        "idealized_right_draws_in_600_seconds": ideal_right,
        "idealized_uniform_target_success_upper_bound": ratio(ideal_right),
        "assumptions": [
            "Target is uniform in the prime subgroup and independent of both sampled lists and the fixed first-link branch.",
            "Each right draw tests both signed first-link roots against the left index; repeats and invalid rows can only lower coverage.",
            "The idealized rate of one right draw per nanosecond is a counting device, not a measured implementation rate.",
            "The bound does not apply to the published fixed target or to target-adaptive list construction."],
        "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                          "n131_manifest": sha(MANIFEST),
                          "script": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "scheduled_bound": ratio(scheduled_right),
                      "idealized_bound": ratio(ideal_right)}))


if __name__ == "__main__":
    main()
