"""Write-once protocol for the accepted d13 public-Q solver seed."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "public_q_first_relation_protocol_v4.json"
    base = json.loads((HERE / "public_q_first_relation_protocol_v3.json").read_text())
    failed = HERE / "public_q_runs/d13_m12_20261009T220843Z/result.json"
    result = json.loads(failed.read_text())
    if (result["status"] != "timeout" or len(result["attempts"]) != 1 or
            result["attempts"][0]["exit_code"] != 255 or
            result["attempts"][0]["solver_status"] != "indeterminate" or
            result["attempts"][0]["stop_reason"] is not None):
        raise ValueError("prior run is not the documented solver argument rejection")
    stderr = HERE / "public_q_runs/d13_m12_20261009T220843Z/attempts/model_01/cryptominisat.stderr.txt"
    if not stderr.read_text().startswith("not an integer: 202610061312\n"):
        raise ValueError("prior solver stderr does not show the frozen seed rejection")
    base["kind"] = "ecc2k130_n131_d13_m12_public_q_first_relation_protocol_v4"
    base["solver_fix"] = {
        "issue": "CryptoMiniSat rejected the previous seed at argument parsing",
        "previous_seed": 202610061312,
        "accepted_seed": 2026100613,
        "preserved_failed_result_sha256": sha(failed),
        "preserved_failed_stderr_sha256": sha(stderr),
        "failure_classification": "indeterminate solver exit without resource stop is producer_solver_failure",
        "unchanged_method_and_resource_envelope": True,
    }
    base["run_policy"]["solver_seed"] = 2026100613
    base["sha256"]["runner"] = sha(HERE / "run_public_q_first_relation_v4.py")
    base["sha256"]["auditor"] = sha(HERE / "audit_public_q_first_relation_v4.py")
    with output.open("x") as stream:
        json.dump(base, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(output)


if __name__ == "__main__":
    main()
