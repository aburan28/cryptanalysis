#!/usr/bin/env python3
# Generate the bitsliced GF(2^m) arithmetic headers for the ECC2K-130 client.
#
#   python3 gen.py [--out ../generated] [--leaf 10]
#
# For each configured curve this emits one header holding
#   * multPrep  : permuted type-II ONB coordinates -> optimal polynomial basis
#   * toOnb     : a 2m-1 coefficient product back to ONB coordinates
#   * mulLeaf   : the Karatsuba leaf multiplier (schoolbook, LOP3-fused)
#   * hamming   : the carry-save weight tree and the distinguished-point test
#   * the squaring permutation, curve parameters, and the polynomial-basis
#     change of basis used by the host reference implementation.
#
# Every emitted routine is verified inside this script against an independent
# model of the field (see field.Onb) on random inputs before it is written out.
#
# No type hints, camelCase identifiers, no itertools (project convention).

import argparse
import random
import sys

import build
import curves
import field
import ir

CHALLENGE_PX = 0x051C99BFA6F18DE467C80C23B98C7994AA
CHALLENGE_PY = 0x042EA2D112ECEC71FCF7E000D7EFC978BD
CHALLENGE_QX = 0x06C997F3E7F2C66A4A5D2FDA13756A37B1
CHALLENGE_QY = 0x04A38D11829D32D347BD0C0F584D546E9A
CHALLENGE_POLY = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
CHALLENGE_TAPS = (13, 2, 1)
CHALLENGE_ELL = 680564733841876926932320129493409985129

# ECC2K-95, solved by Harley's group in May 1998.  GF(2^97) has no type-II
# optimal normal basis (2m+1 = 195 is composite), so this curve uses the
# polynomial-basis backend with the weight taken through one linear map into a
# normal basis -- the same arrangement Harley's client used.
ECC2K95 = {
    'm': 97,
    'poly': (1 << 97) | (1 << 6) | 1,
    'taps': (6, -1, -1),
    'px': 0x08A84FB02034F7771DC940097,
    'py': 0x1D2F10A471D48A720F18F6339,
    'qx': 0x0E0BC08AC5818F303E2B05E90,
    'qy': 0x134C028FC3393124D673E6F8E,
    'ell': 39614081257132074233778707191,
    'knownK': 37837308472231540269443981458,
}

CURVES = [
    {'m': 131, 'basis': 'onb', 'challenge': True, 'dpWeight': 34, 'instances': 0},
    {'m': 83, 'basis': 'onb', 'challenge': False, 'dpWeight': 0, 'instances': 2},
    {'m': 41, 'basis': 'onb', 'challenge': False, 'dpWeight': 0, 'instances': 16},
    {'m': 23, 'basis': 'onb', 'challenge': False, 'dpWeight': 0, 'instances': 16},
    {'m': 97, 'basis': 'pb', 'challenge': True, 'dpWeight': 0, 'instances': 0},
    {'m': 41, 'basis': 'pb', 'challenge': False, 'dpWeight': 0, 'instances': 8},
    {'m': 19, 'basis': 'pb', 'challenge': False, 'dpWeight': 0, 'instances': 8},
    {'m': 13, 'basis': 'pb', 'challenge': False, 'dpWeight': 0, 'instances': 8},
]


def limbs(v, count=3):
    out = []
    for i in range(count):
        out.append((v >> (64 * i)) & 0xFFFFFFFFFFFFFFFF)
    return out


def limbLiteral(v, count=3):
    return '{' + ', '.join('0x%016xull' % x for x in limbs(v, count)) + '}'


