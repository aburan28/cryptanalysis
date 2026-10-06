#!/usr/bin/env python3
"""Check every old native full-digit mixed-radix action stream against the frozen map."""

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
from screen_global_pair_search import (bounded, canonical_step, index, tail_oracle,
                                       lattice_norm)
from screen_mixed_radix_tail import (KIND_PAIR, cost, path_from)
from screen_tau_tail_double import ENDO_LAMBDA


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MODE = "tail-pair-mixed-full-digits"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_traces(stderr):
    traces, other = {}, []
    for line in stderr.splitlines():
        if not line.startswith("trace_actions="):
            other.append(line)
            continue
        values = [int(value) for value in line.removeprefix("trace_actions=").split(":")]
        position, count, *actions = values
        if position in traces or count != len(actions):
            other.append(line)
        else:
            traces[position] = actions
    return traces, "\n".join(other)


def main(bench):
    header = REPO / "src/generated/tau_pair_mixed_full_digits.h"
    screen = json.loads((ROOT / "mixed-full-digits-screen.json").read_text())
    assert sha256(header) == screen["header_sha256"]
    fixture = json.loads((ROOT / "tail-pair-fused-inputs.json").read_text())
    reps, _, words_by_point, _, _ = catalog()
    points = {word: point for point, word in words_by_point.items()}
    options = sorted(((a, b, word) for (a, b), word in words_by_point.items()),
                     key=lambda row: (lattice_norm(row[0], row[1]), row[2]))
    _, pure_actions = tail_oracle(options)
    # Parse the committed action header, so this check does not rebuild the
    # map with the same graph algorithm that generated it.
    import re
    body = header.read_text().split("ca_tau_pair_mixed_full_action[16641] = {")[1].split("};")[0]
    encoded = [int(value) for value in re.findall(r"\d+", body)]
    assert len(encoded) == 16641
    actions = [(value >> 10, value & 1023) for value in encoded]
    rows = list(csv.DictReader((ROOT / "mixed-full-digits-raw.csv").open()))
    by_case = {}
    for row in rows:
        by_case.setdefault(row["case_id"], []).append(row)
    runs = []
    case_totals = []
    input_files = []
    with tempfile.TemporaryDirectory(prefix="mixed-full-native-") as directory:
        for case_index in (0, 1, 4, 5):
            case = fixture["cases"][case_index]
            curve = case["curve"]["name"]
            point_index = case["point_index"]
            order = case["curve"]["order"]
            omega_lambda = order - ENDO_LAMBDA[curve]
            source = ROOT / case["scalar_file"]
            assert sha256(source) == case["scalar_file_sha256"]
            input_files.append(source)
            raw = source.read_bytes()
            totals = {name: 0 for name in ("triples", "tau_steps", "doubles", "adds", "score")}
            for chunk in range(64):
                raw_chunk = raw[512 * chunk:512 * (chunk + 1)]
                scalars = struct.unpack("<64Q", raw_chunk)
                expected = []
                problems = []
                for position, scalar in enumerate(scalars):
                    _, a, b = min(representatives(order, omega_lambda, scalar),
                                  key=lambda row: row[0])
                    high = []
                    while (a, b) != (0, 0) and (not bounded(a, b) or
                                               pure_actions[index(a, b)] is None):
                        (a, b), word = canonical_step(a, b, words_by_point)
                        high.append((KIND_PAIR, word))
                    path = tuple(high) + path_from((a, b), actions, points)
                    encoded_path = [(kind << 10) | word for kind, word in path]
                    expected.append(encoded_path)
                    row = by_case[case["id"]][64 * chunk + position]
                    if int(row["scalar"]) != scalar or int(row["full_digit_score"]) != cost(path):
                        problems.append(f"frozen row mismatch at {position}")
                input_path = Path(directory) / f"{curve}-point{point_index}-{chunk}.bin"
                input_path.write_bytes(raw_chunk)
                command = [str(bench), MODE, curve, str(point_index), str(input_path)]
                try:
                    process = subprocess.run(command, text=True, capture_output=True,
                                             env={**os.environ, "CA_MIXED_TRACE_ACTIONS": "1"},
                                             timeout=120)
                    status, stdout, stderr, returncode = ("exited", process.stdout,
                                                           process.stderr, process.returncode)
                except subprocess.TimeoutExpired as exc:
                    status, returncode = "timeout", None
                    stdout = exc.stdout.decode(errors="replace") if exc.stdout else ""
                    stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
                traces, other_stderr = parse_traces(stderr)
                fields = read_fields(stdout) if returncode == 0 else {}
                if status != "exited" or returncode != 0 or other_stderr:
                    problems.append(f"status={status} returncode={returncode} stderr={other_stderr}")
                if len(traces) != 64:
                    problems.append(f"trace count {len(traces)} != 64")
                for position, path in enumerate(expected):
                    if traces.get(position) != path:
                        problems.append(f"action mismatch at {position}")
                for name, wanted in (("curve", curve), ("point_index", str(point_index)),
                                     ("count", "64"), ("verified", "1"),
                                     ("mixed_checks", "64"), ("mixed_fallbacks", "0"),
                                     ("point_entries", "726")):
                    if fields.get(name) != wanted:
                        problems.append(f"{name}: {fields.get(name)} != {wanted}")
                started = False
                counts = {name: 0 for name in ("triples", "tau_steps", "doubles", "adds")}
                for path in expected:
                    started = False
                    for action in reversed(path):
                        kind, word = action >> 10, action & 1023
                        if started:
                            counts[("triples", "tau_steps", "doubles")[kind]] += 1
                        if word != ZERO:
                            counts["adds"] += 1
                            started = True
                for name, wanted in counts.items():
                    if fields.get(name) != str(wanted):
                        problems.append(f"{name}: {fields.get(name)} != {wanted}")
                    totals[name] += wanted
                totals["score"] += sum(cost(tuple((action >> 10, action & 1023)
                                                   for action in path)) for path in expected)
                runs.append({"case_id": case["id"], "chunk": chunk,
                             "input_sha256": sha256(input_path), "command": command,
                             "status": status, "returncode": returncode,
                             "stdout": stdout, "stderr": stderr,
                             "expected_action_sha256": hashlib.sha256(json.dumps(
                                 expected, separators=(",", ":")).encode()).hexdigest(),
                             "native_action_sha256": hashlib.sha256(json.dumps(
                                 [traces.get(i) for i in range(64)],
                                 separators=(",", ":")).encode()).hexdigest(),
                             "problems": problems})
            frozen = next(item for item in screen["summaries"] if item["case_id"] == case["id"])
            if totals["score"] != frozen["full_digit_score"]:
                raise RuntimeError(f"score mismatch for {case['id']}")
            case_totals.append({"case_id": case["id"], **totals})
    sources = [Path(__file__), ROOT / "screen_mixed_full_digits.py",
               ROOT / "mixed-full-digits-screen.json", ROOT / "mixed-full-digits-raw.csv",
               ROOT / "tail-pair-fused-inputs.json", ROOT / "bench.c",
               REPO / "src/ec_tau.c", REPO / "src/ec_tau_internal.h", header] + input_files
    result = {"schema": 1, "status": "exact_match" if len(runs) == 256 and
              all(not run["problems"] for run in runs) else "mismatch",
              "claim_boundary": "old data native correctness and exact action streams; no CPU speed claim",
              "bench_sha256": sha256(bench),
              "source_sha256": {str(path.relative_to(REPO)): sha256(path) for path in sources},
              "case_totals": case_totals, "runs": runs}
    (ROOT / "mixed-full-native-design.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "runs": len(runs),
                      "action_streams": 64 * len(runs), "case_totals": case_totals},
                     sort_keys=True))
    if result["status"] != "exact_match":
        raise RuntimeError("native actions differ from the frozen map")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    main(args.bench.resolve())
