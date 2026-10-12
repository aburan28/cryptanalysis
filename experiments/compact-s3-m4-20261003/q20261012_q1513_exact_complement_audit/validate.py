#!/usr/bin/env python3
"""Read-only replay of Q1516's frozen first-pair blocks and exact scans."""
import gzip
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("q1516_run", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def check():
    p = run.read(HERE / "protocol.json")
    result = run.read(HERE / "result.json")
    assert result["protocol_sha256"] == run.sha(HERE / "protocol.json")
    assert result["source_sha256"] == run.sha(HERE / "run.py")
    assert run.sha(run.Q1508 / "result.json") == p["q1508_result_sha256"]
    assert run.sha(run.Q1508 / "run.py") == p["q1508_run_sha256"]
    assert run.sha(run.BASE) == p["source_sha256"]["base"]
    assert run.sha(run.Q1488 / "freeze.json") == p["source_sha256"]["q1488_freeze"]
    build = run.read(HERE / "build_receipt.json")
    assert build["source_sha256"] == run.sha(HERE / "build.py")
    assert build["build_stdout_sha256"] == run.sha(HERE / "build.stdout.txt")
    assert build["build_stderr_sha256"] == run.sha(HERE / "build.stderr.txt")
    assert build["config_sha256"] == run.sha(
        Path(build["binary_path"]).parent / "src/config.h")
    assert build["binary_sha256"] == run.sha(Path(build["binary_path"]))
    assert build["parent_build_receipt_sha256"] == run.sha(
        run.Q1508 / "build_receipt.json")
    frozen = run.read(run.Q1488 / "freeze.json")
    raw_base = run.BASE.read_bytes()
    keys = {int.from_bytes(raw_base[i:i + 21], "little")
            for i in range(0, len(raw_base), 21)}
    assert len(keys) == p["factor_base_folded_columns_K"]
    onb = run.CountedOnb(83)
    curve, orbit = run.Curve(onb), run.OrbitKey(onb)
    order = int(run.read(run.BASE_MANIFEST)["curve"]["subgroup_order"])
    rows, scanned, hits, calls, usable, sat_calls = [], 0, 0, 0, 0, 0
    for label in ("selected", "holdout"):
        cell = frozen["inputs"][label]
        raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        target = tuple(run.read(run.TARGETS[label])["public_target"])
        blocks = []
        for number in range(2):
            old_folder = run.Q1508 / "runs" / f"{label}_round{number}"
            old = run.read(old_folder / "receipt.json")
            assert run.pair_exhausted(old, old_folder)
            blocks.append(old["sat"]["first_pair_bits"])
        for number in range(2, 2 + p["max_new_rounds_per_target"]):
            folder = HERE / "runs" / f"{label}_round{number}"
            if not folder.exists():
                break
            row = run.read(folder / "receipt.json")
            assert row["input"] == label and row["round"] == number
            assert row["workload_id"] == cell["workload_id"]
            assert row["blocked_pair_count_before"] == len(blocks)
            assert row["blocked_pair_bits_sha256"] == [
                hashlib.sha256(x.encode()).hexdigest() for x in blocks]
            system = gzip.decompress((folder / "system.xcnf.gz").read_bytes())
            assert system == run.blocked_system(raw, blocks)
            assert hashlib.sha256(system).hexdigest() == row["system_sha256"]
            assert run.sha(folder / "solver.stdout.txt") == row["sat"]["stdout_sha256"]
            assert run.sha(folder / "solver.stderr.txt") == row["sat"]["stderr_sha256"]
            assert row["sat"]["search_started"] and row["sat"]["order_marker_ok"]
            assert row["sat"]["mask_marker_ok"]
            sat_calls += row["sat"]["first_pair_combined_calls"] or 0
            if "solver_binary_sha256" in row:
                assert row["solver_binary_sha256"] == run.read(
                    HERE / "build_receipt.json")["binary_sha256"]
            marker = run.PAIR.findall((folder / "solver.stderr.txt").read_bytes())
            bits = row["sat"]["first_pair_bits"]
            assert len(marker) == (1 if bits is not None else 0)
            if bits is not None:
                assert marker[0][3].decode() == bits
            if bits is not None:
                assert bits not in blocks
                leaves = run.base_pair(bits, onb, curve, orbit, keys, order)
                assert [{k: v for k, v in x.items() if k != "point"}
                        for x in leaves] == row["leaves"]
                is_usable = all(x["exact_base_member"] for x in leaves)
                assert row["both_exact_base_usable"] == is_usable
                usable += int(is_usable)
                if is_usable:
                    assert len(row["scan_rows"]) == 4
                    for summary in row["scan_rows"]:
                        s0, s1 = summary["signs"]
                        scan_folder = folder / f"scan_{s0}_{s1}"
                        scan = run.read(scan_folder / "receipt.json")
                        assert run.sha(scan_folder / "receipt.json") == summary["receipt_sha256"]
                        assert scan["status"] == summary["status"] == "COMPLETE"
                        assert run.sha(scan_folder / "stdout.txt") == scan["stdout_sha256"]
                        assert run.sha(scan_folder / "stderr.txt") == scan["stderr_sha256"]
                        lines = (scan_folder / "stdout.txt").read_text().splitlines()
                        assert scan["native_result"] == json.loads(lines[-1])
                        assert scan["native_hit_lines"] == lines[:-1]
                        assert scan["native_result"]["scanned"] == p["factor_base_actual_B"]
                        p0 = leaves[0]["point"] if s0 == 1 else curve.neg(leaves[0]["point"])
                        p1 = leaves[1]["point"] if s1 == 1 else curve.neg(leaves[1]["point"])
                        comp = curve.add(target, curve.neg(curve.add(p0, p1)))
                        assert scan["complement_x_onb_hex"] == format(onb.toCoords(comp[0]), "x")
                        assert scan["complement_y_onb_hex"] == format(onb.toCoords(comp[1]), "x")
                        scanned += 1
                        hits += scan["native_result"]["hits"]
                        calls += scan["batch_mul_calls_excluding_inversion_internals"] or 0
                else:
                    assert row["scan_rows"] == []
            else:
                assert row["leaves"] == [] and row["scan_rows"] == []
            rows.append({"input": label, "round": number,
                         "status": row["sat"]["status"],
                         "receipt_sha256": run.sha(folder / "receipt.json")})
            if not run.pair_exhausted(row, folder):
                break
            blocks.append(bits)
    assert result["rows"] == rows
    q1509 = run.PARENT / "q20261012_n83_pair_depth_sweep"
    assert run.sha(q1509 / "result.json") == (
        "8df96b60d7d08bdc517a05a03960b3ef0a027b3fea6a229beab8de7db20d956e")
    for label in ("selected", "holdout"):
        for number in (2, 3):
            ours = run.read(HERE / "runs" / f"{label}_round{number}" / "receipt.json")
            prior = run.read(q1509 / "runs" / f"{label}_round{number}" / "receipt.json")
            assert ours["sat"]["first_pair_bits"] == prior["sat"]["first_pair_bits"]
            assert ours["both_exact_base_usable"] == prior["both_exact_base_usable"]
    preflight = HERE / "runs/preflight_max_id_selected_round3"
    failure = run.read(preflight / "receipt.json")
    assert failure["status"] == "DRIVER_PREFLIGHT_FAILURE"
    assert failure["stderr_sha256"] == run.sha(preflight / "solver.stderr.txt")
    assert failure["system_gzip_sha256"] == run.sha(preflight / "system.xcnf.gz")
    assert "dimacs_nb_of_vars <= __MAX_ID__" in (
        preflight / "solver.stderr.txt").read_text()
    return {"proposal_id": "Q1516", "curve_id": p["curve_id"],
            "candidate_id": None, "prior_work": "Q1509", "status": "REPLICATION",
            "measured_replay_rounds": len(rows),
            "replay_first_pair_cnf_xor_calls": sat_calls,
            "replay_first_pair_calls_per_exact_usable_pair": sat_calls / usable if usable else None,
            "replay_exact_base_usable_pairs": usable,
            "replay_complete_signed_complement_scans": scanned,
            "replay_exact_base_hits": hits,
            "replay_batch_mul_calls_excluding_inversion_internals": calls,
            "replay_batch_mul_calls_log2": math.log2(calls) if calls else None,
            "N131_W6_four_sign_full_scan_batch_mul_calls_transfer": 65596347880,
            "N131_W6_four_sign_full_scan_log2_transfer": math.log2(65596347880),
            "N131_full_scan_gap_above_2pow30_6_per_decomposition_bits":
                math.log2(65596347880) - 30.6,
            "complete_n83_decomposition_work_log2": None,
            "complete_n131_solve_work_log2": None}


if __name__ == "__main__":
    output = check()
    if sys.argv[1:] == ["--write-analysis"]:
        (HERE / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    else:
        assert sys.argv[1:] == []
        assert output == run.read(HERE / "analysis.json")
    print("PASS Q1516 exact first-pair blocks and scanned complement replay")
