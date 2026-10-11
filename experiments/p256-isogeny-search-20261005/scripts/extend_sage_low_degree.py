#!/usr/bin/env sage -python
"""Resume a frozen low-degree Sage traversal and retain only new curves."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any

try:
    from sage.all import EllipticCurve, GF
    from sage.env import SAGE_VERSION
except ImportError as exc:  # pragma: no cover - executed only outside Sage
    raise SystemExit("This program must run under `sage -python`.") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from explore_sage import (  # noqa: E402
    P256,
    candidate_id,
    curve_record,
    map_record,
    short_model_with_map,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--ells", default="3,5,11,13")
    parser.add_argument("--target-depth", type=int, required=True)
    parser.add_argument("--max-new-nodes", type=int, default=1000)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ells = [int(value) for value in args.ells.split(",") if value]
    prior = json.loads(args.input.read_text(encoding="utf-8"))
    prior_candidates = prior["candidates"]
    if not prior_candidates or prior_candidates[0]["candidate_id"] != "p256-root":
        raise ValueError("input registry must begin with p256-root")
    prior_depth = max(len(row["path"]) for row in prior_candidates)
    if args.target_depth <= prior_depth:
        raise ValueError("target depth must exceed the input registry depth")

    field = GF(P256.p)
    seen = {int(row["curve"]["j_invariant"]) for row in prior_candidates}
    if len(seen) != len(prior_candidates):
        raise ValueError("input registry contains duplicate j-invariants")

    queue = deque()
    for row in prior_candidates:
        if len(row["path"]) != prior_depth:
            continue
        record = row["curve"]
        curve = EllipticCurve(field, [int(record["a"]), int(record["b"])])
        generator = curve(int(record["generator"]["x"]), int(record["generator"]["y"]))
        if int(curve.j_invariant()) != int(record["j_invariant"]):
            raise AssertionError("reconstructed frontier curve has the wrong j-invariant")
        if generator.is_zero() or not (P256.n * generator).is_zero():
            raise AssertionError("reconstructed frontier generator failed its order check")
        queue.append((curve, generator, row["path"], prior_depth))

    start = time.perf_counter()
    new_candidates: list[dict[str, Any]] = []
    while queue and len(new_candidates) < args.max_new_nodes:
        curve, generator, path, node_depth = queue.popleft()
        if node_depth >= args.target_depth:
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
                new_candidates.append(
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
                                "status": "measured extension from frozen frontier",
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
                if len(new_candidates) >= args.max_new_nodes:
                    break
            if len(new_candidates) >= args.max_new_nodes:
                break

    depth_counts = Counter(len(row["path"]) for row in new_candidates)
    payload = {
        "schema_version": 1,
        "description": (
            "New P-256 horizontal isogeny candidates from a resumed "
            "low-degree breadth-first traversal"
        ),
        "search": {
            "algorithm": "resumed breadth-first rational prime-degree isogenies",
            "ells": ells,
            "input": {
                "path": str(args.input),
                "sha256": sha256(args.input),
                "curves_including_p256": len(prior_candidates),
                "maximum_depth": prior_depth,
            },
            "target_depth": args.target_depth,
            "max_new_nodes": args.max_new_nodes,
            "new_nodes_found": len(new_candidates),
            "new_depth_counts": {
                str(depth): count for depth, count in sorted(depth_counts.items())
            },
            "combined_unique_j_invariants": len(seen),
            "elapsed_seconds": time.perf_counter() - start,
            "sage_version": str(SAGE_VERSION),
        },
        "candidates": [prior_candidates[0], *new_candidates],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "new_nodes_found": len(new_candidates),
                "new_depth_counts": payload["search"]["new_depth_counts"],
                "combined_unique_j_invariants": len(seen),
                "elapsed_seconds": payload["search"]["elapsed_seconds"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
