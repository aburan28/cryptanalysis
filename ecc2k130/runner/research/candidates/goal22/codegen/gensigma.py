"""Generate exact Frobenius bit permutations using a Beneš swap network.

Bit i represents gamma_(i+1), so sigma^k sends it to
gamma_(2^k*(i+1) mod 263), folded by gamma_j = gamma_(263-j).
Padding to 256 bits permits a common network topology for every exponent.
All 256 basis vectors are checked for every generated permutation.
"""
import argparse
import re
from pathlib import Path


def interleave(mask, parity):
    out = 0
    for i in range(mask.bit_length()):
        out |= ((mask >> i) & 1) << (2*i + parity)
    return out


def route(perm):
    n = len(perm)
    if n == 2:
        return [(1, int(perm[0] != 0))]
    inv = [0]*n
    for i, j in enumerate(perm):
        inv[j] = i
    color = [-1]*n
    for root in range(n):
        if color[root] >= 0:
            continue
        color[root] = root & 1
        todo = [root]
        while todo:
            i = todo.pop()
            for j in (i ^ 1, inv[perm[i] ^ 1]):
                if color[j] < 0:
                    color[j] = color[i] ^ 1
                    todo.append(j)
                elif color[j] == color[i]:
                    raise ValueError('inconsistent route coloring')
    first = sum(color[i] << i for i in range(0, n, 2))
    last = sum(color[inv[j]] << j for j in range(0, n, 2))
    sub = [[0]*(n//2) for _ in range(2)]
    for i, j in enumerate(perm):
        sub[color[i]][i//2] = j//2
    a, b = route(sub[0]), route(sub[1])
    middle = [(2*d, interleave(ma, 0) | interleave(mb, 1))
              for (d, ma), (_, mb) in zip(a, b)]
    return [(1, first)] + middle + [(1, last)]


def permutation(k):
    p = list(range(256))
    for i in range(131):
        j = ((i+1)*pow(2, k, 263)) % 263
        p[i] = min(j, 263-j)-1
    return p


def networks():
    nets = []
    for k in range(131):
        p = permutation(k)
        net = route(p)
        for i in range(256):
            x = 1 << i
            for d, mask in net:
                t = ((x >> d) ^ x) & mask
                x ^= t ^ (t << d)
            if x != 1 << p[i]:
                raise ValueError(('bad permutation', k, i))
        nets.append(net)
    return nets


def emitGroup(nets, name, exponents, columns):
    chosen = [nets[k] for k in exponents]
    ops = []
    for stage in range(len(chosen[0])):
        d = chosen[0][stage][0]
        for word in range(8):
            masks = [(net[stage][1] >> (32*word)) & 0xffffffff for net in chosen]
            if any(masks):
                ops.append((d, word, masks))
    unique = list(dict.fromkeys(tuple(row) for _,_,row in ops))
    storage = 'ECC_SIGMA_INV_STORAGE' if name == 'sigmaInvNetwork131' else 'ECC_SIGMA_WALK_STORAGE'
    lines = [storage+' uint32_t %sMasks[%d][%d] = {' % (name,len(unique),columns)]
    for row in unique:
        masks = list(row)+[0]*(columns-len(row))
        lines.append('    {'+','.join('0x%08xu' % v for v in masks)+'},')
    lines += ['};', 'static ECC_BIG P131 %s(P131 a, int index) {' % name,
              '#if defined(__CUDACC__) && !defined(__CUDA_ARCH__)',
              '    const int exponents[] = {'+','.join(map(str,exponents))+'};',
              '    for (int i=0;i<exponents[index];i++) a=sqr131(a);', '    return a;', '#else',
              '    uint32_t v0=a.v[0], v1=a.v[1], v2=a.v[2], v3=a.v[3], v4=a.v[4];',
              '    uint32_t v5=0, v6=0, v7=0, t, mask;']
    for d, word, row in ops:
        idx = unique.index(tuple(row))
        deviceLoad = ('%sMasks[%d][index]' % (name,idx)) if name == 'sigmaInvNetwork131' else ('__ldg(&%sMasks[%d][index])' % (name,idx))
        lines += ['#ifdef __CUDA_ARCH__',
                  '    mask='+deviceLoad+';',
                  '#else', '    mask=%sMasks[%d][index];' % (name,idx), '#endif']
        if d < 32:
            lines += ['    t=((v%d >> %d)^v%d)&mask;' % (word,d,word),
                      '    v%d^=t^(t << %d);' % (word,d)]
        else:
            other = word+d//32
            if other >= 8:
                raise ValueError('unexpected word pair')
            lines += ['    t=(v%d^v%d)&mask;' % (word,other),
                      '    v%d^=t; v%d^=t;' % (word,other)]
    lines += ['    return P131{{v0,v1,v2,v3,v4&7u}};', '#endif', '}']
    return lines, len(ops)


def emitWalkPair(nets):
    # Keep the scalar emitter and its table unchanged. The paired network
    # uses precisely the same operation order and deduplicated mask indices.
    exponents = list(range(3,11))
    chosen = [nets[k] for k in exponents]
    ops = []
    for stage in range(len(chosen[0])):
        d = chosen[0][stage][0]
        for word in range(8):
            masks = [(net[stage][1] >> (32*word)) & 0xffffffff for net in chosen]
            if any(masks):
                ops.append((d, word, masks))
    unique = list(dict.fromkeys(tuple(row) for _,_,row in ops))
    lines = ['#if ECC_PACKED_WEIGHTED_PREFIX == 2',
             'struct SigmaWalkPair131 { P131 first, second; };',
             'static ECC_BIG SigmaWalkPair131 sigmaWalkNetworkPair131(P131 a, P131 b, int index) {',
             '#if defined(__CUDACC__) && !defined(__CUDA_ARCH__)',
             '    const int exponents[] = {'+','.join(map(str,exponents))+'};',
             '    for (int i=0;i<exponents[index];i++) { a=sqr131(a); b=sqr131(b); }',
             '    return SigmaWalkPair131{a,b};', '#else',
             '    uint32_t a0=a.v[0], a1=a.v[1], a2=a.v[2], a3=a.v[3], a4=a.v[4];',
             '    uint32_t b0=b.v[0], b1=b.v[1], b2=b.v[2], b3=b.v[3], b4=b.v[4];',
             '    uint32_t a5=0, a6=0, a7=0, b5=0, b6=0, b7=0, t, mask;']
    for d, word, row in ops:
        idx = unique.index(tuple(row))
        lines += ['#ifdef __CUDA_ARCH__',
                  '    mask=__ldg(&sigmaWalkNetwork131Masks[%d][index]);' % idx,
                  '#else', '    mask=sigmaWalkNetwork131Masks[%d][index];' % idx, '#endif']
        for value in ('a', 'b'):
            if d < 32:
                lines += ['    t=((%s%d >> %d)^%s%d)&mask;' % (value,word,d,value,word),
                          '    %s%d^=t^(t << %d);' % (value,word,d)]
            else:
                other = word+d//32
                if other >= 8:
                    raise ValueError('unexpected word pair')
                lines += ['    t=(%s%d^%s%d)&mask;' % (value,word,value,other),
                          '    %s%d^=t; %s%d^=t;' % (value,word,value,other)]
    lines += ['    return SigmaWalkPair131{P131{{a0,a1,a2,a3,a4&7u}},P131{{b0,b1,b2,b3,b4&7u}}};',
              '#endif', '}', '#endif']
    return lines


def emitSharedWalkPair(nets):
    # Reuse the same generated operations and deduplicated mask row indices.
    # The global helper above remains byte-identical and separately callable.
    original = emitWalkPair(nets)
    shared = original[2:-1]
    shared = [line.replace('sigmaWalkNetworkPair131(', 'sigmaWalkNetworkPairShared131(')
              for line in shared]
    shared = [re.sub(r'__ldg\(&sigmaWalkNetwork131Masks\[(\d+)\]\[index\]\)',
                     r'sigmaWalkShared131Masks[\1][index]', line) for line in shared]
    walk, _ = emitGroup(nets, 'sigmaWalkNetwork131', list(range(3,11)), 8)
    rows = int(re.search(r'Masks\[(\d+)\]\[8\]', walk[0]).group(1))
    lines = ['#if ECC_PACKED_SHARED_SIGMA',
             '#ifdef __CUDACC__',
             'static __shared__ uint32_t sigmaWalkShared131Masks[%d][8];' % rows,
             '#endif',
             'static ECC_HD void initSigmaWalkShared131() {',
             '#ifdef __CUDA_ARCH__',
             '    for (unsigned i=threadIdx.x; i<%du; i+=blockDim.x)' % (rows*8),
             '        sigmaWalkShared131Masks[i/8][i%8]=__ldg(&sigmaWalkNetwork131Masks[i/8][i%8]);',
             '    __syncthreads();',
             '#endif', '}',
             '// Host code emulates the post-barrier values through the original',
             '// immutable table; it does not emulate CUDA block concurrency.']
    return lines + shared + ['#endif']


def generate():
    nets = networks()
    lines = ['// Generated by codegen/gensigma.py; included inside eccPacked131.',
             '#pragma once', '#ifdef __CUDACC__',
             '#define ECC_SIGMA_WALK_STORAGE static __device__ __align__(32) const',
             '#define ECC_SIGMA_INV_STORAGE static __constant__ __align__(32) const', '#else',
             '#define ECC_SIGMA_WALK_STORAGE alignas(32) static const',
             '#define ECC_SIGMA_INV_STORAGE alignas(32) static const', '#endif']
    walk, nw = emitGroup(nets, 'sigmaWalkNetwork131', list(range(3,11)), 8)
    inv, ni = emitGroup(nets, 'sigmaInvNetwork131', [16,32,65], 4)
    lines += walk + inv + emitWalkPair(nets) + emitSharedWalkPair(nets) + ['#undef ECC_SIGMA_WALK_STORAGE', '#undef ECC_SIGMA_INV_STORAGE']
    return '\n'.join(lines)+'\n', (nw,ni)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='../include/packedsigma131.h')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    generated, n = generate()
    if args.check:
        if Path(args.out).read_text() != generated:
            raise SystemExit('Frobenius header does not match the generator')
    else:
        Path(args.out).write_text(generated)
    print('PASS: all 256 basis vectors for all 131 Frobenius powers; word operations', n)
