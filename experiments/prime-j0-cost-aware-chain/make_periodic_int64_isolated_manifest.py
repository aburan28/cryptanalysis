#!/usr/bin/env python3
"""Build the frozen periodic-int64 manifest for the serial isolated runner."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
FIXTURE_SHA256 = "7037c34c8a1a29e58a0831f9767f8828e32d57fa6b18f485e2b26359df46548e"
REFERENCE_COMMIT = "1ecc8f46610c697cba950e2c19bc0274abf66f34"
FIXTURE_COMMIT = "f63f7b36"
MODE = "tail-pair-periodic-gated27"
PAIR_FIELDS = ("curve", "point_index", "count", "base_x", "base_y",
               "input_digest", "output_digest")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def tracked_sources(root):
    raw = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z", "--",
                                   "src", "include", "CMakeLists.txt"])
    paths = [root / part.decode() for part in raw.split(b"\0") if part]
    paths.append(root / "experiments/prime-j0-cost-aware-chain/bench.c")
    if any(not path.is_file() for path in paths):
        raise ValueError("tracked source missing from checkout")
    return paths


def main(args):
    paths = (args.reference_root, args.candidate_root, args.reference,
             args.candidate, args.reference_cache, args.candidate_cache,
             args.reference_library, args.candidate_library, args.cgroup, args.output)
    if any(not path.is_absolute() for path in paths):
        raise ValueError("all paths must be absolute paths on the benchmark host")
    if any(not path.is_file() for path in paths[2:8]):
        raise ValueError("benchmark binary, build cache, or static library missing")
    if git(args.reference_root, "rev-parse", "HEAD") != REFERENCE_COMMIT:
        raise ValueError("reference checkout is not the frozen 128-bit recoder")
    if subprocess.run(["git", "-C", str(args.candidate_root), "merge-base",
                       "--is-ancestor", FIXTURE_COMMIT, "HEAD"], check=False).returncode:
        raise ValueError("candidate checkout does not contain the frozen fixture commit")
    fixture_path = args.candidate_root / \
        "experiments/prime-j0-cost-aware-chain/periodic-pair-int64-inputs.json"
    if sha256(fixture_path) != FIXTURE_SHA256:
        raise ValueError("frozen fixture manifest hash changed")
    fixture = json.loads(fixture_path.read_text())
    if fixture["status"] != "frozen_periodic_pair_int64_disjoint_fixture" or \
       len(fixture["cases"]) != 8:
        raise ValueError("unexpected fixture status or case count")
    old_panel = json.loads((args.candidate_root /
                            "experiments/prime-j0-cost-aware-chain/periodic-pair-native-panel.json")
                           .read_text())
    int64_design = json.loads((args.candidate_root /
                               "experiments/prime-j0-cost-aware-chain/periodic-pair-int64-design.json")
                              .read_text())
    if sha256(args.reference_root / "src/ec_tau.c") != \
       old_panel["source_sha256"]["src/ec_tau.c"]:
        raise ValueError("reference arithmetic source differs from held-out 128-bit source")
    if sha256(args.candidate_root / "src/ec_tau.c") != \
       int64_design["source_sha256"]["src/ec_tau.c"]:
        raise ValueError("candidate arithmetic source differs from exact design control")
    if sha256(args.reference) == sha256(args.candidate):
        raise ValueError("reference and candidate executables have identical bytes")
    if sha256(args.reference_root / "experiments/prime-j0-cost-aware-chain/bench.c") != \
       sha256(args.candidate_root / "experiments/prime-j0-cost-aware-chain/bench.c"):
        raise ValueError("benchmark timer or verifier differs between arms")

    cases = []
    scalar_paths = []
    for case in fixture["cases"]:
        scalar_path = args.candidate_root / "experiments/prime-j0-cost-aware-chain" / \
            case["scalar_file"]
        if sha256(scalar_path) != case["scalar_file_sha256"]:
            raise ValueError("scalar file differs from frozen fixture: " + case["id"])
        scalar_paths.append(scalar_path)
        tail = [MODE, case["curve"]["name"], str(case["point_index"]), str(scalar_path)]
        expected = {"curve": case["curve"]["name"],
                    "point_index": str(case["point_index"]), "count": "4096",
                    "base_x": case["base_x"], "base_y": case["base_y"],
                    "input_digest": case["input_digest"],
                    "output_digest": case["expected_output_digest"]}
        cases.append({"id": case["id"],
                      "reference": [str(args.reference)] + tail,
                      "candidate": [str(args.candidate)] + tail,
                      "expected_fields": expected,
                      "expected_result": case["expected_output_digest"]})
    artifacts = set(tracked_sources(args.reference_root) +
                    tracked_sources(args.candidate_root) + scalar_paths +
                    [fixture_path, args.reference_cache, args.candidate_cache,
                     args.reference_library, args.candidate_library,
                     args.candidate_root / "scripts/isolated_bench.py",
                     Path(__file__).resolve()])
    manifest = {"schema": 1, "name": "periodic-pair-int64-isolated-v1",
                "workdir": str(args.candidate_root),
                "isolation": {"cgroup": str(args.cgroup), "cpus": args.cpus,
                              "execution_cpu": args.execution_cpu,
                              "mem_nodes": args.mem_nodes},
                "build": {"reference_commit": REFERENCE_COMMIT,
                          "candidate_commit": git(args.candidate_root, "rev-parse", "HEAD"),
                          "reference_cache_sha256": sha256(args.reference_cache),
                          "candidate_cache_sha256": sha256(args.candidate_cache),
                          "reference_library_sha256": sha256(args.reference_library),
                          "candidate_library_sha256": sha256(args.candidate_library)},
                "timeout_s": 120, "repetitions": 5,
                "measurement_boundary": "benchmark online_ms: first scalar reduction through last affine output, including recoding, group operations, conversion, and storage; setup and generic replay excluded",
                "pair_fields": list(PAIR_FIELDS), "result_field": "output_digest",
                "artifacts": [str(path) for path in sorted(artifacts)],
                "cases": cases}
    sys.path.insert(0, str(args.candidate_root / "scripts"))
    from isolated_bench import require_manifest
    require_manifest(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": 5,
                      "fixture_sha256": FIXTURE_SHA256,
                      "manifest_sha256": sha256(args.output)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference-root", "candidate-root", "reference", "candidate",
                 "reference-cache", "candidate-cache", "reference-library",
                 "candidate-library", "cgroup", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-nodes", required=True)
    main(parser.parse_args())
