// Included inside eccPacked131, after reverse131 and before sqr131.
// Exact bit permutations; no field multiplication or lookup table.
#pragma once
ECC_HD uint32_t goal22BytePerm(uint32_t a, uint32_t b, unsigned selector) {
#ifdef __CUDA_ARCH__
    return __byte_perm(a, b, selector);
#else
    const uint64_t x = uint64_t(a) | (uint64_t(b) << 32);
    uint32_t y = 0;
    for (int i = 0; i < 4; ++i)
        y |= uint32_t((x >> (8 * ((selector >> (4 * i)) & 7u))) & 255u) << (8 * i);
    return y;
#endif
}
ECC_HD void goal22Zip2(uint32_t a, uint32_t b, uint32_t *lo, uint32_t *hi) {
    // Transpose the input word-index bit with bits 0, 1 and 2 of the
    // within-word index. The remaining byte permutation completes the zip.
    uint32_t t = ((a >> 1) ^ b) & 0x55555555u;
    b ^= t; a ^= t << 1;
    t = ((a >> 2) ^ b) & 0x33333333u;
    b ^= t; a ^= t << 2;
    t = ((a >> 4) ^ b) & 0x0f0f0f0fu;
    b ^= t; a ^= t << 4;
    *lo = goal22BytePerm(a, b, 0x5140u);
    *hi = goal22BytePerm(a, b, 0x7362u);
}
ECC_HD P131 goal22SquareNormal(const P131 &a) {
    const P131 rev = reverse131(a);
    P131 r;
    goal22Zip2(rev.v[0], a.v[0], &r.v[0], &r.v[1]);
    goal22Zip2(rev.v[1], a.v[1], &r.v[2], &r.v[3]);
    r.v[4] = (rev.v[2] & 1u) | ((a.v[2] & 1u) << 1) | ((rev.v[2] & 2u) << 1);
    return r;
}
