#!/usr/bin/env python3
"""Freeze the N83 power-basis Karatsuba comparison on the public workload."""

import json
from pathlib import Path

from karatsuba import HERE, PARENT, runner


def main():
    path = HERE / "protocol.json"
    assert not path.exists()
    parent_path = PARENT / "protocol.json"
    parent_result_path = PARENT / "width16_ordinary.json"
    parent = json.loads(parent_path.read_text())
    assert parent["proposal_id"] == "Q2026101250"
    assert json.loads(parent_result_path.read_text())["status"] == "bounded_unknown"
    assert json.loads((HERE / "karatsuba_control.json").read_text())["status"] == "PASS"
    sources = [HERE / name for name in
               ("shape.py", "karatsuba.py", "control.py", "ordinary.py")]
    assert all(source.is_file() for source in sources)
    protocol = {**parent}
    protocol["kind"] = "n83_shifted_width16_power_basis_karatsuba_five_summand_protocol"
    protocol["proposal_id"] = "Q2026101253"
    protocol["comparison_variable"] = (
        "change field multiplication in four S3 links from direct normal-basis "
        "bilinear expansion to exact power-basis Karatsuba; base, target and "
        "resource limits fixed")
    protocol["method_comparison_parent"] = "Q2026101250 fixed-target width-16 direct normal-basis formula"
    protocol["field_multiplier"] = {
        "basis": "powers 0..82 of gamma_1, inverted against the type-II ONB",
        "convolution": "recursive characteristic-two Karatsuba over 83 coefficients",
        "reduction": "monomial powers 0..164 mapped into the same power basis",
        "s3_encoding": "three products per link, power-basis squaring linear map",
    }
    protocol["fixedtarget_protocol_sha256"] = runner.sha(parent_path)
    protocol["fixedtarget_result_sha256"] = runner.sha(parent_result_path)
    protocol["control_receipt_sha256"] = runner.sha(HERE / "karatsuba_control.json")
    protocol["source_sha256"] = {
        **parent["source_sha256"],
        **{str(source.relative_to(runner.ROOT)): runner.sha(source)
           for source in sources},
    }
    runner.save(path, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "workload_id": protocol["workload_id"],
                      "B": protocol["base_rows"][0]["B"],
                      "K": protocol["base_rows"][0]["K"]}), flush=True)


if __name__ == "__main__":
    main()
