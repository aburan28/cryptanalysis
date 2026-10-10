#!/usr/bin/env python3
"""Emit the verified four-atom resultant monomials for the native kernel."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = HERE / "resultant_terms.json"
    data = json.loads(source.read_text())
    assert data["status"] == "PASS_UNIVERSAL_SAME_SEED_FOUR_ATOM_RESULTANT"
    terms = data["terms_s_p_q_z"]
    assert len(terms) == 150 and all(len(row) == 4 for row in terms)
    header = HERE / "resultant_terms.hpp"
    with header.open("x") as out:
        out.write("// Generated from resultant_terms.json; see terms_header_receipt.json.\n")
        out.write("#pragma once\n")
        out.write("#include <array>\n")
        out.write("#include <cstdint>\n")
        out.write("struct Term {uint8_t s,p,q,z;};\n")
        out.write("constexpr std::array<Term,150> TERMS{{\n")
        for row in terms:
            out.write("    {" + ",".join(map(str, row)) + "},\n")
        out.write("}};\n")
    receipt = {"status": "PASS_RESULTANT_TERM_HEADER",
               "term_count": len(terms),
               "source_sha256": {"script": sha(Path(__file__)),
                                 "terms": sha(source), "header": sha(header)}}
    with (HERE / "terms_header_receipt.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "header_sha256": sha(header)}))


if __name__ == "__main__":
    main()
