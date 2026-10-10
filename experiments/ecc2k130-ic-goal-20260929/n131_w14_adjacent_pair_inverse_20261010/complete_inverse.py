"""Complete adjacent W14 pair inverse, including rank-deficient outputs.

For fixed seed sum s, write a seed representation as (w1+h,w2+h), where
h runs through W14 intersect Frob(W14). Its product varies by h^2+s*h,
which is binary linear on the seven overlap bits. This replaces a scan
of 128 representations with a seven-column solve for each (s,p).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run  # noqa: E402
import oracle  # noqa: E402


def decode_joint(joint, code):
    width = len(joint["sum_w_basis"])
    seed_sum = oracle.coordinate(joint["sum_w_basis"], code & ((1 << width)-1))
    product = oracle.coordinate(joint["product_basis"], code >> width)
    return seed_sum, product


def fixed_sum_product(candidate, joint, seed_sum, product):
    """Return every supported ordered mask pair for one exact (s,p)."""
    field = candidate.field
    particular = oracle.solve(joint["seed_pivots"], seed_sum)
    if particular is None:
        return [], {"status": "SEED_SUM_OUTSIDE_SPAN"}
    left_mask = particular & ((1 << oracle.D)-1)
    right_mask = particular >> oracle.D
    w1 = oracle.coordinate(joint["left_w"], left_mask)
    w2 = oracle.coordinate(joint["right_w"], right_mask)
    overlap = [oracle.coordinate(joint["left_w"],
                 vector & ((1 << oracle.D)-1)) for vector in joint["seed_kernel"]]
    assert len(overlap) == 7
    assert all(oracle.coordinate(joint["right_w"], vector >> oracle.D) == h
               for vector, h in zip(joint["seed_kernel"], overlap))
    product_columns = [field.mul(h, h) ^ field.mul(seed_sum, h) for h in overlap]
    pivots, product_kernel = oracle.echelon(product_columns)
    delta = oracle.solve(pivots, product ^ field.mul(w1, w2))
    if delta is None:
        return [], {"status": "PRODUCT_OUTSIDE_FIXED_SUM_IMAGE",
                    "rank": len(pivots)}
    pairs = []
    for overlap_code in oracle.affine_solutions(delta, product_kernel):
        mask_code = particular
        for i, vector in enumerate(joint["seed_kernel"]):
            if overlap_code >> i & 1:
                mask_code ^= vector
        a = mask_code & ((1 << oracle.D)-1)
        b = mask_code >> oracle.D
        if (a in candidate.valid and b in candidate.valid and
                candidate.columns[a] != candidate.columns[b]):
            assert field.mul(oracle.coordinate(joint["left_w"], a),
                             oracle.coordinate(joint["right_w"], b)) == product
            pairs.append((a, b))
    return sorted(set(pairs)), {"status": "PAIR_CANDIDATES" if pairs else
                                   "SOURCE_FILTER_REJECT", "rank": len(pivots),
                                   "product_nullity": len(product_kernel)}


def inverse(candidate, joint, z):
    """Return all supported pairs whose raw point sum has transformed x=z."""
    field = candidate.field
    if z in (0, 1):
        return [], {"status": "EXCEPTIONAL_EMPTY", "joint_rank": None,
                    "joint_solutions": 0, "seed_sums": 0,
                    "fixed_sum_solves": 0, "raw_pairs_checked": 0}
    z2 = field.mul(z, z)
    az = z2 ^ z
    columns = [field.mul(u, u) for u in joint["sum_u_basis"]] + [
        field.mul(az, p) for p in joint["product_basis"]]
    pivots, kernel = oracle.echelon(columns)
    particular = oracle.solve(pivots, z2)
    if particular is None:
        return [], {"status": "JOINT_SPAN_REJECT", "joint_rank": len(pivots),
                    "joint_solutions": 0, "seed_sums": 0,
                    "fixed_sum_solves": 0, "raw_pairs_checked": 0}
    accepted = set()
    seen_sums = set()
    joint_solutions = fixed_sum_solves = raw_pairs_checked = 0
    for code in oracle.affine_solutions(particular, kernel):
        joint_solutions += 1
        seed_sum, product = decode_joint(joint, code)
        if seed_sum == 0:
            continue
        seen_sums.add(seed_sum)
        pairs, _ = fixed_sum_product(candidate, joint, seed_sum, product)
        fixed_sum_solves += 1
        for a, b in pairs:
            raw_pairs_checked += 1
            if z in run.raw_outputs(candidate, a, b):
                accepted.add((a, b))
    return sorted(accepted), {"status": "PAIR" if accepted else "EXACT_REJECT",
                              "joint_rank": len(pivots),
                              "joint_nullity": len(kernel),
                              "joint_solutions": joint_solutions,
                              "seed_sums": len(seen_sums),
                              "fixed_sum_solves": fixed_sum_solves,
                              "raw_pairs_checked": raw_pairs_checked}
