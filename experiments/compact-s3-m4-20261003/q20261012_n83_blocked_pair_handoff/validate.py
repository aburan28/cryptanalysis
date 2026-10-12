#!/usr/bin/env python3
"""Read-only audit of the frozen Q1508 pair-block handoff."""
import gzip
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("q1508_run", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def check():
    protocol = run.read(HERE / "protocol.json")
    result = run.read(HERE / "result.json")
    sat_build = run.read(HERE / "build_receipt.json")
    native_build = run.read(run.Q1505 / "build_receipt.json")
    frozen = run.read(run.Q1488 / "freeze.json")
    assert result["protocol_sha256"] == run.sha(HERE / "protocol.json")
    assert result["source_sha256"] == run.sha(HERE / "run.py")
    assert sat_build["source_sha256"] == run.sha(HERE / "build.py")
    assert sat_build["parent_build_receipt_sha256"] == run.sha(run.Q1507 / "build_receipt.json")
    assert sat_build["parent_source_sha256"] == run.sha(
        Path(run.read(run.Q1507 / "build_receipt.json")["patched_source_path"]))
    assert sat_build["config_sha256"] == run.sha(
        Path(sat_build["binary_path"]).parent / "src/config.h")
    assert sat_build["build_stdout_sha256"] == run.sha(HERE / "build.stdout.txt")
    assert sat_build["build_stderr_sha256"] == run.sha(HERE / "build.stderr.txt")
    assert run.sha(Path(sat_build["binary_path"])) == sat_build["binary_sha256"]
    assert run.sha(Path(native_build["binary_path"])) == native_build["binary_sha256"]
    for key, path in {"base": run.BASE, "base_manifest": run.BASE_MANIFEST,
                      "q1488_freeze": run.Q1488 / "freeze.json",
                      "q1505_build": run.Q1505 / "build_receipt.json",
                      "q1507_build": run.Q1507 / "build_receipt.json",
                      "q1507_protocol": run.Q1507 / "protocol.json",
                      "selected_target": run.TARGETS["selected"],
                      "holdout_target": run.TARGETS["holdout"]}.items():
        assert run.sha(path) == protocol["source_sha256"][key]
    base = run.BASE.read_bytes()
    keys = {int.from_bytes(base[i:i+21], "little") for i in range(0, len(base), 21)}
    assert len(keys) == protocol["factor_base_folded_columns_K"]
    onb = run.CountedOnb(83)
    curve, orbit = run.Curve(onb), run.OrbitKey(onb)
    order = int(run.read(run.BASE_MANIFEST)["curve"]["subgroup_order"])
    rows = []
    for label in ("selected", "holdout"):
        cell = frozen["inputs"][label]
        raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        blocks = []
        for number in range(protocol["max_rounds_per_target"]):
            folder = HERE / "runs" / f"{label}_round{number}"
            if not folder.exists():
                break
            row = run.read(folder / "receipt.json")
            assert row["input"] == label and row["round"] == number
            assert row["curve_id"] == protocol["curve_id"]
            assert row["workload_id"] == cell["workload_id"]
            assert row["blocked_pair_count_before"] == len(blocks)
            assert row["blocked_pair_bits_sha256"] == [
                hashlib.sha256(x.encode()).hexdigest() for x in blocks]
            system = gzip.decompress((folder / "system.xcnf.gz").read_bytes())
            assert hashlib.sha256(system).hexdigest() == row["system_sha256"]
            assert system == run.blocked_system(raw, blocks)
            assert run.sha(folder / "solver.stdout.txt") == row["sat"]["stdout_sha256"]
            assert run.sha(folder / "solver.stderr.txt") == row["sat"]["stderr_sha256"]
            assert row["sat"]["search_started"] and row["sat"]["order_marker_ok"]
            assert row["sat"]["mask_marker_ok"]
            marker = run.PAIR.findall((folder / "solver.stderr.txt").read_bytes())
            assert len(marker) == 1 and marker[0][3].decode() == row["sat"]["first_pair_bits"]
            bits = row["sat"]["first_pair_bits"]
            assert bits not in blocks
            leaves = run.base_pair(bits, onb, curve, orbit, keys, order)
            assert [{k: v for k, v in x.items() if k != "point"} for x in leaves] == row["leaves"]
            usable = all(x["exact_base_member"] for x in leaves)
            assert row["both_exact_base_usable"] == usable
            if usable:
                assert len(row["scan_rows"]) == 4
                target = tuple(run.read(run.TARGETS[label])["public_target"])
                for summary in row["scan_rows"]:
                    s0, s1 = summary["signs"]
                    scan_folder = folder / f"scan_{s0}_{s1}"
                    scan = run.read(scan_folder / "receipt.json")
                    assert run.sha(scan_folder / "receipt.json") == summary["receipt_sha256"]
                    assert scan["status"] == summary["status"] == "COMPLETE"
                    assert run.sha(scan_folder / "stdout.txt") == scan["stdout_sha256"]
                    assert run.sha(scan_folder / "stderr.txt") == scan["stderr_sha256"]
                    assert scan["native_result"] == json.loads((scan_folder / "stdout.txt").read_text().splitlines()[-1])
                    assert scan["native_result"]["scanned"] == protocol["factor_base_actual_B"]
                    assert scan["native_result"]["hits"] == 0
                    assert scan["native_result"]["exceptional_pairs"] == 0
                    assert scan["batch_mul_calls_excluding_inversion_internals"] == 5 * protocol["scan_pairs_per_complement"]
                    p0 = leaves[0]["point"] if s0 == 1 else curve.neg(leaves[0]["point"])
                    p1 = leaves[1]["point"] if s1 == 1 else curve.neg(leaves[1]["point"])
                    complement = curve.add(target, curve.neg(curve.add(p0, p1)))
                    assert scan["complement_x_onb_hex"] == format(onb.toCoords(complement[0]), "x")
                    assert scan["complement_y_onb_hex"] == format(onb.toCoords(complement[1]), "x")
            else:
                assert row["scan_rows"] == []
            rows.append({"input": label, "round": number,
                         "status": row["sat"]["status"],
                         "receipt_sha256": run.sha(folder / "receipt.json")})
            if run.pair_exhausted(row, folder):
                blocks.append(bits)
            else:
                break
    assert result["rows"] == rows
    assert len(rows) == 4
    for archived in ("preflight_mask_mismatch", "preflight_block_at_eof",
                     "preflight_long_clause_ignored"):
        folder = HERE / "runs" / archived
        failure = run.read(folder / "preflight.json")
        assert failure["status"] == "DRIVER_PREFLIGHT_FAILURE"
        raw = gzip.decompress((folder / "system.xcnf.gz").read_bytes())
        assert hashlib.sha256(raw).hexdigest() == failure.get(
            "source_system_sha256", failure.get("system_sha256"))
        assert run.sha(folder / "solver.stderr.txt") == failure["solver_stderr_sha256"]
    ordinary_scans = 8
    mul_calls = ordinary_scans * 5 * protocol["scan_pairs_per_complement"]
    assert mul_calls == 619551840
    n131_B = 6559634788
    analysis = {"proposal_id": "Q1508", "candidate_id": None,
                "curve_id": protocol["curve_id"],
                "ordinary_targets": 2, "distinct_pairs_per_target": 2,
                "usable_first_pairs": 2, "unusable_second_pairs": 2,
                "complete_signed_complement_scans": ordinary_scans,
                "exact_base_hits": 0,
                "measured_N83_batch_mul_calls_excluding_inversion_internals": mul_calls,
                "measured_N83_batch_mul_calls_log2": math.log2(mul_calls),
                "N131_W6_B": n131_B,
                "N131_full_four_sign_scan_batch_mul_calls_transfer": 10*n131_B,
                "N131_full_four_sign_scan_batch_mul_calls_log2_transfer": math.log2(10*n131_B),
                "N131_per_decomposition_budget_log2_prior_model": 30.6,
                "N131_full_scan_vs_budget_bits_prior_model": math.log2(10*n131_B)-30.6,
                "N131_uniform_first_pair_scan_model_log2_prior_Q1505": 123.289,
                "N131_uniform_model_gap_to_2pow61_bits_prior_Q1505": 123.289-61,
                "complete_N131_solve_work_log2": None,
                "notes": "The N131 transfer assumes one complete four-sign scan and the W<=6 exact base. The Q1505 uniform first-pair model is conditional and excludes first-pair search, rank novelty, matrix, inversion internals, and target stages."}
    return analysis


if __name__ == "__main__":
    analysis = check()
    if sys.argv[1:] == ["--write-analysis"]:
        (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    else:
        assert sys.argv[1:] == []
        assert run.read(HERE / "analysis.json") == analysis
    print("PASS Q1508 exact block, distinct pairs, subgroup/base replay, eight scans")
