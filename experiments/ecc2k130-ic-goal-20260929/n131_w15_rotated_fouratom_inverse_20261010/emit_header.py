"""Emit the exact 266-term rotated resultant as a native constexpr table."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = HERE / "resultant.json"
data = json.loads(source.read_text())
assert data["status"] == "PASS_UNIVERSAL_ROTATED_FOUR_ATOM_RESULTANT"
terms = data["terms"]
assert len(terms) == data["term_count"] == 266
header = HERE / "rotated_terms.hpp"
with header.open("x") as output:
    output.write("// Generated from resultant.json by emit_header.py.\n")
    output.write("#pragma once\n#include <array>\n#include <cstdint>\n")
    output.write("struct Term {uint8_t a,b,p,q,z;};\n")
    output.write("constexpr std::array<Term,266> TERMS{{\n")
    for row in terms:
        output.write("    {" + ",".join(map(str,row)) + "},\n")
    output.write("}};\n")
record = {"status": "PASS_ROTATED_RESULTANT_HEADER",
          "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for name,path in {"emit_header.py": Path(__file__),
                                              "resultant.json": source,
                                              "rotated_terms.hpp": header}.items()}}
with (HERE / "header_receipt.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
