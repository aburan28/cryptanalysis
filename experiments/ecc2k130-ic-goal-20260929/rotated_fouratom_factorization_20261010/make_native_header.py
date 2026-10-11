"""Generate constant quartic coefficients for the frozen N131 positive output."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "n131_positive.json"
data = json.loads(SOURCE.read_text())
assert data["status"] == "PASS_EXACT_SPECIALIZED_RESULTANT_FACTOR"
assert len(data["factors"]) == 2
assert all(item["bidegree"] == [4, 4] and item["term_count"] == 13
           for item in data["factors"])


def limbs(value):
    return [value & ((1 << 64) - 1), (value >> 64) & ((1 << 64) - 1), value >> 128]


def cpp_fe(value):
    return ",".join(f"{limb}ULL" for limb in limbs(value))


lines = ["// Generated from the frozen exact N131 positive-output factors.",
         "#pragma once", "#include <array>", "#include <cstdint>",
         "struct QuarticTerm {uint8_t p,q; Fe coefficient;};",
         f"static constexpr Fe FACTOR_OUTPUT_Z{{{cpp_fe(data['z'])}}};",
         "static const std::array<std::array<QuarticTerm,13>,2> QUARTIC_FACTORS{{"]
for factor in data["factors"]:
    lines.append("  std::array<QuarticTerm,13>{{")
    for p, q, coefficient in factor["terms"]:
        lines.append(f"    QuarticTerm{{{p},{q},Fe{{{cpp_fe(coefficient)}}}}},")
    lines.append("  }},")
lines.append("}};")
with (HERE / "factor_terms.hpp").open("x") as output:
    output.write("\n".join(lines) + "\n")
receipt = {"status": "PASS_FROZEN_FACTOR_HEADER",
           "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
           "header_sha256": hashlib.sha256((HERE / "factor_terms.hpp").read_bytes()).hexdigest(),
           "factor_term_counts": [len(item["terms"]) for item in data["factors"]]}
with (HERE / "header_result.json").open("x") as output:
    json.dump(receipt, output, sort_keys=True, indent=2)
    output.write("\n")
