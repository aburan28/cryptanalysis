#!/usr/bin/env python3
# Read the emitted Verilog back from disk and simulate it against field.Onb.
#
#   python3 testverilog.py [--rtl ../generated/rtl] [--m 131] [--vectors 8]
#
# genverilog.py emits RTL from the same straight-line IR gen.py already checks,
# so what is left to go wrong is the *emission*: a mis-indexed coordinate, an
# operand read from the wrong pipeline stage, a register chain one short, an
# output tied to the wrong wire.  None of those show up in the IR.
#
# So this reads the .v files as text, parses them with a small evaluator that
# knows nothing about the generator, and runs them as a synchronous circuit:
# drive one operand pair per clock, advance the registers, and compare the
# output stream against field.Onb.  It also recovers the latency and the
# initiation interval from the simulated waveform rather than trusting the
# module header, which is the pair of claims an FPGA design lives on.
#
# This is not a substitute for a real simulator -- it covers the subset of
# Verilog the generator emits and nothing else.  tb_ecc_mul131.v is there for
# Icarus, Verilator or Vivado when a toolchain exists.
#
# No type hints, camelCase identifiers, no itertools (project convention).

import argparse
import os
import random
import re

import field

WIRE = re.compile(r'^\s*wire\s+(w\d+)\s*=\s*(.+);\s*$')
REGA = re.compile(r'^\s*(r\d+_\d+)\s*<=\s*(\S+);\s*$')
OUTA = re.compile(r"^\s*assign\s+(\w+)\[(\d+)\]\s*=\s*(\S+);\s*$")
LAT = re.compile(r'latency (\d+) clocks')
PERM = re.compile(r"^\s*assign\s+(\w+)\[(\d+)\]\s*=\s*(\w+)\[(\d+)\];\s*$")
MUX = re.compile(r"^\s*wire\s+\[\d+:0\]\s+(\w+)\s*=\s*sel\[(\d)\]\s*\?\s*(\w+)\s*:\s*(\w+);\s*$")


def parseModule(path):
    """Parse the subset of Verilog genverilog.py emits.

    Returns the combinational assignments in emission (topological) order, the
    register transfers, the output bit map and the latency the header claims.
    """
    assigns = []
    regs = []
    outputs = {}
    latency = None
    fh = open(path)
    for line in fh:
        if latency is None:
            got = LAT.search(line)
            if got:
                latency = int(got.group(1))
        got = WIRE.match(line)
        if got:
            assigns.append((got.group(1), tokenize(got.group(2))))
            continue
        got = REGA.match(line)
        if got:
            regs.append((got.group(1), got.group(2)))
            continue
        got = OUTA.match(line)
        if got:
            outputs.setdefault(got.group(1), {})[int(got.group(2))] = got.group(3)
    fh.close()
    return assigns, regs, outputs, latency


def tokenize(expr):
    return expr.replace('(', ' ( ').replace(')', ' ) ').split()


def evalExpr(tok, vals):
    """Evaluate one emitted right-hand side.  1-bit values only.

    The grammar is the subset genverilog.py emits: ~, &, ^ and | over one-bit
    nets, with Verilog precedence (~ binds tightest, then &, then ^, then |)
    and explicit parentheses around the fused forms.  Parsing it properly
    rather than matching shapes keeps this honest when the IR grows an op --
    the majority gate in the weight tree is what broke shape matching.
    """
    pos = [0]
    out = parseOr(tok, pos, vals)
    if pos[0] != len(tok):
        raise ValueError('unparsed expression: %s' % ' '.join(tok))
    return out


def parsePrimary(tok, pos, vals):
    if pos[0] >= len(tok):
        raise ValueError('expression ended early: %s' % ' '.join(tok))
    head = tok[pos[0]]
    if head == '(':
        pos[0] += 1
        out = parseOr(tok, pos, vals)
        if pos[0] >= len(tok) or tok[pos[0]] != ')':
            raise ValueError('missing ) in %s' % ' '.join(tok))
        pos[0] += 1
        return out
    if head == '~':
        pos[0] += 1
        return 1 - parsePrimary(tok, pos, vals)
    pos[0] += 1
    return lookup(head, vals)


def parseAnd(tok, pos, vals):
    out = parsePrimary(tok, pos, vals)
    while pos[0] < len(tok) and tok[pos[0]] == '&':
        pos[0] += 1
        out = out & parsePrimary(tok, pos, vals)
    return out


def parseXor(tok, pos, vals):
    out = parseAnd(tok, pos, vals)
    while pos[0] < len(tok) and tok[pos[0]] == '^':
        pos[0] += 1
        out = out ^ parseAnd(tok, pos, vals)
    return out


def parseOr(tok, pos, vals):
    out = parseXor(tok, pos, vals)
    while pos[0] < len(tok) and tok[pos[0]] == '|':
        pos[0] += 1
        out = out | parseXor(tok, pos, vals)
    return out


def lookup(name, vals):
    if name == "1'b0":
        return 0
    if name == "1'b1":
        return 1
    return vals[name]


def simulate(assigns, regs, outputs, outName, width, drive, cycles):
    """Run the circuit for `cycles` clocks.  drive(t) sets the input bits.

    Returns the output word sampled at the end of every cycle.
    """
    vals = {}
    for name, _ in regs:
        vals[name] = 0
    trace = []
    for t in range(cycles):
        vals.update(drive(t))
        for name, tok in assigns:
            vals[name] = evalExpr(tok, vals)
        word = 0
        for k in range(width):
            src = outputs[outName].get(k)
            if src is not None and lookup(src, vals):
                word |= 1 << k
        trace.append(word)
        nxt = {}
        for dst, src in regs:
            nxt[dst] = lookup(src, vals)
        vals.update(nxt)
    return trace


