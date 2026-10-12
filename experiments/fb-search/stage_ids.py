#!/usr/bin/env python3
"""AGENTS.md stage-profile identifiers for the above-limit measurements (ABOVE_LIMIT.md).

Every measured cell is a PDP-stage profile with no relation LA or target descent, so it gets
`candidate_id: null` and a label `PS1N<n>C<tag>fb<B>PDP2ht h<12hex>`, hashing its factor-base and
point-decomposition records. The residual solver (Python or C enumeration, MXL, t-closure,
CryptoMiniSat, plain t-Macaulay certificate) is part of the point-decomposition record, so each
solver gets its own PS1 label on the same factor base.

Workload IDs hash the exact target stream (seed string, law, filter, target count). The target
count is recovered by replaying the stream against the recorded rows. Run IDs are
`<PS1>W<workload>R<k>`, numbered in file order when one stage config ran twice on one workload.

When the factor base is too large to enumerate here (2^l points, l >= 24), B and the
enumerated-set digest are unknown. The record then stays recipe-only and the label is null,
as for recipe-only fb-archive entries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "pdp-degree-heuristics"))
sys.path.insert(0, str(HERE))

from factor_base import FactorBase, family_basis  # noqa: E402
from htsolver import HalfTraceSolver  # noqa: E402
from residual import htenum, residual_systems  # noqa: E402
from toycurve import ToyCurve, sha256_hex  # noqa: E402

ENUMERATE_MAX_L = 23
FAMILY, SEED = "geomtraceu", 1

PROJECTION = {
    "stage_code": "PDP2ht",
    "summand_count": 2,
    "summation_polynomial": "S_3(X, Y, S) as the Artin-Schreier equation (p/S)^2 + p/S = (u + sqrt(b)/S)^2, "
    "u = X + Y, p = XY (Courtois, ePrint 2016/003, Sec. 2)",
    "projection": "X^2 + uX + p(u) = 0 projected onto F/V^(2), plus Tr(u) = Tr(sqrt(b)/S), one system per eps; "
    "the residual is the affine solution space U of dimension d = max(0, dim V + dim V^(2) - n - 1 + [V in ker Tr])",
    "residual_system": "the V^(2) coordinates of X^2 + u(t) X + p(u(t)) = 0: 2l - 1 bilinear equations in "
    "x (l bits) and t (d bits), x bits 0..l-1, t bits l..l+d-1 (residual.residual_systems)",
    "cache_policy": "V^(2), its parity checks and HT(v_j^2) precomputed per factor base",
}

RESIDUAL = {
    "ht-python": {"residual_solver": "enumerate U; split each u by one half-trace and keep {X, Y} in V whose "
                  "signed lifts sum to R (htsolver.HalfTraceSolver.decompose)", "family": "enumeration",
                  "monomial_order": "none", "internal_kernel": "Python F_2 bit vectors",
                  "sources": ["experiments/pdp-degree-heuristics/htsolver.py"]},
    "ht-c": {"residual_solver": "enumerate U in Gray-code order with incremental u, u^2, p(u), Montgomery batch "
             "inversion, pclmul field multiplication, byte tables for HT and the V-syndrome (htenum.c)",
             "family": "enumeration", "monomial_order": "none", "internal_kernel": "C, 64-bit words",
             "sources": ["experiments/fb-search/htenum.c", "experiments/fb-search/residual.py"]},
    "mxl": {"residual_solver": "MXL degree scan of the residual Boolean system (macaulay.degree_scan, mode mxl)",
            "family": "xl", "monomial_order": "graded, as macaulay.py",
            "internal_kernel": "dense F_2 elimination (macaulay.py)",
            "sources": ["experiments/fb-search/residual.py", "experiments/pdp-degree-heuristics/macaulay.py"]},
    "smxl": {"residual_solver": "mutant XL closure multiplying by every variable (smxl.c, smxl_run)",
             "family": "xl", "monomial_order": "graded, sorted 64-bit monomial masks",
             "internal_kernel": "dense bit-row echelon over a sparse column map (smxl.c)",
             "sources": ["experiments/fb-search/smxl.c", "experiments/fb-search/residual.py"]},
    "tmxl": {"residual_solver": "mutant closure multiplying by the t variables only, on columns of x-degree <= 1; "
             "linear t-relations read off the closure (smxl.c, smxl_run_restricted)",
             "family": "xl", "monomial_order": "graded, sorted 64-bit monomial masks",
             "internal_kernel": "dense bit-row echelon over a sparse column map (smxl.c)",
             "sources": ["experiments/fb-search/smxl.c", "experiments/fb-search/residual.py"]},
    "cms": {"residual_solver": "CryptoMiniSat 5.15 (pycryptosat), native XOR clauses, one AND-gate variable per "
            "x_i t_k product, Gauss-Jordan on; SAT models rebuilt into X, Y and checked (residual.cms_solve)",
            "family": "sat", "monomial_order": "none", "internal_kernel": "CDCL + Gauss-Jordan (CryptoMiniSat)",
            "sources": ["experiments/fb-search/residual.py", "experiments/fb-search/cms_scan.py"]},
    "plain-t-macaulay": {"residual_solver": "refutation certificate only: is 1 in the span of {m f : m a t-monomial "
                         "of degree <= D - 2, f a residual equation} (certificate.py)", "family": "xl",
                         "monomial_order": "none (column order of first appearance)",
                         "internal_kernel": "Python-int F_2 elimination",
                         "sources": ["experiments/fb-search/certificate.py", "experiments/fb-search/residual.py"]},
}

# results file -> (solver, stream rule, how the factor base was keyed in that script)
FILES = {
    "residual-n23.jsonl": ("mxl", "residual", "record"),
    "residual-n41.jsonl": ("mxl", "residual", "record"),
    "residual-smxl-n41.jsonl": ("smxl", "residual", "record"),
    "residual-tmxl.jsonl": ("tmxl", "residual", None),
    "residual-tmxl-deg5.jsonl": ("tmxl", "residual", "recipe"),
    "cms-scan.jsonl": ("cms", "cms", None),
    "enum-scan.jsonl": ("ht-c", "cms", None),
    "certificate-n41.jsonl": ("plain-t-macaulay", "certificate", "recipe"),
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def snapshot(results: Path, sources: list[str]) -> tuple[dict, str]:
    """Content hashes of the executed sources at the commit that last modified the results file."""
    rel = str(results.relative_to(REPO))
    commit = git("log", "-1", "--format=%H", "--", rel) or git("rev-parse", "HEAD")
    out = {"rule": "content hashes of the sources at the last commit that modified the results file", "sha256": {}}
    for s in sources:
        blob = subprocess.run(["git", "show", f"{commit}:{s}"], cwd=REPO, capture_output=True).stdout
        out["sha256"][s] = hashlib.sha256(blob).hexdigest()
    return out, commit


def factor_base_record(C: ToyCurve, l: int) -> tuple[dict, object]:
    basis, params = family_basis(C, FAMILY, l, SEED)
    if l <= ENUMERATE_MAX_L:
        fb = FactorBase(C, FAMILY, l, SEED, basis=basis, params=params)
        return fb.record(), fb
    rec = {
        "curve_id": C.curve_id,
        "construction": {"family": FAMILY, "basis": [int(b) for b in basis],
                         "params": {k: int(v) for k, v in params.items()},
                         "polynomial_constraint": "none", "shifted_bases": "none"},
        "subgroup_policy": "cofactor_projection",
        "enumerated_set_sha256": None,
        "nominal_dimension": l,
        "geometric_point_count": None,
        "actual_usable_point_count": None,
        "strict_subgroup_point_count": None,
        "quotient_rule": "sign",
        "effective_columns": None,
    }
    return rec, None


def stream_seed(kind: str, n: int, l: int, fb_obj, basis: list[int], keyed: str) -> str:
    if kind == "cms":
        return f"cms|{n}|{l}|{FAMILY}|{SEED}"
    if keyed == "record":
        digest = fb_obj.digest
    else:
        digest = sha256_hex([FAMILY, l, SEED, basis])
    return f"{kind}|{digest}"


def replay_count(C: ToyCurve, sv: HalfTraceSolver, seed: str, rows: list[dict], per_target: str) -> int:
    """Number of targets drawn from the stream to produce `rows` (in file order)."""
    if per_target == "one":
        return len(rows)
    if per_target == "index":
        return max(r["target"] for r in rows) + 1
    rng = random.Random(seed)
    i, drawn = 0, 0
    while i < len(rows) and drawn < 10_000:
        _, R = C.random_subgroup_point(rng)
        drawn += 1
        branches = [(rs["eps"], rs["d"]) for rs in residual_systems(sv, R[0])]
        got = [(r["eps"], r["d"]) for r in rows[i:i + len(branches)]]
        if got != branches and not (i + len(got) == len(rows) and got == branches[:len(got)]):
            raise RuntimeError(f"replay mismatch at row {i}: {got} vs {branches}")
        i += len(got)
    if i != len(rows):
        raise RuntimeError(f"replay matched {i} of {len(rows)} rows")
    return drawn


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(HERE / "results" / "stage-ids.json"))
    ap.add_argument("--max-l", type=int, default=99)
    args = ap.parse_args()
    cells: dict[tuple, list[dict]] = {}
    for fname, (solver, kind, keyed) in FILES.items():
        path = HERE / "results" / fname
        for line in path.read_text().splitlines():
            r = json.loads(line)
            keyed_r = keyed or ("recipe" if r.get("decomposable") is None else "record")
            if kind == "cms":
                keyed_r = None
            cells.setdefault((fname, solver, kind, keyed_r, r["n"], r["l"]), []).append(r)
    curves: dict[int, ToyCurve] = {}
    fbs: dict[tuple, tuple] = {}
    out = []
    runs: dict[tuple, list] = {}
    for (fname, solver, kind, keyed, n, l), rows in sorted(cells.items(), key=lambda kv: (kv[0][4], kv[0][5], kv[0][0])):
        if l > args.max_l:
            continue
        C = curves.setdefault(n, ToyCurve(n))
        if (n, l) not in fbs:
            fbs[(n, l)] = factor_base_record(C, l)
        fb_rec, fb_obj = fbs[(n, l)]
        basis = fb_rec["construction"]["basis"]
        impl, commit = snapshot(HERE / "results" / fname, RESIDUAL[solver]["sources"])
        pd = {**PROJECTION, **{k: v for k, v in RESIDUAL[solver].items() if k != "sources"},
              "implementation": impl, "limits": "per run; see the run record"}
        digest = sha256_hex({"factor_base": fb_rec, "point_decomposition": pd})
        B = fb_rec["actual_usable_point_count"]
        sid = None if B is None else f"PS1N{n}C{C.tag}fb{B}PDP2hth{digest[:12]}"
        seed = stream_seed(kind, n, l, fb_obj, basis, keyed)
        only_refutations = all(r.get("decomposable") is False for r in rows) and kind == "residual" and solver != "mxl"
        per_target = "one" if kind == "cms" else ("index" if kind == "certificate" else "branches")
        sv = HalfTraceSolver(SimpleNamespace(curve=C, basis=basis, l=l))
        if per_target == "branches" and only_refutations:
            count = replay_refutations(C, sv, seed, rows)
        else:
            try:
                count = replay_count(C, sv, seed, rows, per_target)
            except RuntimeError:
                if per_target != "branches" or not all(r.get("decomposable") is False for r in rows):
                    raise
                only_refutations = True
                count = replay_refutations(C, sv, seed, rows)
        wrec = {
            "schema": "fb-search-workload/1",
            "curve_id": C.curve_id,
            "subgroup_order": str(C.r),
            "prng": "CPython random.Random seeded with the string (version-2 seeding)",
            "target_stream": seed,
            "target_law": "R = [k]G, k uniform on [1, r-1] (ToyCurve.random_subgroup_point), drawn in order",
            "target_count": count,
            "filter": "non-decomposable targets only" if only_refutations else "none",
            "cache_state": "cold",
        }
        wid = sha256_hex(wrec)[:12]
        runs.setdefault((sid, wid), []).append(fname)
        run = len(runs[(sid, wid)])
        out.append({
            "candidate_id": None,
            "stage_config_id": sid,
            "stage_config_digest": digest,
            "label_status": "ok" if sid else "null: B not enumerated (2^l points, l > %d); recipe-only factor base" % ENUMERATE_MAX_L,
            "curve_id": C.curve_id,
            "workload_id": wid,
            "run_id": None if sid is None else f"{sid}W{wid}R{run}",
            "results_file": f"experiments/fb-search/results/{fname}",
            "source_snapshot_commit": commit,
            "rows": len(rows),
            "cell": {"n": n, "l": l, "family": FAMILY, "seed": SEED, "solver": solver,
                     "d": sorted({r["d"] for r in rows})},
            "factor_base": fb_rec,
            "point_decomposition": pd,
            "workload": wrec,
            "relation_collection": "none", "relation_linear_algebra": "none", "target_descent": "none",
            "isogeny": "none",
        })
        print(f"{fname:26s} n={n} l={l:2d} {solver:16s} rows={len(rows):3d} targets={count:3d} "
              f"{sid or '(label null)'} W{wid}", flush=True)
    Path(args.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")


def replay_refutations(C: ToyCurve, sv: HalfTraceSolver, seed: str, rows: list[dict]) -> int:
    """As replay_count, for runs that skipped decomposable targets (truth by the C enumeration)."""
    rng = random.Random(seed)
    i, drawn = 0, 0
    while i < len(rows) and drawn < 10_000:
        _, R = C.random_subgroup_point(rng)
        drawn += 1
        systems = residual_systems(sv, R[0])
        if any(htenum(sv, rs, R[0])["hits"] for rs in systems):
            continue
        branches = [(rs["eps"], rs["d"]) for rs in systems]
        got = [(r["eps"], r["d"]) for r in rows[i:i + len(branches)]]
        if got != branches and not (i + len(got) == len(rows) and got == branches[:len(got)]):
            raise RuntimeError(f"replay mismatch at row {i}: {got} vs {branches}")
        i += len(got)
    return drawn


if __name__ == "__main__":
    main()
