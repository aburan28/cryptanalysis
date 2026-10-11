"""Chained-S3 SAT cost control, restricted to the existing degree-13 toys.

No imported points, full-width parameters, or logarithm extraction. The
sumset oracle is kept outside the measured collector and used only for QA.
"""
import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import random
import sys
import time

import audit

E = audit.engine
STREAM_SEEDS = (91001, 91002, 91003)
QUERY_CAP = 512
QUERY_SECONDS = 0.05
STREAM_SECONDS = 45.0


class Circuit:
    def __init__(self, degree, modulus):
        if degree != 13 or modulus != E.PROFILES[13][0]:
            raise ValueError("fixed degree-13 arithmetic only")
        self.degree, self.modulus = degree, modulus
        self.variables = 1
        self.clauses, self.xors = [[1]], []
        self.and_cache, self.xor_cache = {}, {}

    def var(self):
        self.variables += 1
        return self.variables

    def xor(self, *signals):
        parity, terms = False, set()
        for value in signals:
            if value == 0:
                continue
            if value == 1:
                parity = not parity
            elif value in terms:
                terms.remove(value)
            else:
                terms.add(value)
        if not terms:
            return int(parity)
        if len(terms) == 1 and not parity:
            return next(iter(terms))
        key = tuple(sorted(terms)), parity
        if key not in self.xor_cache:
            result = self.var()
            self.xors.append((list(key[0]) + [result], parity))
            self.xor_cache[key] = result
        return self.xor_cache[key]

    def conjunction(self, a, b):
        if not a or not b:
            return 0
        if a == 1:
            return b
        if b == 1 or a == b:
            return a
        key = tuple(sorted((a, b)))
        if key not in self.and_cache:
            result = self.var()
            self.clauses.extend(([-result, a], [-result, b], [result, -a, -b]))
            self.and_cache[key] = result
        return self.and_cache[key]

    def reduced_power(self, exponent):
        value = 1 << exponent
        while value.bit_length() > self.degree:
            value ^= self.modulus << (value.bit_length() - self.degree - 1)
        return value

    def add(self, a, b):
        return [self.xor(x, y) for x, y in zip(a, b)]

    def linear(self, signals, images):
        return [self.xor(*(s for s, image in zip(signals, images) if image >> j & 1))
                for j in range(self.degree)]

    def square(self, vector):
        return self.linear(vector, [self.reduced_power(2 * j) for j in range(self.degree)])

    def multiply(self, a, b):
        values, images = [], []
        for i, left in enumerate(a):
            for j, right in enumerate(b):
                if left and right:
                    values.append(self.conjunction(left, right))
                    images.append(self.reduced_power(i + j))
        return self.linear(values, images)

    def s3(self, u, v, w):
        uv = self.multiply(u, v)
        cross = self.add(self.add(uv, self.multiply(u, w)), self.multiply(v, w))
        output = self.add(self.square(cross), self.multiply(uv, w))
        output[0] = self.xor(output[0], 1)
        for signal in output:
            if signal:
                self.clauses.append([-signal])

    def solver(self):
        import pycryptosat
        solver = pycryptosat.Solver(threads=1, time_limit=QUERY_SECONDS)
        for clause in self.clauses:
            solver.add_clause(clause)
        for variables, parity in self.xors:
            solver.add_xor_clause(variables, parity)
        return solver


def fixture(seed):
    if seed not in audit.SEEDS:
        raise ValueError("only the recorded eight toy bases")
    ledger = E.Ledger()
    curve, prime, generator, lam = E.setup(13, ledger)
    normal = audit.normal_basis(curve.f, seed)
    basis = [normal[4 * j] for j in range(3)]
    xs = audit.subspace(basis)
    base = sorted(p for x in xs for p in curve.lift(x)
                  if p is not None and curve.mul(p, prime) is None)
    bases = [base]
    for _ in range(3):
        bases.append([E.old.phi(curve, p) for p in bases[-1]])
    reps, encoding, _ = E.old.fold_base(curve, base, prime, lam)
    known = E.public_rows(curve, reps, prime, generator, lam)
    return {"seed": seed, "curve": curve, "prime": prime, "generator": generator,
            "lam": lam, "normal": normal, "base": base, "shifted": bases,
            "reps": reps, "encoding": dict(zip(base, encoding)), "known": known,
            "allowed": sorted(i for i, x in enumerate(xs) if any(p[0] == x for p in base)),
            "ledger": ledger}


