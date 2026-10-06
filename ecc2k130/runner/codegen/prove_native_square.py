"""Exact Boolean-polynomial equivalence of the source's 32-to-64 bit spread.

No CUDA execution is modeled: this proves the algebra under the documented
CLMAD semantics, not the compiler, hardware, or performance.
"""
import hashlib
import json
from pathlib import Path
import re

HEADER = Path(__file__).resolve().parents[1] / 'include' / 'packed131.h'


def multiply(a, b):
    # ANF monomials are sets of variables, encoded as bit masks. Boolean
    # variables obey x_i^2=x_i. XOR cancels duplicate monomials.
    out = set()
    for x in a:
        for y in b:
            term = x | y
            out.symmetric_difference_update({term})
    return out


def bit_or(a, b):
    return a ^ b ^ multiply(a, b)


def prove(source):
    match = re.search(r'ECC_HD uint64_t spread32p\(uint32_t x\)\{(.*?)\n\}', source, re.S)
    if not match:
        raise ValueError('unsupported spread32p source shape')
    body = re.sub(r'//[^\n]*', '', match.group(1))
    # Fail closed if the native operands, zero extension, result selection,
    # type, guards or return expression change.
    native, fallback = body.split('#else')
    expected = '''#if ECC_PACKED_CLMAD_SQUARE && defined(__CUDA_ARCH__)
        const uint64_t a = uint64_t(x);
        uint64_t r;
        asm("clmad.lo.u64 %0, %1, %1, 0;" : "=l"(r) : "l"(a));
        return r;'''
    compact = lambda text: re.sub(r'\s+', '', text)
    if compact(native) != compact(expected):
        raise ValueError('native branch is outside the proved source contract')
    lines = [line.strip() for line in fallback.splitlines() if line.strip()]
    if lines[0] != 'uint64_t r=x;' or lines[-2:] != ['return r;', '#endif']:
        raise ValueError('unsupported fallback declaration or return')

    inputs = [{1 << i} for i in range(32)] + [set() for _ in range(32)]
    spread = [set(bit) for bit in inputs]
    stages = []
    for line in lines[1:-2]:
        step = re.fullmatch(r'r=\(r\|\(r<<(\d+)\)\)&(0x[0-9a-fA-F]+)ull;', line)
        if not step:
            raise ValueError('unsupported fallback statement: ' + line)
        shift, mask = int(step[1]), int(step[2], 16)
        if not 0 <= shift < 64 or mask >= 1 << 64:
            raise ValueError('invalid 64-bit shift/mask')
        spread = [bit_or(spread[i], spread[i-shift] if i >= shift else set())
                  if (mask >> i) & 1 else set() for i in range(64)]
        stages.append({'shift': shift, 'mask': hex(mask)})

    # Independently expand the full 64x64 carryless product, then select low
    # 64 bits. This includes the cross terms instead of assuming cancellation.
    product = [set() for _ in range(128)]
    for i, a in enumerate(inputs):
        for j, b in enumerate(inputs):
            product[i+j] ^= multiply(a, b)
    if any(product[64:]):
        raise AssertionError('nonzero product discarded by low-half selection')
    differing = [i for i in range(64) if spread[i] != product[i]]
    if differing:
        raise AssertionError('inequivalent output bits: ' + str(differing))
    return {'equivalent': True, 'input_bits': 32, 'covered_inputs': 1 << 32,
            'output_bits': 64, 'nonzero_output_bits': sum(bool(x) for x in product),
            'discarded_high_half_zero': True, 'fallback_stages': stages,
            'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'scope': 'exact source algebra under PTX CLMAD semantics; no CUDA execution'}


if __name__ == '__main__':
    print(json.dumps(prove(HEADER.read_text()), indent=2))
