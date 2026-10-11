"""Independent field replay and alternate held-out Bernoulli score evaluation."""

import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SOURCE = BASE / "n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"
ORIGINAL = BASE / "n41_w6_public_seed_predictor_20261011/rows.tsv"
MOD = (1 << 41) | (1 << 3) | 1
MASK = (1 << 41) - 1


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mul(a, b):
    product = 0
    while b:
        if b & 1:
            product ^= a
        a <<= 1
        b >>= 1
    while product.bit_length() > 41:
        product ^= MOD << (product.bit_length() - 42)
    return product


def inv(a):
    assert a
    u, v, g, h = a, MOD, 1, 0
    while u != 1:
        j = u.bit_length() - v.bit_length()
        if j < 0:
            u, v, g, h = v, u, h, g
            j = -j
        u ^= v << j
        g ^= h << j
    while g.bit_length() > 41:
        g ^= MOD << (g.bit_length() - 42)
    return g


def point_add(p, q):
    if p is None:
        return q
    if q is None:
        return p
    x, y = p
    u, v = q
    if x == u:
        if y != v or x == 0:
            return None
        slope = x ^ mul(y, inv(x))
        z = mul(slope, slope) ^ slope
        return z, mul(x, x) ^ mul(slope ^ 1, z)
    slope = mul(y ^ v, inv(x ^ u))
    z = mul(slope, slope) ^ slope ^ x ^ u
    return z, mul(slope, x ^ z) ^ z ^ y


def negate(p):
    return None if p is None else (p[0], p[0] ^ p[1])


def source_pairs():
    words = list(map(int, SOURCE.read_text().split()))
    assert words[:4] == [1458168294740, 1672312028033, 549756390943, 6]
    position = 4
    pairs = []
    for block in range(6):
        rotation, size = words[position:position + 2]
        position += 2
        assert rotation == block * 5 and size == 64
        atoms = []
        for _ in range(size):
            x, y, mask, sign, column = words[position:position + 5]
            position += 5
            atoms.append(((x, y), mask, sign, column))
        if block < 2:
            pairs.append([(i, j) for i in range(64) for j in range(64)
                          if atoms[i][1] < atoms[j][1] and atoms[i][3] != atoms[j][3]])
            pairs[-1] = (atoms, pairs[-1])
    assert position == len(words)
    assert len(pairs[0][1]) == len(pairs[1][1]) == 1956
    return pairs


def score_replay(data, labels, xcols):
    shifts = np.arange(41, dtype=np.uint64)
    bits = np.concatenate([((data[:, col, None] >> shifts) & 1).astype(np.uint8)
                           for col in xcols], axis=1)
    train, test = bits[:80000], bits[80000:]
    classes = np.arange(1, 64)
    counts = np.bincount(labels[:80000], minlength=64)[1:]
    ones = np.array([train[labels[:80000] == label].sum(axis=0)
                     for label in classes], dtype=np.float64)
    probability = (ones + 1) / (counts[:, None] + 2)
    score = np.broadcast_to(np.log(counts / 80000), (20000, 63)).copy()
    for bit in range(82):
        score += np.where(test[:, bit, None] != 0,
                          np.log(probability[None, :, bit]),
                          np.log1p(-probability[None, :, bit]))
    order = np.argsort(-score, axis=1, kind="stable")
    return np.any(classes[order[:, :7]] == labels[80000:, None], axis=1)


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "fit_result.json").read_text())
    extract = json.loads((HERE / "extract_receipt_v2.json").read_text())
    assert protocol["residual_sha256"] == extract["residual_sha256"] == digest(HERE / "residuals.tsv")
    assert extract["status"] == "COMPLETE"
    assert result["protocol_sha256"] == digest(HERE / "protocol.json")
    original = np.loadtxt(ORIGINAL, dtype=np.uint64, delimiter="\t", skiprows=1)
    data = np.loadtxt(HERE / "residuals.tsv", dtype=np.uint64, delimiter="\t", skiprows=1)
    outcomes = np.loadtxt(HERE / "holdout_outcomes.tsv", dtype=np.uint16,
                          delimiter="\t", skiprows=1)
    assert original.shape == data.shape == (100000, 10)
    assert outcomes.shape == (20000, 5)
    assert np.array_equal(original[:, :4], data[:, [0, 1, 6, 7]])
    assert np.array_equal(original[:, 4:6], data[:, 8:10])
    assert np.array_equal(outcomes[:, 0], data[80000:, 6])
    labels = data[:, 6].astype(np.int16)
    classes = np.arange(1, 64)
    counts = np.bincount(labels[:80000], minlength=64)[1:]
    baseline = classes[np.argsort(-counts, kind="stable")[:7]]
    assert np.array_equal(outcomes[:, 1], np.isin(labels[80000:], baseline))
    for index, cols in enumerate(((0, 1), (2, 3), (4, 5)), start=2):
        hit = score_replay(data, labels, cols)
        assert np.array_equal(outcomes[:, index], hit)
    sample = list(range(0, 100000, 1562))[:64]
    source = source_pairs()
    for row_index in sample:
        row = data[row_index]
        q = int(row[0]), int(row[1])
        p0, p1 = (int(row[8]), int(row[9]))
        a0, edge0 = source[0]
        a1, edge1 = source[1]
        i, j = edge0[p0]
        first = point_add(a0[i][0], a0[j][0])
        i, j = edge1[p1]
        second = point_add(a1[i][0], a1[j][0])
        r0 = point_add(q, negate(first))
        r01 = point_add(r0, negate(second))
        assert r0 == (int(row[2]), int(row[3]))
        assert r01 == (int(row[4]), int(row[5]))
        assert point_add(point_add(r01, second), first) == q
    assert result["holdout_outcomes_sha256"] == digest(HERE / "holdout_outcomes.tsv")
    audit = {"status": "PASS_PREFIX_RESIDUAL_SEED_SELECTOR",
             "protocol_sha256": digest(HERE / "protocol.json"),
             "extract_receipt_sha256": digest(HERE / "extract_receipt_v2.json"),
             "fit_result_sha256": digest(HERE / "fit_result.json"),
             "holdout_rows_replayed": 20000,
             "independent_group_rows_replayed": len(sample),
             "seven_seed_hits": result["seven_seed_hits"]}
    audit_path = HERE / "audit.json"
    if audit_path.exists():
        assert json.loads(audit_path.read_text()) == audit
    else:
        with audit_path.open("x") as stream:
            json.dump(audit, stream, sort_keys=True, indent=2)
            stream.write("\n")
    print(audit["status"])


if __name__ == "__main__":
    main()
