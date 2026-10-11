#!/usr/bin/env python3
"""Count field-call sites in the frozen direct-rho XYZZ materialization."""

from hashlib import sha256
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
WINDOW = "src/bin/eisenstein_fixed/unit_orbit_windows.rs"


def calls(source: str, name: str) -> int:
    return len(re.findall(r"\b" + re.escape(name) + r"\(", source))


def section(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    return source[begin:source.index(end, begin)]


def main() -> None:
    assert len(sys.argv) == 2, "usage: operation_model.py MATERIALIZED_DIRECTORY"
    path = Path(sys.argv[1]).resolve() / WINDOW
    raw = path.read_bytes()
    source = raw.decode()
    add = section(source, "    fn add_xyzz(self, q: Self) -> Self {",
                  "    // Apply the degree-three endomorphism")
    rho = section(source, "    fn rho_direct(self) -> Self {",
                  "    fn double(self) -> Self {")
    evaluator = section(source, "    let point = if direct_rho {",
                        "    (point, representative, nonidentity.saturating_sub(1),")
    direct, folded = evaluator.split("    } else {", 1)
    model = {
        "add_xyzz": {"mul": calls(add, "u256_mul"),
                     "square": calls(add, "u256_square")},
        "rho_direct": {"mul": calls(rho, "u256_mul"),
                       "square": calls(rho, "u256_square"),
                       "constant_solinas_mul": calls(rho, "u256_mul_const_solinas")},
        "direct_tail": {"add_xyzz": direct.count(".add_xyzz("),
                        "tau": direct.count(".tau()"),
                        "rho_direct": direct.count(".rho_direct()")},
        "folded_tail": {"add_xyzz": folded.count(".add_xyzz("),
                        "tau": folded.count(".tau()"),
                        "rho_direct": folded.count(".rho_direct()")},
    }
    assert model == {
        "add_xyzz": {"mul": 12, "square": 2},
        "rho_direct": {"mul": 9, "square": 5, "constant_solinas_mul": 2},
        "direct_tail": {"add_xyzz": 3, "tau": 2, "rho_direct": 1},
        "folded_tail": {"add_xyzz": 4, "tau": 2, "rho_direct": 0},
    }, model
    model["nominal_delta_direct_minus_folded"] = {
        "mul": -3, "square": 3, "constant_solinas_mul": 2}
    receipt = {"schema": 1, "status": "passed",
               "boundary": "nonidentity ordinary merge path; call sites, not timed operations",
               "generated_source_sha256": sha256(raw).hexdigest(),
               "model": model,
               "counter_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE / "operation-model.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(model, sort_keys=True))


if __name__ == "__main__":
    main()
