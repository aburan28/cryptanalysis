#!/usr/bin/env python3
"""Audit all serial packed-x and gauge-layer arms, including failed gates."""

from hashlib import sha256
from math import exp, log
from pathlib import Path
import json
import random
import subprocess
import statistics
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
JOB = "1068b7066ae148de9edfab8aff9075c0"


def load(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def interval_for(values, seed):
    if len(values) != 16:
        return None
    rng = random.Random(seed)
    logs = [log(value) for value in values]
    boot = sorted(exp(statistics.median(logs[rng.randrange(16)] for _ in range(16)))
                  for _ in range(10000))
    return [boot[250], boot[9749]]


def audit():
    rules = load(HERE / "tier1-eisenstein-packed-gauge-cpu40-rules.json")
    planned = load(HERE / "tier1-eisenstein-packed-gauge-cpu40-manifest.json")
    folder = HERE / JOB
    manifest = load(folder / "manifest.json")
    summary = load(folder / "summary.json")
    runs = rows(folder / "runs.jsonl")
    pairs = rows(folder / "pairs.jsonl")
    assert manifest == planned
    assert manifest["repetitions"] == rules["repetitions"] == 16
    assert len(runs) == 2 * len(manifest["cases"]) * 16 == 128
    assert len(pairs) == len(manifest["cases"]) * 16 == 64
    assert summary["expected_pairs"] == 64
    assert manifest["cases"][0]["expected_fields"]["fixture_sha256"] == rules["fixture_sha256"]
    assert all(case["expected_fields"]["fixture_sha256"] == rules["fixture_sha256"]
               for case in manifest["cases"])

    stems = {
        "baseline": "/workspace/bench-sources/prime-j0-affine-uniform-native/",
        "packed": "/workspace/bench-sources/prime-j0-eisenstein-packed-native/",
        "gauge": "/workspace/bench-sources/prime-j0-eisenstein-gauge-native/",
    }
    hashes = rules["hashes"]
    provenance = HERE / "eisenstein-packed-gauge-native-provenance.tar.gz"
    with tarfile.open(provenance, "r:gz") as archive:
        baseline_front = archive.extractfile(
            "prime-j0-affine-uniform-native/src/bin/eisenstein_fixed.rs").read()
        baseline_windows = archive.extractfile(
            "prime-j0-affine-uniform-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs").read()
        for label in ("packed", "gauge"):
            stem = ("prime-j0-eisenstein-" + label + "-native/")
            overlay = "native_" + ("packed_x" if label == "packed" else "gauge_layer") + "_overlay.py"
            assert sha256(archive.extractfile(stem + overlay).read()).hexdigest() == rules["overlay_sha256"][overlay]
            assert sha256(archive.extractfile(stem + "target/release/eisenstein_fixed").read()).hexdigest() == hashes[label + "_binary"]
            fixture = archive.extractfile(stem + "src/bin/mixed640_uniform_fixture.json").read()
            assert sha256(fixture).hexdigest() == rules["fixture_sha256"]
            replay_name = ("packed" if label == "packed" else "gauge") + "-full-replay.stdout"
            replay = archive.extractfile(stem + replay_name).read().decode().strip()
            replay_fields = dict(word.split("=", 1) for word in replay.split())
            assert replay_fields["verified"] == "1" and replay_fields["count"] == "12288"
            assert replay_fields["fixture_sha256"] == rules["fixture_sha256"]
            assert replay_fields["point"] == manifest["cases"][0]["expected_result"]
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                front = root / "src/bin/eisenstein_fixed.rs"
                windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
                windows.parent.mkdir(parents=True)
                front.write_bytes(baseline_front)
                windows.write_bytes(baseline_windows)
                subprocess.run(["python3", str(HERE / overlay), str(root)],
                               check=True, capture_output=True, text=True)
                assert front.read_bytes() == archive.extractfile(stem + "src/bin/eisenstein_fixed.rs").read()
                assert windows.read_bytes() == archive.extractfile(stem + "src/bin/eisenstein_fixed/unit_orbit_windows.rs").read()
    for label, stem in stems.items():
        assert summary["artifact_sha256"][stem + "target/release/eisenstein_fixed"] == hashes[label + "_binary"]
        assert summary["artifact_sha256"][stem + "src/bin/mixed640_uniform_fixture.json"] == rules["fixture_sha256"]
        if label != "baseline":
            assert summary["artifact_sha256"][stem + "src/bin/eisenstein_fixed.rs"] == hashes[label + "_front"]
            assert summary["artifact_sha256"][stem + "src/bin/eisenstein_fixed/unit_orbit_windows.rs"] == hashes[label + "_windows"]
            overlay = "native_" + ("packed_x" if label == "packed" else "gauge_layer") + "_overlay.py"
            assert summary["artifact_sha256"][stem + overlay] == rules["overlay_sha256"][overlay]
    expected = {case["id"]: case for case in manifest["cases"]}
    invalid_arms = []
    for serial, run in enumerate(runs, 1):
        assert run["serial"] == serial
        case = expected[run["case"]]
        assert run["command"] == case[run["variant"]]
        assert run["binary_sha256"] == summary["artifact_sha256"][run["command"][0]]
        if run["status"] != "valid" or run["issues"] or run["returncode"] != 0 or run["timed_out"]:
            invalid_arms.append({"serial": serial, "status": run["status"], "issues": run["issues"]})
            continue
        assert run["postflight"]["ok"]
        assert (folder / run["stderr_file"]).read_text() == ""
        fields = dict(word.split("=", 1) for word in (folder / run["stdout_file"]).read_text().split())
        assert fields == run["fields"]
        assert float(fields["online_ms"]) == run["online_ms"]
        assert fields["verified"] == "1" and fields["point"] == case["expected_result"]
        assert all(fields.get(key) == value for key, value in case["expected_fields"].items())
    lookup = {(pair["repeat"], pair["case"]): pair for pair in pairs}
    aa_failures = []
    comparisons = {"compare_packed": [], "compare_gauge": []}
    low, high = rules["aa_acceptance"]
    for repeat in range(16):
        before = lookup[(repeat, "cal_before")]
        after = lookup[(repeat, "cal_after")]
        if before["status"] != "valid" or after["status"] != "valid" or not (
                low <= before["speedup"] <= high and low <= after["speedup"] <= high):
            aa_failures.append({"repeat": repeat, "before": before["speedup"],
                                "after": after["speedup"]})
        for name in comparisons:
            pair = lookup[(repeat, name)]
            if pair["status"] == "valid" and not pair["issues"]:
                comparisons[name].append(pair["speedup"])

    result = {
        "schema": 1, "measurement_tier": "tier1_instance", "job_id": JOB,
        "instance_id": manifest["allocation"]["instance_id"],
        "operations_per_arm": 12288, "completed_arms": len(runs),
        "completed_pairs": len(pairs), "invalid_arms": invalid_arms,
        "aa_acceptance": [low, high], "aa_failures": aa_failures,
        "artifact_stable": summary["artifacts_stable"],
        "runner_status": summary["status"],
        "fixture_sha256": rules["fixture_sha256"],
        "provenance_sha256": digest(provenance),
        "runs_sha256": digest(folder / "runs.jsonl"),
        "pairs_sha256": digest(folder / "pairs.jsonl"),
        "comparisons": {},
    }
    for index, (name, ratios) in enumerate(comparisons.items()):
        interval = interval_for(ratios, 30116 + index)
        valid = (summary["status"] == "completed" and summary["artifacts_stable"]
                 and not invalid_arms and not aa_failures and len(ratios) == 16)
        qualified = valid and interval is not None and (interval[0] > 1 or interval[1] < 1)
        measured = [row for row in runs if row["case"] == name and row["status"] == "valid"]
        ref = [row for row in measured if row["variant"] == "reference"]
        cand = [row for row in measured if row["variant"] == "candidate"]
        result["comparisons"][name] = {
            "valid_pairs": len(ratios),
            "descriptive_reference_over_candidate_median": statistics.median(ratios) if ratios else None,
            "paired_bootstrap95_by_repeat": interval,
            "aggregate_status": "qualified" if qualified else "unknown_after_tier_gate",
            "qualified_comparison_ratio": statistics.median(ratios) if qualified else None,
            "reference_online_ms_mean": statistics.mean(r["online_ms"] for r in ref) if ref else None,
            "candidate_online_ms_mean": statistics.mean(r["online_ms"] for r in cand) if cand else None,
            "reference_retained_bytes": sorted({int(r["fields"]["retained_bytes"]) for r in ref}),
            "candidate_retained_bytes": sorted({int(r["fields"]["retained_bytes"]) for r in cand}),
        }
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
