#!/usr/bin/env sage -python
"""Evaluate the ordinary relation against all three saved public XCNFs."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n41_phi_second_link_control_20261009"
SUFFIX = GOAL / "n41_phi_suffix2_corrected_20261009"
TEMPLATE = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m16_static"
sys.path.insert(0, str(TEMPLATE))
import phi_frobenius_sat_gate_m16_sparse_seed_v1 as template


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def literal_value(literal, assignment):
    value = assignment[abs(literal)]
    if value is None:
        raise ValueError("unassigned saved-XCNF literal")
    return value if literal > 0 else not value


def check_xcnf(path, assignment):
    clauses = xors = 0
    with path.open("rt", encoding="ascii") as stream:
        header = stream.readline().split()
        if header[:2] != ["p", "cnf"] or int(header[2]) != len(assignment) - 1:
            raise ValueError("saved XCNF variable count differs from witness")
        for line in stream:
            if not line or line[0] == "c":
                continue
            if line[0] == "x":
                tokens = line[1:].split()
                if tokens[-1] != "0":
                    raise ValueError("unterminated native XOR")
                parity = False
                for value in tokens[:-1]:
                    parity ^= literal_value(int(value), assignment)
                if not parity:
                    raise ValueError("ordinary witness falsifies saved XOR")
                xors += 1
            else:
                tokens = line.split()
                if tokens[-1] != "0" or not any(
                        literal_value(int(value), assignment)
                        for value in tokens[:-1]):
                    raise ValueError("ordinary witness falsifies saved clause")
                clauses += 1
    if clauses + xors != int(header[3]):
        raise ValueError("saved XCNF record count differs from header")
    return {"variables": int(header[2]), "clauses": clauses,
            "xors": xors, "records": clauses + xors,
            "sha256": sha(path)}


def main():
    output = HERE / "xcnf_replay.json"
    if output.exists():
        raise FileExistsError(output)
    result = json.loads((HERE / "result.json").read_text())
    replay = json.loads((HERE / "replay.json").read_text())
    source = json.loads((BASE / "protocol.json").read_text())
    table = json.loads((BASE / "table.json").read_text())
    suffix = json.loads((SUFFIX / "suffix_masks.json").read_text())
    if (result["status"] != "VERIFIED_ORDINARY_RELATION" or
            replay["status"] != "PASS_ORDINARY_RELATION_AND_PUBLIC_XCNF" or
            source["source_sha256"]["source"] != sha(BASE / "source.xcnf") or
            source["source_sha256"]["lookup"] != sha(BASE / "lookup.xcnf") or
            json.loads((SUFFIX / "protocol.json").read_text())["source_sha256"]["guided"] !=
            sha(SUFFIX / "guided.xcnf")):
        raise ValueError("saved public formula sources changed")
    template.N, template.DIM, template.M = 41, 6, 12
    onb = template.field.Onb(41)
    basis = table["basis_coordinate_masks"]
    formula, primary, _roots, prog, node_lits, linear = template.build_formula(
        onb, basis, table["valid_codes"], [source["endpoint_phi_mask"]] * 4)
    codes = replay["leaf_codes"]
    partials = replay["partial_phi_masks"]
    pins = {f"leaf{position}": [(codes[position] >> bit) & 1
                                for bit in range(6)] for position in range(12)}
    pins.update({f"partial{position}": [(mask >> bit) & 1
                 for bit in range(41)] for position, mask in enumerate(partials)})
    pins["endpoint"] = [0, 0]
    base_assignment = template.evaluate_and_check(formula, primary, pins,
                                                   prog, node_lits, linear)
    if len(base_assignment) != 34335:
        raise ValueError("saved primary assignment width changed")
    source_check = check_xcnf(BASE / "source.xcnf", base_assignment)

    row = next(row for row in table["rows"] if row[0] == codes[2])
    if partials[1] not in row[1:]:
        raise ValueError("second-link root absent from frozen lookup")
    lookup_assignment = base_assignment + [False] * (len(table["rows"]) + 1)
    lookup_assignment[34335 + table["valid_codes"].index(codes[2])] = True
    lookup_assignment[-1] = partials[1] == row[2]
    lookup_check = check_xcnf(BASE / "lookup.xcnf", lookup_assignment)

    masks = suffix["masks"]
    if partials[8] not in masks:
        raise ValueError("partial8 absent from frozen target-conditioned suffix")
    guided_assignment = lookup_assignment + [False] * len(masks)
    guided_assignment[len(lookup_assignment) + masks.index(partials[8])] = True
    guided_check = check_xcnf(SUFFIX / "guided.xcnf", guided_assignment)

    receipt = {"kind": "n41_phi_ordinary_witness_saved_xcnf_replay",
               "status": "PASS_SOURCE_LOOKUP_AND_GUIDED_XCNF",
               "target_count": 1, "candidate_id": None, "run_id": None,
               "source": source_check, "lookup": lookup_check,
               "guided": guided_check,
               "second_link_root_choice": int(lookup_assignment[34365]),
               "suffix_selector_index": masks.index(partials[8]),
               "source_sha256": {"result": sha(HERE / "result.json"),
                                 "replay": sha(HERE / "replay.json"),
                                 "auditor": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "records": [source_check["records"],
                                  lookup_check["records"],
                                  guided_check["records"]]}))


if __name__ == "__main__":
    main()
