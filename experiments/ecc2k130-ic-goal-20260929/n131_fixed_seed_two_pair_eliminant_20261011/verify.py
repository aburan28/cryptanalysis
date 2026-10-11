"""Independent field-arithmetic audit of the fixed-seed pair eliminant."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n131_fixed_seed_eight_pair_circuit_20261010"
FIELD = ROOT / "n131_fixed_seed_halftrace_cubic_20261011" / "verify.py"
spec = importlib.util.spec_from_file_location("independent_n131_field", FIELD)
field = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parameters(item):
    seed = field.coordinate(212)
    t = field.frobenius(field.square(field.halftrace(seed)), item["rotation"])
    p = field.frobenius(field.mul(field.coordinate(item["masks"][0]),
                                    field.coordinate(item["masks"][1])),
                        item["rotation"])
    return 1 ^ t, p, t


def independent_eliminant(left, right, c):
    mul, square = field.mul, field.square
    k, p, t = left
    ell, q, u = right
    alpha = mul(p, field.inverse(k))
    beta = mul(t, field.inverse(k))
    gamma = mul(q, field.inverse(ell))
    delta = mul(u, field.inverse(ell))
    c2 = square(c)
    A = mul(c2, mul(alpha, gamma)) ^ c
    B = alpha ^ mul(c2, mul(alpha, delta))
    C = gamma ^ mul(c2, mul(beta, gamma))
    D = c2 ^ beta ^ delta ^ mul(c2, mul(beta, delta))
    U = mul(ell, square(B)) ^ mul(q, mul(B, A)) ^ mul(u, square(A))
    V = mul(q, mul(B, C) ^ mul(D, A))
    W = mul(ell, square(D)) ^ mul(q, mul(D, C)) ^ mul(u, square(C))
    R, S = mul(U, alpha) ^ V, mul(U, beta) ^ W
    return mul(k, square(S)) ^ mul(p, mul(S, R)) ^ mul(t, square(R))


def s3(a, b, c):
    mul, square = field.mul, field.square
    product = mul(mul(a, b), c)
    return square(product) ^ product ^ square(a ^ b ^ c)


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    selected = json.loads((OLD / "derive_result.json").read_text())["selected"]
    chain = json.loads((OLD / "planted_chain_result.json").read_text())
    assert protocol["source_sha256"]["runner"] == sha(HERE / "run.py")
    assert protocol["source_sha256"]["derive"] == sha(OLD / "derive_result.json")
    assert protocol["source_sha256"]["chain"] == sha(OLD / "planted_chain_result.json")
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["status"] == "PASS_EXACT_N131_TWO_PAIR_ELIMINANT"
    assert result["circuit_gate"]["and_gates"] == 50780
    assert result["circuit_gate"]["assignment_check"] == {
        "clauses": 152471, "native_xor_rows": 23592}
    tested = rejected = 0
    for block, item in enumerate(result["cases"]):
        i = 2 * block
        left, right = parameters(selected[i]), parameters(selected[i + 1])
        a, b = (field.standard_reciprocal(chain["pair_rotated_z"][index])
                for index in (i, i + 1))
        assert field.mul(left[0], field.square(a)) ^ field.mul(left[1], a) ^ left[2] == 0
        assert field.mul(right[0], field.square(b)) ^ field.mul(right[1], b) ^ right[2] == 0
        a2 = a ^ field.mul(left[1], field.inverse(left[0]))
        b2 = b ^ field.mul(right[1], field.inverse(right[0]))
        c = item["positive_output"]
        assert c == protocol["positive_block_outputs"][block]
        assert s3(a, b, c) == independent_eliminant(left, right, c) == 0
        for bit in range(1, 33):
            value = c ^ (1 << bit)
            equation = independent_eliminant(left, right, value) == 0
            roots = any(s3(x, y, value) == 0
                        for x in (a, a2) for y in (b, b2))
            assert equation == roots
            tested += 1
            rejected += not equation
    assert tested == rejected == result["negative_controls"] == 128
    audit = {"status": "PASS_INDEPENDENT_N131_TWO_PAIR_ELIMINANT_AUDIT",
             "curve_id": protocol["curve_id"], "positive_blocks": len(result["cases"]),
             "negative_controls_checked": tested,
             "negative_controls_rejected": rejected,
             "gate_assignment_rows": sum(result["circuit_gate"]["assignment_check"].values()),
             "source_sha256": {"script": sha(__file__),
                               "independent_field": sha(FIELD),
                               "protocol": sha(HERE / "protocol.json"),
                               "result": sha(HERE / "result.json")}}
    with (HERE / "audit_result.json").open("x") as stream:
        json.dump(audit, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
