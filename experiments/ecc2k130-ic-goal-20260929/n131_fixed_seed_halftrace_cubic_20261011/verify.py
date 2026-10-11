"""Independent field/group and artifact audit of the N131 halftrace circuit."""

import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
SUPPORT = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010" / "support_w18.tsv"
N = 131
MODULUS = (1 << N) | (1 << 13) | (1 << 2) | (1 << 1) | 1
SEED = 212
ROTATIONS = [0, 16, 32, 48, 64, 80, 96, 112]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mul(a, b):
    result = 0
    while b:
        low = b & -b
        result ^= a << (low.bit_length() - 1)
        b ^= low
    for degree in range(result.bit_length() - 1, N - 1, -1):
        if result >> degree & 1:
            result ^= MODULUS << (degree - N)
    return result


def square(a):
    expanded = 0
    while a:
        low = a & -a
        expanded ^= 1 << (2 * (low.bit_length() - 1))
        a ^= low
    for degree in range(expanded.bit_length() - 1, N - 1, -1):
        if expanded >> degree & 1:
            expanded ^= MODULUS << (degree - N)
    return expanded


def inverse(value):
    assert value
    result, base, exponent = 1, value, (1 << N) - 2
    while exponent:
        if exponent & 1:
            result = mul(result, base)
        base = square(base)
        exponent >>= 1
    assert mul(value, result) == 1
    return result


def trace(value):
    result = 0
    for _ in range(N):
        result ^= value
        value = square(value)
    assert result in (0, 1)
    return result


