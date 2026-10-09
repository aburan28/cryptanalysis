#!/usr/bin/env python3
"""Independently stream-check both lookup XCNFs and their local truth table."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_d13_first_link_branches_20261009"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def text_clause(values):
    return " ".join(str(value) for value in values) + " 0\n"


def verify_truth_table():
    for bit0 in (0, 1):
        for bit1 in (0, 1):
            for selected in (0, 1):
                for sign in (0, 1):
                    for output in (0, 1):
                        if bit0 == bit1:
                            clauses = [((not selected) or output == bit0)]
                        else:
                            clauses = [
                                ((not selected) or sign == 1 or output == bit0),
                                ((not selected) or sign == 0 or output == bit1),
                            ]
                        valid = all(clauses)
                        expected = (not selected) or output == (bit1 if sign else bit0)
                        if valid != expected:
                            raise ValueError("output-bit clause template is not equivalent")


def verify_formula(branch, table_rows, codes, expected):
    source = SOURCE / f"branch{branch}.xcnf"
    encoded = HERE / f"branch{branch}_lookup.xcnf"
    if (sha(source) != expected["source_formula_sha256"] or
            sha(encoded) != expected["lookup_formula_sha256"]):
        raise ValueError("source or lookup formula hash changed")
    selector_start = expected["source_variables"] + 1
    sign = selector_start + len(codes)
    if (selector_start != 115290 or sign != 119424 or
            expected["lookup_variables"] != sign):
        raise ValueError("new selector variable block changed")
    count = 0
    with source.open("rt", encoding="ascii") as src, encoded.open(
            "rt", encoding="ascii") as dst:
        old_header = src.readline().split()
        new_header = dst.readline().split()
        if (old_header != ["p", "cnf", "115289", "292712"] or
                new_header != ["p", "cnf", str(sign),
                               str(expected["lookup_records"])]):
            raise ValueError("XCNF header mismatch")
        for original in src:
            if dst.readline() != original:
                raise ValueError("lookup formula changed a source record")
        for index, ((code, mask0, mask1), expected_code) in enumerate(
                zip(table_rows, codes)):
            if code != expected_code:
                raise ValueError("lookup code order changed")
            selector = selector_start + index
            mismatch = []
            for bit in range(13):
                variable = 28 + bit
                truth = variable if (code >> bit) & 1 else -variable
                if dst.readline() != text_clause([-selector, truth]):
                    raise ValueError("selector implication changed")
                mismatch.append(-truth)
                count += 1
            if dst.readline() != text_clause([*mismatch, selector]):
                raise ValueError("selector converse changed")
            count += 1
            for bit in range(131):
                variable = 289 + bit
                value0 = (mask0 >> bit) & 1
                value1 = (mask1 >> bit) & 1
                literal0 = variable if value0 else -variable
                if value0 == value1:
                    if dst.readline() != text_clause([-selector, literal0]):
                        raise ValueError("constant output bit changed")
                    count += 1
                else:
                    literal1 = variable if value1 else -variable
                    if (dst.readline() != text_clause([-selector, sign, literal0]) or
                            dst.readline() != text_clause([-selector, -sign, literal1])):
                        raise ValueError("sign-dependent output bit changed")
                    count += 2
        if dst.readline():
            raise ValueError("unexpected lookup formula suffix")
    if count != expected["added_cnf_clauses"] or 292712 + count != expected["lookup_records"]:
        raise ValueError("clause count mismatch")
    return {"branch": branch, "verified_source_records": 292712,
            "verified_appended_clauses": count,
            "verified_selector_codes": len(codes),
            "lookup_formula_sha256": sha(encoded)}


def main():
    output = HERE / "encoding_audit.json"
    if output.exists():
        raise FileExistsError(output)
    preflight_path, table_path, audit_path = (HERE / name for name in
                                              ("preflight.json", "table.json", "audit.json"))
    preflight = json.loads(preflight_path.read_text())
    table = json.loads(table_path.read_text())
    table_audit = json.loads(audit_path.read_text())
    if (preflight["status"] != "FROZEN_ENCODING_AWAITING_INDEPENDENT_AUDIT" or
            preflight["source_sha256"]["table"] != sha(table_path) or
            preflight["source_sha256"]["table_audit"] != sha(audit_path) or
            table_audit["status"] != "PASS_EXACT_COMPLETE_TWO_ROOT_TABLES" or
            preflight["target_count"] != 1):
        raise ValueError("lookup inputs or table audit changed")
    verify_truth_table()
    if len(preflight["branches"]) != 2 or len(table["branches"]) != 2:
        raise ValueError("both exact roots are required")
    verified = [verify_formula(index, table["branches"][index]["rows"],
                               table["valid_codes"], preflight["branches"][index])
                for index in range(2)]
    receipt = {
        "kind": "n131_d13_exact_second_link_lookup_encoding_audit",
        "status": "PASS_EXACT_APPEND_ONLY_ENCODING",
        "proposal_id": preflight["proposal_id"],
        "candidate_id": None, "run_id": None,
        "target_count": 1, "branches": verified,
        "local_truth_table": "PASS_SELECTOR_AND_OUTPUT_EQUIVALENCE",
        "source_sha256": {"preflight": sha(preflight_path),
                          "table": sha(table_path), "table_audit": sha(audit_path),
                          "auditor": sha(Path(__file__))},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "clauses": [item["verified_appended_clauses"]
                                  for item in verified]}))


if __name__ == "__main__":
    main()
