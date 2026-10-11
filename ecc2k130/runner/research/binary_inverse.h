// Experimental polynomial-basis binary extended-GCD inversion.
// Include after packed131.h. No change to the field, walk, or point encoding.
#pragma once
namespace eccPacked131 {
ECC_HD int goal22Degree(P131 a) {
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
ECC_HD P131 goal22BinaryInverse(P131 a) {
    // Exact polynomial from codegen.genpolyreduce.polynomial(), degree 131.
    const P131 modulus = {{0xdu, 0u, 0xdu, 0x1d0d000du, 0xdu}};
    P131 u = a, v = modulus, b = {{1, 0, 0, 0, 0}}, c = {{0, 0, 0, 0, 0}};
    int du = goal22Degree(u), dv = 131;
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
            du = goal22Degree(u);
        }
        const uint32_t odd = 0u - (b.v[0] & 1u);
#pragma unroll
        for (int i = 0; i < 5; ++i) b.v[i] ^= modulus.v[i] & odd;
#pragma unroll
        for (int i = 0; i < 4; ++i) {
            u.v[i] = (u.v[i] >> 1) | (u.v[i + 1] << 31);
            b.v[i] = (b.v[i] >> 1) | (b.v[i + 1] << 31);
        }
        u.v[4] >>= 1; b.v[4] >>= 1; --du;
    }
    return b;
}
} // namespace eccPacked131
