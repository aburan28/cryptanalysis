#!/usr/bin/env python3
"""Exact top-level field API calls in Q1413's enumerated base core."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_probe import HERE, sha

OUT = HERE / "runs/q1413_exact_base_api_call_vectors.json"
SOURCE = HERE / "enumerate_q1413_projected_x.py"
PROTOCOL = HERE / "q1413_projected_x_protocol.json"
GRID = ((83, 4), (83, 5), (131, 5), (131, 6))


def build():
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1413"
    assert protocol["source_sha256"] == sha(SOURCE)
    rows = []
    for n, weight in GRID:
        path = HERE / "runs" / f"n{n}_q1413_projected_x_w{weight}.json"
        base = json.loads(path.read_text())
        assert base["proposal_id"] == "Q1413"
        assert base["protocol_sha256"] == sha(PROTOCOL)
        assert base["source_sha256"] == sha(SOURCE)
        assert base["field_degree_n"] == n
        assert base["normal_basis_weight_bound"] == weight
        raw = sum(row["x_orbits"] for row in base["strata"])
        rational = sum(row["rational_x_orbits"] for row in base["strata"])
        identity = sum(row["identity_projection_orbits"]
                       for row in base["strata"])
        duplicates = sum(row["duplicate_projection_orbits"]
                         for row in base["strata"])
        nonidentity = rational - identity
        controls = sum(row["sampled_group_controls"]
                       for row in base["strata"])
        assert nonidentity - duplicates == base[
            "signed_frobenius_columns_K"]
        assert nonidentity >= 0 and controls <= 16 * weight
        rows.append({
            "field_degree_n": n,
            "normal_basis_weight_bound": weight,
            "raw_x_orbits_examined": raw,
            "rational_x_orbits": rational,
            "identity_projection_orbits": identity,
            "duplicate_projection_orbits": duplicates,
            "distinct_folded_columns_K": base[
                "signed_frobenius_columns_K"],
            "base_core_api_calls": {
                "field_inv": raw + nonidentity,
                "field_trace": 2 * raw,
                "field_sqr": rational + nonidentity,
                "field_add": rational + nonidentity,
                "onb_from_coords": raw,
                "orbit_cycle_bits": nonidentity,
                "canonical_rotation_steps": nonidentity * (n - 1),
                "distinct_key_hash_updates": base[
                    "signed_frobenius_columns_K"],
            },
            "sampled_group_controls_outside_core": controls,
            "enumeration_wall_seconds_including_controls_excluding_final_sort_digest": base[
                "enumeration_wall_seconds"],
            "peak_rss_raw": base["peak_rss_raw"],
            "peak_rss_units": base["peak_rss_units"],
            "base_receipt_sha256": sha(path),
        })
    return {
        "kind": "q1413_exact_projected_x_base_core_api_call_vectors",
        "proposal_id": "Q1413", "parent_base_proposal_id": "Q1303",
        "candidate_id": None, "isogeny": "none",
        "rows": rows,
        "accounting_boundary": (
            "Counts direct calls in projected_x, orbit conversion, and "
            "canonical rotation for each enumerated raw x orbit. They "
            "exclude internal arithmetic of field inverse, necklace "
            "generation, Python set lookup, sorting, serialized digest, "
            "and separately counted group controls. The recorded wall "
            "interval includes necklace generation and group controls "
            "but stops before final key sorting and digest serialization; "
            "it is exploratory on the unisolated host."),
        "is_complete_base_work_equivalent": False,
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
        "source_sha256": sha(Path(__file__)),
        "enumerator_source_sha256": sha(SOURCE),
        "protocol_sha256": sha(PROTOCOL),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(build(), indent=2) + "\n"
    if args.check:
        assert OUT.read_text() == content
    else:
        assert not OUT.exists()
        OUT.write_text(content)
    print(json.dumps({"status": "PASS", "full_n131_base_api_calls":
                      build()["rows"][-1]["base_core_api_calls"]}))


if __name__ == "__main__":
    main()
