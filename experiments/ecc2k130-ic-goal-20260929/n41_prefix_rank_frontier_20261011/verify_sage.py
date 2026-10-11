"""Independent checked-Sage rank and exact point-sum replay for full prefixes."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing, EllipticCurve

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SYSTEM = ROOT / "n41_w6_s8_quadratic_joint/ordinary_subgroup_root_R1/functional_system.ms"
BASE = ROOT / "n131_w18_four_pairs/native_join/native_input.txt"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_equations():
    lines = SYSTEM.read_text().splitlines()
    assert lines[1] == "2" and len(lines) == 500
    equations = []
    for line in lines[2:]:
        terms = set()
        for part in line.rstrip(",").split("+"):
            term = tuple(sorted(set(int(piece[1:]) for piece in part.split("*")
                                    if piece != "1")))
            assert all(0 <= i < 420 for i in term)
            terms.symmetric_difference_update([term])
        equations.append(terms)
    return equations


def rank_for_prefix(equations, prefix):
    chosen = sum(int(mask) << (6 * slot) for slot, mask in enumerate(prefix))
    fixed = 48
    reduced = []
    all_monomials = set()
    for equation in equations:
        terms = set()
        for term in equation:
            selected = all(chosen >> i & 1 for i in term if i < fixed)
            if not selected:
                continue
            free = tuple(i for i in term if i >= fixed)
            terms.symmetric_difference_update([free])
            if free:
                all_monomials.add(free)
        reduced.append(terms)
    monomials = {term: index for index, term in enumerate(sorted(all_monomials))}
    pivots = {}
    for terms in reduced:
        rhs = int(() in terms)
        row = sum(1 << monomials[term] for term in terms if term)
        while row:
            pivot = (row & -row).bit_length() - 1
            prior = pivots.get(pivot)
            if prior is None:
                pivots[pivot] = (row, rhs)
                break
            row ^= prior[0]
            rhs ^= prior[1]
        if not row and rhs:
            return len(pivots), False, len(monomials)
    return len(pivots), True, len(monomials)


def load_points(curve, field):
    basis = [field.gen()**i for i in range(41)]

    def from_bits(value):
        output = field.zero()
        for i, bit in enumerate(basis):
            if value >> i & 1:
                output += bit
        return output

    words = iter(map(int, BASE.read_text().split()))
    qx, qy, order, slots = (next(words) for _ in range(4))
    assert slots == 8 and order == 549756390943
    target = curve(from_bits(qx), from_bits(qy))
    domains = []
    for _ in range(slots):
        assert next(words) == 64
        by_mask = {}
        for _ in range(64):
            x, y, column, mask, branch, sign = (next(words) for _ in range(6))
            assert branch == 0 and sign in (0, 1)
            by_mask.setdefault(mask, {})[sign] = curve(from_bits(x), from_bits(y))
        assert len(by_mask) == 32 and all(len(signs) == 2 for signs in by_mask.values())
        domains.append(by_mask)
    assert next(words, None) is None
    return target, domains


def group_match_count(target, domains, prefix):
    states = {domains[0][prefix[0]][0], domains[0][prefix[0]][1]}
    for slot in range(1, 8):
        states = {state + domains[slot][prefix[slot]][sign]
                  for state in states for sign in (0, 1)}
    return int(target in states), len(states)


protocol = json.loads((HERE / "protocol.json").read_text())
producer = json.loads((HERE / "result.json").read_text())
runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
assert runtime["status"] == "verified"
assert producer["protocol_sha256"] == sha(HERE / "protocol.json")
assert protocol["source_sha256"]["quadratic_system"] == sha(SYSTEM)
assert protocol["source_sha256"]["base"] == sha(BASE)

ring = PolynomialRing(GF(2), "t")
t = ring.gen()
field = GF(2**41, "a", modulus=t**41 + t**3 + 1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])
target, domains = load_points(curve, field)
equations = parse_equations()
records = []
for index in range(5):
    prefix = protocol["samples"]["4"][index]
    rank, consistent, unknowns = rank_for_prefix(equations, prefix)
    reference = producer["rows"][3]["decisions"][index]
    assert prefix == reference["prefix"]
    assert rank == reference["rank"] and consistent == reference["consistent"]
    matched, state_count = group_match_count(target, domains, prefix)
    if index == 0:
        assert matched == 1
    else:
        assert matched == 0
    records.append({"sample_index": index, "rank": rank,
                    "linear_relaxation_consistent": consistent,
                    "group_target_match": bool(matched),
                    "distinct_signed_sums": state_count,
                    "free_monomials_used": unknowns})

out = {"status": "PASS_INDEPENDENT_SAGE_PREFIX_AND_GROUP_REPLAY",
       "curve_id": protocol["curve_id"], "target": protocol["target"],
       "records": records,
       "sha256": {"verifier": sha(Path(__file__)), "protocol": sha(HERE / "protocol.json"),
                  "producer": sha(HERE / "result.json"), "runtime": sha(HERE / "sage_runtime_info.json"),
                  "quadratic_system": sha(SYSTEM), "base": sha(BASE)}}
(HERE / "sage_replay.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], [(r["rank"], r["group_target_match"]) for r in records])