def halftrace(value):
    assert trace(value) == 0
    original = value
    result = 0
    for _ in range((N + 1) // 2):
        result ^= value
        value = square(square(value))
    assert square(result) ^ result == original
    return result


def coordinate(mask):
    return sum(1 << (bit + 1) for bit in range(18) if mask >> bit & 1)


def standard_reciprocal(z):
    assert z not in (0, 1)
    return mul(z, inverse(z ^ 1))


def frobenius(value, exponent):
    for _ in range(exponent):
        value = square(value)
    return value


def point_add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2:
        if y1 ^ y2 == x1:
            return None
        assert left == right and x1
        slope = x1 ^ mul(y1, inverse(x1))
        x3 = square(slope) ^ slope
        y3 = square(x1) ^ mul(slope ^ 1, x3)
    else:
        slope = mul(y1 ^ y2, inverse(x1 ^ x2))
        x3 = square(slope) ^ slope ^ x1 ^ x2
        y3 = mul(slope, x1 ^ x3) ^ x3 ^ y1
    return x3, y3


def point_options(mask):
    w = coordinate(mask)
    u = halftrace(w)
    assert u and square(u) ^ u == w
    x = 1 ^ inverse(u)
    assert x
    rhs = x ^ mul(inverse(x), inverse(x))
    lam = halftrace(rhs)
    y = mul(x, lam)
    assert square(y) ^ mul(x, y) == mul(square(x), x) ^ 1
    return [(x, y), (x, y ^ x)]


def scan_formula(path, expected):
    clauses = xor_rows = 0
    with path.open("rb") as stream:
        header = stream.readline().split()
        assert header[:2] == [b"p", b"cnf"]
        assert int(header[2]) == expected["variables"]
        for line in stream:
            if line.startswith(b"x"):
                xor_rows += 1
            else:
                clauses += 1
    assert clauses == expected["clauses"]
    assert xor_rows == expected["native_xor_rows"]
    assert clauses + xor_rows == int(header[3])
    assert path.stat().st_size == expected["xcnf_bytes"]
    assert sha(path) == expected["xcnf_sha256"]
    return clauses, xor_rows


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    query = json.loads((HERE / "query_result.json").read_text())
    derive = json.loads((OLD / "derive_result.json").read_text())
    chain = json.loads((OLD / "planted_chain_result.json").read_text())
    target = json.loads((OLD / "target_preimages.json").read_text())
    assert protocol["source_sha256"]["runner"] == sha(HERE / "run.py")
    assert protocol["source_sha256"]["support"] == sha(SUPPORT)
    assert protocol["source_sha256"]["derive"] == sha(OLD / "derive_result.json")
    assert protocol["source_sha256"]["chain"] == sha(OLD / "planted_chain_result.json")
    assert protocol["source_sha256"]["target"] == sha(OLD / "target_preimages.json")
    assert control["protocol_sha256"] == query["protocol_sha256"] == sha(HERE / "protocol.json")
    assert query["public_target"] == target["public_target"]
    assert query["workload_id"] == target["workload_id"]
    assert query["raw_preimage_index"] == 0
    assert query["formula"]["variables"] < control["formula"]["variables"]
    control_counts = scan_formula(HERE / "control.xcnf", control["formula"])
    query_counts = scan_formula(HERE / "ordinary.xcnf", query["formula"])
    assert sha(HERE / "solver.stdout.txt") == query["stdout_sha256"]
    assert sha(HERE / "solver.stderr.txt") == query["stderr_sha256"]
    with (HERE / "solver.stdout.txt").open() as stream:
        restart_rows = bracket_rows = 0
        for line in stream:
            restart_rows += line.startswith("c rst ")
            bracket_rows += line.startswith("c [")
    # The frozen runner's restart_rows field counts bracketed diagnostics.
    assert query["restart_rows"] == bracket_rows
    assert restart_rows > 0

    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    selected = derive["selected"]
    assert len(selected) == 8 and derive["seed_mask"] == SEED
    assert [item["rotation"] for item in selected] == ROTATIONS
    seed_h2 = square(halftrace(coordinate(SEED)))
    occupied = set()
    signed_pair_options = []
    for slot, item in enumerate(selected):
        left, right = item["masks"]
        assert left ^ right == SEED and left in columns and right in columns
        assert columns[left] != columns[right]
        assert not ({columns[left], columns[right]} & occupied)
        occupied.update((columns[left], columns[right]))
        p = mul(coordinate(left), coordinate(right))
        assert p == item["product_p"]
        z = item["unrotated_pair_output_z"]
        a = standard_reciprocal(z)
        assert square(z) ^ seed_h2 ^ mul(square(z) ^ z, p) == 0
        assert mul(1 ^ seed_h2, square(a)) ^ mul(a, p) ^ seed_h2 == 0
        rotated_a = frobenius(a, item["rotation"])
        assert rotated_a == standard_reciprocal(chain["pair_rotated_z"][slot])
        options = set()
        for source_left, source_right in itertools.product(point_options(left), point_options(right)):
            result = point_add(source_left, source_right)
            if result is not None and result[0] and inverse(result[0]) == a:
                options.add((frobenius(result[0], item["rotation"]),
                             frobenius(result[1], item["rotation"])))
        assert len(options) == 2
        signed_pair_options.append(tuple(sorted(options)))

    pair_a = [standard_reciprocal(z) for z in chain["pair_rotated_z"]]
    intermediate_a = [standard_reciprocal(z) for z in chain["intermediate_z"]]
    constructed_a = standard_reciprocal(chain["raw_target_z"])
    assert constructed_a == inverse(chain["raw_target"][0])
    running = pair_a[0]
    branches = []
    for index in range(1, 8):
        output = intermediate_a[index - 1] if index < 7 else constructed_a
        total = running ^ pair_a[index] ^ output
        assert trace(total) == 0
        bit = mul(mul(running, pair_a[index]), output) ^ halftrace(square(total))
        assert bit in (0, 1)
        branches.append(bit)
        running = output
    assert branches == control["branch_bits"]

    raw_target = tuple(chain["raw_target"])
    paths = list(signed_pair_options[0])
    for index in range(1, 8):
        expected = intermediate_a[index - 1] if index < 7 else constructed_a
        next_paths = []
        for running, option in itertools.product(paths, signed_pair_options[index]):
            summed = point_add(running, option)
            if summed is not None and summed[0] and inverse(summed[0]) == expected:
                next_paths.append(summed)
        assert next_paths
        paths = next_paths
    matching_signs = sum(point == raw_target for point in paths)
    assert matching_signs > 0
    assert query["formula"]["xcnf_sha256"] != control["formula"]["xcnf_sha256"]
    assert query["stop_reason"] == "PARENT_TIMEOUT" and query["status"] == "BOUNDED_UNKNOWN"
    result = {"status": "PASS_INDEPENDENT_N131_HALFTRACE_CUBIC_AUDIT",
              "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
              "source_pairs_checked": len(selected), "group_links_checked": len(branches),
              "signed_group_replay_matches": matching_signs,
              "control_formula_records": sum(control_counts),
              "ordinary_formula_records": sum(query_counts),
              "ordinary_status": query["status"],
              "solver_restart_rows_actual": restart_rows,
              "solver_bracket_diagnostic_rows": bracket_rows,
              "source_sha256": {"script": sha(__file__),
                                "protocol": sha(HERE / "protocol.json"),
                                "control": sha(HERE / "control_result.json"),
                                "query": sha(HERE / "query_result.json")}}
    with (HERE / "audit_result.json").open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
