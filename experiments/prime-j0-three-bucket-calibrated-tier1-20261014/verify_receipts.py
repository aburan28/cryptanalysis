#!/usr/bin/env python3
"""Independently replay the first calibrated RunPod pair of frozen cases."""

import hashlib
import json
from pathlib import Path
import statistics
import sys
import tarfile


HERE = Path(__file__).resolve().parent
ARCHIVE_SHA256 = "7a694647b00e100b17b553a1d905d66dc0e41cd07751fd7c16f63685da9d3f1e"
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)
JOBS = {7: "00df46d220fa4f5a923fcfb686584d82",
        8: "049757e6d700437bb0feec72b7535776"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    x1, y1 = a
    x2, y2 = b
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    slope = ((3 * x1 * x1) * pow(2 * y1, -1, P) if a == b else
             (y2 - y1) * pow((x2 - x1) % P, -1, P)) % P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def multiply(k):
    result = None
    base = G
    while k:
        if k & 1:
            result = add(result, base)
        base = add(base, base)
        k >>= 1
    return result


def main():
    archive = Path(sys.argv[1]) if len(sys.argv) == 2 else HERE / "raw-receipts.tar.gz"
    assert sha(archive.read_bytes()) == ARCHIVE_SHA256
    with tarfile.open(archive, "r:gz") as tar:
        members = {member.name: member for member in tar.getmembers() if member.isfile()}

        def read(name):
            stream = tar.extractfile(members[name])
            assert stream is not None, name
            return stream.read()

        def obj(name):
            return json.loads(read(name))

        base = "source/"
        runner_sha = sha(read(base + "isolated_bench.py"))
        wrapper_sha = sha(read(base + "calibrated_tier1_bench.py"))
        calibrator_sha = sha(read(base + "tier1_calibrator.py"))
        allocation_sha = sha(read("receipts/allocation.json"))
        output = []
        for case_index, job in JOBS.items():
            stem = f"results/{job}/"
            manifest_bytes = read(stem + "manifest.json")
            manifest = json.loads(manifest_bytes)
            summary = obj(stem + "summary.json")
            pairs = [json.loads(line) for line in read(stem + "pairs.jsonl").splitlines()]
            runs = [json.loads(line) for line in read(stem + "runs.jsonl").splitlines()]
            cal_pairs = [json.loads(line) for line in read(stem + "calibration_pairs.jsonl").splitlines()]
            cals = [json.loads(line) for line in read(stem + "calibrations.jsonl").splitlines()]
            case = manifest["cases"][0]
            assert int(case["expected_fields"]["case_id"]) == case_index
            scalar = int(case["expected_fields"]["scalar"], 16)
            x, y = multiply(scalar)
            assert case["expected_result"] == f"{x:064x}:{y:064x}"
            assert summary["manifest_sha256"] == sha(manifest_bytes)
            assert summary["runner_sha256"] == runner_sha
            assert summary["calibrated_runner_sha256"] == wrapper_sha
            assert summary["allocation_receipt_sha256"] == allocation_sha
            assert summary["calibration_receipt_sha256"] == sha(read(stem + "calibrations.jsonl"))
            assert summary["artifact_sha256"]["/workspace/isolated-bench/source/tier1_calibrator.py"] == calibrator_sha
            assert len(pairs) == len(cal_pairs) == 5 and len(runs) == 10 and len(cals) == 20
            assert summary["speedup_qualified"] is False and summary["paired_speedup"] is None
            assert summary["artifacts_stable"] and summary["binaries_stable"] and summary["runner_stable"]
            for row in runs:
                assert row["fields"]["point"] == case["expected_result"]
                assert row["fields"]["verified"] == "1"
                assert row["attempt_stop_monotonic_ns"] > row["attempt_start_monotonic_ns"]
                assert row["attempt_stop_utc_ns"] > row["attempt_start_utc_ns"]
                assert case["expected_result"].encode() in read(stem + row["stdout_file"])
            expected_cal = manifest["calibration"]["expected_fields"]
            for row in cals:
                assert row["fields"]["verified"] == "1"
                assert all(row["fields"][key] == value for key, value in expected_cal.items())
                assert row["attempt_stop_monotonic_ns"] > row["attempt_start_monotonic_ns"]
                assert expected_cal["digest"].encode() in read(stem + "calibration/" + row["stdout_file"])
            bad = [p for p in cal_pairs if p["status"] != "valid"]
            if case_index == 7:
                assert summary["status"] == "completed" and summary["valid_pairs"] == 5
                assert not bad and all(p["status"] == "valid" for p in pairs)
                ratios = [p["speedup"] for p in pairs]
                assert abs(statistics.median(ratios) - summary["observed_ratio_median"]) < 1e-12
            else:
                assert summary["status"] == "invalid" and summary["valid_pairs"] == 3
                assert len(bad) == 2 and sum(p["status"] == "invalid" for p in pairs) == 2
                assert all("A/A calibration spread exceeds frozen limit" in p["issues"] for p in bad)
                assert all(p["max_over_min"] > 1.05 for p in bad)
            output.append({"case": case_index, "job": job, "status": summary["status"],
                           "valid_pairs": summary["valid_pairs"], "valid_aa_pairs": 5-len(bad)})
    print(json.dumps({"independent_scalar_replays": 2, "jobs": output,
                      "controlled_speedup": None}, sort_keys=True))


if __name__ == "__main__":
    main()
