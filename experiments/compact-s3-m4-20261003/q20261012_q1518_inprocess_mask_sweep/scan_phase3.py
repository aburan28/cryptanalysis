#!/usr/bin/env python3
"""Exact full-base complementary-pair screen for Q1518 phase three."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
Q1512 = run.PARENT / "q20261012_n83_raw_x_prefilter"


def main():
    p = run.read(HERE / "scan_protocol.json")
    assert run.sha(HERE / "result.json") == p["q1518_result_sha256"]
    assert run.sha(Q1512 / "build_receipt.json") == p["q1512_build_receipt_sha256"]
    build = run.read(Q1512 / "build_receipt.json")
    binary = Path(build["binary_path"])
    assert run.sha(binary) == build["binary_sha256"]
    assert not (HERE / "scan_result.json").exists()
    prior = run.read(HERE / "result.json")
    base = run.BASE.read_bytes()
    keys = {int.from_bytes(base[i:i + 21], "little")
            for i in range(0, len(base), 21)}
    onb = run.base_runner.CountedOnb(83)
    curve, orbit = run.base_runner.Curve(onb), run.base_runner.OrbitKey(onb)
    order = int(run.read(run.BASE_MANIFEST)["curve"]["subgroup_order"])
    rows = []
    for label in ("selected", "holdout"):
        target = tuple(run.read(run.base_runner.TARGETS[label])["public_target"])
        assert curve.onCurve(target)
        stage = next(x for x in prior["rows"] if x["input"] == label and
                     x["phase"] == p["phase"])
        assert stage["status"] == "EIGHT_PAIRS_TERMINATED"
        for index, item in enumerate(stage["exact_base_outcomes"]):
            if not item["both_exact_base_usable"]:
                continue
            leaves = run.base_runner.base_pair(item["bits"], onb, curve,
                                                orbit, keys, order)
            assert all(x["exact_base_member"] for x in leaves)
            for s0 in (1, -1):
                for s1 in (1, -1):
                    p0 = leaves[0]["point"] if s0 == 1 else curve.neg(leaves[0]["point"])
                    p1 = leaves[1]["point"] if s1 == 1 else curve.neg(leaves[1]["point"])
                    complement = curve.add(target, curve.neg(curve.add(p0, p1)))
                    assert complement is not None and curve.onCurve(complement)
                    assert curve.add(curve.add(p0, p1), complement) == target
                    xhex = format(onb.toCoords(complement[0]), "x")
                    yhex = format(onb.toCoords(complement[1]), "x")
                    args = [str(binary), str(run.BASE), xhex, yhex,
                            str(p["scan_pairs_per_complement"]), str(p["batch_pairs"]),
                            str(p["bloom_log2_bits"]), str(p["bloom_hashes"])]
                    folder = HERE / "scans" / label / f"pair{index}" / f"sign{s0}_{s1}"
                    folder.mkdir(parents=True, exist_ok=False)
                    started = time.monotonic()
                    try:
                        child = subprocess.run(args, text=True, capture_output=True,
                                               timeout=p["wall_seconds_per_complement"])
                        stdout, stderr = child.stdout, child.stderr
                        status = "COMPLETE" if child.returncode == 0 else "PROCESS_FAILURE"
                        code = child.returncode
                    except subprocess.TimeoutExpired as exc:
                        stdout = (exc.stdout or b"").decode(errors="replace")
                        stderr = (exc.stderr or b"").decode(errors="replace")
                        status, code = "TIMEOUT", None
                    (folder / "stdout.txt").write_text(stdout)
                    (folder / "stderr.txt").write_text(stderr)
                    lines = stdout.splitlines()
                    native = json.loads(lines[-1]) if status == "COMPLETE" else None
                    if native:
                        assert native["actual_B"] == p["factor_base_actual_B"]
                        assert native["scanned"] == p["factor_base_actual_B"]
                    row = {"input": label, "workload_id": stage["workload_id"],
                           "phase": p["phase"], "pair_index": index,
                           "signs": [s0, s1], "status": status,
                           "return_code": code, "complement_x_onb_hex": xhex,
                           "complement_y_onb_hex": yhex,
                           "native_result": native,
                           "native_hit_lines": lines[:-1] if native else [],
                           "batch_mul_calls_excluding_inversion_internals":
                               5 * p["scan_pairs_per_complement"] if native and
                               native["hits"] == 0 and native["exceptional_pairs"] == 0 else None,
                           "wall_seconds_exploratory": time.monotonic() - started,
                           "stdout_sha256": run.sha(folder / "stdout.txt"),
                           "stderr_sha256": run.sha(folder / "stderr.txt")}
                    run.save(folder / "receipt.json", row)
                    rows.append(row)
                    run.save(HERE / "scan_result.partial.json",
                             {"proposal_id": "Q1518", "rows": rows})
                    print(label, index, s0, s1, status,
                          native["hits"] if native else None, flush=True)
    run.save(HERE / "scan_result.json", {
        "proposal_id": "Q1518", "candidate_id": None, "run_id": None,
        "curve_id": prior["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "scan_protocol_sha256": run.sha(HERE / "scan_protocol.json"),
        "scan_source_sha256": run.sha(Path(__file__)), "rows": rows,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()
