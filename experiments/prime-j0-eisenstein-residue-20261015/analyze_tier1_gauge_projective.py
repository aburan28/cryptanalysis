#!/usr/bin/env python3
"""Audit the serial gauge affine versus projective class-join panel."""

from hashlib import sha256
from math import exp, log
from pathlib import Path
import json
import random
import statistics
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
JOB = "792dca682b8d4aa799e4745fb7dd1ce9"


def load(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def audit():
    rules = load(HERE / "tier1-eisenstein-gauge-projective-cpu40-rules.json")
    planned = load(HERE / "tier1-eisenstein-gauge-projective-cpu40-manifest.json")
    folder = HERE / JOB
    manifest = load(folder / "manifest.json")
    summary = load(folder / "summary.json")
    runs = rows(folder / "runs.jsonl")
    pairs = rows(folder / "pairs.jsonl")
    assert manifest == planned
    assert len(runs) == 2 * len(manifest["cases"]) * rules["repetitions"] == 96
    assert len(pairs) == len(manifest["cases"]) * rules["repetitions"] == 48
    assert summary["expected_pairs"] == 48
    assert summary["artifact_sha256"]["/workspace/isolated-bench/panels/tier1-eisenstein-gauge-projective-cpu40-rules.json"] == digest(
        HERE / "tier1-eisenstein-gauge-projective-cpu40-rules.json")
    hashes = rules["hashes"]
    stems = {
        "gauge": "/workspace/bench-sources/prime-j0-eisenstein-gauge-native/",
        "projective": "/workspace/bench-sources/prime-j0-eisenstein-gauge-projective-native/",
    }
    for label, stem in stems.items():
        for suffix, key in (
            ("target/release/eisenstein_fixed", "binary"),
            ("src/bin/eisenstein_fixed.rs", "front"),
            ("src/bin/eisenstein_fixed/unit_orbit_windows.rs", "windows"),
        ):
            assert summary["artifact_sha256"][stem + suffix] == hashes[label + "_" + key]
        assert summary["artifact_sha256"][stem + "src/bin/mixed640_uniform_fixture.json"] == rules["fixture_sha256"]
    assert summary["artifact_sha256"][stems["projective"] + "native_gauge_projective_overlay.py"] == rules["overlay_sha256"]

    provenance = HERE / "eisenstein-gauge-projective-native-provenance.tar.gz"
    with tarfile.open(provenance, "r:gz") as archive:
        base = "prime-j0-eisenstein-gauge-native/"
        candidate = "prime-j0-eisenstein-gauge-projective-native/"
        overlay_name = "native_gauge_projective_overlay.py"
        assert sha256(archive.extractfile(candidate + overlay_name).read()).hexdigest() == rules["overlay_sha256"]
        assert sha256(archive.extractfile(candidate + "target/release/eisenstein_fixed").read()).hexdigest() == hashes["projective_binary"]
        replay = archive.extractfile(candidate + "gauge-projective-full-replay.stdout").read().decode().strip()
        fields = dict(word.split("=", 1) for word in replay.split())
        assert fields["verified"] == "1" and fields["count"] == "12288"
        assert fields["fixture_sha256"] == rules["fixture_sha256"]
        assert fields["point"] == manifest["cases"][0]["expected_result"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            front = root / "src/bin/eisenstein_fixed.rs"
            windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
            windows.parent.mkdir(parents=True)
            front.write_bytes(archive.extractfile(base + "src/bin/eisenstein_fixed.rs").read())
            windows.write_bytes(archive.extractfile(base + "src/bin/eisenstein_fixed/unit_orbit_windows.rs").read())
            subprocess.run(["python3", str(HERE / overlay_name), str(root)],
                           check=True, capture_output=True, text=True)
            assert front.read_bytes() == archive.extractfile(candidate + "src/bin/eisenstein_fixed.rs").read()
            assert windows.read_bytes() == archive.extractfile(candidate + "src/bin/eisenstein_fixed/unit_orbit_windows.rs").read()

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
        assert fields == run["fields"] and fields["verified"] == "1"
        assert float(fields["online_ms"]) == run["online_ms"]
        assert fields["point"] == case["expected_result"]
        assert all(fields.get(key) == value for key, value in case["expected_fields"].items())
    lookup = {(pair["repeat"], pair["case"]): pair for pair in pairs}
    aa_failures = []
    ratios = []
    low, high = rules["aa_acceptance"]
    for repeat in range(16):
        before, measured, after = (lookup[(repeat, name)] for name in
                                   ("cal_before", "compare", "cal_after"))
        if (before["status"] != "valid" or after["status"] != "valid" or
                not (low <= before["speedup"] <= high and low <= after["speedup"] <= high)):
            aa_failures.append({"repeat": repeat, "before": before["speedup"],
                                "after": after["speedup"]})
        if measured["status"] == "valid" and not measured["issues"]:
            ratios.append(measured["speedup"])
    interval = None
    if len(ratios) == 16:
        rng = random.Random(30117)
        logs = [log(ratio) for ratio in ratios]
        boot = sorted(exp(statistics.median(logs[rng.randrange(16)] for _ in range(16)))
                      for _ in range(10000))
        interval = [boot[250], boot[9749]]
    qualified = (summary["status"] == "completed" and summary["artifacts_stable"]
                 and not invalid_arms and not aa_failures and interval is not None
                 and (interval[0] > 1 or interval[1] < 1))
    measured_runs = [run for run in runs if run["case"] == "compare" and run["status"] == "valid"]
    ref = [run for run in measured_runs if run["variant"] == "reference"]
    cand = [run for run in measured_runs if run["variant"] == "candidate"]
    return {
        "schema": 1, "measurement_tier": "tier1_instance", "job_id": JOB,
        "instance_id": manifest["allocation"]["instance_id"],
        "operations_per_arm": 12288, "completed_arms": len(runs),
        "completed_pairs": len(pairs), "invalid_arms": invalid_arms,
        "artifact_stable": summary["artifacts_stable"], "runner_status": summary["status"],
        "aa_acceptance": [low, high], "aa_failures": aa_failures,
        "valid_comparison_pairs": len(ratios),
        "descriptive_reference_over_candidate_median": statistics.median(ratios) if ratios else None,
        "paired_bootstrap95_by_repeat": interval,
        "aggregate_status": "qualified" if qualified else "unknown_after_tier_gate",
        "qualified_comparison_ratio": statistics.median(ratios) if qualified else None,
        "reference_online_ms_mean": statistics.mean(r["online_ms"] for r in ref) if ref else None,
        "candidate_online_ms_mean": statistics.mean(r["online_ms"] for r in cand) if cand else None,
        "reference_retained_bytes": sorted({int(r["fields"]["retained_bytes"]) for r in ref}),
        "candidate_retained_bytes": sorted({int(r["fields"]["retained_bytes"]) for r in cand}),
        "fixture_sha256": rules["fixture_sha256"],
        "provenance_sha256": digest(provenance),
        "runs_sha256": digest(folder / "runs.jsonl"),
        "pairs_sha256": digest(folder / "pairs.jsonl"),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True, indent=2))
