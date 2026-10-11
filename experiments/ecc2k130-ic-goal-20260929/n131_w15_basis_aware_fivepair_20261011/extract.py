"""Freeze exact N131 W15 five-pair target fibers through checked Sage."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
INPUT = GOAL / "n131_w15_unrestricted_fivepair_public_20261010/input.json"
PUBLIC = GOAL / "n131_w15_unrestricted_fivepair_public_20261010/result.json"
RUN = GOAL / "n131_w15_onepair_fixed_sat_gate_20261010/fivepair_run.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location("fivepair_source_for_quartic", RUN)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    _, field, curve, _, _ = old.experiment.run.source()
    data = json.loads(INPUT.read_text())
    public = json.loads(PUBLIC.read_text())
    targets = (data["constructed_residual_target_q"],
               data["public_residual_target_q"])
    fibers = []
    for target in targets:
        raw = old.experiment.run.prior.prior.old.target_preimages(curve, tuple(target))
        fibers.append({"projected_target": target,
                       "raw_points": [list(point) for point in raw],
                       "reciprocals": [field.inv(point[0]) for point in raw]})
    assert fibers[0]["raw_points"][data["constructed_residual_preimage_index"]] == data["constructed_residual_raw"]
    assert fibers[1]["raw_points"] == public["raw_target_preimages"]
    record = {"status": "PASS_N131_W15_TARGET_FIBER_EXTRACT",
              "curve_id": data["curve_id"], "fibers": fibers,
              "source_sha256": {"extract.py": sha(__file__), "input.json": sha(INPUT),
                                "public_result.json": sha(PUBLIC),
                                "fivepair_run.py": sha(RUN),
                                "sage_runtime_info.json": sha(HERE / "sage_runtime_info.json")}}
    (HERE / "fibers.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": record["status"],
                      "fiber_sizes": [len(row["raw_points"]) for row in fibers]}))


if __name__ == "__main__":
    main()