def template(data, shifted):
    circuit = Circuit(13, data["curve"].f.modulus)
    leaves, xvars = [], []
    for slot in range(4):
        variables = [circuit.var() for _ in range(3)]
        leaves.append(variables)
        for value in range(8):
            if value not in data["allowed"]:
                circuit.clauses.append([(-v if value >> j & 1 else v) for j, v in enumerate(variables)])
        images = [data["normal"][4 * j + (slot if shifted else 0)] for j in range(3)]
        xvars.append(circuit.linear(variables, images))
    if not shifted:
        for first, second in zip(leaves, leaves[1:]):
            for a in data["allowed"]:
                for b in data["allowed"]:
                    if a > b:
                        circuit.clauses.append([(-v if a >> j & 1 else v) for j, v in enumerate(first)] +
                                               [(-v if b >> j & 1 else v) for j, v in enumerate(second)])
    target = [circuit.var() for _ in range(13)]
    chain = [[circuit.var() for _ in range(13)] for _ in range(2)] + [target]
    left = xvars[0]
    for right, out in zip(xvars[1:], chain):
        circuit.s3(left, right, out)
        left = out
    return circuit, leaves, target


def query(data, model, target, shifted):
    started = time.perf_counter()
    circuit, leaves, target_vars = model
    solver = circuit.solver()  # Fresh state for every ordinary input.
    assumptions = [(v if target[0] >> j & 1 else -v) for j, v in enumerate(target_vars)]
    rejected = 0
    while time.perf_counter() - started < QUERY_SECONDS:
        sat, assignment = solver.solve(assumptions=assumptions)
        if sat is None:
            return "timeout", None, rejected
        if not sat:
            return "no_chain_model", None, rejected
        coords = [sum(int(assignment[v]) << j for j, v in enumerate(block)) for block in leaves]
        candidate_points = []
        for slot, coordinate in enumerate(coords):
            x = 0
            for j in range(3):
                if coordinate >> j & 1:
                    x ^= data["normal"][4 * j + (slot if shifted else 0)]
            base = data["shifted"][slot] if shifted else data["base"]
            points = [(i, p) for i, p in enumerate(base) if p[0] == x]
            if not points:
                raise AssertionError("solver violates leaf domain")
            candidate_points.append(points)
        for choices in product(*candidate_points):
            total = None
            for _, point in choices:
                total = data["curve"].add(total, point)
            if total == target:
                return "verified", [i for i, _ in choices], rejected
        rejected += 1
        solver.add_clause([(-v if assignment[v] else v) for block in leaves for v in block])
    return "timeout", None, rejected


