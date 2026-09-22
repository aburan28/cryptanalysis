"""Generate packed linear ONB/optimal-polynomial-basis conversions.

The inverse parity recursion can be reordered by shift distance. For each
distance h, the product of suffix-XOR factors is (1+R_h)^popcount(i mod h).
In characteristic two, its binary exponent bits select shifts h*2^j. This
groups many scalar-coefficient XORs into masked operations on 32-bit words.
"""
import argparse
from pathlib import Path
import random
import build
import ir


def stages(n, inverse):
    result = []
    if inverse:
        h = 2
        while h < n:
            for j in range(h.bit_length().bit_length()):
                shift = h << j
                if shift >= n:
                    break
                mask = sum(((bin(i & (h-1)).count('1') >> j) & 1) << i
                           for i in range(n-shift))
                if mask:
                    result.append((shift, mask))
            h *= 2
    else:
        s = 1 << (n.bit_length()-1)
        while s:
            shift = 2*s
            mask = sum(bool(i & s) << i for i in range(max(0,n-shift)))
            if mask:
                result.append((shift,mask))
            s //= 2
    return result


def check(n, inverse):
    p = ir.Prog()
    inputs = [p.addInput('a',i) for i in range(n)]
    roots = (build.unexpandIr if inverse else build.expandIr)(p,inputs)
    # All basis vectors establish equality of these linear transformations.
    rng = random.Random(n)
    for x in [1 << i for i in range(n)] + [rng.getrandbits(n) for _ in range(32)]:
        expected = sum(v << i for i,v in enumerate(p.evaluate({('a',i):(x>>i)&1 for i in range(n)},roots)))
        actual = x
        for shift,mask in stages(n,inverse):
            actual ^= (actual >> shift) & mask
        if actual != expected:
            raise ValueError(('packed transform mismatch', n, inverse, x))


def wordTail(tail):
    """Compose the final word-aligned stages as a triangular linear map."""
    if any(shift % 32 for shift, _ in tail):
        raise ValueError('non-word transform tail')
    coeff = [[0xffffffff if i == j else 0 for j in range(5)] for i in range(5)]
    for shift, mask in tail:
        offset = shift // 32
        for i in range(5-offset):
            wordmask = (mask >> (32*i)) & 0xffffffff
            for j in range(5):
                coeff[i][j] ^= coeff[i+offset][j] & wordmask
    for bit in range(160):
        x = 1 << bit
        for shift, mask in tail:
            x ^= (x >> shift) & mask
        words = [(1 << (bit % 32)) if bit // 32 == i else 0 for i in range(5)]
        out = [0] * 5
        for i in range(5):
            for j in range(5):
                out[i] ^= words[j] & coeff[i][j]
        if sum(v << (32*i) for i, v in enumerate(out)) != x:
            raise ValueError('composed transform tail differs')
    lines = ['    // Compose the word-aligned triangular transform stages.']
    for i in range(5):
        parts = ['(v%d & 0x%08xu)' % (j, coeff[i][j])
                 for j in range(i+1,5) if coeff[i][j]]
        if parts:
            lines.append('    v%d ^= ' % i + ' ^ '.join(parts) + ';')
    return lines


def checkByteFunnels():
    # These byte selectors are linear maps of two 32-bit words. All 64
    # input basis vectors establish equality to the corresponding funnel.
    for shift, selector in ((8, 0x4321), (16, 0x5432), (24, 0x6543)):
        for bit in range(64):
            x = 1 << bit
            actual = sum(((x >> (8*((selector >> (4*i)) & 7))) & 255) << (8*i)
                         for i in range(4))
            if actual != ((x >> shift) & 0xffffffff):
                raise ValueError('byte funnel selector differs')


def emitStages(n, inverse, combineTail=False, byteFunnels=False):
    words = (n+31)//32
    lines = []
    allStages = stages(n,inverse)
    for stage, (shift,mask) in enumerate(allStages):
        if combineTail and n == 131 and inverse and shift >= 32:
            lines += wordTail(allStages[stage:])
            break
        offset, bits = divmod(shift,32)
        lines.append('    // shift %d' % shift)
        # Increasing destinations preserve all higher source words in-place.
        for i in range(words):
            wordMask = (mask >> (32*i)) & 0xffffffff
            if not wordMask:
                continue
            expr = 'v%d' % (i+offset)
            if byteFunnels and bits in (8, 16, 24) and i+offset+1 < words:
                selector = {8: 0x4321, 16: 0x5432, 24: 0x6543}[bits]
                expr = 'goal22BytePerm(v%d,v%d,0x%04xu)' % (i+offset, i+offset+1, selector)
            elif bits:
                expr += ' >> %d' % bits
                if i+offset+1 < words:
                    expr = '(%s) | (v%d << %d)' % (expr,i+offset+1,32-bits)
            if wordMask == 0xffffffff:
                lines.append('    v%d ^= %s;' % (i,expr))
            else:
                lines.append('    v%d ^= (%s) & 0x%08xu;' % (i,expr,wordMask))
    return lines


def generate():
    check(131,True); check(261,False)
    checkByteFunnels()
    lines = ['// Generated by codegen/genpacked.py. Included inside eccPacked131.',
             '#pragma once', 'ECC_HD P131 toPolynomial131(const P131 &a) {',
             '    const uint32_t sign = 0u - ((a.v[4] >> 2) & 1u);']
    for i in range(5):
        expr = '(a.v[%d] << 1)' % i
        if i:
            expr += ' | (a.v[%d] >> 31)' % (i-1)
        expr = '(%s) ^ sign' % expr
        if i == 4:
            expr = '(%s) & 7u' % expr
        lines.append('    uint32_t v%d = %s;' % (i,expr))
    lines += ['#if ECC_FROBENIUS_FUSED'] + emitStages(131,True,True,True)
    lines += ['#else'] + emitStages(131,True) + ['#endif']
    lines += ['    return P131{{v0,v1,v2,v3,v4}};', '}',
              'ECC_HD P131 fromPolynomialProduct131(const uint32_t *h) {']
    for i in range(9):
        lines.append('    uint32_t v%d = h[%d];' % (i,i))
    lines += ['#if ECC_FROBENIUS_FUSED'] + emitStages(261,False,byteFunnels=True)
    lines += ['#else'] + emitStages(261,False) + ['#endif']
    lines += ['    const uint32_t sign = 0u - (v0 & 1u);','    P131 out;']
    for i in range(5):
        expr = '((v%d >> 1) | (v%d << 31)) ^ ((reverse32(v%d) >> 25) | (reverse32(v%d) << 7)) ^ sign' % (i,i+1,8-i,7-i)
        if i==4:
            expr='((v4 >> 1) ^ (reverse32(v4) >> 25) ^ sign) & 7u'
        lines.append('    out.v[%d] = %s;' % (i,expr))
    lines += ['    return out;','}']
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='../include/packedtransform131.h')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    generated=generate()
    if args.check:
        if Path(args.out).read_text()!=generated:
            raise SystemExit('packed transform header does not match the generator')
        print('Packed transforms verified; generated header matches:',args.out)
    else:
        Path(args.out).write_text(generated)
        print('Packed transforms verified on every basis vector and generated:',args.out)
