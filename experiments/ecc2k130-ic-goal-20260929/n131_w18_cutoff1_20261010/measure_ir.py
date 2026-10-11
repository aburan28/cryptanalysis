"""Source-bound nonlinear/linear gate census for W18 Karatsuba cutoffs."""

from collections import Counter
import gc
import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n131_fixed_seed_eight_pair_circuit_20261010"
RESULTANT = GOAL / "n131_w18_two_link_resultant_20261010"
ROOT = HERE.parents[2]
sys.path[:0] = [str(BASE), str(RESULTANT), str(ROOT / "ecc2k130/codegen")]
import build  # noqa: E402
import fixed_pair_circuit as pair  # noqa: E402
import ir  # noqa: E402
import resultant_circuit as circuit  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def multiplication_check(cutoff):
    prog = ir.Prog()
    a = [prog.addInput("a", i) for i in range(pair.N)]
    b = [prog.addInput("b", i) for i in range(pair.N)]
    outputs = build.pbMulIr(prog, a, b, pair.N, pair.TAPS, cutoff)
    rng = random.Random(20261010)
    samples = [(rng.getrandbits(pair.N), rng.getrandbits(pair.N)) for _ in range(128)]
    lanes = {}
    for name, index in (("a", 0), ("b", 1)):
        for bit in range(pair.N):
            lanes[(name, bit)] = sum(((sample[index] >> bit) & 1) << lane
                                     for lane, sample in enumerate(samples))
    result = prog.evaluate(lanes, outputs)
    for lane, (left, right) in enumerate(samples):
        got = sum(((value >> lane) & 1) << bit for bit, value in enumerate(result))
        assert got == pair.gf_mul(left, right)
    return len(samples)


def main():
    paths = {"script": HERE / "measure_ir.py",
             "pair": BASE / "fixed_pair_circuit.py",
             "resultant": RESULTANT / "resultant_circuit.py",
             "fourmul": GOAL / "n131_reciprocal_s3_fourmul_20261010" / "fourmul.py",
             "build": ROOT / "ecc2k130/codegen/build.py",
             "ir": ROOT / "ecc2k130/codegen/ir.py",
             "constructed": BASE / "planted_chain_result.json"}
    protocol = json.loads((HERE / "ir_protocol.json").read_text())
    assert protocol["source_sha256"] == {name: digest(path) for name, path in paths.items()}
    original = build.pbMulIr
    rows = []
    for cutoff in (1, 3):
        build.pbMulIr = lambda prog, a, b, n, taps, ignored, cutoff=cutoff: \
            original(prog, a, b, n, taps, cutoff)
        started = time.monotonic_ns()
        prog, roots, deltas, _ = circuit.build_program()
        terminal = roots + [bit for delta in deltas for bit in delta]
        use = prog.refCounts(terminal)
        counts = Counter(prog.ops[index][0] for index in range(len(prog.ops))
                         if use[index] and prog.ops[index] is not None)
        values, _ = circuit.constructed_values()
        assert not any(prog.evaluate(values, roots))
        row = {"cutoff": cutoff, "live_and_gates": counts["and"],
               "live_xor_gates": counts["xor"], "live_total_gates": sum(counts.values()),
               "ir_live_ops": prog.opCount(roots),
               "constructed_roots_satisfied": len(roots),
               "field_multiplication_controls": multiplication_check(cutoff),
               "diagnostic_elapsed_ns": time.monotonic_ns()-started}
        rows.append(row)
        del prog, roots, deltas, terminal, use, values
        gc.collect()
    build.pbMulIr = original
    assert [row["ir_live_ops"] for row in rows] == [469003, 389853]
    result = {"status": "PASS_W18_CUTOFF_GATE_CENSUS",
              "curve_id": "EC1N131Ckb1heb5f1998f20b", "candidate_id": None,
              "rows": rows, "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "source_sha256": protocol["source_sha256"],
              "protocol_sha256": digest(HERE / "ir_protocol.json")}
    (HERE / "ir_result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": result["status"],
                      "rows": [{k: v for k, v in row.items() if k not in ("diagnostic_elapsed_ns",)}
                               for row in rows]}))


if __name__ == "__main__":
    main()
