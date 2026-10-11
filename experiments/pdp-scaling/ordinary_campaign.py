#!/usr/bin/env python3
"""Bounded ordinary-query PDP measurements; generated public research inputs.

Freeze first, run second, independently replay signed rows and rank last.
No target supplied by an external service and no discrete-log recovery stage.
"""

import argparse
from collections import Counter
from functools import cache
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gf2n import Curve, GF2n, INF, Point
from groebner_compare.certificate import vanishes
from groebner_compare.relation_metrics import RelationRank, comparison_gate

BACKENDS = ("direct", "cryptominisat", "hybrid-cryptominisat", "repository-f5b", "block-f4")
ACCOUNTING = "fresh-process wall + charged frozen base and workload construction; all queries and failures"


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def encode(p):
    return [p.x, p.y, p.inf]


def decode(p):
    return Point(*p)


def scalar_mul(E, p, k):
    result = INF
    while k:
        if k & 1:
            result = E.add(result, p)
        p = E.add(p, p)
        k >>= 1
    return result


@cache
def prime_certificate(p):
    """Full-factorization Lucas certificate, recursively reaching 2."""
    from sympy import factorint
    if p == 2:
        return {"p": 2}
    factors = {int(q): int(e) for q, e in factorint(p - 1).items()}
    witnesses = {}
    for q in factors:
        witnesses[str(q)] = next(a for a in range(2, 10000)
                                if pow(a, p - 1, p) == 1
                                and math.gcd(pow(a, (p - 1) // q, p) - 1, p) == 1)
    return {"p": p, "factors": [[q, e, prime_certificate(q)] for q, e in factors.items()],
            "witnesses": witnesses}


def check_prime(c):
    p = c["p"]
    if p == 2:
        return True
    if p < 3 or math.prod(q**e for q, e, _ in c["factors"]) != p - 1:
        return False
    return all(q == child["p"] and e > 0 and check_prime(child)
               and pow(c["witnesses"][str(q)], p - 1, p) == 1
               and math.gcd(pow(c["witnesses"][str(q)], (p - 1) // q, p) - 1, p) == 1
               for q, e, child in c["factors"])


def curve_order(n):
    # E/F_2 has four points: trace=-1, alpha+beta=-1, alpha*beta=2.
    previous, current = 2, -1
    for _ in range(2, n + 1):
        previous, current = current, -current - 2 * previous
    return (1 << n) + 1 - current


def prepare(n, l):
    from sympy import factorint
    if n not in (7, 13, 17, 31, 53, 83) or not 1 <= l <= 6:
        raise ValueError("bounded campaign supports listed odd degrees and l<=6")
    F = GF2n(n)
    E = Curve(F, 1)
    order = curve_order(n)
    r = max(int(p) for p in factorint(order))
    h = order // r
    cert = prime_certificate(r)
    if not check_prime(cert):
        raise ValueError("uncertified rank modulus")
    original = set()
    for x in range(1 << l):
        p = E.lift_x(x)
        if p is not None:
            original.update((p, E.neg(p)))
    original = sorted(original, key=encode)
    projected = {p: scalar_mul(E, p, h) for p in original}
    usable = sorted(set(projected.values()) - {INF}, key=encode)
    if not usable or any(not E.on_curve(p) or scalar_mul(E, p, r) != INF for p in usable):
        raise ValueError("invalid projected subgroup base")
    representatives = sorted({min((p, E.neg(p)), key=encode) for p in usable}, key=encode)
    base = {"n": n, "l": l, "modulus": F.mod, "curve": "y^2+xy=x^3+1",
            "curve_order": order, "subgroup_order": r, "cofactor": h,
            "prime_certificate": cert, "original_points": list(map(encode, original)),
            "projected_points": list(map(encode, usable)),
            "signed_representatives": list(map(encode, representatives)),
            "B": len(usable), "effective_columns": len(representatives),
            "generator": encode(usable[0]), "projection": "P -> [cofactor]P",
            "folding": "sign only; no Frobenius quotient",
            "coverage_bound_numerator": (len(usable) + int(INF in projected.values())) ** 3,
            "coverage_bound_denominator": r - 1}
    return E, base


def source_hashes():
    files = list(Path(__file__).parent.glob("*.py")) + list((ROOT / "groebner_compare").glob("*.py"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def freeze(args):
    start = time.monotonic()
    E, base = prepare(args.n, args.l)
    base_seconds = time.monotonic() - start
    workloads = []
    for seed in args.seeds:
        start = time.monotonic()
        rng = random.Random(seed)
        generator = decode(base["generator"])
        queries = []
        for _ in range(args.attempts):
            k = rng.randrange(1, base["subgroup_order"])
            queries.append({"scalar": k, "point": encode(scalar_mul(E, generator, k))})
        work = {"seed": seed, "law": "uniform nonidentity subgroup scalar; no planted decomposition",
                "queries": queries, "base_sha256": digest(base)}
        workloads.append({"work": work, "sha256": digest(work),
                          "generation_seconds": time.monotonic() - start})
    manifest = {"schema": "ordinary-pdp-v1", "scope": "relation-collection stage diagnostic",
                "candidate_id": None, "full_dlp_speedup": None, "base": base,
                "base_sha256": digest(base), "base_construction_seconds": base_seconds,
                "workloads": workloads, "backends": list(BACKENDS),
                "attempt_seconds": args.attempt_seconds, "cell_seconds": args.cell_seconds,
                "memory_mib": 2048, "threads": 1, "accounting": ACCOUNTING,
                "source_sha256": source_hashes(), "gate_min_seeds": 5, "gate_min_rank": 8,
                "stop": "fixed query count or cell watchdog; no adaptive replenishment",
                "exclusions": ["dependency installation", "manifest serialization", "post-run audit and summary"]}
    with args.output.open("x") as f:
        json.dump(manifest, f, sort_keys=True, indent=2)
        f.write("\n")
    print(json.dumps({"manifest": str(args.output), "sha256": digest(manifest),
                      "B": base["B"], "columns": base["effective_columns"],
                      "coverage_upper_bound": min(1, base["coverage_bound_numerator"] /
                                                   base["coverage_bound_denominator"])}))


def relation(E, base, target, xs):
    """Exact signed point sum and cofactor projection; independent of equations."""
    if len(xs) != 3 or any(type(x) is not int or not 0 <= x < 1 << base["l"] for x in xs):
        return None
    pts = [E.lift_x(x) for x in xs]
    if any(p is None for p in pts):
        return None
    allowed = {decode(p) for p in base["original_points"]}
    reps = [decode(p) for p in base["signed_representatives"]]
    columns = {p: (i, sign) for i, rep in enumerate(reps) for p, sign in ((rep, 1), (E.neg(rep), -1))}
    for signs in itertools.product((1, -1), repeat=3):
        signed = [p if s == 1 else E.neg(p) for p, s in zip(pts, signs)]
        if any(p not in allowed for p in signed) or E.sum(signed) != target:
            continue
        images = [scalar_mul(E, p, base["cofactor"]) for p in signed]
        if E.sum(images) != scalar_mul(E, target, base["cofactor"]):
            raise ValueError("projection mismatch")
        row = [0] * len(reps)
        for p in images:
            if p != INF:
                if p not in columns:
                    raise ValueError("point outside frozen projected base")
                i, sign = columns[p]
                row[i] += sign
        return {"points": list(map(encode, signed)), "xs": xs, "coefficients": row}
    return None


def sat_solver(equations, n):
    import pycryptosat
    solver = pycryptosat.Solver(threads=1)
    # Ensure even an unconstrained input variable occurs in the model.
    for i in range(1, n + 1):
        solver.add_clause([i, -i])
    gates = {m: n + i + 1 for i, m in enumerate(sorted({
        m for row in equations for m in row if m.bit_count() > 1}))}
    for m, aux in gates.items():
        factors = [i + 1 for i in range(n) if m >> i & 1]
        for factor in factors:
            solver.add_clause([-aux, factor])
        solver.add_clause([aux, *(-i for i in factors)])
    for row in equations:
        variables = [gates.get(m, m.bit_length()) for m in row if m]
        if variables:
            solver.add_xor_clause(variables, 0 in row)
        elif 0 in row:
            solver.add_clause([])
    return solver


def solve_attempt(request):
    """Only receives a public target point, never its generating scalar."""
    from descend import descend, Instance
    from sumpoly import summation_polynomials
    base, target = request["base"], decode(request["target"])
    F = GF2n(base["n"], base["modulus"])
    E = Curve(F, 1)
    start = time.monotonic()
    anf = descend(summation_polynomials(4), F, E, 3, base["l"], target.x)
    inst = Instance(base["n"], F.mod, 1, 3, base["l"], target.x, anf, 0, [])
    equations = [sorted(row) for row in inst.equations()]
    input_record = {"nvars": inst.nvars, "equations": equations, "target": request["target"]}
    Path(request["input_path"]).write_text(json.dumps(input_record) + "\n")
    timing = {"encoding_seconds": time.monotonic() - start}
    name = request["backend"]
    stats = {}
    constraints = equations
    if name in ("repository-f5b", "block-f4"):
        gb_request = {"operation": "solve", "ring": {"nvars": inst.nvars},
                      "instance": {"equations": equations, "blocks": [base["l"]] * 3}}
        if name == "repository-f5b":
            from groebner_compare.worker import solve
        else:
            from groebner_compare.research_worker import solve
        result = solve(name, gb_request)
        if result["status"] != "ok":
            return result
        constraints = result["basis_terms"]
        stats = result.get("metrics", {})
    # Root extraction for GB outputs is charged. Only witnesses checked against
    # the ORIGINAL equations and group law are accepted; no completeness claim.
    solver = sat_solver(constraints, inst.nvars)
    guesses = itertools.product((False, True), repeat=3) if name == "hybrid-cryptominisat" else [()]
    rejected = branches = 0
    for values in guesses:
        branches += 1
        assumptions = [(i + 1) if value else -(i + 1) for i, value in enumerate(values)]
        while True:
            sat, model = solver.solve(assumptions=assumptions)
            if sat is not True:
                break
            word = sum(1 << i for i in range(inst.nvars) if model[i + 1])
            xs = inst.x_from_assignment(word)
            witness = relation(E, base, target, xs) if vanishes(equations, word) else None
            if witness is not None:
                return {"status": "witness", "xs": xs, "assignment": word,
                        "input_sha256": digest(input_record), "rejected_roots": rejected,
                        "branches": branches, "metrics": stats, **timing}
            rejected += 1
            solver.add_clause([-(i + 1) if word >> i & 1 else i + 1 for i in range(inst.nvars)])
    return {"status": "no_witness_uncertified", "input_sha256": digest(input_record),
            "rejected_roots": rejected, "branches": branches, "metrics": stats, **timing}


def emit(obj):
    print(json.dumps(obj, sort_keys=True), flush=True)


def worker(manifest, backend, work_index, directory):
    memory = manifest["memory_mib"] * 1024**2
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    base = manifest["base"]
    E = Curve(GF2n(base["n"], base["modulus"]), 1)
    work = manifest["workloads"][work_index]["work"]
    rank = RelationRank(base["subgroup_order"], base["effective_columns"])
    points = [decode(p) for p in base["original_points"]]
    started = time.monotonic()
    pairs = {}
    if backend == "direct":
        for i, p in enumerate(points):
            for q in points[i:]:
                pairs.setdefault(E.add(p, q), (p, q))
    emit({"event": "setup", "backend": backend, "pair_index_seconds": time.monotonic() - started})
    for i, query in enumerate(work["queries"]):
        started = time.monotonic()
        target = decode(query["point"])
        certificate = None
        if backend == "direct":
            for p in points:
                pair = pairs.get(E.add(target, E.neg(p)))
                if pair is not None:
                    certificate = relation(E, base, target, [pair[0].x, pair[1].x, p.x])
                    if certificate is None:
                        raise ValueError("direct lookup verification failed")
                    break
            response = {"status": "witness" if certificate else "no_relation_exact"}
        else:
            request = {"base": base, "target": query["point"], "backend": backend,
                       "input_path": str(directory / f"input-{i}.json")}
            (directory / f"request-{i}.json").write_text(json.dumps(request) + "\n")
            with (directory / f"solver-{i}.stdout").open("w") as out, (directory / f"solver-{i}.stderr").open("w") as err:
                proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "attempt"],
                                        stdin=subprocess.PIPE, stdout=out, stderr=err, text=True)
                try:
                    proc.communicate(json.dumps(request), timeout=manifest["attempt_seconds"])
                    if proc.returncode:
                        response = {"status": "error", "returncode": proc.returncode}
                    else:
                        response = json.loads((directory / f"solver-{i}.stdout").read_text())
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    response = {"status": "timeout"}
            telemetry = dict(response.get("metrics", {}))
            for line in (directory / f"solver-{i}.stderr").read_text().splitlines():
                if line.startswith("GROEBNER_TELEMETRY "):
                    try:
                        progress = json.loads(line.split(" ", 1)[1])
                    except json.JSONDecodeError:
                        continue
                    for key in ("highest_degree", "largest_matrix_rows", "largest_matrix_columns"):
                        if type(progress.get(key)) is int:
                            telemetry[key] = max(telemetry.get(key, 0), progress[key])
            response["backend_reported_telemetry"] = {
                key: telemetry.get(key) for key in
                ("highest_degree", "largest_matrix_rows", "largest_matrix_columns")}
            if response["status"] == "witness":
                certificate = relation(E, base, target, response["xs"])
                if certificate is None:
                    raise ValueError("solver witness failed independent group check")
        rank_status = None
        if certificate is not None:
            certificate["rhs_scalar"] = base["cofactor"] * query["scalar"] % base["subgroup_order"]
            rank_status = rank.add(certificate["coefficients"])
        emit({"event": "attempt", "index": i, "response": response,
              "certificate": certificate, "rank_status": rank_status, "rank_after": rank.rank,
              "wall_seconds": time.monotonic() - started})
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    emit({"event": "complete", "rank": rank.rank,
          "cpu_seconds_self_and_reaped_children": own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime,
          "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          "peak_child_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss})


def replay(manifest, work_index, events):
    """Separate post-run group checks and batch rank via SymPy's finite field."""
    from sympy import GF
    from sympy.polys.matrices import DomainMatrix
    base = manifest["base"]
    E = Curve(GF2n(base["n"], base["modulus"]), 1)
    queries = manifest["workloads"][work_index]["work"]["queries"]
    reps = [decode(p) for p in base["signed_representatives"]]
    allowed = {decode(p) for p in base["original_points"]}
    rows, seen = [], set()
    if not check_prime(base["prime_certificate"]):
        raise ValueError("prime replay failed")
    for ev in events:
        if ev["event"] != "attempt":
            continue
        i = ev["index"]
        if i in seen or i != len(seen):
            raise ValueError("missing or repeated query")
        seen.add(i)
        query = queries[i]
        cert = ev["certificate"]
        if cert is not None:
            pts = [decode(p) for p in cert["points"]]
            if len(pts) != 3 or any(p not in allowed or not E.on_curve(p) for p in pts):
                raise ValueError("replay: point outside base")
            if E.sum(pts) != decode(query["point"]):
                raise ValueError("replay: wrong signed point sum")
            row = [0] * len(reps)
            for p in pts:
                image = scalar_mul(E, p, base["cofactor"])
                if image == INF:
                    continue
                if image in reps:
                    row[reps.index(image)] += 1
                elif E.neg(image) in reps:
                    row[reps.index(E.neg(image))] -= 1
                else:
                    raise ValueError("replay: projected point outside columns")
            rhs = base["cofactor"] * query["scalar"] % base["subgroup_order"]
            if row != cert["coefficients"] or rhs != cert["rhs_scalar"]:
                raise ValueError("replay: wrong coefficients or RHS")
            lhs = E.sum([scalar_mul(E, p, x % base["subgroup_order"]) for p, x in zip(reps, row)])
            if lhs != scalar_mul(E, decode(base["generator"]), rhs):
                raise ValueError("replay: invalid subgroup row")
            rows.append(row)
        actual_rank = (DomainMatrix.from_list(rows, GF(base["subgroup_order"])).rank() if rows else 0)
        if actual_rank != ev["rank_after"]:
            raise ValueError("independent batch rank disagrees")
    return len(seen), (DomainMatrix.from_list(rows, GF(base["subgroup_order"])).rank() if rows else 0)


def run(args):
    manifest = json.loads(args.manifest.read_text())
    if source_hashes() != manifest["source_sha256"]:
        raise ValueError("source changed after freeze; create a new manifest")
    base = manifest["base"]
    if digest(base) != manifest["base_sha256"]:
        raise ValueError("base digest mismatch")
    # Reconstruction checks occur outside measured workers. Their original
    # construction cost is explicitly charged once to EVERY comparison arm.
    _, regenerated = prepare(base["n"], base["l"])
    if regenerated != base:
        raise ValueError("base regeneration mismatch")
    for w in manifest["workloads"]:
        if digest(w["work"]) != w["sha256"]:
            raise ValueError("workload digest mismatch")
        E = Curve(GF2n(base["n"], base["modulus"]), 1)
        rng = random.Random(w["work"]["seed"])
        for query in w["work"]["queries"]:
            k = rng.randrange(1, base["subgroup_order"])
            if query != {"scalar": k, "point": encode(scalar_mul(E, decode(base["generator"]), k))}:
                raise ValueError("query differs from frozen ordinary sampling law")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "manifest.json").write_text(args.manifest.read_text())
    host = {"platform": platform.platform(), "python": sys.version,
            "cpu": platform.processor(), "cpu_count": os.cpu_count(),
            "pycryptosat": __import__("pycryptosat").__version__,
            "sympy": __import__("sympy").__version__, "source_sha256": source_hashes()}
    (args.output / "host.json").write_text(json.dumps(host, indent=2) + "\n")
    runs = []
    for wi, workload in enumerate(manifest["workloads"]):
        order = list(manifest["backends"])
        if wi % 2:
            order.reverse()
        for backend in order:
            directory = (args.output / f"seed-{workload['work']['seed']}-{backend}").resolve()
            directory.mkdir()
            env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                   "MKL_NUM_THREADS": "1", "PYTHONHASHSEED": "0"}
            started = time.monotonic()
            timed_out = False
            with (directory / "journal.jsonl").open("w") as out, (directory / "stderr.txt").open("w") as err:
                proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "worker",
                                         str(args.manifest.resolve()), backend, str(wi), str(directory)],
                                        stdout=out, stderr=err, env=env, start_new_session=True)
                try:
                    proc.wait(timeout=manifest["cell_seconds"])
                except subprocess.TimeoutExpired:
                    timed_out = True
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
            wall = time.monotonic() - started
            events = []
            for line in (directory / "journal.jsonl").read_text().splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    break
            count, rank = replay(manifest, wi, events)
            complete = (not timed_out and proc.returncode == 0 and events
                        and events[-1]["event"] == "complete" and count == len(workload["work"]["queries"]))
            charged = wall + manifest["base_construction_seconds"] + workload["generation_seconds"]
            attempts = [e for e in events if e["event"] == "attempt"]
            row = {"backend": backend, "seed": workload["work"]["seed"], "rank": rank,
                   "status": "complete" if complete else "cell_timeout" if timed_out else "error",
                   "attempts": count, "attempt_budget": len(workload["work"]["queries"]),
                   "verified_relations": sum(e["certificate"] is not None for e in attempts),
                   "outcomes": dict(Counter(e["response"]["status"] for e in attempts)),
                   "rank_outcomes": dict(Counter(e["rank_status"] for e in attempts if e["rank_status"])),
                   "verification_replayed": True, "worker_wall_seconds": wall,
                   "charged_wall_seconds": charged, "seconds_per_new_row": charged / rank if rank else None,
                   "base_sha256": manifest["base_sha256"], "workload_sha256": workload["sha256"],
                   "accounting": ACCOUNTING, "returncode": proc.returncode,
                   "memory": events[-1] if complete else None}
            runs.append(row)
            (directory / "summary.json").write_text(json.dumps(row, indent=2) + "\n")
            emit(row)
    gates = [comparison_gate(runs, ["direct", "cryptominisat"], candidate,
                              min_seeds=manifest["gate_min_seeds"], min_rank=manifest["gate_min_rank"])
             for candidate in manifest["backends"] if candidate not in ("direct", "cryptominisat")]
    result = {"schema": manifest["schema"], "scope": manifest["scope"], "runs": runs,
              "gates": gates, "candidate_id": None, "full_dlp_speedup": None}
    (args.output / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    f = subs.add_parser("freeze")
    f.add_argument("output", type=Path)
    f.add_argument("--n", type=int, required=True)
    f.add_argument("--l", type=int, required=True)
    f.add_argument("--seeds", nargs="+", type=int, default=[20260928, 20260929])
    f.add_argument("--attempts", type=int, default=8)
    f.add_argument("--attempt-seconds", type=float, default=3)
    f.add_argument("--cell-seconds", type=float, default=60)
    r = subs.add_parser("run")
    r.add_argument("manifest", type=Path)
    r.add_argument("output", type=Path)
    w = subs.add_parser("worker")
    w.add_argument("manifest", type=Path)
    w.add_argument("backend", choices=BACKENDS)
    w.add_argument("work_index", type=int)
    w.add_argument("directory", type=Path)
    subs.add_parser("attempt")
    args = parser.parse_args()
    if args.command == "freeze":
        if args.attempts < 1 or args.attempt_seconds <= 0 or args.cell_seconds <= 0 or len(set(args.seeds)) != len(args.seeds):
            parser.error("positive budgets and unique seeds required")
        freeze(args)
    elif args.command == "run":
        run(args)
    elif args.command == "worker":
        worker(json.loads(args.manifest.read_text()), args.backend, args.work_index, args.directory)
    else:
        try:
            emit(solve_attempt(json.load(sys.stdin)))
        except ImportError as error:
            emit({"status": "unavailable", "reason": str(error)})


if __name__ == "__main__":
    main()
