#!/usr/bin/env python3
"""Measure extracted-equation rejection on unpinned N41 public residuals."""

import hashlib
import itertools
import json
import random
import time
from pathlib import Path

from produce import Curve, Field, pair_states

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coordinate_terms() -> list[tuple[int, ...]]:
    terms = [()]
    terms.extend((i,) for i in range(93))
    terms.extend(itertools.combinations(range(93), 2))
    terms.extend(term for term in itertools.combinations(range(93), 3) if term[0] < 12)
    return terms


def main() -> None:
    frozen = json.loads((HERE / "public_probe_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError(f"public probe input changed: {name}")
    if digest(Path(__file__)) != frozen["source_sha256"]:
        raise ValueError("public probe source changed after freeze")
    output = HERE / "public_residual_probe.json"
    if output.exists():
        raise FileExistsError("preserve first public-target probe")
    original = json.loads((HERE / "protocol.json").read_text())
    equations = json.loads((HERE / "equations.json").read_text())["equations"]
    terms = coordinate_terms()
    base = None
    for expected_seed, equation in enumerate(equations):
        stripped = []
        for feature in equation["support"]:
            term = terms[feature]
            if expected_seed not in term:
                raise ValueError("selected equation does not factor by its seed bit")
            coordinate = tuple(bit - 12 for bit in term if bit != expected_seed)
            if any(bit < 0 or bit >= 81 for bit in coordinate):
                raise ValueError("selected factor is not coordinate-only")
            stripped.append(coordinate)
        candidate = tuple(sorted(stripped))
        if base is None:
            base = candidate
        elif candidate != base:
            raise ValueError("selected equations do not share a coordinate factor")
    if base is None or len(base) != 24:
        raise ValueError("coordinate factor changed")

    geometry = json.loads(Path(original["inputs"]["geometry"]).read_text())["n41"]
    curve = Curve(Field(41, [0, 3]), 0)
    domains = [pair_states(curve, geometry["point_rows_by_unique_rotation"][str(r)])
               for r in frozen["prefix_rotations"]]
    target = tuple(original["public_target_q"])
    if not curve.on_curve(target) or curve.mul(original["subgroup_order"], target) is not None:
        raise ValueError("public point subgroup check changed")

    def coordinate_factor(point: tuple[int, int]) -> int:
        x, y = point
        if x & 1:
            raise ValueError("public residual outside trace-zero-x encoding")
        bits = [(x >> (i + 1)) & 1 for i in range(40)]
        bits.extend((y >> i) & 1 for i in range(41))
        return sum(all(bits[bit] for bit in term) for term in base) & 1

    start = time.monotonic_ns()
    rng = random.Random(frozen["random_seed"])
    seen = set()
    draws = overlap_rejects = checked = zero = nonzero = 0
    identity_prefixes = []
    while checked < frozen["residual_count"]:
        if draws >= frozen["max_draws"]:
            raise TimeoutError("public prefix draw cap before residual count")
        i, j = rng.randrange(1956), rng.randrange(1956)
        draws += 1
        if (i, j) in seen:
            continue
        seen.add((i, j))
        left, right = domains[0][i], domains[1][j]
        if left[2] & right[2]:
            overlap_rejects += 1
            continue
        prefix = curve.add(left[1], right[1])
        if prefix is None:
            raise ValueError("valid four-column prefix is identity")
        residual = curve.add(target, curve.neg(prefix))
        if residual is None:
            identity_prefixes.append([i, j])
            checked += 1
            continue
        if coordinate_factor(residual):
            nonzero += 1
        else:
            zero += 1
        checked += 1
    if identity_prefixes:
        status = "FOUR_POINT_PREFIX_EQUALS_PUBLIC_TARGET"
    else:
        status = "PUBLIC_RESIDUALS_EVALUATED"
    result = {"status": status, "proposal_id": original["proposal_id"],
              "candidate_id": None, "curve_id": original["curve_id"],
              "public_target_q": original["public_target_q"],
              "prefix_rotations": frozen["prefix_rotations"],
              "prefix_pair_domain_sizes": list(map(len, domains)),
              "draws": draws, "cross_column_rejects": overlap_rejects,
              "valid_prefix_residuals": checked,
              "nonidentity_coordinate_factor_zero": zero,
              "nonidentity_coordinate_factor_one": nonzero,
              "identity_prefix_indices": identity_prefixes,
              "selected_equation_count": len(equations),
              "selected_equation_support_sizes": [e["support_size"] for e in equations],
              "seed_assignment_rejections_on_zero_factor": 0,
              "coordinate_factor_terms": [list(term) for term in base],
              "source_sha256": digest(Path(__file__)),
              "protocol_sha256": digest(HERE / "public_probe_protocol.json"),
              "wall_ns": time.monotonic_ns() - start}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "checked": checked, "factor_zero": zero,
                      "factor_one": nonzero, "wall_s": result["wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
