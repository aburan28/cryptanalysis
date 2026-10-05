#!/usr/bin/env python3
"""Compare native exact-pair words against the frozen Python design policy."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from make_inputs import read_fields
from make_tau_pair_fused import ZERO, catalog
from run import representatives
from screen_global_pair_search import lattice_norm, score, search, tail_oracle
from screen_tau_tail_double import ENDO_LAMBDA


ROOT = Path(__file__).resolve().parent
FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211
MASK = (1 << 64) - 1


def digest_word(state, value):
    for octet in value.to_bytes(8, "little"):
        state = ((state ^ octet) * FNV_PRIME) & MASK
    return state


def expected(scalars, order, omega_lambda, reps, words_by_point, choices,
             costs, actions, beam):
    digest = FNV_OFFSET
    triples = adds = trials = 0
    for scalar in scalars:
        _, a, b = min(representatives(order, omega_lambda, scalar),
                      key=lambda row: row[0])
        baseline, candidate, expanded, _states = search(
            (a, b), 1, words_by_point, choices, costs, actions, reps)
        words = candidate if beam else baseline
        assert score(words) <= score(baseline)
        digest = digest_word(digest, len(words))
        for word in words:
            digest = digest_word(digest, word)
        triples += max(len(words) - 1, 0)
        adds += sum(word != ZERO for word in words)
        trials += expanded if beam else 0
    return {"global_word_digest": f"{digest:016x}", "triples": triples,
            "adds": adds, "global_trials": trials}


def main(bench):
    fixture = json.loads((ROOT / "tail-pair-fused-inputs.json").read_text())
    reps, _, words_by_point, _, _ = catalog()
    options = [(a, b, word) for (a, b), word in words_by_point.items()]
    options.sort(key=lambda item: (lattice_norm(item[0], item[1]), item[2]))
    choices = {(ra, rb): [(a, b, word) for a, b, word in options
                          if a % 3 == ra and b % 3 == rb][:32]
               for ra in range(3) for rb in range(3)}
    costs, actions = tail_oracle(options)
    rows = []
    with tempfile.TemporaryDirectory(prefix="global-pair-design-") as temporary:
        for case in (fixture["cases"][0], fixture["cases"][4]):
            path = ROOT / case["scalar_file"]
            raw = path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == case["scalar_file_sha256"]
            selected = raw[:64 * 8]
            scalars = struct.unpack("<64Q", selected)
            input_path = Path(temporary) / (case["id"] + ".scalars.bin")
            input_path.write_bytes(selected)
            curve = case["curve"]["name"]
            order = case["curve"]["order"]
            omega_lambda = order - ENDO_LAMBDA[curve]
            for beam, arm in ((False, "tail-pair-global-canonical"),
                              (True, "tail-pair-global-beam32")):
                predicted = expected(scalars, order, omega_lambda, reps,
                                     words_by_point, choices, costs, actions, beam)
                command = [str(bench), arm, curve, "0", str(input_path)]
                process = subprocess.run(command, text=True, capture_output=True)
                if process.returncode:
                    raise RuntimeError((command, process.returncode,
                                        process.stdout, process.stderr))
                fields = read_fields(process.stdout)
                for key, value in predicted.items():
                    if str(fields[key]) != str(value):
                        raise AssertionError((curve, arm, key, value, fields[key]))
                assert fields["verified"] == "1"
                rows.append({"curve": curve, "arm": arm, "scalars": 64,
                             "predicted": predicted,
                             "output_digest": fields["output_digest"],
                             "native_global_states": int(fields["global_states"]),
                             "native_global_fallbacks": int(fields["global_fallbacks"])})
    for curve in {row["curve"] for row in rows}:
        assert len({row["output_digest"] for row in rows if row["curve"] == curve}) == 1
    repo = ROOT.parents[1]
    sources = [Path(__file__), ROOT / "screen_global_pair_search.py",
               ROOT / "make_global_pair_native.py", ROOT / "bench.c",
               repo / "src/ec_tau.c", repo / "src/ec_tau_internal.h",
               repo / "src/generated/tau_pair_global.h", repo / "CMakeLists.txt"]
    result = {"schema": 1, "status": "old_design_data_native_exact_word_match",
              "cpu_timing_claim": None,
              "bench_sha256": hashlib.sha256(bench.read_bytes()).hexdigest(),
              "source_sha256": {str(path.relative_to(repo)):
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in sources},
              "rows": rows}
    output = ROOT / "global-pair-native-design.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "rows": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    main(args.bench.resolve())
