#!/usr/bin/env python3
"""Read-only exact-input, solver-marker and group replay for Q1510."""
import gzip
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("q1510_run", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
q8 = run.q8
build_spec = importlib.util.spec_from_file_location("q1510_build", HERE / "build.py")
build_mod = importlib.util.module_from_spec(build_spec)
build_spec.loader.exec_module(build_mod)


def check():
    protocol = q8.read(HERE / "protocol.json")
    result = q8.read(HERE / "result.json")
    build = q8.read(HERE / "build_receipt.json")
    assert result["protocol_sha256"] == q8.sha(HERE / "protocol.json")
    assert result["source_sha256"] == q8.sha(HERE / "run.py")
    assert result["hardware_sha256"] == q8.sha(HERE / "hardware.json")
    hardware = q8.read(HERE / "hardware.json")
    assert hardware["architecture"] == "arm64"
    assert hardware["host_level_isolation"] is False
    assert build["source_sha256"] == q8.sha(HERE / "build.py")
    assert build["priorities"] == build_mod.priorities()
    assert build["binary_sha256"] == q8.sha(Path(build["binary_path"]))
    assert build["patched_source_sha256"] == q8.sha(Path(build["patched_source_path"]))
    assert build["config_sha256"] == q8.sha(Path(build["binary_path"]).parent / "src/config.h")
    assert build["build_stdout_sha256"] == q8.sha(HERE / "build.stdout.txt")
    assert build["build_stderr_sha256"] == q8.sha(HERE / "build.stderr.txt")
    for name, path in (("q1488_freeze", q8.Q1488 / "freeze.json"),
                       ("q1507_build", run.PARENT / "q20261012_n83_target_mid_priority/build_receipt.json"),
                       ("order_manifest", run.PARENT / "q20261011_wdsat_order/order_manifest.json"),
                       ("base", q8.BASE), ("base_manifest", q8.BASE_MANIFEST),
                       ("selected_target", q8.TARGETS["selected"]),
                       ("holdout_target", q8.TARGETS["holdout"])):
        assert q8.sha(path) == protocol["source_sha256"][name]
    frozen = q8.read(q8.Q1488 / "freeze.json")
    raw_base = q8.BASE.read_bytes()
    keys = {int.from_bytes(raw_base[i:i+21], "little") for i in range(0, len(raw_base), 21)}
    assert len(keys) == protocol["factor_base_folded_columns_K"]
    onb = q8.CountedOnb(83)
    curve, orbit = q8.Curve(onb), q8.OrbitKey(onb)
    order = int(q8.read(q8.BASE_MANIFEST)["curve"]["subgroup_order"])
    rows, summaries = [], []
    scan_count = 0
    for label in protocol["inputs"]:
        cell = frozen["inputs"][label]
        raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        target = tuple(q8.read(q8.TARGETS[label])["public_target"])
        for k in protocol["target_midpoint_prefix_lengths"]:
            mode = f"q1510_tmid{k}"
            folder = HERE / "runs" / f"{label}_{mode}"
            row = q8.read(folder / "receipt.json")
            assert row["input"] == label and row["mode"] == mode
            assert row["workload_id"] == cell["workload_id"]
            assert row["curve_id"] == protocol["curve_id"]
            assert row["hardware_sha256"] == result["hardware_sha256"]
            assert row["target_midpoint_prefix_length"] == k
            system = gzip.decompress((folder / "system.xcnf.gz").read_bytes())
            assert system == raw and hashlib.sha256(system).hexdigest() == row["system_sha256"]
            assert q8.sha(folder / "solver.stdout.txt") == row["sat"]["stdout_sha256"]
            assert q8.sha(folder / "solver.stderr.txt") == row["sat"]["stderr_sha256"]
            log = (folder / "solver.stderr.txt").read_text(errors="replace")
            assert row["sat"]["order_marker_ok"] and f"Q1469_ORDER {mode} {334+k}" in log
            assert row["sat"]["mask_marker_ok"] and row["sat"]["search_started"]
            marker = q8.PAIR.findall((folder / "solver.stderr.txt").read_bytes())
            bits = row["sat"]["first_pair_bits"]
            assert len(marker) == (1 if bits else 0)
            if bits:
                assert marker[0][3].decode() == bits
                assert row["sat"]["first_pair_combined_calls"] == int(marker[0][1])+int(marker[0][2])
                leaves = q8.base_pair(bits, onb, curve, orbit, keys, order)
                assert [{a: b for a, b in leaf.items() if a != "point"} for leaf in leaves] == row["leaves"]
                usable = all(leaf["exact_base_member"] for leaf in leaves)
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
                        assert q8.sha(scan_folder / "stderr.txt") == scan["stderr_sha256"]
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
                        scan_count += 1
                else:
                    assert row["scan_rows"] == []
            else:
                assert row["leaves"] == [] and row["scan_rows"] == []
                usable = False
            summaries.append({"input": label, "mode": mode, "k": k,
                              "status": row["sat"]["status"],
                              "combined_calls": row["sat"]["first_pair_combined_calls"],
                              "pair_bits_sha256": hashlib.sha256(bits.encode()).hexdigest() if bits else None,
                              "exact_base_usable": usable,
                              "child_user_cpu_seconds": row["sat"]["child_user_cpu_seconds"],
                              "child_peak_rss_bytes_darwin": row["sat"]["child_peak_rss_bytes_darwin"]})
            rows.append({"input": label, "mode": mode,
                         "receipt_sha256": q8.sha(folder / "receipt.json")})
    assert result["rows"] == rows
    assert len(rows) == 2*len(protocol["target_midpoint_prefix_lengths"])
    by_k = {k: [x for x in summaries if x["k"] == k]
            for k in protocol["target_midpoint_prefix_lengths"]}
    assert all(len(values) == 2 for values in by_k.values())
    assert all(values[0]["pair_bits_sha256"] == values[1]["pair_bits_sha256"]
               for values in by_k.values())
    first_eight = set()
    for number in range(8):
        source = (run.PARENT / "q20261012_n83_blocked_pair_handoff" if number < 2
                  else run.PARENT / "q20261012_n83_pair_depth_sweep")
        prior = q8.read(source / "runs" / f"selected_round{number}" / "receipt.json")
        first_eight.add(hashlib.sha256(prior["sat"]["first_pair_bits"].encode()).hexdigest())
    assert len(first_eight) == 8
    assert by_k[0][0]["pair_bits_sha256"] in first_eight
    assert by_k[64][0]["pair_bits_sha256"] not in first_eight
    assert by_k[83][0]["status"] == by_k[83][1]["status"] == "CPU_CAP_SEARCH_STARTED"
    n131_scan = 10*6559634788
    return {"proposal_id": "Q1510", "candidate_id": None,
            "curve_id": protocol["curve_id"], "rows": summaries,
            "complete_signed_complement_scans": scan_count,
            "exact_base_hits": 0,
            "k64_new_pair_vs_q1508_q1509_first_eight": True,
            "same_pair_across_targets_at_each_prefix": True,
            "q1509_result_sha256": q8.sha(run.PARENT / "q20261012_n83_pair_depth_sweep/result.json"),
            "scan_batch_mul_calls_excluding_inversion_internals":
                scan_count * 5 * protocol["scan_pairs_per_complement"],
            "N131_W6_full_scan_batch_mul_calls_transfer": n131_scan,
            "N131_W6_full_scan_log2_transfer": math.log2(n131_scan),
            "N131_per_decomposition_budget_log2_prior_model": 30.6,
            "N131_full_scan_vs_budget_bits_prior_model": math.log2(n131_scan)-30.6,
            "N131_uniform_first_pair_scan_model_log2_prior_Q1505": 123.289,
            "N131_uniform_model_gap_to_2pow61_bits_prior_Q1505": 62.289,
            "complete_n131_solve_work_log2": None}


if __name__ == "__main__":
    analysis = check()
    if sys.argv[1:] == ["--write-analysis"]:
        (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    else:
        assert sys.argv[1:] == []
        assert q8.read(HERE / "analysis.json") == analysis
    print("PASS Q1510 frozen target-prefix and exact-base replay")
