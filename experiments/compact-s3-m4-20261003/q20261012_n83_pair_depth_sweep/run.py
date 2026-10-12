#!/usr/bin/env python3
"""Extend the exact-blocked N83 first-pair sequence on frozen targets."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1508 = PARENT / "q20261012_n83_blocked_pair_handoff"
spec = importlib.util.spec_from_file_location("q1508", Q1508 / "run.py")
q8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q8)


def main():
    protocol = q8.read(HERE / "protocol.json")
    assert protocol["start_round"] == 2 and protocol["max_rounds_per_target"] == 8
    for name, path in (("q1508_result", Q1508 / "result.json"),
                       ("q1508_analysis", Q1508 / "analysis.json"),
                       ("q1508_run", Q1508 / "run.py")):
        assert q8.sha(path) == protocol["source_sha256"][name]
    build = q8.read(HERE / "build_receipt.json")
    binary = Path(build["binary_path"])
    assert q8.sha(binary) == build["binary_sha256"]
    native_build = q8.read(q8.Q1505 / "build_receipt.json")
    native = Path(native_build["binary_path"])
    assert q8.sha(native) == native_build["binary_sha256"]
    frozen = q8.read(q8.Q1488 / "freeze.json")
    raw_base = q8.BASE.read_bytes()
    keys = {int.from_bytes(raw_base[i:i + 21], "little")
            for i in range(0, len(raw_base), 21)}
    assert len(keys) == protocol["factor_base_folded_columns_K"]
    onb = q8.CountedOnb(83)
    curve, orbit = q8.Curve(onb), q8.OrbitKey(onb)
    order = int(q8.read(q8.BASE_MANIFEST)["curve"]["subgroup_order"])
    assert not (HERE / "result.json").exists()
    all_rows = []
    for label in ("selected", "holdout"):
        cell = frozen["inputs"][label]
        raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        target = tuple(q8.read(q8.TARGETS[label])["public_target"])
        blocks = []
        for prior_number in range(protocol["start_round"]):
            prior_folder = Q1508 / "runs" / f"{label}_round{prior_number}"
            prior = q8.read(prior_folder / "receipt.json")
            assert q8.pair_exhausted(prior, prior_folder)
            blocks.append(prior["sat"]["first_pair_bits"])
        for number in range(protocol["start_round"], protocol["max_rounds_per_target"]):
            assert len(blocks) == number
            folder = HERE / "runs" / f"{label}_round{number}"
            if folder.exists():
                prior = q8.read(folder / "receipt.json")
                assert prior["input"] == label and prior["round"] == number
                all_rows.append({"input": label, "round": number,
                                 "receipt_sha256": q8.sha(folder / "receipt.json")})
                if q8.pair_exhausted(prior, folder):
                    blocks.append(prior["sat"]["first_pair_bits"])
                    continue
                break
            folder.mkdir(parents=True)
            system_bytes = q8.blocked_system(raw, blocks)
            system = folder / "system.xcnf"
            system.write_bytes(system_bytes)
            sat = q8.sat_pair(binary, system, folder, protocol)
            system_sha256 = q8.sha(system)
            (folder / "system.xcnf.gz").write_bytes(gzip.compress(system_bytes, mtime=0))
            system.unlink()
            assert sat["order_marker_ok"] and sat["mask_marker_ok"]
            bits = sat["first_pair_bits"]
            assert bits is None or bits not in blocks
            leaves = q8.base_pair(bits, onb, curve, orbit, keys, order) if bits else []
            usable = bool(leaves) and all(x["exact_base_member"] for x in leaves)
            scans = q8.scan_pair(label, leaves, target, native, folder,
                                 protocol, onb, curve) if usable else []
            row = {"proposal_id": "Q1509", "candidate_id": None,
                   "run_id": None, "curve_id": protocol["curve_id"],
                   "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
                   "input": label, "workload_id": cell["workload_id"],
                   "round": number, "blocked_pair_count_before": len(blocks),
                   "blocked_pair_bits_sha256": [hashlib.sha256(x.encode()).hexdigest()
                                                for x in blocks],
                   "system_sha256": system_sha256, "sat": sat,
                   "leaves": [{k: v for k, v in x.items() if k != "point"}
                              for x in leaves],
                   "both_exact_base_usable": usable,
                   "scan_rows": [{"signs": x["signs"], "status": x["status"],
                                  "receipt_sha256": q8.sha(folder / f"scan_{x['signs'][0]}_{x['signs'][1]}" / "receipt.json")}
                                 for x in scans],
                   "complete_n83_decomposition_work_log2": None,
                   "complete_n131_solve_work_log2": None}
            q8.save(folder / "receipt.json", row)
            all_rows.append({"input": label, "round": number,
                             "receipt_sha256": q8.sha(folder / "receipt.json")})
            q8.save(HERE / "result.partial.json", {"proposal_id": "Q1509",
                                                 "rows": all_rows})
            print(label, number, sat["status"],
                  sat["first_pair_combined_calls"], usable, flush=True)
            if q8.pair_exhausted(row, folder):
                blocks.append(bits)
            else:
                break
    q8.save(HERE / "result.json", {"proposal_id": "Q1509", "candidate_id": None,
                                  "run_id": None, "curve_id": protocol["curve_id"],
                                  "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
                                  "protocol_sha256": q8.sha(HERE / "protocol.json"),
                                  "source_sha256": q8.sha(Path(__file__)),
                                  "rows": all_rows,
                                  "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()