def collect(base_seed, stream_seed, shifted, cap=QUERY_CAP):
    if stream_seed not in STREAM_SEEDS or not 1 <= cap <= QUERY_CAP:
        raise ValueError("fixed stream seeds and bounded query count only")
    start = time.perf_counter()
    data = fixture(base_seed)
    setup_seconds = time.perf_counter() - start
    span = E.Span(len(data["reps"]), data["prime"])
    for known in data["known"]:
        span.add(known["row"])
    initial = span.rank
    begin = time.perf_counter()
    model = template(data, shifted) if data["base"] and span.rank < len(data["reps"]) else None
    template_seconds = time.perf_counter() - begin
    rng = random.Random(stream_seed)
    records, phases, statuses = [], Counter(), Counter()
    for _ in range(cap if model else 0):
        if time.perf_counter() - start > STREAM_SECONDS:
            break
        begin = time.perf_counter()
        scalar = rng.randrange(1, data["prime"])
        target = data["curve"].mul(data["generator"], scalar)
        phases["input_generation"] += time.perf_counter() - begin
        begin = time.perf_counter()
        status, witness, rejected = query(data, model, target, shifted)
        phases["solver_load_solve_lift"] += time.perf_counter() - begin
        row, novel = None, False
        if witness is not None:
            begin = time.perf_counter()
            row = [0] * len(data["reps"])
            replay = None
            for slot, index in enumerate(witness):
                original = data["base"][index]
                col, coefficient = data["encoding"][original]
                row[col] = (row[col] + coefficient * (pow(data["lam"], slot, data["prime"]) if shifted else 1)) % data["prime"]
                point = data["shifted"][slot][index] if shifted else original
                replay = data["curve"].add(replay, point)
            if replay != target:
                raise AssertionError("witness sum mismatch")
            total = None
            for coefficient, rep in zip(row, data["reps"]):
                total = data["curve"].add(total, data["curve"].mul(rep, coefficient))
            if total != target:
                raise AssertionError("folded row mismatch")
            novel = span.add(row)
            phases["row_verification_rank"] += time.perf_counter() - begin
        statuses[status] += 1
        records.append({"scalar": scalar, "target": target, "status": status,
                        "witness": witness, "row": row, "novel": novel,
                        "rank_gain": span.rank - initial, "rejected_leaf_models": rejected})
        if span.rank == len(data["reps"]):
            break
    elapsed = time.perf_counter() - start
    gain = span.rank - initial
    status = ("empty_base" if not data["base"] else "already_known" if initial == len(data["reps"])
              else "full_rank" if span.rank == len(data["reps"]) else "stream_time_cap" if elapsed > STREAM_SECONDS else "query_cap")
    result = {"base_seed": base_seed, "stream_seed": stream_seed, "shifted": shifted,
              "status": status, "base_points": len(data["base"]), "columns": len(data["reps"]),
              "initial_rank": initial, "rank_gain": gain, "cold_seconds": elapsed,
              "cold_seconds_per_rank": elapsed / gain if gain else None,
              "setup_seconds": setup_seconds, "template_seconds": template_seconds,
              "phases": dict(phases), "solver_statuses": dict(statuses), "records": records,
              "template_variables": model[0].variables if model else 0,
              "native_query_budget_seconds": QUERY_SECONDS,
              "hard_per_query_timeout": False}
    # Offline QA starts only after the charged collector stops. No oracle is
    # consulted during query generation, model construction, solving or rank.
    bases = data["shifted"] if shifted else [data["base"]] * 4
    oracle = audit.histogram(data["curve"], bases, not shifted)
    missing = 0
    for record in records:
        covered = tuple(record["target"]) in oracle
        record["offline_oracle_covered"] = covered
        if record["status"] == "verified" and not covered:
            raise AssertionError("solver output absent from exhaustive oracle")
        missing += covered and record["status"] != "verified"
    result["covered_but_not_solved"] = missing
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    import pycryptosat
    rows = []
    for base_seed in (87006,) if args.smoke else audit.SEEDS:
        for stream_seed in STREAM_SEEDS[:1] if args.smoke else STREAM_SEEDS:
            for shifted in ((False, True) if (base_seed + stream_seed) % 2 else (True, False)):
                row = collect(base_seed, stream_seed, shifted, 32 if args.smoke else QUERY_CAP)
                rows.append(row)
                print(json.dumps({key: row[key] for key in ("base_seed", "stream_seed", "shifted", "status", "rank_gain", "cold_seconds", "covered_but_not_solved")}), flush=True)
    sources = audit.source_hashes()
    sources[str(Path(__file__).relative_to(audit.ROOT.parent.parent))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = {"kind": "bounded_degree13_chained_s3_collection", "sources": sources,
              "pycryptosat_version": pycryptosat.__version__, "python": sys.version,
              "rows": rows, "smoke": args.smoke, "full_width_speedup": None,
              "scope": "Fixed degree 13, dimension 3, arity 4; no log extraction",
              "limitation": "Chained affine S3 models may omit decompositions with identity intermediates; offline exhaustive support diagnoses misses"}
    with args.out.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
