#!/usr/bin/env python3
"""Compare all prospective held-out native streams with the frozen policy."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from check_periodic_pair_design import parse_trace
from make_inputs import read_fields
from make_tau_pair_fused import ZERO, catalog
from run import representatives
from screen_global_pair_search import bounded, index as tail_index, lattice_norm, score, tail_oracle
from screen_periodic_pair_atlas import periodic_plan, reference_plan
from screen_tau_tail_double import ENDO_LAMBDA


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MODE = "tail-pair-periodic-firstword27"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(bench):
    screen_path = ROOT / "firstword-pair-gate-screen.json"
    screen = json.loads(screen_path.read_text())
    header = REPO / "src/generated/tau_pair_firstword_gate.h"
    assert sha256(header) == screen["gate_sha256"]
    selected = set(screen["selected_words"])
    fixture_path = ROOT / "firstword-pair-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert sha256(fixture_path) == "d144189c6b53317c9380515baecb3ea3aec41fc00d8b82b367dba808eb0eaaf5"
    assert len(fixture["cases"]) == 8
    reps, _, words_by_point, _, _ = catalog()
    options = sorted(((a, b, word) for (a, b), word in words_by_point.items()),
                     key=lambda item: (lattice_norm(item[0], item[1]), item[2]))
    _, actions = tail_oracle(options)
    assert sum(action is not None for action in actions) == 15043
    runs = []
    inputs = []
    with tempfile.TemporaryDirectory(prefix="firstword-pair-heldout-words-") as directory:
        for case in fixture["cases"]:
            source_path = ROOT / case["scalar_file"]
            raw = source_path.read_bytes()
            assert sha256(source_path) == case["scalar_file_sha256"]
            assert len(raw) == 4096 * 8
            inputs.append(source_path)
            curve = case["curve"]["name"]
            order = case["curve"]["order"]
            omega_lambda = order - ENDO_LAMBDA[curve]
            for chunk in range(64):
                raw_chunk = raw[512 * chunk:512 * (chunk + 1)]
                scalars = struct.unpack("<64Q", raw_chunk)
                expected_words = []
                expected_lookups = expected_selected = 0
                for scalar in scalars:
                    _, a, b = min(representatives(order, omega_lambda, scalar),
                                  key=lambda row: row[0])
                    reference = reference_plan((a, b), words_by_point, actions, reps)
                    periodic, periodic_lookups, misses = periodic_plan(
                        (a, b), 27, words_by_point, actions, reps)
                    assert periodic is not None and not misses and periodic
                    gate_atlas_lookup = not (bounded(a, b) and
                                             actions[tail_index(a, b)] is not None)
                    expected_lookups += gate_atlas_lookup
                    choose_periodic = periodic[0] in selected
                    if choose_periodic:
                        expected_selected += 1
                        expected_lookups += periodic_lookups
                    expected_words.append(periodic if choose_periodic else reference)
                input_path = Path(directory) / f"{curve}-point{case['point_index']}-{chunk}.bin"
                input_path.write_bytes(raw_chunk)
                command = [str(bench), MODE, curve, str(case["point_index"]), str(input_path)]
                try:
                    process = subprocess.run(command, text=True, capture_output=True,
                                             env={**os.environ, "CA_PAIR_TRACE_WORDS": "1"},
                                             timeout=120)
                    status = "exited"
                    stdout, stderr, returncode = (process.stdout, process.stderr,
                                                  process.returncode)
                except subprocess.TimeoutExpired as exc:
                    status = "timeout"
                    stdout = exc.stdout.decode(errors="replace") if exc.stdout else ""
                    stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
                    returncode = None
                traces, other_stderr = parse_trace(stderr)
                fields = read_fields(stdout) if returncode == 0 else {}
                problems = []
                if status != "exited" or returncode != 0 or other_stderr:
                    problems.append(f"status={status} returncode={returncode} stderr={other_stderr}")
                if len(traces) != 64:
                    problems.append(f"trace count {len(traces)} != 64")
                for index, words in enumerate(expected_words):
                    if traces.get(index) != words:
                        problems.append(f"word mismatch at scalar {index}")
                expected_triples = sum(max(len(words) - 1, 0) for words in expected_words)
                expected_adds = sum(word != ZERO for words in expected_words for word in words)
                for name, wanted in (("curve", curve),
                                     ("point_index", str(case["point_index"])),
                                     ("count", "64"), ("triples", str(expected_triples)),
                                     ("adds", str(expected_adds)),
                                     ("periodic_lookups", str(expected_lookups)),
                                     ("periodic_accepted", str(expected_selected)),
                                     ("periodic_fallbacks", "0"),
                                     ("periodic_checks", "64"),
                                     ("point_entries", "726"), ("verified", "1")):
                    if fields.get(name) != wanted:
                        problems.append(f"{name}: {fields.get(name)} != {wanted}")
                expected_digest = hashlib.sha256(json.dumps(
                    expected_words, separators=(",", ":")).encode()).hexdigest()
                actual_digest = hashlib.sha256(json.dumps(
                    [traces.get(index) for index in range(64)],
                    separators=(",", ":")).encode()).hexdigest()
                runs.append({"case_id": case["id"], "chunk": chunk,
                             "input_sha256": sha256(input_path), "command": command,
                             "status": status, "returncode": returncode,
                             "stdout": stdout, "stderr": stderr,
                             "expected_word_sha256": expected_digest,
                             "native_word_sha256": actual_digest,
                             "expected_triples": expected_triples,
                             "expected_adds": expected_adds,
                             "expected_lookups": expected_lookups,
                             "expected_selected": expected_selected,
                             "problems": problems})
    sources = [Path(__file__), ROOT / "screen_firstword_pair_gate.py", screen_path,
               ROOT / "screen_periodic_pair_atlas.py", ROOT / "screen_global_pair_search.py",
               ROOT / "make_tau_pair_fused.py", ROOT / "bench.c", fixture_path,
               REPO / "src/ec_tau.c", REPO / "src/ec_tau_internal.h", header,
               REPO / "src/generated/tau_pair_periodic.h"] + inputs
    result = {"schema": 1, "status": "exact_match" if
              len(runs) == 512 and all(not run["problems"] for run in runs) else "mismatch",
              "claim_boundary": "prospective held-out exact word/control result; no CPU speed claim",
              "bench_sha256": sha256(bench),
              "source_sha256": {str(path.relative_to(REPO)): sha256(path) for path in sources},
              "runs": runs}
    (ROOT / "firstword-pair-native-heldout-words.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "runs": len(runs),
                      "word_streams": 64 * len(runs)}, sort_keys=True))
    if result["status"] != "exact_match":
        raise RuntimeError("native first-word policy differs from frozen Python streams")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    main(args.bench.resolve())
