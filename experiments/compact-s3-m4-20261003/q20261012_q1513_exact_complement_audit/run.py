#!/usr/bin/env python3
"""Continue exact-blocked N83 first-pair enumeration after Q1508's two rounds."""
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1508 = PARENT / "q20261012_n83_blocked_pair_handoff"
sys.path.insert(0, str(Q1508))
from run import (BASE, BASE_MANIFEST, PAIR, Q1488, Q1505, TARGETS,  # noqa: E402
                 CountedOnb, Curve, OrbitKey, base_pair, blocked_system,
                 pair_exhausted, read, sat_pair, save, scan_pair, sha)


def main():
    p = read(HERE / "protocol.json")
    assert sha(Q1508 / "result.json") == p["q1508_result_sha256"]
    assert sha(Q1508 / "run.py") == p["q1508_run_sha256"]
    assert sha(BASE) == p["source_sha256"]["base"]
    assert sha(Q1488 / "freeze.json") == p["source_sha256"]["q1488_freeze"]
    native_build = read(Q1505 / "build_receipt.json")
    sat_build = read(HERE / "build_receipt.json")
    native, sat = Path(native_build["binary_path"]), Path(sat_build["binary_path"])
    assert sha(native) == native_build["binary_sha256"]
    assert sha(sat) == sat_build["binary_sha256"]
    raw_base = BASE.read_bytes()
    keys = {int.from_bytes(raw_base[i:i + 21], "little")
            for i in range(0, len(raw_base), 21)}
    assert len(keys) == p["factor_base_folded_columns_K"]
    onb = CountedOnb(83)
    curve, orbit = Curve(onb), OrbitKey(onb)
    order = int(read(BASE_MANIFEST)["curve"]["subgroup_order"])
    frozen = read(Q1488 / "freeze.json")
    assert not (HERE / "result.json").exists()
    rows = []
    for label in ("selected", "holdout"):
        cell = frozen["inputs"][label]
        raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        fixture = read(TARGETS[label])
        assert fixture["workload_id"] == cell["workload_id"]
        target = tuple(fixture["public_target"])
        assert curve.onCurve(target)
        blocks = []
        for round_number in range(2):
            old_folder = Q1508 / "runs" / f"{label}_round{round_number}"
            old = read(old_folder / "receipt.json")
            assert pair_exhausted(old, old_folder)
            bits = old["sat"]["first_pair_bits"]
            assert bits and bits not in blocks
            blocks.append(bits)
        for round_number in range(2, 2 + p["max_new_rounds_per_target"]):
            folder = HERE / "runs" / f"{label}_round{round_number}"
            if folder.exists():
                prior = read(folder / "receipt.json")
                assert prior["input"] == label and prior["round"] == round_number
                bits = prior["sat"]["first_pair_bits"]
                assert bits and bits not in blocks
                rows.append({"input": label, "round": round_number,
                             "status": prior["sat"]["status"],
                             "receipt_sha256": sha(folder / "receipt.json")})
                if not pair_exhausted(prior, folder):
                    break
                blocks.append(bits)
                continue
            folder.mkdir(parents=True, exist_ok=False)
            system_bytes = blocked_system(raw, blocks)
            system = folder / "system.xcnf"
            system.write_bytes(system_bytes)
            attempt = sat_pair(sat, system, folder, p)
            system_sha256 = sha(system)
            (folder / "system.xcnf.gz").write_bytes(gzip.compress(system_bytes, mtime=0))
            system.unlink()
            assert attempt["order_marker_ok"] and attempt["mask_marker_ok"]
            bits = attempt["first_pair_bits"]
            if bits is not None:
                assert bits not in blocks
                leaves = base_pair(bits, onb, curve, orbit, keys, order)
                scans = scan_pair(label, leaves, target, native, folder, p, onb,
                                  curve) if all(x["exact_base_member"] for x in leaves) else []
            else:
                leaves, scans = [], []
            row = {"proposal_id": "Q1516", "candidate_id": None, "run_id": None,
                   "curve_id": p["curve_id"], "isogeny": "none",
                   "point_decomposition_stage_code": "PDP4hybrid",
                   "input": label, "workload_id": cell["workload_id"],
                   "round": round_number, "blocked_pair_count_before": len(blocks),
                   "blocked_pair_bits_sha256": [hashlib.sha256(x.encode()).hexdigest()
                                                for x in blocks],
                   "system_sha256": system_sha256, "sat": attempt,
                   "solver_binary_sha256": sat_build["binary_sha256"],
                   "leaves": [{k: v for k, v in x.items() if k != "point"}
                              for x in leaves],
                   "both_exact_base_usable": bool(leaves) and all(
                       x["exact_base_member"] for x in leaves),
                   "scan_rows": [{"signs": x["signs"], "status": x["status"],
                                  "receipt_sha256": sha(folder / f"scan_{x['signs'][0]}_{x['signs'][1]}" / "receipt.json")}
                                 for x in scans],
                   "complete_n83_decomposition_work_log2": None,
                   "complete_n131_solve_work_log2": None}
            save(folder / "receipt.json", row)
            rows.append({"input": label, "round": round_number,
                         "status": attempt["status"],
                         "receipt_sha256": sha(folder / "receipt.json")})
            save(HERE / "result.partial.json", {"proposal_id": "Q1516", "rows": rows})
            print(label, round_number, attempt["status"],
                  attempt["first_pair_combined_calls"],
                  row["both_exact_base_usable"], flush=True)
            if bits is None or not pair_exhausted(row, folder):
                break
            blocks.append(bits)
    save(HERE / "result.json", {"proposal_id": "Q1516", "candidate_id": None,
                                "run_id": None, "curve_id": p["curve_id"],
                                "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
                                "protocol_sha256": sha(HERE / "protocol.json"),
                                "source_sha256": sha(Path(__file__)), "rows": rows,
                                "complete_n83_decomposition_work_log2": None,
                                "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()
