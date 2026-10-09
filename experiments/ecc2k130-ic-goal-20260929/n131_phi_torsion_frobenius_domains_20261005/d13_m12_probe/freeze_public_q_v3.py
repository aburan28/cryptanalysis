"""Write-once protocol for the corrected d13 public-Q runner and audit."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "public_q_first_relation_protocol_v3.json"
    base = json.loads((HERE / "public_q_first_relation_protocol_v2.json").read_text())
    failed = (HERE / "public_q_runs/d13_m12_20261009T220450Z/result.json")
    result = json.loads(failed.read_text())
    if (result["status"] != "producer_failure" or
            result["error"] != {"type": "ValueError",
                                "message": "official Q or cofactor fiber changed"} or
            result["attempts"]):
        raise ValueError("prior failed run is not the documented fixture check")
    base["kind"] = "ecc2k130_n131_d13_m12_public_q_first_relation_protocol_v3"
    base["correctness_fix"] = {
        "issue": "same official-Q coordinates stored as decimal strings in workload and integers in geometry",
        "comparison": "convert workload coordinate strings to integers before equality check",
        "preserved_failed_result_sha256": sha(failed),
        "unchanged_method_and_resource_envelope": True,
    }
    base["sha256"]["runner"] = sha(HERE / "run_public_q_first_relation_v3.py")
    base["sha256"]["auditor"] = sha(HERE / "audit_public_q_first_relation_v3.py")
    with output.open("x") as stream:
        json.dump(base, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(output)


if __name__ == "__main__":
    main()
