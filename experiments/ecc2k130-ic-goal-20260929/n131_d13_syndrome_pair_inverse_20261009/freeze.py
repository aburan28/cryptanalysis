"""Freeze the second exact pair-inverse design on the prior matched inputs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_d13_batched_pair_inverse_20261009"
SOURCE = HERE.parent / "n131_d13_same_rotation_pairs_20261009"
CODEGEN = HERE.parents[2] / "ecc2k130/codegen"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    base_protocol = json.loads((BASE / "protocol.json").read_text())
    base_result = json.loads((BASE / "result.json").read_text())
    base_audit = json.loads((BASE / "audit.json").read_text())
    if (base_result["status"] != "PASS_EXACT_MATCH" or
            base_audit["status"] != "PASS_GROUP_REPLAY_AND_RAW_RECEIPT"):
        raise ValueError("matched source comparison lacks its audit")
    paths = {"run": HERE / "run.py", "audit": HERE / "audit.py",
             "base_run": BASE / "run.py", "base_protocol": BASE / "protocol.json",
             "base_result": BASE / "result.json", "base_audit": BASE / "audit.json",
             "field": CODEGEN / "field.py", "pivots": SOURCE / "pivots.bin",
             "valid_codes": SOURCE / "valid_codes.json",
             "runtime": HERE / "runtime_info.json"}
    protocol = {"status": "FROZEN", "proposal_id": "Q20261009231000",
                "candidate_id": None, "curve_id": base_protocol["curve_id"],
                "question": "Do eight exact low-weight image checks reduce batched inverse pivot work?",
                "inputs": base_protocol["inputs"], "repetitions": 2,
                "methods": ["linear_dense", "syndrome8"],
                "check_count": 8, "max_check_weight": 3,
                "wall_cap_seconds": 300, "rss_cap_bytes": 4 * 1024**3,
                "measurement_boundary": "one complete output query over 8191 seed sums, including denominator inversion, 14 field products, RHS XORs, parity checks, pivot solves, and pair validation; dual index setup separate",
                "host_isolation": None,
                "source_sha256": {name: sha(path) for name, path in paths.items()}}
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "inputs": len(protocol["inputs"])}))


if __name__ == "__main__":
    main()
