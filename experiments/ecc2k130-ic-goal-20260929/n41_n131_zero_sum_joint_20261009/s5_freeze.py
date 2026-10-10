#!/usr/bin/env python3
"""Freeze target-ended S5 formulas, runner, and independent replay sources."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CMS = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = HERE / "s5_protocol.json"
    if output.exists():
        raise FileExistsError(output)
    files = {
        "freezer": "s5_freeze.py",
        "builder": "build_s5.py",
        "block_builder": "build_n41.py",
        "chart_builder": "s5_chart.py",
        "runner": "s5_solver.py",
        "model_checker": "run.py",
        "auditor": "s5_audit.py",
        "algebra_auditor": "s5_identity_audit.py",
        "s5_identity": "s5_identity.json",
        "witness_chart": "witness_chart.json",
        "runtime": "sage_runtime_info.json",
        "public_formula": "s5_public.xcnf",
        "public_build": "s5_public_build.json",
        "control_formula": "s5_control.xcnf",
        "control_build": "s5_control_build.json",
        "chart_formula": "s5_chart.xcnf",
        "chart_build": "s5_chart_build.json",
        "source_input": "../n41_n131_zero_sum_triple_20261009/input_public.txt",
        "source_public_result": "../n41_n131_zero_sum_triple_20261009/public/result.json",
        "karatsuba": "../../koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py",
        "circuit": "../../koblitz-s5-invariant-20260924/circuit_sat.py",
    }
    assert (HERE / files["karatsuba"]).resolve() == \
        (ROOT / "experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py").resolve()
    assert (HERE / files["circuit"]).resolve() == \
        (ROOT / "experiments/koblitz-s5-invariant-20260924/circuit_sat.py").resolve()
    for mode in ("public", "control"):
        receipt = json.loads((HERE / f"s5_{mode}_build.json").read_text())
        assert receipt["status"] == "BUILT" and receipt["mode"] == mode
        assert receipt["sha256"]["source"] == sha(HERE / "build_s5.py")
        assert receipt["sha256"]["formula"] == sha(HERE / f"s5_{mode}.xcnf")
    chart = json.loads((HERE / "s5_chart_build.json").read_text())
    assert chart["status"] == "BUILT_PINNED_CHART"
    assert chart["sha256"]["source"] == sha(HERE / "s5_chart.py")
    assert chart["sha256"]["formula"] == sha(HERE / "s5_chart.xcnf")
    identity = json.loads((HERE / "s5_identity.json").read_text())
    assert identity["status"] == "PASS_EXACT_S5_CHART"
    protocol = {
        "status": "FROZEN_S5",
        "proposal_id": "Q20261009205500", "candidate_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "target_count": 1,
        "target": [1458168294740, 1672312028033],
        "method": "four implicit W7 zero-sum triple quartics joined by one exact five-point target invariant with four raw target preimages",
        "control_policy": "chart pins the known public row masks, four block output fields, and target fiber flag; control pins only the eight source mask vectors; public pins none",
        "limits": {"workers": 1, "chart_seconds": 30,
                   "control_seconds": 60, "public_seconds": 120,
                   "combined_rss_bytes": 4*1024**3},
        "files": files,
        "sha256": {key: sha(HERE / name) for key, name in files.items()} |
                  {"cryptominisat_binary": sha(CMS)},
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": protocol["status"],
                      "protocol_sha256": sha(output),
                      "public_formula_sha256": sha(HERE / "s5_public.xcnf")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
