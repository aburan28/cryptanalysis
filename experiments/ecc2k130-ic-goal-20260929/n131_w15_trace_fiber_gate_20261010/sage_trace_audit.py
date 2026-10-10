#!/usr/bin/env sage -python
"""Independent Sage arithmetic audit of the exact W15 trace fiber."""

import hashlib
import importlib.util
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w15_onepair_fixed_sat_gate_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    spec = importlib.util.spec_from_file_location("trace_audit_prior", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    prior = load(PRIOR / "fivepair_run.py")
    inp = json.loads((PRIOR / "fivepair_input.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    assert control["status"] == "PASS_FULL_TRACE_FIBER_XCNF_CONTROL"
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, name="t", modulus=t**131 + t**13 + t**2 + t + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return sum((field.gen()**bit for bit in range(131) if value >> bit & 1),
                   field.zero())

    def point(values):
        return curve(decode(values[0]), decode(values[1]))

    basis_traces = [int(decode(1 << bit).trace()) for bit in range(1, 16)]
    assert basis_traces == [0] * 15
    _, _, old_curve, _, _ = prior.experiment.run.source()
    raw = prior.experiment.run.prior.prior.old.target_preimages(
        old_curve, tuple(inp["residual_target_q"]))
    q = point(inp["residual_target_q"])
    traces = []
    reciprocals = []
    for values in raw:
        preimage = point(values)
        assert 4 * preimage == q
        reciprocal = 1 / preimage[0]
        traces.append(int(reciprocal.trace()))
        reciprocals.append(sum(int(bit) << index for index, bit in
                               enumerate(reciprocal.polynomial().list())))
    assert traces == protocol["raw_target_reciprocal_traces"] == [0, 1, 0, 1]
    assert reciprocals == protocol["raw_target_reciprocals"]
    assert protocol["admissible_target_preimage_indices"] == [0, 2]
    assert inp["residual_target_preimage_index"] == 2
    assert point(raw[2]) == point(inp["residual_raw"])
    assert q + 4 * point(inp["first_pair_raw"]) == point(inp["original_target_q"])
    middle_traces = [int(decode(value).trace()) for value in
                     inp["remaining_middle_reciprocals"]]
    assert middle_traces == [0] * 8
    result = {
        "status": "PASS_INDEPENDENT_SAGE_TRACE_FIBER_AUDIT",
        "curve_id": protocol["curve_id"],
        "source_basis_traces": basis_traces,
        "residual_raw_preimage_reciprocal_traces": traces,
        "constructed_middle_reciprocal_traces": middle_traces,
        "admissible_target_preimage_indices": [0, 2],
        "checked_target_preimages": len(raw),
        "source_sha256": {"script": sha(__file__),
                          "protocol": sha(HERE / "protocol.json"),
                          "control": sha(HERE / "control_result.json"),
                          "prior_input": sha(PRIOR / "fivepair_input.json"),
                          "prior_runner": sha(PRIOR / "fivepair_run.py"),
                          "runtime": sha(HERE / "sage_runtime_info.json")},
    }
    with (HERE / "sage_trace_audit.json").open("x") as sink:
        json.dump(result, sink, indent=2, sort_keys=True)
        sink.write("\n")
    print(json.dumps({"status": result["status"], "traces": traces}))


if __name__ == "__main__":
    main()