def sizeChain(m, leaf):
    out = [m]
    while out[-1] > leaf:
        out.append((out[-1] + 1) // 2)
    return out


# Emit the straight-line routines in a liveness-minimising order rather than
# the order the DAG was built in.  See HOST-SCHEDULE.md; --no-schedule is the
# paired control.
SCHEDULE = True

# Karatsuba cutoffs tried when building a generated leaf.  Instruction count
# and peak liveness both depend on the cutoff, so chooseLeaf and the emitters
# share this list and the same fewest-instruction pick.
LEAF_CUTOFFS = (4, 6, 8, 12, 16, 24, 33, 66)


def bestMulLeaf(n, cuts=None):
    """Fewest-instruction polyMul of size n after LOP3 fusion.

    Returns (instrCount, cutoff, prog, roots), or None if every cutoff is
    larger than n.  chooseLeaf scores peakLive of this DAG so the register
    budget describes the function that is written into the header."""
    if cuts is None:
        cuts = LEAF_CUTOFFS
    best = None
    for cut in cuts:
        if cut > n:
            continue
        p = ir.Prog()
        a = [p.addInput('a', i) for i in range(n)]
        b = [p.addInput('b', i) for i in range(n)]
        r = build.polyMulIr(p, a, b, cut)
        p.fuseLop3(r)
        count = p.instrCount(r)
        if best is None or count < best[0]:
            best = (count, cut, p, r)
    return best


def chooseLeaf(m, budget):
    """Largest halving-chain size whose straight-line multiply still fits in
    `budget` simultaneously live values.

    The leaf is where generated code stops and the C++ Karatsuba recursion
    begins, and the recursion is expensive in a way the leaf is not: it hands
    each level arrays -- four of length H and three of 2H-1 -- and a
    pointer-indexed array is something ptxas puts in local memory.  Three levels
    of it at m=131 moved 4020 words to and from local memory to perform 2011 bit
    operations.  So the leaf wants to be as large as it can be.

    What stops it is the register file.  Past the budget the compiler spills,
    and a spilled value costs two memory instructions every time it is touched,
    which is the same trade the recursion was already making.  So take the
    largest size that still fits: at m=131 that is 66 words, 254 live against
    255 registers, which is one level of recursion instead of three and a leaf
    that spills 284 bytes rather than a multiply that moved 16 kilobytes."""
    sizes = [m]
    while sizes[-1] > 4:
        sizes.append((sizes[-1] + 1) // 2)
    best = sizes[-1]
    for n in sizes:
        if n <= best:
            continue
        picked = bestMulLeaf(n)
        if picked is not None and picked[2].peakLive(picked[3]) <= budget:
            best = n
    return best


def dpWeightFor(m, ell):
    """Pick the weight cutoff so a walk runs about sqrt(iterations) steps,
    which keeps the distinguished-point count near the collision count."""
    import math
    iters = math.sqrt(math.pi * ell / (4.0 * m))
    target = max(4.0, math.sqrt(iters) / 4.0)     # steps per walk
    # P(weight <= w) over m coefficients, only even weights occur in the
    # trace-zero subgroup, so count the even ones and double.
    for w in range(2, m + 1):
        tot = 0
        for k in range(0, w + 1):
            tot += comb(m, k)
        prob = float(tot) / float(1 << m)
        if prob > 0 and 1.0 / prob <= target:
            return w
    return m


def comb(n, k):
    r = 1
    for i in range(k):
        r = r * (n - i) // (i + 1)
    return r


def buildProgs(m, leaf, rng, onb):
    """Build and verify every straight-line routine for this field."""
    progs = {}

    pMul = ir.Prog()
    a = [pMul.addInput('a', i) for i in range(m)]
    b = [pMul.addInput('b', i) for i in range(m)]
    pa = build.multPrepIr(pMul, a, m)
    pb = build.multPrepIr(pMul, b, m)
    hh = build.polyMulIr(pMul, pa, pb, leaf)
    rr = build.toOnbIr(pMul, hh, m)
    verifyMul(pMul, rr, m, onb, rng)

    pPrep = ir.Prog()
    ap = [pPrep.addInput('a', i) for i in range(m)]
    rPrep = build.multPrepIr(pPrep, ap, m)
    pPrep.fuseLop3(rPrep)
    progs['multPrep'] = (pPrep, rPrep, ['a'], m)

    pTo = ir.Prog()
    ht = [pTo.addInput('h', i) for i in range(2 * m - 1)]
    rTo = build.toOnbIr(pTo, ht, m)
    pTo.fuseLop3(rTo)
    progs['toOnb'] = (pTo, rTo, ['h'], 2 * m - 1)

    chain = sizeChain(m, leaf)
    lsz = chain[-1]
    bestLeaf = bestMulLeaf(lsz)
    progs['mulLeaf'] = (bestLeaf[2], bestLeaf[3], ['a', 'b'], lsz)
    progs['_leafCut'] = bestLeaf[1]

    nBits = 1
    while (1 << nBits) <= m:
        nBits += 1
    pHam = ir.Prog()
    xh = [pHam.addInput('x', i) for i in range(m)]
    rHam = build.hammingIr(pHam, xh, nBits)
    verifyHamming(pHam, rHam, m, nBits)
    pHam.fuseLop3(rHam)
    progs['hamming'] = (pHam, rHam, ['x'], m)
    progs['_chain'] = chain
    progs['_nBits'] = nBits
    return progs


def verifyMul(prog, roots, m, onb, rng):
    xs = []
    ys = []
    for _ in range(64):
        xs.append(onb.randomElement(rng))
        ys.append(onb.randomElement(rng))
    vals = {}
    for i in range(m):
        wa = 0
        wb = 0
        for lane in range(64):
            if (onb.toCoords(xs[lane]) >> i) & 1:
                wa |= 1 << lane
            if (onb.toCoords(ys[lane]) >> i) & 1:
                wb |= 1 << lane
        vals[('a', i)] = wa
        vals[('b', i)] = wb
    out = prog.evaluate(vals, roots)
    for lane in range(64):
        got = 0
        for i in range(m):
            if (out[i] >> lane) & 1:
                got |= 1 << i
        want = onb.toCoords(onb.mul(xs[lane], ys[lane]))
        if got != want:
            raise RuntimeError('multiplication mismatch for m=%d lane %d' % (m, lane))


def verifyHamming(prog, roots, m, nBits):
    rng = random.Random(99)
    vals = {}
    lanes = 64
    weights = []
    cols = [0] * m
    for lane in range(lanes):
        v = rng.getrandbits(m)
        weights.append(bin(v).count('1'))
        for i in range(m):
            if (v >> i) & 1:
                cols[i] |= 1 << lane
    for i in range(m):
        vals[('x', i)] = cols[i]
    out = prog.evaluate(vals, roots)
    for lane in range(lanes):
        got = 0
        for i in range(nBits):
            if (out[i] >> lane) & 1:
                got |= 1 << i
        if got != weights[lane]:
            raise RuntimeError('hamming mismatch m=%d lane %d: %d != %d' % (m, lane, got, weights[lane]))


def emitFunction(name, prog, roots, inputs, outLen, indent='    '):
    args = []
    for nm in inputs:
        args.append('const W *%s' % nm)
    args.append('W *o')
    if SCHEDULE:
        prog.scheduleLive(roots)
    lines, slots = prog.emit(roots, 'o', indent=indent)
    head = 'template <class W> ECC_BIG void %s(%s) {' % (name, ', '.join(args))
    return [head] + lines + ['}'], slots


def instanceData(onb, curve, ell, rng, count):
    out = []
    for _ in range(count):
        p = curve.randomPointOfOrder(ell, 4, rng)
        k = rng.randrange(1, ell)
        q = curve.mul(p, k)
        out.append((p, q, k))
    return out


def generate(cfg, leaf, outDir, verbose):
    m = cfg['m']
    rng = random.Random(0x5EED0000 + m)
    onb = field.Onb(m)
    onb.selfTest(rng)
    curve = curves.Curve(onb)

    if cfg['challenge']:
        poly, taps = CHALLENGE_POLY, CHALLENGE_TAPS
        ell = CHALLENGE_ELL
        if curves.curveOrder(m) != 4 * ell:
            raise RuntimeError('challenge order mismatch')
    else:
        poly, taps = curves.findIrreduciblePoly(m)
        ell = curves.curveOrder(m) // 4
        if not curves.isPrimeBig(ell):
            raise RuntimeError('ell not prime for m=%d' % m)

    root, zToOnb, gammaToPb = curves.basisImages(onb, poly, m, rng)

    def pbToOnb(v):
        acc = 0
        for i in range(m):
            if (v >> i) & 1:
                acc ^= zToOnb[i]
        return onb.fromCoords(acc)

    def onbToPb(u):
        c = onb.toCoords(u)
        acc = 0
        for i in range(m):
            if (c >> i) & 1:
                acc ^= gammaToPb[i]
        return acc

    # the change of basis must be a ring homomorphism
    pbField = field.Pb(m, poly)
    for _ in range(64):
        u = rng.getrandbits(m)
        v = rng.getrandbits(m)
        if pbToOnb(pbField.mul(u, v)) != onb.mul(pbToOnb(u), pbToOnb(v)):
            raise RuntimeError('change of basis is not multiplicative (m=%d)' % m)
        if onbToPb(pbToOnb(u)) != u:
            raise RuntimeError('change of basis does not round-trip (m=%d)' % m)

    if cfg['challenge']:
        px, py = pbToOnb(CHALLENGE_PX), pbToOnb(CHALLENGE_PY)
        qx, qy = pbToOnb(CHALLENGE_QX), pbToOnb(CHALLENGE_QY)
        basePoint = (px, py)
        target = (qx, qy)
        if not curve.onCurve(basePoint) or not curve.onCurve(target):
            raise RuntimeError('challenge point is not on the curve')
        if curve.mul(basePoint, ell) is not None or curve.mul(target, ell) is not None:
            raise RuntimeError('challenge point does not have order ell')
        instances = []
    else:
        basePoint = curve.randomPointOfOrder(ell, 4, rng)
        target = curve.mul(basePoint, rng.randrange(1, ell))
        instances = instanceData(onb, curve, ell, rng, cfg['instances'])

    s = curves.frobeniusEigenvalue(curve, basePoint, ell)
    if pow(s, m, ell) != 1 or (s * s + s + 2) % ell != 0:
        raise RuntimeError('bad Frobenius eigenvalue')

    dpW = cfg['dpWeight'] if cfg['dpWeight'] else dpWeightFor(m, ell)
    progs = buildProgs(m, leaf, rng, onb)
    chain = progs['_chain']
    nBits = progs['_nBits']

    sqPerm = []
    for i in range(1, m + 1):
        sqPerm.append(onb.fold(2 * i) - 1)

    lines = []
    ap = lines.append
    ap('// AUTO-GENERATED by codegen/gen.py -- do not edit by hand.')
    ap('// Field GF(2^%d), permuted type-II optimal normal basis, n = %d.' % (m, onb.n))
    ap('#pragma once')
    ap('')
    ap('namespace eccF%d {' % m)
    ap('')
    ap('static const int M = %d;' % m)
    ap('static const int NRING = %d;' % onb.n)
    ap('static const int PRODLEN = %d;' % (2 * m - 1))
    ap('static const int LEAF = %d;' % chain[-1])
    ap('static const int HWBITS = %d;' % nBits)
    ap('static const int DP_WEIGHT = %d;' % dpW)
    ap('static const int PB_TAPS[3] = {%d, %d, %d};' % taps)
    ap('static const char *ELL_DEC = "%d";' % ell)
    ap('static const char *S_DEC = "%d";' % s)
    ap('static const int SIZE_CHAIN[%d] = {%s};' % (len(chain), ', '.join(str(v) for v in chain)))
    ap('static const int SIZE_CHAIN_LEN = %d;' % len(chain))
    ap('')
    ap('// squaring is the index permutation i -> fold(2i) on ONB coordinates')
    ap('static const int SQ_PERM[%d] = {' % m)
    for i in range(0, m, 16):
        ap('    ' + ', '.join(str(v) for v in sqPerm[i:i + 16]) + ',')
    ap('};')
    ap('')
    ap('// P, Q in ONB coordinates (three 64-bit limbs, little endian)')
    ap('static const unsigned long long PX[3] = %s;' % limbLiteral(onb.toCoords(basePoint[0])))
    ap('static const unsigned long long PY[3] = %s;' % limbLiteral(onb.toCoords(basePoint[1])))
    ap('static const unsigned long long QX[3] = %s;' % limbLiteral(onb.toCoords(target[0])))
    ap('static const unsigned long long QY[3] = %s;' % limbLiteral(onb.toCoords(target[1])))
    ap('')
    ap('// change of basis to and from the polynomial basis F_2[z]/(F)')
    ap('static const unsigned long long Z_TO_ONB[%d][3] = {' % m)
    for i in range(m):
        ap('    %s,' % limbLiteral(zToOnb[i]))
    ap('};')
    ap('static const unsigned long long GAMMA_TO_PB[%d][3] = {' % m)
    for i in range(m):
        ap('    %s,' % limbLiteral(gammaToPb[i]))
    ap('};')
    ap('')
    ap('static const int NUM_INSTANCES = %d;' % len(instances))
    if instances:
        ap('static const unsigned long long INSTANCE_PX[%d][3] = {' % len(instances))
        for p, q, k in instances:
            ap('    %s,' % limbLiteral(onb.toCoords(p[0])))
        ap('};')
        ap('static const unsigned long long INSTANCE_PY[%d][3] = {' % len(instances))
        for p, q, k in instances:
            ap('    %s,' % limbLiteral(onb.toCoords(p[1])))
        ap('};')
        ap('static const unsigned long long INSTANCE_QX[%d][3] = {' % len(instances))
        for p, q, k in instances:
            ap('    %s,' % limbLiteral(onb.toCoords(q[0])))
        ap('};')
        ap('static const unsigned long long INSTANCE_QY[%d][3] = {' % len(instances))
        for p, q, k in instances:
            ap('    %s,' % limbLiteral(onb.toCoords(q[1])))
        ap('};')
        ap('static const char *INSTANCE_K[%d] = {' % len(instances))
        for p, q, k in instances:
            ap('    "%d",' % k)
        ap('};')
    else:
        ap('static const unsigned long long (*INSTANCE_PX)[3] = 0;')
        ap('static const unsigned long long (*INSTANCE_PY)[3] = 0;')
        ap('static const unsigned long long (*INSTANCE_QX)[3] = 0;')
        ap('static const unsigned long long (*INSTANCE_QY)[3] = 0;')
        ap('static const char **INSTANCE_K = 0;')
    ap('')

    stats = {}
    for name in ('multPrep', 'toOnb', 'mulLeaf', 'hamming'):
        prog, roots, inputs, outLen = progs[name]
        body, slots = emitFunction(name, prog, roots, inputs, outLen)
        stats[name] = (prog.instrCount(roots), prog.bitOpCount(roots), slots,
                       prog.peakLive(roots))
        ap('// %s: %d instructions (%d two-input bit operations), %d locals, '
           '%d live at the peak'
           % (name, stats[name][0], stats[name][1], slots, stats[name][3]))
        lines.extend(body)
        ap('')
    ap('}  // namespace eccF%d' % m)

    path = '%s/eccF%d.h' % (outDir, m)
    fh = open(path, 'w')
    fh.write('\n'.join(lines) + '\n')
    fh.close()

    if verbose:
        print('m=%3d  n=%3d  ell=%.1f bits  dpWeight=%d  chain=%s' %
              (m, onb.n, __import__('math').log2(ell), dpW, chain))
        for name in ('multPrep', 'toOnb', 'mulLeaf', 'hamming'):
            print('        %-9s %6d instr %6d bitops %4d locals %4d peak live' %
                  (name, stats[name][0], stats[name][1], stats[name][2], stats[name][3]))
        total = stats['multPrep'][0] * 2 + stats['toOnb'][0]
        print('        conversions per multiplication: %d instructions, leaf cutoff %d'
              % (total, progs['_leafCut']))
    return stats


def generatePb(cfg, leaf, outDir, verbose):
    """Emit a polynomial-basis field: arithmetic in F_2[z]/(F), orbit weight
    through one linear map into a normal basis."""
    m = cfg['m']
    rng = random.Random(0x9B00 + m)
    challenge = cfg['challenge']
    if challenge:
        poly, taps = ECC2K95['poly'], ECC2K95['taps']
        ell = ECC2K95['ell']
        if m != 97 or curves.curveOrder(m) != 4 * ell:
            raise RuntimeError('ECC2K-95 order mismatch')
    else:
        poly, taps = curves.findIrreduciblePoly(m)
        ell = curves.curveOrder(m) // 4
        if not curves.isPrimeBig(ell):
            raise RuntimeError('ell not prime for m=%d' % m)
    pb = field.Pb(m, poly)
    if not pb.isIrreducible():
        raise RuntimeError('reduction polynomial is not irreducible')
    curve = curves.CurvePb(pb)

    if challenge:
        basePoint = (ECC2K95['px'], ECC2K95['py'])
        target = (ECC2K95['qx'], ECC2K95['qy'])
        if not curve.onCurve(basePoint) or not curve.onCurve(target):
            raise RuntimeError('challenge point is not on the curve')
        if curve.mul(basePoint, ell) is not None or curve.mul(target, ell) is not None:
            raise RuntimeError('challenge point does not have order ell')
        if curve.mul(basePoint, ECC2K95['knownK']) != target:
            raise RuntimeError('published ECC2K-95 solution does not check out')
        instances = []
        knownK = ECC2K95['knownK']
    else:
        basePoint = curve.randomPointOfOrder(ell, 4, rng)
        target = curve.mul(basePoint, rng.randrange(1, ell))
        instances = []
        for _ in range(cfg['instances']):
            p = curve.randomPointOfOrder(ell, 4, rng)
            k = rng.randrange(1, ell)
            instances.append((p, curve.mul(p, k), k))
        knownK = None

    s = curves.frobeniusEigenvalue(curve, basePoint, ell)
    if pow(s, m, ell) != 1 or (s * s + s + 2) % ell != 0:
        raise RuntimeError('bad Frobenius eigenvalue')

    beta, nbRows, conj = curves.findNormalBasis(pb, m, rng, tries=300)
    # the weight in this basis must be invariant under squaring
    for _ in range(50):
        x = rng.getrandbits(m)
        a = 0
        b = 0
        sx = pb.sqr(x)
        for i in range(m):
            a |= (bin(nbRows[i] & x).count('1') & 1) << i
            b |= (bin(nbRows[i] & sx).count('1') & 1) << i
        if bin(a).count('1') != bin(b).count('1'):
            raise RuntimeError('normal-basis weight is not squaring invariant')
        if (((a << 1) | (a >> (m - 1))) & ((1 << m) - 1)) != b:
            raise RuntimeError('squaring is not a rotation of normal-basis coordinates')

    tapsPos = tuple(t for t in taps if t is not None and t > 0)
    dpW = cfg['dpWeight'] if cfg['dpWeight'] else dpWeightFor(m, ell)
    nBits = 1
    while (1 << nBits) <= m:
        nBits += 1
    chain = sizeChain(m, leaf)

    progs = {}
    bestLeaf = bestMulLeaf(chain[-1])
    progs['mulLeaf'] = (bestLeaf[2], bestLeaf[3], ['a', 'b'], chain[-1])

    pr = ir.Prog()
    hh = [pr.addInput('h', i) for i in range(2 * m - 1)]
    rr = build.pbReduceIr(pr, hh, m, tapsPos)
    pr.fuseLop3(rr)
    progs['reduce'] = (pr, rr, ['h'], 2 * m - 1)

    ps = ir.Prog()
    aa = [ps.addInput('a', i) for i in range(m)]
    ss = build.pbSqrIr(ps, aa, m, tapsPos)
    ps.fuseLop3(ss)
    progs['sqr'] = (ps, ss, ['a'], m)

    bestHam = None
    for blk in (1, 4, 6):
        p = ir.Prog()
        xx = [p.addInput('x', i) for i in range(m)]
        hb = build.pbHammingIr(p, xx, nbRows, blk, nBits)
        p.fuseLop3(hb)
        if bestHam is None or p.instrCount(hb) < bestHam[0]:
            bestHam = (p.instrCount(hb), p, hb)
    progs['hamming'] = (bestHam[1], bestHam[2], ['x'], m)

    verifyPbMul(m, tapsPos, pb, rng, bestLeaf[1])

    lines = []
    ap = lines.append
    ap('// AUTO-GENERATED by codegen/gen.py -- do not edit by hand.')
    ap('// Field GF(2^%d) = F_2[z]/(F), polynomial basis.' % m)
    ap('// The orbit weight is taken in a normal basis reached by one linear map,')
    ap('// which is how Harley solved ECC2K-95 in 1998.')
    ap('#pragma once')
    ap('')
    ap('namespace eccP%d {' % m)
    ap('')
    ap('static const int M = %d;' % m)
    ap('static const int NRING = 0;   // no cyclic ring: this is a polynomial basis')
    ap('static const int PRODLEN = %d;' % (2 * m - 1))
    ap('static const int LEAF = %d;' % chain[-1])
    ap('static const int HWBITS = %d;' % nBits)
    ap('static const int DP_WEIGHT = %d;' % dpW)
    ap('static const int PB_TAPS[3] = {%d, %d, %d};' % (taps[0], taps[1], taps[2]))
    ap('static const char *ELL_DEC = "%d";' % ell)
    ap('static const char *S_DEC = "%d";' % s)
    ap('static const int SIZE_CHAIN[%d] = {%s};' % (len(chain), ', '.join(str(v) for v in chain)))
    ap('static const int SIZE_CHAIN_LEN = %d;' % len(chain))
    ap('')
    ap('static const unsigned long long PX[3] = %s;' % limbLiteral(basePoint[0]))
    ap('static const unsigned long long PY[3] = %s;' % limbLiteral(basePoint[1]))
    ap('static const unsigned long long QX[3] = %s;' % limbLiteral(target[0]))
    ap('static const unsigned long long QY[3] = %s;' % limbLiteral(target[1]))
    ap('[[maybe_unused]] static const char *KNOWN_K = %s;' % (('"%d"' % knownK) if knownK else '0'))
    ap('')
    ap('// rows of the polynomial-basis to normal-basis map, for the host reference')
    ap('static const unsigned long long NB_ROWS[%d][3] = {' % m)
    for i in range(m):
        ap('    %s,' % limbLiteral(nbRows[i]))
    ap('};')
    ap('')
    ap('static const int NUM_INSTANCES = %d;' % len(instances))
    if instances:
        for name, idx in (('INSTANCE_PX', (0, 0)), ('INSTANCE_PY', (0, 1)),
                          ('INSTANCE_QX', (1, 0)), ('INSTANCE_QY', (1, 1))):
            ap('static const unsigned long long %s[%d][3] = {' % (name, len(instances)))
            for inst in instances:
                ap('    %s,' % limbLiteral(inst[idx[0]][idx[1]]))
            ap('};')
        ap('static const char *INSTANCE_K[%d] = {' % len(instances))
        for inst in instances:
            ap('    "%d",' % inst[2])
        ap('};')
    else:
        ap('static const unsigned long long (*INSTANCE_PX)[3] = 0;')
        ap('static const unsigned long long (*INSTANCE_PY)[3] = 0;')
        ap('static const unsigned long long (*INSTANCE_QX)[3] = 0;')
        ap('static const unsigned long long (*INSTANCE_QY)[3] = 0;')
        ap('static const char **INSTANCE_K = 0;')
    ap('')

    stats = {}
    for name in ('mulLeaf', 'reduce', 'sqr', 'hamming'):
        prog, roots, inputs, outLen = progs[name]
        body, slots = emitFunction(name, prog, roots, inputs, outLen)
        stats[name] = (prog.instrCount(roots), prog.bitOpCount(roots), slots,
                       prog.peakLive(roots))
        ap('// %s: %d instructions (%d two-input bit operations), %d locals, '
           '%d live at the peak'
           % (name, stats[name][0], stats[name][1], slots, stats[name][3]))
        lines.extend(body)
        ap('')
    ap('}  // namespace eccP%d' % m)

    path = '%s/eccP%d.h' % (outDir, m)
    fh = open(path, 'w')
    fh.write('\n'.join(lines) + '\n')
    fh.close()

    if verbose:
        import math as _m
        print('m=%3d  polynomial basis  ell=%.1f bits  dpWeight=%d  taps=%s' %
              (m, _m.log2(ell), dpW, str(tapsPos)))
        for name in ('mulLeaf', 'reduce', 'sqr', 'hamming'):
            print('        %-9s %6d instr %6d bitops %4d locals %4d peak live' %
                  (name, stats[name][0], stats[name][1], stats[name][2], stats[name][3]))
    return stats


def verifyPbMul(m, tapsPos, pb, rng, cut):
    prog = ir.Prog()
    a = [prog.addInput('a', i) for i in range(m)]
    b = [prog.addInput('b', i) for i in range(m)]
    r = build.pbMulIr(prog, a, b, m, tapsPos, cut)
    xs = []
    ys = []
    for _ in range(64):
        xs.append(rng.getrandbits(m))
        ys.append(rng.getrandbits(m))
    vals = {}
    for i in range(m):
        wa = 0
        wb = 0
        for lane in range(64):
            if (xs[lane] >> i) & 1:
                wa |= 1 << lane
            if (ys[lane] >> i) & 1:
                wb |= 1 << lane
        vals[('a', i)] = wa
        vals[('b', i)] = wb
    out = prog.evaluate(vals, r)
    for lane in range(64):
        got = 0
        for i in range(m):
            if (out[i] >> lane) & 1:
                got |= 1 << i
        if got != pb.mul(xs[lane], ys[lane]):
            raise RuntimeError('polynomial-basis multiplication mismatch, m=%d' % m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='../generated')
    ap.add_argument('--leaf', type=int, default=0,
                    help='generated-leaf size; 0 picks the largest that fits --regs')
    ap.add_argument('--regs', type=int, default=255,
                    help='live values a leaf may use before the compiler spills')
    ap.add_argument('--no-schedule', dest='schedule', action='store_false',
                    help='emit in construction order (the pre-scheduling control)')
    ap.add_argument('--only', type=int, default=0)
    ap.add_argument('--basis', default='')
    args = ap.parse_args()
    global SCHEDULE
    SCHEDULE = args.schedule

    def leafFor(cfg):
        if args.leaf:
            return args.leaf
        return chooseLeaf(cfg['m'], args.regs)

    for cfg in CURVES:
        if args.only and cfg['m'] != args.only:
            continue
        if args.basis and cfg.get('basis', 'onb') != args.basis:
            continue
        if cfg.get('basis', 'onb') == 'pb':
            generatePb(cfg, leafFor(cfg), args.out, True)
        else:
            generate(cfg, leafFor(cfg), args.out, True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
