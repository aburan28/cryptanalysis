# Straight-line generators for the bitsliced field operations.
#
# Representation (all in the permuted type-II ONB, n = 2m+1):
#   onb   -- m words, word i-1 is the coefficient of gamma_i = zeta^i + zeta^-i,
#            with the coefficient of index 0 normalised to zero.
#   opb   -- m words, the "optimal polynomial basis" of Bernstein-Lange:
#            coefficients of c^k, k = 0..m-1, where c = gamma_1.
#
# Multiplication is  multPrep (onb -> opb) on each operand, one 131x131
# polynomial multiplication over GF(2), then toOnb (2m-1 opb coefficients back
# to onb, folding indices modulo n).
#
# The conversions are generated from the substitution c = z + 1/z, which splits
# by parity as  H(c) = Heven(c^2) + c * Hodd(c^2)  and, because squaring is the
# index permutation i -> 2i, costs O(K log K) XORs instead of the O(K*m) of a
# dense matrix.  The inverse runs the same recursion backwards (the odd part is
# recovered by a suffix XOR chain).
#
# No type hints, camelCase identifiers, no itertools (project convention).

import ir


# ---------------------------------------------------------------------------
# c = z + 1/z substitution and its inverse
# ---------------------------------------------------------------------------
def expandIr(prog, h):
    """h = coefficients of sum h_k c^k.  Returns the non-negative half of the
    symmetric Laurent expansion, res[j] for j = 0..len(h)-1."""
    if len(h) == 1:
        return [h[0]]
    hE = h[0::2]
    hO = h[1::2]
    e = expandIr(prog, hE)
    o = expandIr(prog, hO)
    res = [None] * len(h)
    for j in range(len(h)):
        if j % 2 == 0:
            if j // 2 < len(e):
                res[j] = e[j // 2]
        else:
            lo = (j - 1) // 2
            hi = (j + 1) // 2
            a = o[lo] if lo < len(o) else None
            b = o[hi] if hi < len(o) else None
            res[j] = prog.xor(a, b)
    return res


def unexpandIr(prog, v):
    """Inverse of expandIr on a vector of the same length."""
    if len(v) == 1:
        return [v[0]]
    k = len(v) - 1
    e = []
    j = 0
    while j <= k:
        e.append(v[j])
        j += 2
    nOdd = (k + 1) // 2
    o = [None] * nOdd
    for t in range(nOdd - 1, -1, -1):
        nxt = o[t + 1] if t + 1 < nOdd else None
        o[t] = prog.xor(v[2 * t + 1], nxt)
    hE = unexpandIr(prog, e) if e else []
    hO = unexpandIr(prog, o) if o else []
    out = [None] * len(v)
    for i in range(len(hE)):
        out[2 * i] = hE[i]
    for i in range(len(hO)):
        out[2 * i + 1] = hO[i]
    return out


def multPrepIr(prog, a, m):
    """onb coordinates (m words) -> opb coordinates (m words)."""
    # Move to the representative whose support avoids index m:  if the
    # coefficient of gamma_m is set, add the all-ones vector (which is zero in
    # the field) so that the support fits in indices 0..m-1.
    mask = a[m - 1]
    v = [None] * m
    v[0] = mask
    for i in range(1, m):
        v[i] = prog.xor(a[i - 1], mask)
    return unexpandIr(prog, v)


def toOnbIr(prog, h, m):
    """opb coefficients of degree < 2m-1 -> onb coordinates (m words)."""
    n = 2 * m + 1
    res = expandIr(prog, h)               # indices 0 .. len(h)-1  (<= 2m-2)
    w = [None] * (m + 1)
    for j in range(len(res)):
        idx = j % n
        if idx > m:
            idx = n - idx
        w[idx] = prog.xor(w[idx], res[j])
    mask = w[0]
    out = [None] * m
    for i in range(1, m + 1):
        out[i - 1] = prog.xor(w[i], mask)
    return out


# ---------------------------------------------------------------------------
# polynomial multiplication (leaf DAG)
# ---------------------------------------------------------------------------
def polyMulIr(prog, a, b, cutoff):
    outLen = len(a) + len(b) - 1
    n = max(len(a), len(b))
    a = list(a) + [None] * (n - len(a))
    b = list(b) + [None] * (n - len(b))
    if n <= cutoff:
        r = [None] * (2 * n - 1)
        for i in range(len(a)):
            if a[i] is None:
                continue
            for j in range(len(b)):
                if b[j] is None:
                    continue
                r[i + j] = prog.xor(r[i + j], prog.andOp(a[i], b[j]))
        return r[:outLen]
    half = (n + 1) // 2
    a0, a1 = a[:half], a[half:]
    b0, b1 = b[:half], b[half:]
    while len(a1) < len(a0):
        a1 = a1 + [None]
    while len(b1) < len(b0):
        b1 = b1 + [None]
    am = []
    bm = []
    for i in range(len(a0)):
        am.append(prog.xor(a0[i], a1[i]))
        bm.append(prog.xor(b0[i], b1[i]))
    p0 = polyMulIr(prog, a0, b0, cutoff)
    p1 = polyMulIr(prog, a1, b1, cutoff)
    pm = polyMulIr(prog, am, bm, cutoff)
    for i in range(len(pm)):
        pm[i] = prog.xor(pm[i], prog.xor(p0[i] if i < len(p0) else None,
                                         p1[i] if i < len(p1) else None))
    out = [None] * (2 * n - 1)
    for i in range(len(p0)):
        if i < len(out):
            out[i] = prog.xor(out[i], p0[i])
    for i in range(len(pm)):
        if half + i < len(out):
            out[half + i] = prog.xor(out[half + i], pm[i])
    for i in range(len(p1)):
        if 2 * half + i < len(out):
            out[2 * half + i] = prog.xor(out[2 * half + i], p1[i])
    return out[:outLen]


# ---------------------------------------------------------------------------
# Hamming weight (carry-save adder tree) and the distinguished-point test
# ---------------------------------------------------------------------------
def hammingIr(prog, x, nBits):
    buckets = [list(x)]
    for _ in range(nBits + 1):
        buckets.append([])
    level = 0
    while level < nBits:
        cur = buckets[level]
        out = []
        while len(cur) >= 3:
            a, b, c = cur.pop(), cur.pop(), cur.pop()
            s = prog._node(ir.OP_XOR3, (a, b, c))
            k = prog._node(ir.OP_MAJ, (a, b, c))
            out.append(s)
            buckets[level + 1].append(k)
        if len(cur) == 2:
            a, b = cur.pop(), cur.pop()
            out.append(prog.xor(a, b))
            buckets[level + 1].append(prog.andOp(a, b))
        while cur:
            out.append(cur.pop())
        if len(out) > 1:
            buckets[level] = out
            continue
        buckets[level] = out
        level += 1
    bits = []
    for i in range(nBits):
        bits.append(buckets[i][0] if buckets[i] else None)
    return bits


def leqConstIr(prog, bits, limit, ones):
    """Mask that is all-ones in lanes where the bitsliced integer <= limit."""
    le = ones
    for i in range(len(bits) - 1, -1, -1):
        b = bits[i]
        if b is None:
            if (limit >> i) & 1:
                le = ones
            continue
        nb = prog._node(ir.OP_NOT, (b,))
        if (limit >> i) & 1:
            le = prog._node(ir.OP_OR, tuple(sorted((le, nb))))
        else:
            le = prog.andOp(le, nb)
    return le


# ---------------------------------------------------------------------------
# polynomial basis
#
# Fields with no type-II optimal normal basis (2m+1 composite, e.g. m = 97 for
# ECC2K-95) are handled the way Harley's 1998 client was: all arithmetic in a
# polynomial basis F_2[z]/(F), with the orbit-invariant weight taken in a normal
# basis reached by one linear map.  Reduction modulo a trinomial or pentanomial
# is a handful of XORs, so a multiplication here is just Karatsuba plus that.
# ---------------------------------------------------------------------------
def pbReduceIr(prog, h, m, taps):
    """Reduce 2m-1 coefficients modulo z^m + sum z^taps + 1, in place."""
    c = list(h) + [None] * max(0, (2 * m - 1) - len(h))
    for j in range(len(c) - 1, m - 1, -1):
        v = c[j]
        if v is None:
            continue
        c[j] = None
        c[j - m] = prog.xor(c[j - m], v)
        for t in taps:
            if t is None or t < 0:
                continue
            # j - m + t < j because t < m, so the contribution lands strictly
            # lower and this single downward pass is enough
            c[j - m + t] = prog.xor(c[j - m + t], v)
    return c[:m]


def pbMulIr(prog, a, b, m, taps, cutoff):
    return pbReduceIr(prog, polyMulIr(prog, a, b, cutoff), m, taps)


def pbSqrIr(prog, a, m, taps):
    wide = [None] * (2 * m - 1)
    for i in range(m):
        wide[2 * i] = a[i]
    return pbReduceIr(prog, wide, m, taps)


def linearMapIr(prog, x, rows, block):
    """Apply a GF(2) matrix given as `rows` (each an input bitmask).

    Uses the four-Russians decomposition: every block of `block` inputs gets
    its 2^block - block - 1 non-trivial sums precomputed once, and each output
    then XORs one value per block.  That turns an m x m dense matrix from about
    m^2/2 XORs into roughly m^2/block."""
    n = len(x)
    nb = (n + block - 1) // block
    tables = []
    for b in range(nb):
        lo = b * block
        hi = min(n, lo + block)
        width = hi - lo
        tab = [None] * (1 << width)
        for mask in range(1, 1 << width):
            low = mask & (mask - 1)
            if low == 0:
                bit = mask.bit_length() - 1
                tab[mask] = x[lo + bit]
            else:
                high = mask ^ low
                tab[mask] = prog.xor(tab[low], tab[high])
        tables.append((lo, width, tab))
    out = []
    for row in rows:
        parts = []
        for lo, width, tab in tables:
            sel = (row >> lo) & ((1 << width) - 1)
            if sel:
                parts.append(tab[sel])
        out.append(prog.xorList(parts))
    return out


def pbHammingIr(prog, x, rows, block, nBits):
    """Normal-basis weight of a polynomial-basis element: one linear map into
    normal-basis coordinates, then the carry-save adder tree."""
    nb = linearMapIr(prog, x, rows, block)
    return hammingIr(prog, nb, nBits)
