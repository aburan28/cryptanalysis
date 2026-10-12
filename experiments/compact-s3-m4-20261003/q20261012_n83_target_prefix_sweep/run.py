#!/usr/bin/env python3
"""Frozen ordinary N83 target-midpoint priority sweep and exact-base screen."""
import gzip
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1508 = PARENT / "q20261012_n83_blocked_pair_handoff"
spec = importlib.util.spec_from_file_location("q1508", Q1508 / "run.py")
q8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q8)


def main():
    protocol = q8.read(HERE / "protocol.json")
    build = q8.read(HERE / "build_receipt.json")
    sat = Path(build["binary_path"])
    assert q8.sha(sat) == build["binary_sha256"]
    native_build = q8.read(q8.Q1505 / "build_receipt.json")
    native = Path(native_build["binary_path"])
    assert q8.sha(native) == native_build["binary_sha256"]
    for name, path in (("q1488_freeze", q8.Q1488 / "freeze.json"),
                       ("q1507_build", PARENT / "q20261012_n83_target_mid_priority/build_receipt.json"),
                       ("order_manifest", PARENT / "q20261011_wdsat_order/order_manifest.json"),
                       ("base", q8.BASE), ("base_manifest", q8.BASE_MANIFEST),
                       ("selected_target", q8.TARGETS["selected"]),
                       ("holdout_target", q8.TARGETS["holdout"])):
        assert q8.sha(path) == protocol["source_sha256"][name]
    frozen = q8.read(q8.Q1488 / "freeze.json")
    raw_base = q8.BASE.read_bytes()
    keys = {int.from_bytes(raw_base[i:i+21], "little")
            for i in range(0, len(raw_base), 21)}
    assert len(keys) == protocol["factor_base_folded_columns_K"]
    onb = q8.CountedOnb(83)
    curve, orbit = q8.Curve(onb), q8.OrbitKey(onb)
    order = int(q8.read(q8.BASE_MANIFEST)["curve"]["subgroup_order"])
    assert not (HERE / "result.json").exists()
    rows = []
    for label in protocol["inputs"]:
        cell = frozen["inputs"][label]
        raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        target = tuple(q8.read(q8.TARGETS[label])["public_target"])
        assert curve.onCurve(target)
        for k in protocol["target_midpoint_prefix_lengths"]:
            mode = f"q1510_tmid{k}"
            folder = HERE / "runs" / f"{label}_{mode}"
            if folder.exists():
                prior = q8.read(folder / "receipt.json")
                assert prior["input"] == label and prior["mode"] == mode
                rows.append({"input": label, "mode": mode,
                             "receipt_sha256": q8.sha(folder / "receipt.json")})
                continue
            folder.mkdir(parents=True)
            system = folder / "system.xcnf"
            system.write_bytes(raw)
            params = {**protocol, "branch_order": mode,
                      "cpu_soft_seconds_per_sat_attempt": protocol["cpu_soft_seconds_per_cell"],
                      "cpu_hard_seconds_per_sat_attempt": protocol["cpu_hard_seconds_per_cell"],
                      "wall_seconds_per_sat_attempt": protocol["wall_seconds_per_cell"]}
            attempt = q8.sat_pair(sat, system, folder, params)
            expected = f"Q1469_ORDER {mode} {334+k}"
            attempt["order_marker_ok"] = expected in (
                folder / "solver.stderr.txt").read_text(errors="replace")
            system_sha256 = q8.sha(system)
            (folder / "system.xcnf.gz").write_bytes(gzip.compress(raw, mtime=0))
            system.unlink()
            assert attempt["order_marker_ok"] and attempt["mask_marker_ok"]
            bits = attempt["first_pair_bits"]
            leaves = q8.base_pair(bits, onb, curve, orbit, keys, order) if bits else []
            usable = bool(leaves) and all(x["exact_base_member"] for x in leaves)
            scans = q8.scan_pair(label, leaves, target, native, folder,
                                 params, onb, curve) if usable else []
            row = {"proposal_id": "Q1510", "candidate_id": None, "run_id": None,
                   "curve_id": protocol["curve_id"], "isogeny": "none",
                   "point_decomposition_stage_code": protocol["point_decomposition_stage_code"],
                   "input": label, "workload_id": cell["workload_id"],
                   "mode": mode, "target_midpoint_prefix_length": k,
                   "system_sha256": system_sha256, "sat": attempt,
                   "leaves": [{key: value for key, value in leaf.items() if key != "point"}
                              for leaf in leaves],
                   "both_exact_base_usable": usable,
                   "scan_rows": [{"signs": x["signs"], "status": x["status"],
                                  "receipt_sha256": q8.sha(folder / f"scan_{x['signs'][0]}_{x['signs'][1]}" / "receipt.json")}
                                 for x in scans],
                   "complete_n83_decomposition_work_log2": None,
                   "complete_n131_solve_work_log2": None}
            q8.save(folder / "receipt.json", row)
            rows.append({"input": label, "mode": mode,
                         "receipt_sha256": q8.sha(folder / "receipt.json")})
            q8.save(HERE / "result.partial.json", {"proposal_id": "Q1510", "rows": rows})
            print(label, k, attempt["status"], attempt["first_pair_combined_calls"],
                  usable, flush=True)
    q8.save(HERE / "result.json", {"proposal_id": "Q1510", "candidate_id": None,
                                  "run_id": None, "curve_id": protocol["curve_id"],
                                  "isogeny": "none", "point_decomposition_stage_code": protocol["point_decomposition_stage_code"],
                                  "protocol_sha256": q8.sha(HERE / "protocol.json"),
                                  "source_sha256": q8.sha(Path(__file__)),
                                  "rows": rows,
                                  "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()
