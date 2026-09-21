// Included within eccPacked131 after reducePolynomial131 is defined.
#pragma once
#ifndef GOAL22_POLY_NATIVE
#define GOAL22_POLY_NATIVE 0
#endif
ECC_HD void goal22SpreadPolynomial(uint32_t x, uint32_t *lo, uint32_t *hi) {
#ifdef __CUDA_ARCH__
    uint32_t a = __byte_perm(x, 0u, 0x4140u);
    uint32_t b = __byte_perm(x, 0u, 0x4342u);
#else
    uint32_t a = (x & 0xffu) | ((x & 0xff00u) << 8);
    uint32_t b = ((x >> 16) & 0xffu) | ((x >> 8) & 0xff0000u);
#endif
    a = (a | (a << 4)) & 0x0f0f0f0fu;
    b = (b | (b << 4)) & 0x0f0f0f0fu;
    a = (a | (a << 2)) & 0x33333333u;
    b = (b | (b << 2)) & 0x33333333u;
    *lo = (a | (a << 1)) & 0x55555555u;
    *hi = (b | (b << 1)) & 0x55555555u;
}
ECC_HD P131 goal22SquarePolynomial(P131 a) {
    static_assert(GOAL22_POLY_NATIVE >= 0 && GOAL22_POLY_NATIVE <= 4);
    uint32_t h[9];
#pragma unroll
    for (int i = 0; i < 4; ++i) {
        if (i < GOAL22_POLY_NATIVE) {
            const uint64_t word = spread32p(a.v[i]);
            h[2*i] = uint32_t(word);
            h[2*i+1] = uint32_t(word >> 32);
        } else {
            goal22SpreadPolynomial(a.v[i], &h[2*i], &h[2*i+1]);
        }
    }
    // Reduced polynomial coordinates have exactly three bits in word four.
    h[8] = (a.v[4] & 1u) | ((a.v[4] & 2u) << 1) | ((a.v[4] & 4u) << 2);
    return reducePolynomial131(h);
}
