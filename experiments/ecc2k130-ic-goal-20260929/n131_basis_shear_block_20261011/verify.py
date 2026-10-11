"""Audit the exact N131 W15 arithmetic-block projection receipt."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def main():
    protocol = load(HERE / "protocol.json")
    run = load(HERE / "run_result.json")
    worker = load(HERE / "worker_result.json")
    control = load(ROOT / "n41_quartic_joint_public_20261010" / "audit_result.json")["n131_control"]
    witness = load(ROOT / "n131_w15_joint_block_resultant_20261010" / "restricted_result.json")
    assert protocol["status"] == "FROZEN_BEFORE_N131_BLOCK_CONSTRUCTION"
    assert protocol["source_sha256"] == {
        name: sha(path) for name, path in protocol["source_paths"].items()}
    assert run["status"] == worker["status"] == "PASS_N131_W15_BLOCK_EXACT_ASSIGNMENT"
    assert run["worker_returncode"] == 0 and not run["worker_timed_out"]
    assert not run["worker_rss_exceeded"]
    assert run["parent_wall_seconds"] <= protocol["parent_wall_cap_seconds"]
    assert run["sampled_peak_rss_bytes"] <= protocol["combined_rss_cap_bytes"]
    assert run["protocol_sha256"] == sha(HERE / "protocol.json")
    assert run["worker_record_sha256"] == sha(HERE / "worker_result.json")
    assert run["stdout_sha256"] == sha(HERE / "worker.stdout.txt")
    assert run["stderr_sha256"] == sha(HERE / "worker.stderr.txt")
    assert not (HERE / "worker.stderr.txt").read_bytes()
    assert worker["curve_id"] == protocol["curve_id"]
    assert worker["masks"] == witness["masks"][4:8] == protocol["control_masks"]
    assert worker["z"] == control["z"] and worker["w"] == control["existential_branch_witness"]
    assert worker["and_gates"] == 216341 and worker["variables"] == 349088
    assert worker["quartic_sparse_multiplications"] == 2
    assert worker["quartic_generic_multiplications"] == 45
    direct = load(ROOT / "n131_w15_unrestricted_sixpair_public_20261010" / "control.json")
    direct_gates = direct["formula"]["and_gates"] if "formula" in direct else direct["and_gates"]
    assert direct_gates == 77021
    record = {"status": "PASS_N131_BLOCK_SOURCE_AND_ASSIGNMENT_AUDIT",
              "curve_id": protocol["curve_id"],
              "block_and_gates": worker["and_gates"],
              "direct_sixpair_control_and_gates": direct_gates,
              "block_variables": worker["variables"],
              "block_clauses": worker["clauses"],
              "block_native_xor_rows": worker["native_xor_rows"],
              "target_count": protocol["target_count"],
              "source_sha256": {name: sha(HERE / name) for name in (
                  "verify.py", "protocol.json", "run_result.json", "worker_result.json",
                  "worker.stdout.txt", "worker.stderr.txt")}}
    (HERE / "audit_result.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": record["status"], "block_and_gates": worker["and_gates"]}))


if __name__ == "__main__":
    main()
