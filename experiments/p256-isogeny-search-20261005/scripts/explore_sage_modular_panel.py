#!/usr/bin/env sage -python
"""Recover one-hop P-256 isogenies with instantiated modular polynomials.

Unlike ``isogenies_prime_degree()``, this route never constructs or factors the
full division polynomial.  For each simple root j2 of Phi_ell(j1, Y), symmetry
provides both first partial derivatives.  The modular-multipoints tangent
formula then gives the normalized codomain, after which Sage's BMSS algorithm
recovers the kernel polynomial and explicit rational map.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
import traceback
from pathlib import Path
from typing import Any

try:
    from sage.all import EllipticCurve, GF, ZZ, kronecker, pari
    from sage.env import SAGE_VERSION
    from sage.schemes.elliptic_curves.mod_poly import classical_modular_polynomial
except ImportError as exc:  # pragma: no cover - executed only outside Sage
    raise SystemExit("This program must run under `sage -python`.") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import explore_sage  # noqa: E402

P256 = explore_sage.P256


def root_candidate(curve: Any, generator: Any) -> dict[str, Any]:
    return {
        "candidate_id": "p256-root",
        "curve": explore_sage.curve_record(curve, generator),
        "path": [],
        "properties": {
            "sage_version": str(SAGE_VERSION),
            "explicit_path_verified": True,
            "automorphism_order_geometric": 2,
        },
        "cost_accounting": {
            "discovery_and_reusable_precomputation": {
                "status": "measured",
                "wall_seconds_to_discovery": 0.0,
                "path_degree_product": "1",
            },
            "per_instance_mapping": {
                "status": "not applicable",
                "required_source_points": 0,
            },
        },
    }


def explore_degree(ell: int) -> dict[str, Any]:
    field = GF(P256.p)
    curve = EllipticCurve(field, [P256.a, P256.b])
    generator = curve(P256.gx, P256.gy)
    discriminant = ZZ(P256.frobenius_discriminant)
    splitting = int(kronecker(discriminant, ell))
    if splitting == -1:
        raise ValueError(f"inert prime has no horizontal edge: {ell}")

    start = time.perf_counter()
    j1 = curve.j_invariant()
    fiber = classical_modular_polynomial(ell, j1)
    roots = fiber.roots(multiplicities=False)
    expected_roots = 1 if splitting == 0 else 2
    if len(roots) != expected_roots:
        raise AssertionError(
            f"degree {ell}: expected {expected_roots} rational roots, got {len(roots)}"
        )

    mu1 = 18 * curve.a6() / curve.a4()
    j1_derivative = mu1 * j1
    candidates = [root_candidate(curve, generator)]
    for j2 in roots:
        if j2 in (0, 1728):
            raise AssertionError(f"degree {ell}: exceptional codomain j={j2}")

        reverse_fiber = classical_modular_polynomial(ell, j2)
        partial_x = reverse_fiber.derivative()(j1)
        partial_y = fiber.derivative()(j2)
        if not partial_x or not partial_y:
            raise AssertionError(f"degree {ell}: nonsimple modular root")

        tangent = -j1_derivative * partial_x / (ell * partial_y)
        a2 = -(ell**4) * tangent**2 / (48 * j2 * (j2 - 1728))
        b2 = -(ell**6) * tangent**3 / (864 * j2**2 * (j2 - 1728))
        codomain = EllipticCurve(field, [a2, b2])
        if codomain.j_invariant() != j2:
            raise AssertionError(f"degree {ell}: normalized codomain has wrong j")

        isogeny = curve.isogeny(None, codomain=codomain, degree=ell)
        mapped_generator = isogeny(generator)
        if mapped_generator.is_zero() or not (P256.n * mapped_generator).is_zero():
            raise AssertionError(f"degree {ell}: mapped generator failed order check")
        if isogeny.kernel_polynomial().degree() != ell // 2:
            raise AssertionError(f"degree {ell}: kernel polynomial has wrong degree")

        next_j = int(j2)
        elapsed = time.perf_counter() - start
        candidates.append(
            {
                "candidate_id": explore_sage.candidate_id(next_j),
                "curve": explore_sage.curve_record(codomain, mapped_generator),
                "path": [
                    {
                        "degree": ell,
                        "domain_j": str(int(j1)),
                        "codomain_j": str(next_j),
                        "map": {
                            "isogeny": explore_sage.map_record(isogeny),
                            "codomain_short_model_isomorphism": None,
                        },
                        "kernel_polynomial": str(isogeny.kernel_polynomial()),
                    }
                ],
                "properties": {
                    "sage_version": str(SAGE_VERSION),
                    "explicit_path_verified": True,
                    "automorphism_order_geometric": 2,
                },
                "cost_accounting": {
                    "discovery_and_reusable_precomputation": {
                        "status": "measured",
                        "wall_seconds_to_discovery": elapsed,
                        "path_degree_product": str(ell),
                    },
                    "per_instance_mapping": {
                        "status": "formula retained; evaluation not timed",
                        "required_source_points": 2,
                    },
                },
            }
        )

    return {
        "schema_version": 1,
        "description": "P-256 horizontal isogeny candidates with explicit paths",
        "search": {
            "algorithm": (
                "instantiated classical modular polynomial, modular-multipoints "
                "normalized codomain, and BMSS kernel recovery"
            ),
            "ells": [ell],
            "depth": 1,
            "max_nodes": expected_roots + 1,
            "nodes_found": len(candidates),
            "elapsed_seconds": time.perf_counter() - start,
            "sage_version": str(SAGE_VERSION),
            "frobenius_discriminant": str(discriminant),
            "kronecker_symbol": splitting,
        },
        "candidates": candidates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ells", required=True)
    parser.add_argument("--pari-stack-gib", type=int, default=4)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.pari_stack_gib < 1:
        raise SystemExit("--pari-stack-gib must be positive")
    ells = [int(value) for value in args.ells.split(",") if value]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pari.allocatemem(args.pari_stack_gib * 1024**3, silent=True)
    classical_modular_polynomial.set_cache_bound(0)

    started = time.time()
    records = []
    for ell in ells:
        print(f"degree {ell}: starting modular recovery", flush=True)
        degree_started = time.time()
        output = args.output_dir / f"degree-{ell}.json"
        try:
            payload = explore_degree(ell)
            output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            record = {
                "ell": ell,
                "status": "completed",
                "nodes_found": payload["search"]["nodes_found"],
                "elapsed_seconds": time.time() - degree_started,
                "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "artifact": output.name,
            }
            print(
                f"degree {ell}: completed with {record['nodes_found'] - 1} neighbors",
                flush=True,
            )
        except Exception as exc:  # preserve every other independent degree
            record = {
                "ell": ell,
                "status": "failed",
                "elapsed_seconds": time.time() - degree_started,
                "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "exception_type": type(exc).__name__,
                "exception": str(exc),
                "traceback": traceback.format_exc(),
            }
            print(f"degree {ell}: failed: {type(exc).__name__}: {exc}", flush=True)
        records.append(record)
        panel = {
            "schema_version": 1,
            "sage_version": str(SAGE_VERSION),
            "algorithm": "instantiated modular polynomial with BMSS map recovery",
            "pari_stack_gib": args.pari_stack_gib,
            "requested_ells": ells,
            "records": records,
            "elapsed_wall_seconds": time.time() - started,
        }
        (args.output_dir / "panel-status.json").write_text(
            json.dumps(panel, indent=2, sort_keys=True) + "\n"
        )


if __name__ == "__main__":
    main()
