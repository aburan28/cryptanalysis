#!/usr/bin/env python3
"""Replay the archived five-case scalar panel without trusting its summary."""

import hashlib
import json
import statistics
import tarfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if left == right:
        slope = (3 * x1 * x1) * pow(2 * y1, -1, P) % P
    else:
        slope = (y2 - y1) * pow((x2 - x1) % P, -1, P) % P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def multiply(k):
    answer = None
    base = G
    while k:
        if k & 1:
            answer = add(answer, base)
        base = add(base, base)
        k >>= 1
    return answer


def main():
    index = json.loads((HERE / "panel-index.json").read_text())
    archive = HERE / "raw-receipts.tar.gz"
    assert digest(archive.read_bytes()) == (
        "7e1ba66f7c384d9323587bf07f4d6d7095600648d3071707c6797c94954946f6"
    )
    with tarfile.open(archive, "r:gz") as tar:
        members = {item.name: item for item in tar.getmembers() if item.isfile()}

        def read(path):
            assert path in members, path
            stream = tar.extractfile(members[path])
            assert stream is not None
            return stream.read()

        def parsed(path):
            return json.loads(read(path))

        assert digest(read("isolated-bench/source/isolated_bench-7e9.py")) == index["runner_sha256"]
        assert parsed("isolated-bench/three-bucket-panel-index.json") == index
        assert index["controlled_speedup"] is None
        assert index["all_expected_pairs"] == index["all_valid_pairs"] == 25
        assert [row["case_index"] for row in index["cases"]] == [2, 3, 4, 5, 6]

        medians = []
        for item in index["cases"]:
            stem = "isolated-bench/results/" + item["job_id"] + "/"
            manifest_bytes = read(stem + "manifest.json")
            manifest = json.loads(manifest_bytes)
            summary = parsed(stem + "summary.json")
            preflight = parsed(stem + "preflight.json")
            pairs = [json.loads(line) for line in read(stem + "pairs.jsonl").splitlines()]
            runs = [json.loads(line) for line in read(stem + "runs.jsonl").splitlines()]
            case = manifest["cases"][0]
            assert digest(manifest_bytes) == item["manifest_sha256"] == summary["manifest_sha256"]
            assert preflight["ok"] and preflight["tier"] == "tier1"
            assert summary["status"] == "completed"
            assert summary["valid_pairs"] == summary["expected_pairs"] == 5
            assert summary["artifacts_stable"] and summary["binaries_stable"]
            assert summary["runner_stable"]
            assert summary["runner_sha256"] == index["runner_sha256"]
            assert summary["instance_id"] == index["instance_id"]
            assert summary["allocation_receipt_sha256"] == digest(
                read("isolated-bench/receipts/allocation.json")
            )
            assert len(pairs) == 5 and len(runs) == 10
            assert all(pair["status"] == "valid" and not pair["issues"] for pair in pairs)
            assert all(run["status"] == "valid" and not run["issues"] for run in runs)
            assert all(run["postflight"]["ok"] for run in runs)
            assert all(run["fields"]["verified"] == "1" for run in runs)
            assert all("start_ns" not in run and "stop_ns" not in run for run in runs)

            assert case["expected_fields"]["fixture_sha256"] == index["fixture_sha256"]
            assert case["expected_fields"]["case_id"] == str(item["case_index"])
            scalar = int(case["expected_fields"]["scalar"], 16)
            x, y = multiply(scalar)
            assert case["expected_result"] == f"{x:064x}:{y:064x}"
            for run in runs:
                assert run["fields"]["point"] == case["expected_result"]
                assert all(run["fields"][key] == value for key, value in case["expected_fields"].items())
                stdout = read(stem + run["stdout_file"]).decode()
                assert "verified=1" in stdout and case["expected_result"] in stdout
                assert run["online_ms"] > 0
            by_serial = {run["serial"]: run for run in runs}
            ratios = []
            for pair in pairs:
                ref = by_serial[pair["run_serials"]["reference"]]
                cand = by_serial[pair["run_serials"]["candidate"]]
                ratio = ref["metric_ms"] / cand["metric_ms"]
                assert abs(ratio - pair["speedup"]) < 1e-12
                ratios.append(ratio)
            assert ratios == item["pair_ratios"]
            median = statistics.median(ratios)
            assert abs(median - item["median_reference_over_candidate"]) < 1e-12
            medians.append(median)

        assert index["case_median_range"] == [min(medians), max(medians)]
        # The archived runner has no A/A calibration workload or receipts.
        # Its five valid pair statuses therefore do not pass the current Tier 1 gate.
        runner = read("isolated-bench/source/isolated_bench-7e9.py")
        assert b"calibration" not in runner.lower()
        assert not any("calibration" in name.lower() for name in members)
    print(json.dumps({"verified_cases": 5, "verified_pairs": 25,
                      "independent_scalar_replays": 5,
                      "case_median_range": index["case_median_range"],
                      "aa_calibration": "missing", "run_timestamps": "missing",
                      "controlled_speedup": None},
                     sort_keys=True))


if __name__ == "__main__":
    main()
