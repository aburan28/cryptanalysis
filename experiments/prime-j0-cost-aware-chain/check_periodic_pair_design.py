#!/usr/bin/env python3
"""Compare every native modulus-27 word to the frozen Python design policy."""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from make_inputs import read_fields
from make_tau_pair_fused import ZERO, catalog
from run import representatives
from screen_global_pair_search import lattice_norm, score, tail_oracle
from screen_periodic_pair_atlas import periodic_plan, reference_plan
from screen_tau_tail_double import ENDO_LAMBDA


ROOT = Path(__file__).resolve().parent
ARMS = ((0, "tail-pair-periodic-canonical"),
        (1, "tail-pair-periodic-gated27"))


def parse_trace(stderr):
    traces = {}
    other = []
    for line in stderr.splitlines():
        if not line.startswith("trace_words="):
            other.append(line)
            continue
        parts = [int(item) for item in line[len("trace_words="):].split(":")]
        index, count, *words = parts
        assert index not in traces and len(words) == count
        traces[index] = tuple(words)
    return traces, other


def main(bench):
    fixture = json.loads((ROOT / "tail-pair-fused-inputs.json").read_text())
    reps, _, words_by_point, _, _ = catalog()
    options = [(a, b, word) for (a, b), word in words_by_point.items()]
    options.sort(key=lambda item: (lattice_norm(item[0], item[1]), item[2]))
    _, actions = tail_oracle(options)
    assert sum(action is not None for action in actions) == 15043
    runs = []
    raw_rows = []
    with tempfile.TemporaryDirectory(prefix="periodic-pair-design-") as temporary:
        for case in (fixture["cases"][0], fixture["cases"][4]):
            path = ROOT / case["scalar_file"]
            raw = path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == case["scalar_file_sha256"]
            scalars = struct.unpack("<512Q", raw[:512 * 8])
            curve = case["curve"]["name"]
            order = case["curve"]["order"]
            omega_lambda = order - ENDO_LAMBDA[curve]
            for chunk in range(8):
                selected = scalars[64 * chunk:64 * (chunk + 1)]
                input_path = Path(temporary) / f"{curve}-{chunk}.scalars.bin"
                input_path.write_bytes(raw[512 * chunk:512 * (chunk + 1)])
                expected = []
                lookups = accepted = 0
                for scalar in selected:
                    _, a, b = min(representatives(order, omega_lambda, scalar),
                                  key=lambda row: row[0])
                    baseline = reference_plan((a, b), words_by_point, actions, reps)
                    periodic, count, misses = periodic_plan((a, b), 27, words_by_point,
                                                             actions, reps)
                    assert periodic is not None and misses == 0
                    if score(periodic) < score(baseline):
                        chosen = periodic
                        accepted += 1
                    else:
                        chosen = baseline
                    expected.append((baseline, chosen))
                    lookups += count
                for gated, arm in ARMS:
                    command = [str(bench), arm, curve, "0", str(input_path)]
                    process = subprocess.run(
                        command, text=True, capture_output=True,
                        env={**os.environ, "CA_PAIR_TRACE_WORDS": "1"})
                    traces, other_stderr = parse_trace(process.stderr)
                    fields = read_fields(process.stdout) if process.returncode == 0 else {}
                    problems = []
                    if process.returncode:
                        problems.append(f"exit {process.returncode}")
                    if len(traces) != 64:
                        problems.append(f"expected 64 traces, got {len(traces)}")
                    words = [pair[gated] for pair in expected]
                    for index, planned in enumerate(words):
                        if traces.get(index) != planned:
                            problems.append(f"word mismatch at {index}")
                    expected_triples = sum(max(len(stream) - 1, 0) for stream in words)
                    expected_adds = sum(word != ZERO for stream in words for word in stream)
                    for key, value in (("triples", expected_triples),
                                       ("adds", expected_adds),
                                       ("periodic_lookups", lookups if gated else 0),
                                       ("periodic_accepted", accepted if gated else 0),
                                       ("periodic_fallbacks", 0),
                                       ("periodic_checks", 64)):
                        if fields.get(key) != str(value):
                            problems.append(f"{key}: {fields.get(key)} != {value}")
                    if fields.get("verified") != "1":
                        problems.append("generic scalar replay failed")
                    for index, scalar in enumerate(selected):
                        raw_rows.append((curve, arm, chunk, index, scalar,
                                         " ".join(map(str, traces.get(index, ()))),
                                         " ".join(map(str, words[index])),
                                         traces.get(index) == words[index]))
                    runs.append({"curve": curve, "arm": arm, "chunk": chunk,
                                 "command": command, "returncode": process.returncode,
                                 "stdout": process.stdout, "stderr": process.stderr,
                                 "other_stderr": other_stderr, "problems": problems,
                                 "expected_triples": expected_triples,
                                 "expected_adds": expected_adds,
                                 "expected_lookups": lookups if gated else 0,
                                 "expected_accepted": accepted if gated else 0})
    raw_path = ROOT / "periodic-pair-native-design-words.csv"
    with raw_path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("curve", "arm", "chunk", "index", "scalar",
                         "native_words", "expected_words", "exact_match"))
        writer.writerows(raw_rows)
    repo = ROOT.parents[1]
    sources = [Path(__file__), ROOT / "screen_periodic_pair_atlas.py",
               ROOT / "make_periodic_pair_native.py", ROOT / "bench.c",
               repo / "src/ec_tau.c", repo / "src/ec_tau_internal.h",
               repo / "src/generated/tau_pair_periodic.h", repo / "CMakeLists.txt"]
    result = {"schema": 1, "status": "old_design_data_native_periodic_word_comparison",
              "cpu_timing_claim": None, "runs": runs,
              "raw_csv": raw_path.name,
              "raw_csv_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
              "bench_sha256": hashlib.sha256(bench.read_bytes()).hexdigest(),
              "source_sha256": {str(path.relative_to(repo)):
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in sources}}
    output = ROOT / "periodic-pair-native-design.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if any(run["problems"] for run in runs):
        raise RuntimeError("native periodic word check retained mismatches")
    print(json.dumps({"status": result["status"], "runs": len(runs),
                      "exact_words": len(raw_rows)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    main(args.bench.resolve())
