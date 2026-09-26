// Experimental mixed carryless multiplier: one 64-bit Karatsuba leaf
// uses integer arithmetic; the other two keep native CLMAD. Include after
// packed131.h. Outputs are the same unreduced 131-by-131-bit product.
#pragma once
namespace eccPacked131 {
ECC_HD void goal22Clmul64Soft(uint32_t r[4], const uint32_t a[2], const uint32_t b[2]) {
    uint32_t lo0, hi0, lo1, hi1, lom, him;
    lo0 = clmul32(a[0], b[0], &hi0);
    lo1 = clmul32(a[1], b[1], &hi1);
    lom = clmul32(a[0] ^ a[1], b[0] ^ b[1], &him);
    /* middle = (a0+a1)(b0+b1) - a0b0 - a1b1, XOR in characteristic 2 */
    lom ^= lo0 ^ lo1;
    him ^= hi0 ^ hi1;
    r[0] = lo0;
    r[1] = hi0 ^ lom;
    r[2] = lo1 ^ him;
    r[3] = hi1;
}
ECC_HD void goal22Clmul128Mixed(uint32_t r[8], const uint32_t a[4], const uint32_t b[4]) {
    uint32_t lo[4], hi[4], mid[4], as[2], bs[2];
    goal22Clmul64Soft(lo, a, b);
    clmul64(hi, a + 2, b + 2);
    as[0] = a[0] ^ a[2]; as[1] = a[1] ^ a[3];
    bs[0] = b[0] ^ b[2]; bs[1] = b[1] ^ b[3];
    clmul64(mid, as, bs);
#pragma unroll
    for (int i=0; i<4; ++i) mid[i] ^= lo[i] ^ hi[i];
    r[0]=lo[0]; r[1]=lo[1]; r[2]=lo[2]^mid[0]; r[3]=lo[3]^mid[1];
    r[4]=hi[0]^mid[2]; r[5]=hi[1]^mid[3]; r[6]=hi[2]; r[7]=hi[3];
}
ECC_HD void goal22ProductMixed(const P131 &a, const P131 &b, uint32_t c[9]) {
    goal22Clmul128Mixed(c, a.v, b.v); c[8]=0;
#pragma unroll
    for (int k=0; k<3; ++k) {
        uint32_t ma=0u-((a.v[4]>>k)&1u), mb=0u-((b.v[4]>>k)&1u);
#pragma unroll
        for (int i=0; i<4; ++i) {
            uint32_t t=(a.v[i]&mb)^(b.v[i]&ma);
            c[4+i]^=t<<k;
            if(k) c[5+i]^=t>>(32-k);
        }
        c[8]^=(b.v[4]&ma)<<k;
    }
}
} // namespace eccPacked131
