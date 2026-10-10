#!/usr/bin/env sage -python
"""Breadth-first horizontal isogeny exploration for SageMath.

Run with, for example:

    sage -python scripts/explore_sage.py --ells 3,5,11,13 --depth 2 \
        --max-nodes 100 --output data/candidates/generated/depth-2.json

Every retained node includes the image of the P-256 generator and a complete
path whose individual isogeny and model-isomorphism maps are serialized as Sage
rational functions.  The JSON is therefore an auditable interchange artifact;
for long searches, also retain the workflow logs and Sage version.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

try:
    from sage.all import EllipticCurve, GF, ZZ, kronecker
    from sage.env import SAGE_VERSION
except ImportError as exc:  # pragma: no cover - executed only outside Sage
    raise SystemExit("This program must run under `sage -python`.") from exc

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from p256_isogeny_search.constants import P256  # noqa: E402


def map_record(morphism: Any) -> dict[str, Any]:
    record: dict[str, Any] = {"sage_repr": str(morphism)}
    try:
        maps = morphism.rational_maps()
        record["rational_maps"] = [str(value) for value in maps]
    except (AttributeError, NotImplementedError):
        record["rational_maps"] = None
    return record


def short_model_with_map(curve: Any) -> tuple[Any, Any | None]:
    short = curve.short_weierstrass_model()
    if curve == short:
        return short, None
    return short, curve.isomorphism_to(short)


def curve_record(curve: Any, generator: Any) -> dict[str, str | dict[str, str]]:
    invariants = list(curve.a_invariants())
    if any(invariants[index] != 0 for index in (0, 1, 2)):
        raise ValueError("candidate is not in short Weierstrass form")
    return {
        "p": str(int(curve.base_field().order())),
        "a": str(int(invariants[3])),
        "b": str(int(invariants[4])),
        "n": str(P256.n),
        "generator": {"x": str(int(generator[0])), "y": str(int(generator[1]))},
        "j_invariant": str(int(curve.j_invariant())),
    }


def candidate_id(j_invariant: int) -> str:
    return f"p256-j-{j_invariant:064x}"


def explore(ells: list[int], depth: int, max_nodes: int) -> dict[str, Any]:
    field = GF(P256.p)
    root_curve = EllipticCurve(field, [P256.a, P256.b])
    root_generator = root_curve(P256.gx, P256.gy)
    discriminant = ZZ(P256.frobenius_discriminant)

    inert = [ell for ell in ells if kronecker(discriminant, ell) == -1]
    if inert:
        raise ValueError(f"inert primes have no horizontal edges: {inert}")

    start = time.perf_counter()
    root_j = int(root_curve.j_invariant())
    queue = deque([(root_curve, root_generator, [], 0)])
    seen = {root_j}
    candidates: list[dict[str, Any]] = [
        {
            "candidate_id": "p256-root",
            "curve": curve_record(root_curve, root_generator),
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
    ]

    while queue and len(candidates) < max_nodes:
        curve, generator, path, node_depth = queue.popleft()
        if node_depth >= depth:
            continue
        for ell in ells:
            for isogeny in curve.isogenies_prime_degree(ell):
                raw_codomain = isogeny.codomain()
                codomain, model_isomorphism = short_model_with_map(raw_codomain)
                next_generator = isogeny(generator)
                if model_isomorphism is not None:
                    next_generator = model_isomorphism(next_generator)
                next_j = int(codomain.j_invariant())
                if next_j in seen:
                    continue
                if next_generator.is_zero() or not (P256.n * next_generator).is_zero():
                    raise AssertionError("mapped generator failed its order check")

                step = {
                    "degree": int(isogeny.degree()),
                    "domain_j": str(int(curve.j_invariant())),
                    "codomain_j": str(next_j),
                    "map": {
                        "isogeny": map_record(isogeny),
                        "codomain_short_model_isomorphism": (
                            map_record(model_isomorphism)
                            if model_isomorphism is not None
                            else None
                        ),
                    },
                    "kernel_polynomial": str(isogeny.kernel_polynomial()),
                }
                next_path = [*path, step]
                seen.add(next_j)
                elapsed = time.perf_counter() - start
                candidates.append(
                    {
                        "candidate_id": candidate_id(next_j),
                        "curve": curve_record(codomain, next_generator),
                        "path": next_path,
                        "properties": {
                            "sage_version": str(SAGE_VERSION),
                            "explicit_path_verified": True,
                            "automorphism_order_geometric": 2,
                        },
                        "cost_accounting": {
                            "discovery_and_reusable_precomputation": {
                                "status": "measured",
                                "wall_seconds_to_discovery": elapsed,
                                "path_degree_product": str(
                                    math.prod(item["degree"] for item in next_path)
                                ),
                            },
                            "per_instance_mapping": {
                                "status": "formula retained; evaluation not timed",
                                "required_source_points": 2,
                            },
                        },
                    }
                )
                queue.append((codomain, next_generator, next_path, node_depth + 1))
                if len(candidates) >= max_nodes:
                    break
            if len(candidates) >= max_nodes:
                break

    return {
        "schema_version": 1,
        "description": "P-256 horizontal isogeny candidates with explicit paths",
        "search": {
            "algorithm": "breadth-first rational prime-degree isogenies",
            "ells": ells,
            "depth": depth,
            "max_nodes": max_nodes,
            "nodes_found": len(candidates),
            "elapsed_seconds": time.perf_counter() - start,
            "sage_version": str(SAGE_VERSION),
            "frobenius_discriminant": str(discriminant),
        },
        "candidates": candidates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ells", default="3,5,11,13")
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--max-nodes", type=int, default=25)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ells = [int(value) for value in args.ells.split(",") if value]
    payload = explore(ells, args.depth, args.max_nodes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
