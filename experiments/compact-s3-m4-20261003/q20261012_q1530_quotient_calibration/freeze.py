#!/usr/bin/env python3
"""Freeze the Q1530 source records before calculating the sweep."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCES = {
    "n53_full_protocol": PARENT / "q20261011_n53_full_pipeline/protocol.json",
    "n53_full_measurement": PARENT / "q20261011_n53_full_pipeline/native_measurement.json",
    "n53_full_replay": PARENT / "q20261011_n53_full_pipeline/independent_replay.json",
    "n53_ordinary_protocol": PARENT / "q20261011_n53_table2m/protocol.json",
    "n53_ordinary_measurement": PARENT / "q20261011_n53_table2m/measurement.json",
    "n53_ordinary_analysis": PARENT / "q20261011_n53_table2m/analysis.json",
    "n53_ordinary_replay": PARENT / "q20261011_n53_table2m/independent_replay.json",
    "n131_q1526_sweep": PARENT / "q20261012_q1526_pair_hyperparams/analysis.json",
    "n83_q1529_measurement": PARENT / "q20261012_q1529_n83_w5_pair_table/analysis.json",
}


def main():
    target = HERE / "protocol.json"
    assert not target.exists(), "protocol already frozen"
    records = {name: {"relative_path": str(path.relative_to(PARENT)),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
               for name, path in SOURCES.items()}
    protocol = {
        "proposal_id": "Q1530", "candidate_id": None, "run_id": None,
        "isogeny": "none", "stage_code": "PDP4mitm",
        "curve_ids": {"n53": "EC1N53Ckb1hf77aab617904",
                      "n83": "EC1N83Ckb1h876c2921cb64",
                      "n131": "EC1N131Ckb1h6816f880945e"},
        "source_records": records,
        "calibration": "N53 full quotient table and ordinary 2m random descriptor table; compare distinct-key coverage, matched positions, and B^2/(2r) conditional law",
        "sweep": {"weights": [5, 6, 7, 8],
                  "table_fraction_exponents": list(range(21)),
                  "charged_pair_additions": "T+(1+1/(2*n))*Q_lifted",
                  "T": "n*K^2*2^-j",
                  "Q_lifted": "K*2*r/B^2*2^j",
                  "matrix_proxy_modular_events": "4*K^2",
                  "budget_exponent": 61,
                  "assumptions": "Q1526 uniform independent query support and one novel rank row per useful match; W7/W8 base sizes sampled; N131 native reuse extrapolated from Q1529 N83 implementation"},
        "stop_rule": "reprice exactly 84 Q1526 cells and N53 two frozen calibration rows; no solver or challenge dispatch",
    }
    target.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
