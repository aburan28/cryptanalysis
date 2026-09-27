#!/usr/bin/env python3
"""Paper-style relation-collection and linear-algebra accounting for IC receipts.

The optional paper panel reproduces the *models*, not measurements, from Table 1
of Galbraith, Granger, Merz and Petit, On Index Calculus Algorithms for Subfield
Curves (SAC 2020). H_i is an unknown cost of solving one polynomial system.
"""

from __future__ import annotations

import argparse
import json
import math
from fractions import Fraction
from pathlib import Path

PAPER = "https://sacworkshop.org/SAC20/files/preproceedings/18-IndexCalculus.pdf"
COLLECTION = ("queries", "pdp", "relation_check")
MATRIX = ("matrix_build", "relation_la")
ALL_PHASES = ("setup", "isogeny", "factor_base", "precompute", *COLLECTION,
              *MATRIX, "target_descent", "recovery_check")


def phase_sum(phases: dict, names: tuple[str, ...]) -> int | None:
    if not isinstance(phases, dict) or any(phases.get(k) is None for k in names):
        return None
    return sum(phases[k] for k in names)


def ratio(a: int | None, b: int | None) -> float | None:
    return a / b if a is not None and b is not None and b > 0 else None


def wilson95(success: int, trials: int) -> tuple[float, float] | None:
    if not 0 <= success <= trials or trials == 0:
        return None
    z = 1.959963984540054
    p = success / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    width = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return max(0., centre - width), min(1., centre + width)


def measure(rec: dict) -> dict:
    """No extrapolation: missing/uncharged phases stay unknown, including prime LA."""
    if rec.get("kind") != "full_dlp":
        raise ValueError("expected a full_dlp receipt; a PDP-stage profile is not an IC run")
    c = rec["counts"]
    ops, walls = rec.get("phase_operations"), rec.get("phase_wall_ns")
    prime = rec["source_curve_ref"].startswith("EC1P")
    queries = c["ordinary_queries"]
    rows = c["novel_rows"]
    if queries < 0 or rows < 0:
        raise ValueError("query and novel-row counts must be nonnegative")
    # The prime bridge puts counted relation-oracle and probe work in precompute.
    # Graph LA is not separately metered, even when its zero placeholder is present.
    collection = ("precompute",) if prime else COLLECTION
    col_ops, col_wall = phase_sum(ops, collection), phase_sum(walls, collection)
    la_ops = None if prime else phase_sum(ops, MATRIX)
    la_wall = None if prime else phase_sum(walls, MATRIX)
    solver_attempts = c.get("pdp_attempts", 0)
    h_ops = None if prime else ratio(phase_sum(ops, ("pdp",)), solver_attempts)
    h_wall = None if prime else ratio(phase_sum(walls, ("pdp",)), solver_attempts)
    complete = (rec.get("status") == "complete" and rec.get("verified_scalar") is True
                and c.get("targets_verified") == c.get("targets") and c.get("targets", 0) > 0)
    charged = phase_sum(ops, ALL_PHASES)
    total = rec.get("total_operations")
    if total is not None and charged is not None and total != charged:
        raise ValueError(f"{rec.get('run_id')}: total_operations disagrees with exclusive phases")
    online = rec.get("online") or {}
    rho_measured = rec.get("rho_measured") or {}
    primary = c.get("targets") == 1 and complete and rho_measured.get("verified") is True
    online_speedup = ratio(online.get("rho_online_ns"), online.get("ic_online_ns")) if primary else None
    # Positive-query count has a Bernoulli interpretation in the binary harness;
    # prime orbit relations can be produced in batches, so no binomial CI there.
    successes = c.get("solved_queries")
    success_ci = (wilson95(successes, queries) if not prime and isinstance(successes, int)
                  else None)
    return {
        "profile_id": rec["profile_id"], "candidate_id": rec["candidate_id"],
        "workload_id": rec["workload_id"], "run_id": rec["run_id"],
        "regime": "prime orbit" if prime else "binary PDP",
        "source_curve_ref": rec["source_curve_ref"], "status": rec["status"],
        "verified": complete, "targets": c.get("targets"),
        "unit": rec.get("operation_unit"), "calibration_id": (rec.get("provenance") or {}).get("calibration_id"),
        "factor_base_points": (rec.get("stage") or {}).get("fb_points") if not prime else
                              (rec.get("native_prime_report") or {}).get("factor_base", {}).get("points"),
        "matrix_columns": c.get("effective_columns"), "rank": c.get("final_rank"),
        "queries": queries, "verified_relations": c.get("verified_relations"), "novel_rows": rows,
        "unsat": c.get("pdp_proved_unsat"), "timeouts": c.get("pdp_timeout"),
        "budget": c.get("pdp_budget"), "errors": c.get("pdp_error"),
        "query_success_wilson95": success_ci,
        "collection_ops": col_ops, "collection_wall_ns": col_wall,
        "systems_solved": None if prime else solver_attempts,
        "mean_H_ops": h_ops, "mean_H_wall_ns": h_wall,
        "queries_per_novel_row": ratio(queries, rows),
        "collection_ops_per_novel_row": ratio(col_ops, rows),
        "matrix_ops": la_ops, "matrix_wall_ns": la_wall,
        "total_ops": total if complete else None,
        "rho_expected_ops": rec.get("rho_operations"),
        "cold_ic_over_rho": ratio(total, rec.get("rho_operations")) if complete and c.get("targets") == 1 else None,
        "online_ic_ns": online.get("ic_online_ns") if primary else None,
        "online_rho_ns": online.get("rho_online_ns") if primary else None,
        "online_rho_over_ic": online_speedup,
        "prime_stage_note": ("counted oracle/probe group operations in precompute; "
                             "graph LA and its wall time are not separately metered") if prime else None,
    }


