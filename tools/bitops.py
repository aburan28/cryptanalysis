"""`bitop/v1`: one unit of work for every ECDLP cost (Python implementation).

A bit operation is one two-input Boolean gate (AND, XOR, OR) in the textbook
circuit for a primitive.  Every primitive has a frozen gate count that is a
function of the operand widths alone, so

    work = sum(count(primitive) * gates(primitive, widths))

is an exact integer that depends on the counts and this file, never on a host.

This is a transcription of the reference implementation
`crypto:src/cryptanalysis/bitops.rs`; the conventions and their derivations are
`crypto:docs/units/BITOPS.md`.  `docs/units/bitop-v1.vectors.json` (a verbatim
copy, see `docs/units/README.md`) holds the gate count of every primitive at a
spread of widths, and `tests/test_bitops.py` checks that this module reproduces
every row exactly.  The convention is frozen: a different one is `bitop/v2`,
never an edit here.

Fields are dicts in the vectors' encoding:
    {"kind": "prime", "bits": b}    F_p, p of b bits (Montgomery)
    {"kind": "binary", "n": n}      F_{2^n}, polynomial basis, pentanomial reduction
    {"kind": "fp4", "bits": b}      F_{p^4}, p of b bits
`r_bits` is the bit length of the subgroup order r.
"""

from __future__ import annotations

import math

UNIT = "bitop/v1"

PRIMS = (
    "field_add",
    "field_mul",
    "field_sqr",
    "field_inv",
    "field_sqrt",
    "legendre",
    "as_solve",
    "canon",
    "group_add",
    "group_double",
    "modr_mul",
    "modr_add",
    "word_op",
    "hash_probe",
)


class NoPrice(ValueError):
    """A primitive with no bitop/v1 price over a field (the counter is misclassified)."""


def prime_field(bits: int) -> dict:
    return {"kind": "prime", "bits": int(bits)}


def binary_field(n: int) -> dict:
    return {"kind": "binary", "n": int(n)}


def fp4_field(bits: int) -> dict:
    return {"kind": "fp4", "bits": int(bits)}


# ------------------------------------------------------------------ integers
def int_add(w: int) -> int:
    """w-bit ripple-carry addition: w full adders of five gates."""
    return 5 * w


def int_mul(w: int) -> int:
    """w x w schoolbook product: w^2 partial-product ANDs and w - 1 w-bit row additions."""
    return w * w + 5 * w * max(w - 1, 0)


# ------------------------------------------------------------------ F_p (Montgomery)
def fp_add(b: int) -> int:
    """Addition, conditional subtraction of p and a b-bit select."""
    return 2 * int_add(b) + 3 * b


def fp_mul(b: int) -> int:
    """Product, reduction product and final conditional subtraction."""
    return 2 * int_mul(b) + fp_add(b)


def fp_sqr(b: int) -> int:
    return fp_mul(b)


def fp_inv(b: int) -> int:
    """Binary extended Euclid: 2b steps of a subtraction, a comparison and a select."""
    return 2 * b * fp_add(b)


def fp_sqrt(b: int) -> int:
    """Tonelli-Shanks: b squarings, b/2 products and a b/2-product allowance."""
    return 2 * b * fp_mul(b)


def fp_legendre(b: int) -> int:
    return fp_inv(b)


# ------------------------------------------------------------------ F_{2^n}
_LOW_TERMS = 4  # pentanomial: the dearer modulus, so no curve is flattered by its own


def f2_add(n: int) -> int:
    return n


def f2_mul(n: int) -> int:
    """Schoolbook carry-less product (n^2 AND, (n-1)^2 XOR) and the reduction."""
    return n * n + (n - 1) * (n - 1) + _LOW_TERMS * (n - 1)


def f2_sqr(n: int) -> int:
    """Spreading the bits is wiring; the reduction is not."""
    return _LOW_TERMS * (n - 1)


def f2_inv(n: int) -> int:
    """Polynomial extended Euclid: 2n steps of a shift-XOR pair and an n-bit select."""
    return 2 * n * (2 * n + 3 * n)


def f2_as_solve(n: int) -> int:
    """Half-trace as a precomputed n x n F_2 matrix times a vector: n^2 AND + n(n-1) XOR."""
    return n * n + n * (n - 1)


def f2_canon(n: int) -> int:
    """Normal-basis conversion and the least of n rotations."""
    return f2_as_solve(n) + 2 * n * n


# ------------------------------------------------------------------ group operations
# (inv, mul, sqr, add) field operations behind one affine group operation
PRIME_ADD = (1, 2, 1, 6)
PRIME_DOUBLE = (1, 2, 2, 8)
BINARY_ADD = (1, 2, 1, 9)
BINARY_DOUBLE = (1, 2, 2, 5)
FP4_GROUP_OP_FP_MULS = 97
FP4_MUL_FP_MULS = 16


