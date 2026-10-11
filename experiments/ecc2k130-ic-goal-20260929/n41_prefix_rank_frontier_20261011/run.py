"""Exact degree-two linear relaxation after fixing successive source pairs."""

import hashlib
import importlib.util
import json
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n41_w6_s8_quadratic_joint/linearized_prefix_screen/screen.py"
PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location("frozen_prefix_screen", OLD)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def sample_prefixes(maps, known, pairs, count, seed):
    rng = random.Random(seed)
    records = [list(known[:2 * pairs])]
    seen = {tuple(records[0])}
    while len(records) < count + 1:
        prefix = [rng.choice(tuple(sorted(maps[i]))) for i in range(2 * pairs)]
        columns = [maps[i][mask] for i, mask in enumerate(prefix)]
        if len(set(columns)) != len(columns) or tuple(prefix) in seen:
            continue
        seen.add(tuple(prefix))
        records.append(prefix)
    return records


def prepare():
    if PROTOCOL.exists():
        raise FileExistsError(PROTOCOL)
    target, maps = old.masks_by_slot()
    preflight = json.loads(old.PREFLIGHT.read_text())
    assert target == preflight["results"]["ordinary"]["public_target_q"]
    assert sha(old.FROZEN) == preflight["results"]["ordinary"]["branches"][0]["msolve_input_sha256"]
    known = preflight["results"]["ordinary"]["known_row_masks"]
    assert len(known) == 8
    samples = {str(k): sample_prefixes(maps, known, k, 128, 20261011 + k)
               for k in (2, 3, 4)}
    report = {
        "status": "FROZEN_N41_PREFIX_RANK_FRONTIER",
        "curve_id": preflight["curve_id"],
        "target": target,
        "candidate_id": None,
        "fixed_pair_counts": [1, 2, 3, 4],
        "random_prefixes_per_count": 128,
        "sampling_law": "uniform valid slot masks with rejection of repeated folded columns; known positive inserted at index 0",
        "samples": samples,
        "source_sha256": {"runner": sha(Path(__file__)), "prior_screen": sha(OLD),
                          "quadratic_system": sha(old.FROZEN), "base": sha(old.BASE),
                          "preflight": sha(old.PREFLIGHT)},
    }
    PROTOCOL.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(report["status"])


def templates(polynomials, fixed_count):
    unknown = sorted({term for poly in polynomials for term in poly
                      if term and all(variable >= fixed_count for variable in term)})
    # Cross terms become linear in a free bit once the fixed bit is chosen.
    unknown.extend((variable,) for variable in range(fixed_count, 420)
                   if (variable,) not in unknown)
    unknown = sorted(set(unknown))
    column = {term: i for i, term in enumerate(unknown)}
    output = []
    for polynomial in polynomials:
        base = 0
        conditional = []
        constant = int(() in polynomial)
        for term in polynomial:
            if not term:
                continue
            fixed = tuple(i for i in term if i < fixed_count)
            free = tuple(i for i in term if i >= fixed_count)
            if free:
                bit = 1 << column[free]
                if fixed:
                    conditional.append((sum(1 << i for i in fixed), bit))
                else:
                    base ^= bit
            else:
                conditional.append((sum(1 << i for i in fixed), 0))
        output.append((base, conditional, constant))
    return len(unknown), output


def solve(prefix, forms, fixed_count):
    chosen = sum((mask << (6 * i)) for i, mask in enumerate(prefix))
    assert len(prefix) * 6 == fixed_count
    pivots = {}
    for base, conditional, constant in forms:
        row = base
        rhs = constant
        for needed, bit in conditional:
            if chosen & needed == needed:
                if bit:
                    row ^= bit
                else:
                    rhs ^= 1
        while row:
            pivot = row.bit_length() - 1
            prior = pivots.get(pivot)
            if prior is None:
                pivots[pivot] = (row, rhs)
                break
            row ^= prior[0]
            rhs ^= prior[1]
        if not row and rhs:
            return False, len(pivots)
    return True, len(pivots)


def run():
    if RESULT.exists():
        raise FileExistsError(RESULT)
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["source_sha256"]["runner"] == sha(Path(__file__))
    assert protocol["source_sha256"]["quadratic_system"] == sha(old.FROZEN)
    polynomials = old.equations()
    start = time.monotonic_ns()
    rows = []
    for pairs in protocol["fixed_pair_counts"]:
        fixed_count = 12 * pairs
        variables, forms = templates(polynomials, fixed_count)
        if pairs == 1:
            _, maps = old.masks_by_slot()
            prefixes = [[a, b] for a in sorted(maps[0]) for b in sorted(maps[1])
                        if maps[0][a] != maps[1][b]]
            known = json.loads(old.PREFLIGHT.read_text())["results"]["ordinary"]["known_row_masks"][:2]
            known_index = prefixes.index(known)
        else:
            prefixes = protocol["samples"][str(pairs)]
            known_index = 0
        decisions = []
        for prefix in prefixes:
            consistent, rank = solve(prefix, forms, fixed_count)
            decisions.append({"prefix": prefix, "consistent": consistent, "rank": rank})
        assert decisions[known_index]["consistent"]
        rows.append({"fixed_pairs": pairs, "fixed_bits": fixed_count,
                     "lifted_unknown_monomials": variables,
                     "prefix_count": len(decisions),
                     "consistent_count": sum(d["consistent"] for d in decisions),
                     "known_positive_index": known_index,
                     "rank_min": min(d["rank"] for d in decisions),
                     "rank_max": max(d["rank"] for d in decisions),
                     "decisions": decisions})
    elapsed = time.monotonic_ns() - start
    report = {"status": "COMPLETE_N41_PREFIX_RANK_FRONTIER",
              "candidate_id": None, "protocol_sha256": sha(PROTOCOL),
              "source_sha256": sha(Path(__file__)),
              "elapsed_wall_ns": elapsed,
              "peak_self_ru_maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "rows": rows}
    RESULT.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print([(r["fixed_pairs"], r["consistent_count"], r["prefix_count"])
           for r in rows], round(elapsed / 1e9, 3))


if __name__ == "__main__":
    if sys.argv[1:] == ["prepare"]:
        prepare()
    elif sys.argv[1:] == ["run"]:
        run()
    else:
        raise SystemExit("usage: run.py prepare|run")
