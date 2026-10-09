#!/usr/bin/env python3
"""Add exact second-link lookup propagation to both frozen public-Q branches."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n131_d13_first_link_branches_20261009"
MAPPING = GOAL / "n131_d13_public_bridge_projection_20261009/budget1/variable_map.json"
BASE_VARS = 115289
BASE_CLAUSES = 292712
LEAF2 = list(range(28, 41))
PARTIAL1 = list(range(289, 420))


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def clause(stream, *literals):
    stream.write(" ".join(str(literal) for literal in literals) + " 0\n")


def popcount(value):
    return bin(value).count("1")


def main():
    preflight_path = HERE / "preflight.json"
    if preflight_path.exists():
        raise FileExistsError(preflight_path)
    table_path, audit_path, protocol_path = (HERE / name for name in
                                             ("table.json", "audit.json", "protocol.json"))
    table = json.loads(table_path.read_text())
    audit = json.loads(audit_path.read_text())
    protocol = json.loads(protocol_path.read_text())
    if (audit["status"] != "PASS_EXACT_COMPLETE_TWO_ROOT_TABLES" or
            audit["source_sha256"]["table"] != sha(table_path) or
            table["source_sha256"]["protocol"] != sha(protocol_path) or
            protocol["target_count"] != 1 or
            len(table["valid_codes"]) != 4134):
        raise ValueError("exact table audit or one-target protocol changed")
    mapping = json.loads(MAPPING.read_text())
    if mapping["new_to_old"][:420] != list(range(420)):
        raise ValueError("third leaf or second partial primary variables moved")
    if len(table["branches"]) != 2:
        raise ValueError("both first-link roots are required")

    rows = []
    for branch, entry in enumerate(table["branches"]):
        source_path = SOURCE / f"branch{branch}.xcnf"
        destination = HERE / f"branch{branch}_lookup.xcnf"
        if destination.exists():
            raise FileExistsError(destination)
        if (entry["branch"] != branch or entry["exceptional"] or
                [row[0] for row in entry["rows"]] != table["valid_codes"]):
            raise ValueError("branch table is incomplete or reordered")
        selector_start = BASE_VARS + 1
        sign_variable = selector_start + len(table["valid_codes"])
        lookup_clauses = sum(14 + 131 + popcount(mask0 ^ mask1)
                             for _, mask0, mask1 in entry["rows"])
        with source_path.open("rt", encoding="ascii") as src, destination.open(
                "x", encoding="ascii") as dst:
            header = src.readline().split()
            if header != ["p", "cnf", str(BASE_VARS), str(BASE_CLAUSES)]:
                raise ValueError("frozen branch XCNF dimensions changed")
            dst.write(f"p cnf {sign_variable} {BASE_CLAUSES + lookup_clauses}\n")
            for line in src:
                dst.write(line)
            emitted = 0
            for index, (code, mask0, mask1) in enumerate(entry["rows"]):
                selector = selector_start + index
                match_lits = []
                for bit, variable in enumerate(LEAF2):
                    truth_lit = variable if (code >> bit) & 1 else -variable
                    clause(dst, -selector, truth_lit)
                    match_lits.append(-truth_lit)
                    emitted += 1
                clause(dst, *match_lits, selector)
                emitted += 1
                for bit, output_variable in enumerate(PARTIAL1):
                    bit0 = (mask0 >> bit) & 1
                    bit1 = (mask1 >> bit) & 1
                    output0 = output_variable if bit0 else -output_variable
                    if bit0 == bit1:
                        clause(dst, -selector, output0)
                        emitted += 1
                    else:
                        output1 = output_variable if bit1 else -output_variable
                        clause(dst, -selector, sign_variable, output0)
                        clause(dst, -selector, -sign_variable, output1)
                        emitted += 2
            if emitted != lookup_clauses:
                raise ValueError("lookup clause count mismatch")
        rows.append({
            "branch": branch, "source_formula_sha256": sha(source_path),
            "lookup_formula_sha256": sha(destination),
            "lookup_formula_bytes": destination.stat().st_size,
            "source_variables": BASE_VARS, "source_records": BASE_CLAUSES,
            "lookup_variables": sign_variable,
            "added_selector_variables": len(table["valid_codes"]),
            "added_sign_variables": 1, "added_cnf_clauses": lookup_clauses,
            "lookup_records": BASE_CLAUSES + lookup_clauses,
        })
    preflight = {
        "kind": "n131_d13_exact_second_link_lookup_encoding_preflight",
        "status": "FROZEN_ENCODING_AWAITING_INDEPENDENT_AUDIT",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "target_count": 1, "branches": rows,
        "semantics": "selector iff 13-bit third-leaf code; one unconstrained root-choice bit; selected code and bit determine all 131 second-partial bits",
        "source_sha256": {"table": sha(table_path), "table_audit": sha(audit_path),
                          "protocol": sha(protocol_path), "mapping": sha(MAPPING),
                          "encoder": sha(Path(__file__))},
    }
    preflight_path.write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": preflight["status"],
                      "added_clauses": [row["added_cnf_clauses"] for row in rows]}))


if __name__ == "__main__":
    main()
