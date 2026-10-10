#!/usr/bin/env python3
"""Freeze the N41 implicit four-block joint SAT control and public query."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_n131_zero_sum_triple_20261009"
ROOT = HERE.parents[2]
CMS = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    files = {
        "freezer": "freeze.py",
        "builder": "build_n41.py",
        "runner": "run.py",
        "auditor": "audit.py",
        "algebra_auditor": "algebra_audit.py",
        "witness_chart": "witness_chart.json",
        "runtime": "sage_runtime_info.json",
        "public_formula": "public.xcnf",
        "public_build": "public_build.json",
        "control_formula": "control.xcnf",
        "control_build": "control_build.json",
        "source_input": "../n41_n131_zero_sum_triple_20261009/input_public.txt",
        "source_public_result": "../n41_n131_zero_sum_triple_20261009/public/result.json",
        "karatsuba": "../../koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py",
        "circuit": "../../koblitz-s5-invariant-20260924/circuit_sat.py",
    }
    assert (HERE / files["source_input"]).resolve() == \
        (SOURCE / "input_public.txt").resolve()
    assert (HERE / files["karatsuba"]).resolve() == \
        (ROOT / "experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py").resolve()
    assert (HERE / files["circuit"]).resolve() == \
        (ROOT / "experiments/koblitz-s5-invariant-20260924/circuit_sat.py").resolve()
    build_sha = sha(HERE / "build_n41.py")
    for mode in ("control", "public"):
        receipt = json.loads((HERE / f"{mode}_build.json").read_text())
        assert receipt["status"] == "BUILT" and receipt["mode"] == mode
        assert receipt["sha256"]["source"] == build_sha
        assert receipt["sha256"]["xcnf"] == sha(HERE / f"{mode}.xcnf")
        assert receipt["sha256"]["runtime"] == sha(HERE / "sage_runtime_info.json")
    chart = json.loads((HERE / "witness_chart.json").read_text())
    assert chart["status"] == "PASS_EXACT_ALGEBRAIC_CHART"
    assert chart["sha256"]["source"] == sha(HERE / "algebra_audit.py")
    protocol = {
        "status": "FROZEN",
        "proposal_id": "Q20261009200400",
        "candidate_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "target_count": 1,
        "target": [1458168294740, 1672312028033],
        "method": "four W7 zero-sum triple quartics using low-power products, joined by three target-ended S3 equations over four raw preimages; all source masks implicit",
        "control_policy": "fix only the eight source mask vectors of an independently audited public row; the public formula has no mask units",
        "limits": {"workers": 1, "control_seconds": 60,
                   "public_seconds": 120,
                   "combined_rss_bytes": 4*1024**3},
        "files": files,
        "sha256": {key: sha(HERE / name) for key, name in files.items()} |
                  {"cryptominisat_binary": sha(CMS)},
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": protocol["status"],
                      "protocol_sha256": sha(output),
                      "public_formula_sha256": protocol["sha256"]["public_formula"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