def _group(formula: tuple[int, int, int, int], inv: int, mul: int, sqr: int, add: int) -> int:
    fi, fm, fs, fa = formula
    return fi * inv + fm * mul + fs * sqr + fa * add


def gates(prim: str, field: dict, r_bits: int) -> int:
    """Gates of one `prim` over `field` with a subgroup order of `r_bits` bits."""
    if prim not in PRIMS:
        raise KeyError(f"unknown bitop/v1 primitive {prim!r}")
    w = max(int(r_bits), 1)
    # Arithmetic modulo r is prime-field arithmetic at r's width.
    if prim == "modr_mul":
        return fp_mul(w)
    if prim == "modr_add":
        return fp_add(w)
    if prim == "word_op":
        return 64
    kind = field["kind"]
    if kind == "prime":
        b = int(field["bits"])
        table = {
            "field_add": fp_add,
            "field_mul": fp_mul,
            "field_sqr": fp_sqr,
            "field_inv": fp_inv,
            "field_sqrt": fp_sqrt,
            "legendre": fp_legendre,
        }
        if prim in table:
            return table[prim](b)
        if prim == "group_add":
            return _group(PRIME_ADD, fp_inv(b), fp_mul(b), fp_sqr(b), fp_add(b))
        if prim == "group_double":
            return _group(PRIME_DOUBLE, fp_inv(b), fp_mul(b), fp_sqr(b), fp_add(b))
        if prim == "hash_probe":
            return 4 * b
    elif kind == "binary":
        n = int(field["n"])
        table = {
            "field_add": f2_add,
            "field_mul": f2_mul,
            "field_sqr": f2_sqr,
            "field_inv": f2_inv,
            "as_solve": f2_as_solve,
            "canon": f2_canon,
        }
        if prim in table:
            return table[prim](n)
        if prim == "group_add":
            return _group(BINARY_ADD, f2_inv(n), f2_mul(n), f2_sqr(n), f2_add(n))
        if prim == "group_double":
            return _group(BINARY_DOUBLE, f2_inv(n), f2_mul(n), f2_sqr(n), f2_add(n))
        if prim == "hash_probe":
            return 4 * n
    elif kind == "fp4":
        b = int(field["bits"])
        if prim == "field_add":
            return 4 * fp_add(b)
        if prim in ("field_mul", "field_sqr"):
            return FP4_MUL_FP_MULS * fp_mul(b)
        if prim in ("group_add", "group_double"):
            return FP4_GROUP_OP_FP_MULS * fp_mul(b)
        if prim == "hash_probe":
            return 16 * b
    else:
        raise KeyError(f"unknown field kind {kind!r}")
    raise NoPrice(f"{prim} has no bitop/v1 price over {field}")


def element_bits(field: dict) -> int:
    kind = field["kind"]
    if kind == "binary":
        return int(field["n"])
    if kind == "fp4":
        return 4 * int(field["bits"])
    return int(field["bits"])


def log2(x: int) -> float:
    """log2 of an exact gate count, exact on powers of two (as the reference's `log2`)."""
    if x <= 0:
        return -math.inf
    shift = max(x.bit_length() - 53, 0)
    return math.log2(x >> shift) + shift


def work(counts: dict[str, int], field: dict, r_bits: int) -> dict:
    """Price primitive counts: {"unit", "primitives", "bitops", "log2_bitops"}."""
    prims = {p: int(k) for p, k in sorted(counts.items()) if k}
    total = sum(k * gates(p, field, r_bits) for p, k in prims.items())
    return {"unit": UNIT, "primitives": prims, "bitops": total, "log2_bitops": log2(total)}


# Widths of the reference vectors (bitops.rs `vectors()`), in the same order.
VECTOR_FIELDS = (
    prime_field(17),
    prime_field(32),
    prime_field(256),
    binary_field(23),
    binary_field(41),
    binary_field(131),
    fp4_field(13),
)
VECTOR_R_BITS = (16, 40, 130)


def vectors() -> list[dict]:
    """Every priced (field, r_bits, prim) row of the reference vectors, gates as decimal strings."""
    out = []
    for field in VECTOR_FIELDS:
        for r_bits in VECTOR_R_BITS:
            for prim in PRIMS:
                try:
                    g = gates(prim, field, r_bits)
                except NoPrice:
                    continue
                out.append({"field": dict(field), "r_bits": r_bits, "prim": prim, "gates": str(g)})
    return out
