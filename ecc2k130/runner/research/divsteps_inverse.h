// Experimental fixed-step polynomial extended-GCD inversion.
// Include after packed131.h; all values use the existing polynomial basis.
#pragma once
namespace eccPacked131 {
ECC_HD P131 goal22DivstepsInverse(P131 a) {
    const P131 modulus = {{0xdu, 0u, 0xdu, 0x1d0d000du, 0xdu}};
    P131 f = modulus, g = a, v = {{0, 0, 0, 0, 0}}, r = {{1, 0, 0, 0, 0}};
    int delta = 1;
    // f == a*v and g == a*r modulo modulus. No lane-dependent loop bound
    // or degree scan. Keep 262 passes even when a particular lane is done.
#pragma unroll 1
    for (int step = 0; step < 262; ++step) {
        const uint32_t odd = 0u - (g.v[0] & 1u);
        const bool swap = delta > 0 && odd;
        delta = 1 + (swap ? -delta : delta);
#pragma unroll
        for (int i = 0; i < 5; ++i) {
            const uint32_t fi = f.v[i], gi = g.v[i], vi = v.v[i], ri = r.v[i];
            f.v[i] = swap ? gi : fi;
            g.v[i] = (swap ? fi : gi) ^ (f.v[i] & odd);
            v.v[i] = swap ? ri : vi;
            r.v[i] = (swap ? vi : ri) ^ (v.v[i] & odd);
        }
        const uint32_t correction = 0u - (r.v[0] & 1u);
#pragma unroll
        for (int i = 0; i < 5; ++i) r.v[i] ^= modulus.v[i] & correction;
#pragma unroll
        for (int i = 0; i < 4; ++i) {
            g.v[i] = (g.v[i] >> 1) | (g.v[i + 1] << 31);
            r.v[i] = (r.v[i] >> 1) | (r.v[i + 1] << 31);
        }
        g.v[4] >>= 1; r.v[4] >>= 1;
    }
    return v;
}
} // namespace eccPacked131