def findLatency(trace, expected):
    """Recover the pipeline latency from the waveform, and check II = 1."""
    n = len(expected)
    for d in range(len(trace) - n + 1):
        ok = True
        for i in range(n):
            if trace[d + i] != expected[i]:
                ok = False
                break
        if ok:
            return d
    return None


def driveWords(names, widths, words):
    bits = {}
    for k in range(len(names)):
        for i in range(widths[k]):
            bits['%s[%d]' % (names[k], i)] = (words[k] >> i) & 1
    return bits


def checkMul(rtl, m, onb, rng, count):
    path = os.path.join(rtl, 'ecc_mul%d.v' % m)
    assigns, regs, outputs, claimed = parseModule(path)
    vectors = []
    for k in range(count):
        u = onb.randomElement(rng)
        v = onb.randomElement(rng)
        vectors.append((onb.toCoords(u), onb.toCoords(v),
                        onb.toCoords(onb.mul(u, v))))
    idle = (0, 0, 0)

    def drive(t):
        row = vectors[t] if t < len(vectors) else idle
        return driveWords(['a', 'b'], [m, m], [row[0], row[1]])

    cycles = count + claimed + 4
    trace = simulate(assigns, regs, outputs, 'p', m, drive, cycles)
    expected = []
    for row in vectors:
        expected.append(row[2])
    got = findLatency(trace, expected)
    if got is None:
        raise RuntimeError('ecc_mul%d: product stream never matched field.Onb' % m)
    if got != claimed:
        raise RuntimeError('ecc_mul%d: latency is %d clocks, header claims %d'
                           % (m, got, claimed))
    print('ecc_mul%d.v: PASS -- %d multiplications, II=1, latency %d clk, '
          'checked against field.Onb' % (m, count, got))
    return got


def checkHamming(rtl, m, nBits, rng, count):
    path = os.path.join(rtl, 'ecc_hamming%d.v' % m)
    assigns, regs, outputs, claimed = parseModule(path)
    vectors = []
    for _ in range(count):
        vectors.append(rng.getrandbits(m))

    def drive(t):
        word = vectors[t] if t < len(vectors) else 0
        return driveWords(['x'], [m], [word])

    trace = simulate(assigns, regs, outputs, 'hw', nBits, drive,
                     count + claimed + 4)
    expected = []
    for v in vectors:
        expected.append(bin(v).count('1'))
    got = findLatency(trace, expected)
    if got is None:
        raise RuntimeError('ecc_hamming%d: weights never matched popcount' % m)
    print('ecc_hamming%d.v: PASS -- %d weights, II=1, latency %d clk'
          % (m, count, got))


def checkSigma(rtl, m, onb, rng, trials):
    """The Frobenius module is pure wiring; check the permutation it wires."""
    path = os.path.join(rtl, 'ecc_sigma%d.v' % m)
    perms = {}
    muxes = []
    fh = open(path)
    for line in fh:
        got = PERM.match(line)
        if got:
            dst, di, src, si = got.group(1), int(got.group(2)), got.group(3), int(got.group(4))
            perms.setdefault(dst, {})[di] = (src, si)
            continue
        got = MUX.match(line)
        if got:
            muxes.append((got.group(1), int(got.group(2)), got.group(3), got.group(4)))
    fh.close()
    if not perms or len(muxes) != 3:
        raise RuntimeError('ecc_sigma%d: expected one permutation set and 3 muxes' % m)

    def valueOf(netName, sel, xBits, cache):
        if netName == 'x':
            return xBits
        if netName in cache:
            return cache[netName]
        for name, bit, onNet, offNet in muxes:
            if name == netName:
                chosen = onNet if (sel >> bit) & 1 else offNet
                out = valueOf(chosen, sel, xBits, cache)
                cache[netName] = out
                return out
        table = perms[netName]
        src = [None] * m
        for di in range(m):
            srcName, si = table[di]
            src[di] = valueOf(srcName, sel, xBits, cache)[si]
        cache[netName] = src
        return src

    for _ in range(trials):
        u = onb.randomElement(rng)
        coords = onb.toCoords(u)
        xBits = []
        for i in range(m):
            xBits.append((coords >> i) & 1)
        for sel in range(8):
            out = valueOf('c2', sel, xBits, {})
            got = 0
            for i in range(m):
                if out[i]:
                    got |= 1 << i
            want = u
            for _ in range(3 + sel):
                want = onb.mul(want, want)
            if got != onb.toCoords(want):
                raise RuntimeError('ecc_sigma%d: sel=%d is not sigma^%d'
                                   % (m, sel, 3 + sel))
    print('ecc_sigma%d.v: PASS -- sigma^(3+sel) for all 8 selects, %d elements, '
          '0 gates' % (m, trials))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rtl', default=os.path.join('..', 'generated', 'rtl'))
    ap.add_argument('--m', type=int, default=131)
    ap.add_argument('--vectors', type=int, default=8)
    args = ap.parse_args()

    m = args.m
    rng = random.Random(0xF00D0000 + m)
    onb = field.Onb(m)
    nBits = 1
    while (1 << nBits) <= m:
        nBits += 1

    checkMul(args.rtl, m, onb, rng, args.vectors)
    checkHamming(args.rtl, m, nBits, rng, args.vectors)
    checkSigma(args.rtl, m, onb, rng, 4)
    print('all emitted modules agree with field.Onb')


if __name__ == '__main__':
    main()
