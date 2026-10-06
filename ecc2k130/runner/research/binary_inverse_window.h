// Experimental polynomial-basis binary extended-GCD inversion.
// Include after packed131.h. No change to the field, walk, or point encoding.
#pragma once
namespace eccPacked131 {
ECC_HD int goal22WindowDegree(P131 a) {
#pragma unroll
    for (int i = 4; i >= 0; --i) {
        if (a.v[i]) {
#ifdef __CUDA_ARCH__
            return 32 * i + 31 - __clz(a.v[i]);
#else
            return 32 * i + 31 - __builtin_clz(a.v[i]);
#endif
        }
    }
    return -1;
}
ECC_HD P131 goal22WindowInverse(P131 a) {
    // Exact polynomial from codegen.genpolyreduce.polynomial(), degree 131.
    const P131 modulus = {{0xdu, 0u, 0xdu, 0x1d0d000du, 0xdu}};
    P131 u = a, v = modulus, b = {{1, 0, 0, 0, 0}}, c = {{0, 0, 0, 0, 0}};
    int du = goal22WindowDegree(u), dv = 131;
    if (du < 0) return c; // Match inv131(0)'s convention.
    // Invariants: u == a*b (mod modulus), v == a*c (mod modulus).
    // Each pass decreases deg(u)+deg(v), initially <=261. Odd u and v
    // cancel their constant terms; swap first to preserve the degree bound.
    for (int step = 0; step < 262 && du > 0; ++step) {
        if (u.v[0] & 1u) {
            if (du < dv) {
                const P131 tu = u, tb = b; u = v; b = c; v = tu; c = tb;
                const int td = du; du = dv; dv = td;
            }
#pragma unroll
            for (int i = 0; i < 5; ++i) { u.v[i] ^= v.v[i]; b.v[i] ^= c.v[i]; }
            du = goal22WindowDegree(u);
        }
        // Divide u by up to eight powers of x in one pass. Choose q so
        // b + q*modulus has the same zero low bits. The inverse of the
        // modulus modulo x^8 is 0x9d = 1+x^2+x^3+x^4+x^7.
        int shift = 8;
        if (u.v[0]) {
#ifdef __CUDA_ARCH__
            shift = __ffs(u.v[0]) - 1;
#else
            shift = __builtin_ctz(u.v[0]);
#endif
            if (shift > 8) shift = 8;
        }
        const uint32_t lo = b.v[0];
        const uint32_t q = (lo ^ (lo << 2) ^ (lo << 3) ^ (lo << 4) ^ (lo << 7)) & ((1u << shift) - 1u);
        const uint32_t t = q ^ (q << 2) ^ (q << 3);
        // F = x^124 + (1+x^2+x^3)(1+x^64+x^96+x^112+x^120+x^128).
        // q has at most eight bits, so these are all five words of q*F.
        b.v[0] ^= t;
        b.v[2] ^= t;
        b.v[3] ^= t ^ (t << 16) ^ (t << 24) ^ (q << 28);
        b.v[4] ^= t ^ (t >> 8) ^ (q >> 4);
#pragma unroll
        for (int i = 0; i < 4; ++i) {
            u.v[i] = (u.v[i] >> shift) | (u.v[i + 1] << (32 - shift));
            b.v[i] = (b.v[i] >> shift) | (b.v[i + 1] << (32 - shift));
        }
        u.v[4] >>= shift; b.v[4] >>= shift; du -= shift;
    }
    return b;
}
} // namespace eccPacked131