def short(value: int | float | None, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value:,}" if abs(value) < 1_000_000 else f"{value:.3g}"
    return f"{value:.{digits}g}"


def empirical_table(rows: list[dict]) -> str:
    lines = ["## Observed IC costs", "",
             "| Method / workload | status | B → columns | queries → verified → rank | Relation collection (ops; ms) | mean H (ops/system) | Final matrix (ops; ms) | queries/rank | collection ops/rank | one-target rho/IC online |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        name = f"{r['regime']} / {r['profile_id']} / {r['workload_id']} / {r['candidate_id'][-12:]}"
        co = f"{short(r['collection_ops'])}; {short(r['collection_wall_ns']/1e6) if r['collection_wall_ns'] is not None else '—'}"
        la = f"{short(r['matrix_ops'])}; {short(r['matrix_wall_ns']/1e6) if r['matrix_wall_ns'] is not None else '—'}"
        lines.append(f"| {name} | {r['status']}{' ✓' if r['verified'] else ''} | "
                     f"{short(r['factor_base_points'])} → {short(r['matrix_columns'])} | "
                     f"{short(r['queries'])} → {short(r['verified_relations'])} → {short(r['novel_rows'])} | "
                     f"{co} | {short(r['mean_H_ops'])} | {la} | {short(r['queries_per_novel_row'])} | "
                     f"{short(r['collection_ops_per_novel_row'])} | {short(r['online_rho_over_ic'])} |")
    lines += ["", "| Workload / candidate suffix | verified-query yield (Wilson 95%) | unsat / timeout / budget / error | rank / columns | cold IC / one-rho ops |",
              "|---|---:|---:|---:|---:|"]
    for r in rows:
        ci = r["query_success_wilson95"]
        success = (f"[{short(100*ci[0])}%, {short(100*ci[1])}%]" if ci else "—")
        lines.append(f"| {r['workload_id']} / {r['candidate_id'][-12:]} | {success} | "
                     f"{short(r['unsat'])} / {short(r['timeouts'])} / {short(r['budget'])} / {short(r['errors'])} | "
                     f"{short(r['rank'])} / {short(r['matrix_columns'])} | {short(r['cold_ic_over_rho'])} |")
    lines += ["", "Each row uses its receipt's native unit: binary `rps` and prime counted group operations. "
              "Times are milliseconds on the run host. Do not compare absolute operations between regimes. "
              "The rho/IC column uses paired, verified, one-target **online wall time** (values above 1 favor IC).",
              "Collection includes failed searches. In binary receipts it is queries + PDP + relation checks; "
              "mean H is measured PDP work divided by *all* PDP attempts. Matrix includes build + final relation LA, "
              "not the internal Macaulay elimination. Prime receipts put counted oracle/probe work in precompute; "
              "their final graph LA is not separately metered, so its entry is unknown rather than zero.",
              "The yield interval uses binary positive-query counts; prime relation batches have no Bernoulli "
              "interval. Cold IC/rho is supplementary and compares counted operations for one target. "
              "Zero rank leaves cost per independent row unknown. Incomplete or unverified runs cannot show an "
              "end-to-end speedup. The observed rank is checked, never multiplied by a theoretical Frobenius factor.",
              ""]
    return "\n".join(lines)


def paper_models(q: int, n: int, n_prime: int, m: int) -> list[tuple[str, Fraction, Fraction, str]]:
    if q < 2 or n_prime < 1 or m < 2 or n < n_prime * m:
        raise ValueError("require q >= 2, n' >= 1, m >= 2, n >= m*n'")
    base = Fraction(q ** (n_prime + n - n_prime * m), 2**m)
    square = q ** (2 * n_prime)
    return [
        ("General IC", math.factorial(m) * base, Fraction(m * square), "H1"),
        ("m distinct bases", m * base, Fraction(m**3 * square), "H1"),
        ("Koblitz symmetry", base, Fraction(m * square), "H2"),
        ("one Frobenius invariant base", math.factorial(m) * base / n_prime,
         Fraction(m * square, n * n), "H3"),
        ("invariant + symmetry", m * base / n, Fraction(m**3 * square, n * n), "H4"),
    ]


def invariant_dimension_check(q: int, n: int, n_prime: int) -> str | None:
    """A cheap feasibility check when n is prime and gcd(q,n)=1.

    Frobenius-invariant linear subspaces correspond to factors of X^n-1 over
    F_q. For prime n, its nontrivial irreducible factors all have degree
    ord_n(q). This does not judge nonlinear invariant factor bases.
    """
    if n < 2 or any(n % d == 0 for d in range(2, math.isqrt(n) + 1)) or math.gcd(q, n) != 1:
        return None
    order = next(d for d in range(1, n) if pow(q, d, n) == 1)
    possible = {e * order + offset for e in range((n-1)//order + 1)
                for offset in (0, 1)}
    if n_prime not in possible:
        return (f"Dimension check: ord_{n}({q})={order}, so no Frobenius-invariant "
                f"F_{q}-linear subspace of F_{q}^{n} has dimension {n_prime}. "
                "The invariant-vector-space rows are formal substitutions here, "
                "not applicable constructions. Nonlinear invariant bases need separate evidence.")
    return None


def theory_table(q: int, n: int, n_prime: int, m: int) -> str:
    lines = [f"## Paper model (q={q}, n={n}, n′={n_prime}, m={m}, k={n-m*n_prime})", "",
             "| Method | Expected polynomial systems | Relation collection cost | LA asymptotic proxy |",
             "|---|---:|---:|---:|"]
    for name, count, la, h in paper_models(q, n, n_prime, m):
        lines.append(f"| {name} | {float(count):.4g} | {float(count):.4g} × {h} | O({float(la):.4g}) |")
    lines += ["", f"Source: {PAPER} (Table 1). These are heuristic system counts and asymptotic LA "
              "proxies, **not measured timings**. H1–H4 are different, unmeasured per-system solve costs. "
              "The Frobenius rows require a subfield curve, an invariant usable factor base and the "
              "claimed independent orbit relations; no measured candidate is assigned these gains automatically."]
    dimension_note = invariant_dimension_check(q, n, n_prime)
    if dimension_note:
        lines += ["", dimension_note]
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jsonl", nargs="*", type=Path, help="normalized IC full-DLP receipt files")
    ap.add_argument("--paper", nargs=4, type=int, metavar=("Q", "N", "N_PRIME", "M"),
                    help="append Table 1's symbolic model for q,n,n',m")
    ap.add_argument("--json", action="store_true", help="output derived measured fields as JSON")
    args = ap.parse_args()
    if not args.jsonl and not args.paper:
        ap.error("provide a JSONL receipt or --paper")
    rows = [measure(json.loads(line)) for path in args.jsonl
            for line in path.read_text().splitlines() if line.strip()]
    if args.json:
        print(json.dumps({"observed": rows, "paper_parameters": args.paper}, indent=2))
    else:
        if rows:
            print(empirical_table(rows))
        if args.paper:
            print(theory_table(*args.paper))


if __name__ == "__main__":
    main()
