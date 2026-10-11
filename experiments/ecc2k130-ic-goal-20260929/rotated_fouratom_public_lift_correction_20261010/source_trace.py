"""Exact trace-basis and public-lift character gate for W6 and W15."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def traces(n, width):
    modulus = ((1 << 41) | (1 << 3) | 1) if n == 41 else \
              ((1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1)

    def mul(a, b):
        result = 0
        while b:
            if b & 1:
                result ^= a
            b >>= 1
            a <<= 1
            if a & (1 << n):
                a ^= modulus
        return result

    def trace(a):
        result = 0
        for _ in range(n):
            result ^= a
            a = mul(a, a)
        assert result in (0, 1)
        return result

    basis = [trace(1 << bit) for bit in range(1, width + 1)]
    assert basis == [0] * width
    return basis, trace


def main():
    protocol = json.loads((HERE / "source_trace_protocol.json").read_text())
    for name, (path, digest) in protocol["source_sha256"].items():
        assert sha(Path(path)) == digest, name
    corrected = json.loads((HERE / "result.json").read_text())
    screen = json.loads((ROOT / "n41_n131_diagonal_atom_20261010" / "screen.json").read_text())
    archived_trace = json.loads((ROOT / "n131_w15_middle_trace_public_gate_20261010" /
                                 "trace_proof.json").read_text())
    assert archived_trace["polynomial_basis_trace_support"] == [0, 129]
    rows = {}
    for label, n, width in (("n41", 41, 6), ("n131", 131, 15)):
        basis, trace = traces(n, width)
        case = corrected[label]
        assert [item["index"] for item in case["preimages"] if item["trace_z_h"] == 0] == [0, 1]
        assert [item["index"] for item in case["preimages"] if item["trace_z_h"] == 1] == [2, 3]
        if n == 41:
            assert len(screen["raw_audit"]) == 32
            assert all(item["w"] == item["mask"] << 1 and trace(item["w"]) == 0
                       for item in screen["raw_audit"])
            support_count = len(screen["raw_audit"])
        else:
            census = json.loads((ROOT / "n131_w15_cofactor_class_gate_20261010" /
                                 "census.json").read_text())
            assert census["rational_support_masks"] == 16441
            support_count = census["rational_support_masks"]
        rows[label] = {"field_degree": n, "subspace_width": width,
                       "basis_traces": basis, "raw_rational_source_masks": support_count,
                       "admissible_public_raw_lift_indices_by_trace": [0, 1],
                       "excluded_public_raw_lift_indices_by_trace": [2, 3]}
    result = {"status": "PASS_W6_W15_TWO_DESCENT_TARGET_LIFT_GATE",
              "protocol_sha256": sha(HERE / "source_trace_protocol.json"),
              "cases": rows,
              "proof_rule": "Tr(x(P+Q))=Tr(x(P))+Tr(x(Q)) from x(P+Q)=lambda^2+lambda+x(P)+x(Q); rational P with x != 0 has Tr(x)=Tr(1/x); every source atom has x=1/w and Tr(w)=0"}
    with (HERE / "source_trace_result.json").open("x") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps({"status": result["status"],
                      "admissible_lifts": {label: row["admissible_public_raw_lift_indices_by_trace"]
                                           for label, row in rows.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
