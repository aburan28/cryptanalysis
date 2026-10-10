#!/usr/bin/env python3
"""Bind the quotient result to frozen sources and older native controls."""

import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
parent = here.parent / "n131_w14_coupled_fouratom_inverse_20261010"
protocol = json.loads((here / "protocol.json").read_text())
result = json.loads((here / "result.json").read_text())
sources = {
    "run.py": here / "run.py",
    "resultant_terms.json": parent / "resultant_terms.json",
    "inputs.json": parent / "inputs.json",
}
assert protocol["source_sha256"] == {
    name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sources.items()
}
assert result["source_sha256"] == protocol["source_sha256"]
assert result["status"] == "PASS_EXACT_SYMMETRIC_QUOTIENT"
assert result["exact_polynomial_identity"]
assert result["original_terms"] == 150 and result["quotient_terms"] == 87
for n, d in [(41, 6), (131, 14)]:
    panel = result["panels"][str(n)]
    assert panel["product_space_size"] == 1 << (d - 1)
    for item in panel["selected_conditional_images"]:
        assert item["image_size"] == 1 << (d - 1 if item["P"] == 0 else d - 2)
    if n == 41:
        assert panel["controls"]["positive_z"]["ordered_algebraic_hits"] == 2
        assert panel["controls"]["positive_z"]["quotient_algebraic_hits"] == 1
        assert panel["controls"]["trace_zero_control_z"]["ordered_algebraic_hits"] == 0
    else:
        assert panel["controls"]["positive_z"]["constructed_pair_vanishes"]
        assert not panel["controls"]["trace_zero_control_z"]["constructed_pair_vanishes"]
for n in (41, 131):
    for case, key in [("positive", "positive_z"),
                      ("trace_zero_control", "trace_zero_control_z")]:
        native = json.loads((parent / f"native_run_n{n}_{case}" / "result.json").read_text())
        assert native["status"] == "COMPLETE_ALGEBRAIC_SCAN"
        if n == 41:
            assert len(native["hits"]) == result["panels"]["41"]["controls"][key]["ordered_algebraic_hits"]
        elif case == "positive":
            assert len(native["hits"]) == 2
        else:
            assert len(native["hits"]) == 0
audit = {"status": "PASS_INDEPENDENT_RECEIPT_AUDIT",
         "protocol_sha256": hashlib.sha256((here / "protocol.json").read_bytes()).hexdigest(),
         "result_sha256": hashlib.sha256((here / "result.json").read_bytes()).hexdigest(),
         "checked_native_controls": 4}
(here / "audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True)+"\n")
print(json.dumps(audit, sort_keys=True))
