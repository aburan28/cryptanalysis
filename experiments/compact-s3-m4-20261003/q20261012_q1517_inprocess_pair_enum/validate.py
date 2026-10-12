#!/usr/bin/env python3
"""Read-only source, input, search, and matched-output audit for Q1517."""
import gzip
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("q1517_run", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
spec_build = importlib.util.spec_from_file_location("q1517_build", HERE / "build.py")
builder = importlib.util.module_from_spec(spec_build)
spec_build.loader.exec_module(builder)


def check():
    p = run.read(HERE / "protocol.json")
    result = run.read(HERE / "result.json")
    build = run.read(HERE / "build_receipt.json")
    assert result["protocol_sha256"] == run.sha(HERE / "protocol.json")
    assert result["run_source_sha256"] == run.sha(HERE / "run.py")
    assert run.sha(run.Q1488 / "freeze.json") == p["q1488_freeze_sha256"]
    assert run.sha(run.Q1509 / "result.json") == p["q1509_result_sha256"]
    assert run.sha(run.Q1509 / "build_receipt.json") == p["q1509_build_receipt_sha256"]
    assert build["builder_sha256"] == run.sha(HERE / "build.py")
    assert build["parent_build_receipt_sha256"] == p["q1509_build_receipt_sha256"]
    source = Path(run.read(run.Q1509 / "build_receipt.json")["binary_path"]).parent / "src/wdsat.c"
    assert build["parent_wdsat_sha256"] == run.sha(source)
    target = Path(build["binary_path"]).parent / "src/wdsat.c"
    anchor = "bool wdsat_solve_rest(int_t l, int_t set_end, int_t conf[]) {\n"
    assert target.read_text() == source.read_text().replace(
        anchor, builder.GATE + anchor + "\tif(q1517_gate(conf[0])) return false;\n")
    assert build["patched_wdsat_sha256"] == run.sha(target)
    assert build["config_sha256"] == run.sha(target.parent / "config.h")
    assert build["binary_sha256"] == run.sha(Path(build["binary_path"]))
    assert build["build_stdout_sha256"] == run.sha(HERE / "build.stdout.txt")
    assert build["build_stderr_sha256"] == run.sha(HERE / "build.stderr.txt")
    frozen = run.read(run.Q1488 / "freeze.json")
    assert len(result["rows"]) == 2
    rows = []
    for label, row in zip(("selected", "holdout"), result["rows"]):
        cell = frozen["inputs"][label]
        assert row["input"] == label and row["workload_id"] == cell["workload_id"]
        folder = HERE / "runs" / label
        raw = gzip.decompress((folder / "system.xcnf.gz").read_bytes())
        source_raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert raw == source_raw
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"] == row["system_sha256"]
        assert row["stdout_sha256"] == run.sha(folder / "solver.stdout.txt")
        assert row["stderr_sha256"] == run.sha(folder / "solver.stderr.txt")
        stderr = (folder / "solver.stderr.txt").read_bytes()
        markers = [(int(a), int(b), int(c), int(d), e.decode())
                   for a, b, c, d, e in run.PAIR.findall(stderr)]
        assert row["first_pairs"] == [
            {"index": a, "branch": b, "cnf_calls": c,
             "xor_calls": d, "bits": e} for a, b, c, d, e in markers]
        assert [x[0] for x in markers] == list(range(1, 9))
        assert len(set(x[4] for x in markers)) == 8
        assert all(a[2] + a[3] < b[2] + b[3]
                   for a, b in zip(markers, markers[1:]))
        assert [x[4] for x in markers] == run.baseline_bits(label)
        assert row["sequence_equal_q1509"] is True
        assert row["status"] == "EIGHT_PAIRS_TERMINATED" and row["return_code"] == 47
        assert row["search_started"] and row["order_marker_ok"]
        assert f"Q1481_MASK {p['phase']} ".encode() in stderr
        old_rows = [run.read((run.Q1508 if i < 2 else run.Q1509) / "runs" /
                             f"{label}_round{i}" / "receipt.json") for i in range(8)]
        assert [x["sat"]["first_pair_bits"] for x in old_rows] == [
            x[4] for x in markers]
        assert [i for i, x in enumerate(old_rows) if x["both_exact_base_usable"]] == [0, 2, 6]
        for i in (0, 2, 6):
            parent = run.Q1508 if i < 2 else run.Q1509
            scan_folder = parent / "runs" / f"{label}_round{i}"
            assert len(old_rows[i]["scan_rows"]) == 4
            for item in old_rows[i]["scan_rows"]:
                s0, s1 = item["signs"]
                scan = run.read(scan_folder / f"scan_{s0}_{s1}" / "receipt.json")
                assert scan["status"] == "COMPLETE"
                assert scan["native_result"]["scanned"] == p["factor_base_actual_B"]
                assert scan["native_result"]["hits"] == 0
        baseline = sum(x["sat"]["first_pair_combined_calls"] for x in old_rows)
        assert row["q1509_restarted_calls"] == baseline
        calls = markers[-1][2] + markers[-1][3]
        rows.append({"input": label, "workload_id": row["workload_id"],
                     "distinct_pairs": 8,
                     "exact_base_usable_pairs_from_matched_Q1509": 3,
                     "new_inprocess_cnf_xor_calls": calls,
                     "Q1509_restarted_cnf_xor_calls": baseline,
                     "call_reduction": baseline - calls,
                     "call_ratio": baseline / calls,
                     "work_bits_saved": math.log2(baseline / calls),
                     "new_calls_per_exact_usable_pair": calls / 3,
                     "status": row["status"]})
    return {"proposal_id": "Q1517", "candidate_id": None,
            "curve_id": p["curve_id"], "isogeny": "none",
            "point_decomposition_stage_code": "PDP4sat",
            "rows": rows, "complete_n83_decomposition_work_log2": None,
            "complete_n131_solve_work_log2": None}


if __name__ == "__main__":
    output = check()
    if sys.argv[1:] == ["--write-analysis"]:
        (HERE / "analysis.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")
    else:
        assert sys.argv[1:] == []
        assert output == run.read(HERE / "analysis.json")
    print("PASS Q1517 exact in-process eight-pair sequence and matched work")
