#!/usr/bin/env python3
"""Count exact four-column affine-plane blocks from audited mask support."""

import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
N41 = ROOT / "n41_coupled_sixpair_full_ic_20261010" / "online_atoms.txt"
WIDTH = ROOT / "n131_w16_w18_sixpair_width_gate_20261010"
R41 = 549756390943
R131 = 680564733841876926932320129493409985129


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def n41_columns():
    lines = N41.read_text().splitlines()
    assert lines[0].split() == ["0", "0", str(R41), "6"]
    assert lines[1].split() == ["0", "64"]
    columns = {}
    for line in lines[2:66]:
        _, _, mask, _, column, _ = map(int, line.split())
        if mask in columns:
            assert columns[mask] == column
        else:
            columns[mask] = column
    assert len(columns) == 32
    return columns


def n131_columns(dimension):
    path = WIDTH / f"support_w{dimension}.tsv"
    columns = {}
    for line in path.read_text().splitlines():
        mask, column = map(int, line.split())
        assert mask not in columns
        columns[mask] = column
    return columns


def block_count(columns, offset):
    edges = []
    for mask, left in columns.items():
        partner = mask ^ offset
        if mask >= partner or partner not in columns:
            continue
        right = columns[partner]
        if left == right:
            continue
        edges.append(tuple(sorted((left, right))))
    e = len(edges)
    degrees = Counter(column for edge in edges for column in edge)
    parallels = Counter(edges)
    compatible = e*(e-1)//2
    compatible -= sum(degree*(degree-1)//2 for degree in degrees.values())
    compatible += sum(count*(count-1)//2 for count in parallels.values())
    assert 0 <= compatible <= e*(e-1)//2
    # Four choices of first-mask representative per compatible unordered
    # pair of offset edges, then 2^4 choices of source point signs.
    return {"offset_mask": offset, "offset_edges": e,
            "compatible_edge_pairs": compatible,
            "signed_four_atom_block_states": 64*compatible}


def main():
    protocol = json.loads((HERE / "support_protocol.json").read_text())
    for name, path in {"script": Path(__file__), "n41_atoms": N41,
                       "width_census": WIDTH / "result.json",
                       "w16_support": WIDTH / "support_w16.tsv",
                       "w18_support": WIDTH / "support_w18.tsv"}.items():
        assert protocol["source_sha256"][name] == digest(path), name
    width = json.loads((WIDTH / "result.json").read_text())
    width_rows = {item["degree"]: item for item in width["widths"]}
    cases = []
    for degree, columns, pair_states, order in (
        (6, n41_columns(), 1956, R41),
        (16, n131_columns(16), width_rows[16]["signed_pair_states_N"], R131),
        (18, n131_columns(18), width_rows[18]["signed_pair_states_N"], R131),
    ):
        offsets = [block_count(columns, offset) for offset in range(1, 64)]
        best = max(offsets, key=lambda value: (value["signed_four_atom_block_states"],
                                                -value["offset_mask"]))
        control_offset = 4 if degree == 6 else 10
        control = offsets[control_offset-1]
        for selection, item in (("archived_control_offset", control),
                                ("best_of_offsets_1_to_63", best)):
            block = item["signed_four_atom_block_states"]
            mean = Fraction(pair_states*pair_states*block*block, order)
            cases.append({"field_degree": 41 if degree == 6 else 131,
                          "source_dimension": degree, "selection": selection,
                          "actual_rational_masks": len(columns),
                          "free_signed_pair_states_N": pair_states,
                          "subgroup_order": str(order), **item,
                          "six_pair_labeled_tuple_ceiling": str(pair_states*pair_states*block*block),
                          "uniform_target_mean_ceiling": str(mean),
                          "uniform_target_mean_ceiling_decimal": format(float(mean), ".9g")})
    result = {"status": "PASS_EXACT_AFFINE_PLANE_BLOCK_SUPPORT",
              "candidate_id": None, "target_count": 0,
              "policy": "two free pair slots and two same-rotation four-atom blocks; each block uses four distinct source columns and one fixed mask offset c with q=p+c^2+s*c; cross-block column exclusions omitted for upper ceiling",
              "offset_search_set": list(range(1, 64)),
              "cases": cases,
              "source_sha256": {name: digest(path) for name, path in {
                  "script": Path(__file__), "protocol": HERE / "support_protocol.json",
                  "n41_atoms": N41, "width_census": WIDTH / "result.json",
                  "w16_support": WIDTH / "support_w16.tsv",
                  "w18_support": WIDTH / "support_w18.tsv"}.items()}}
    with (HERE / "support_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "cases": [{key: row[key] for key in (
                          "source_dimension", "selection", "offset_mask",
                          "signed_four_atom_block_states",
                          "uniform_target_mean_ceiling_decimal")}
                                for row in cases]}))


if __name__ == "__main__":
    main()
