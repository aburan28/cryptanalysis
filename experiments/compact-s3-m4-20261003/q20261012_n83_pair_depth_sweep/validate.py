#!/usr/bin/env python3
"""Read-only audit of Q1509 blocked-pair depth and signed scans."""
import gzip
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("q1509", HERE / "run.py")
q9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q9)
q8 = q9.q8


def check():
    protocol = q8.read(HERE / "protocol.json")
    result = q8.read(HERE / "result.json")
    build = q8.read(HERE / "build_receipt.json")
    assert build["source_sha256"] == q8.sha(HERE / "build.py")
    assert build["parent_build_receipt_sha256"] == q8.sha(q9.Q1508 / "build_receipt.json")
    assert build["config_sha256"] == q8.sha(Path(build["binary_path"]).parent / "src/config.h")
    assert build["binary_sha256"] == q8.sha(Path(build["binary_path"]))
    assert build["build_stdout_sha256"] == q8.sha(HERE / "build.stdout.txt")
    assert build["build_stderr_sha256"] == q8.sha(HERE / "build.stderr.txt")
    assert result["protocol_sha256"] == q8.sha(HERE / "protocol.json")
    assert result["source_sha256"] == q8.sha(HERE / "run.py")
    assert result["curve_id"] == protocol["curve_id"]
    for name, path in (("q1508_result", q9.Q1508 / "result.json"),
                       ("q1508_analysis", q9.Q1508 / "analysis.json"),
                       ("q1508_run", q9.Q1508 / "run.py")):
        assert q8.sha(path) == protocol["source_sha256"][name]
    frozen = q8.read(q8.Q1488 / "freeze.json")
    raw_base = q8.BASE.read_bytes()
    keys = {int.from_bytes(raw_base[i:i+21], "little") for i in range(0, len(raw_base), 21)}
    assert len(keys) == protocol["factor_base_folded_columns_K"]
    onb = q8.CountedOnb(83)
    curve, orbit = q8.Curve(onb), q8.OrbitKey(onb)
    order = int(q8.read(q8.BASE_MANIFEST)["curve"]["subgroup_order"])
    rows, pairs = [], {}
    scans_total = 0
    for label in ("selected", "holdout"):
        cell = frozen["inputs"][label]
        raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        target = tuple(q8.read(q8.TARGETS[label])["public_target"])
        blocks = []
        for number in range(protocol["max_rounds_per_target"]):
            if number < protocol["start_round"]:
                folder = q9.Q1508 / "runs" / f"{label}_round{number}"
            else:
                folder = HERE / "runs" / f"{label}_round{number}"
            row = q8.read(folder / "receipt.json")
            assert row["round"] == number and row["input"] == label
            bits = row["sat"]["first_pair_bits"]
            assert bits and bits not in blocks
            if number >= protocol["start_round"]:
                assert row["blocked_pair_count_before"] == len(blocks)
                assert row["blocked_pair_bits_sha256"] == [
                    hashlib.sha256(x.encode()).hexdigest() for x in blocks]
                system = gzip.decompress((folder / "system.xcnf.gz").read_bytes())
                assert hashlib.sha256(system).hexdigest() == row["system_sha256"]
                assert system == q8.blocked_system(raw, blocks)
                assert q8.sha(folder / "solver.stdout.txt") == row["sat"]["stdout_sha256"]
                assert q8.sha(folder / "solver.stderr.txt") == row["sat"]["stderr_sha256"]
                marker = q8.PAIR.findall((folder / "solver.stderr.txt").read_bytes())
                assert len(marker) == 1 and marker[0][3].decode() == bits
                assert row["sat"]["search_started"] and row["sat"]["order_marker_ok"]
                assert row["sat"]["mask_marker_ok"]
            leaves = q8.base_pair(bits, onb, curve, orbit, keys, order)
            assert [{k: v for k, v in x.items() if k != "point"} for x in leaves] == row["leaves"]
            usable = all(x["exact_base_member"] for x in leaves)
            assert row["both_exact_base_usable"] == usable
            if usable:
                assert len(row["scan_rows"]) == 4
                for summary in row["scan_rows"]:
                    s0, s1 = summary["signs"]
                    scan_folder = folder / f"scan_{s0}_{s1}"
                    scan = q8.read(scan_folder / "receipt.json")
                    assert q8.sha(scan_folder / "receipt.json") == summary["receipt_sha256"]
                    assert scan["status"] == summary["status"] == "COMPLETE"
                    assert q8.sha(scan_folder / "stdout.txt") == scan["stdout_sha256"]
                    assert scan["native_result"] == json.loads((scan_folder / "stdout.txt").read_text().splitlines()[-1])
                    assert scan["native_result"]["scanned"] == protocol["factor_base_actual_B"]
                    assert scan["native_result"]["hits"] == 0
                    assert scan["native_result"]["exceptional_pairs"] == 0
                    assert scan["batch_mul_calls_excluding_inversion_internals"] == 5*protocol["scan_pairs_per_complement"]
                    p0 = leaves[0]["point"] if s0 == 1 else curve.neg(leaves[0]["point"])
                    p1 = leaves[1]["point"] if s1 == 1 else curve.neg(leaves[1]["point"])
                    complement = curve.add(target, curve.neg(curve.add(p0,p1)))
                    assert scan["complement_x_onb_hex"] == format(onb.toCoords(complement[0]), "x")
                    assert scan["complement_y_onb_hex"] == format(onb.toCoords(complement[1]), "x")
                    if number >= protocol["start_round"]:
                        scans_total += 1
            else:
                assert row["scan_rows"] == []
            assert q8.pair_exhausted(row, folder)
            blocks.append(bits)
            if number >= protocol["start_round"]:
                rows.append({"input": label, "round": number,
                             "receipt_sha256": q8.sha(folder / "receipt.json")})
                pairs.setdefault(label, []).append({"round": number,
                    "combined_calls": row["sat"]["first_pair_combined_calls"],
                    "usable": usable,
                    "rational_lifts": [x["rational_lift"] for x in leaves],
                    "bits_sha256": hashlib.sha256(bits.encode()).hexdigest()})
    assert rows == result["rows"] and len(rows) == 12
    assert [x["bits_sha256"] for x in pairs["selected"]] == [
        x["bits_sha256"] for x in pairs["holdout"]]
    analysis = {"proposal_id": "Q1509", "candidate_id": None,
                "curve_id": protocol["curve_id"], "rows": pairs,
                "new_distinct_pairs": len(rows),
                "new_usable_pairs": sum(x["usable"] for values in pairs.values() for x in values),
                "new_complete_signed_scans": scans_total,
                "new_scan_batch_mul_calls_excluding_inversion_internals":
                    scans_total * 5 * protocol["scan_pairs_per_complement"],
                "all_eight_pairs_same_across_targets": True,
                "exact_base_hits": 0,
                "N131_uniform_first_pair_scan_model_log2_prior_Q1505": 123.289,
                "N131_uniform_model_gap_to_2pow61_bits_prior_Q1505": 62.289,
                "complete_N131_solve_work_log2": None}
    return analysis


if __name__ == "__main__":
    analysis = check()
    if sys.argv[1:] == ["--write-analysis"]:
        (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    else:
        assert sys.argv[1:] == []
        assert q8.read(HERE / "analysis.json") == analysis
    print("PASS Q1509 eight-pair two-target exact-base and complement replay")
