// Three-input logic, checked against the scalar definitions for every host
// word type this machine can build.
//
// ECC_SEL and ECC_MAJ are not spelled out on any target that matters: they are
// vpternlogd on AVX-512, LOP3 on the GPU, and BSL on aarch64, where ECC_MAJ in
// particular is a select on a ^ b between c and a & b rather than anything
// that looks like a majority.  The walk tests would catch a wrong substitution
// only through whatever the iteration happens to exercise, so check the
// identities themselves, lane by lane, on random inputs.
#include <cstdio>

#include "../include/bitslice.h"

static unsigned long long nextRandom(unsigned long long &s) {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return s;
}

template <class W>
static int checkWord(const char *name, unsigned long long &seed) {
    const int lanes = WordTraits<W>::LANES;
    const int limbs = lanes / 64;
    int bad = 0;
    for (int trial = 0; trial < 256 && !bad; ++trial) {
        unsigned long long a[8], b[8], c[8];
        unsigned long long x3[8], xa[8], mj[8], sl[8];
        for (int i = 0; i < limbs; ++i) {
            a[i] = nextRandom(seed);
            b[i] = nextRandom(seed);
            c[i] = nextRandom(seed);
            // the definitions the generated code was written against
            x3[i] = a[i] ^ b[i] ^ c[i];
            xa[i] = a[i] ^ (b[i] & c[i]);
            mj[i] = (a[i] & b[i]) | (c[i] & (a[i] ^ b[i]));
            sl[i] = (a[i] & b[i]) | (~a[i] & c[i]);
        }
        const W wa = eccWordFromLimbs<W>(a);
        const W wb = eccWordFromLimbs<W>(b);
        const W wc = eccWordFromLimbs<W>(c);
        if (!(ECC_XOR3(wa, wb, wc) == eccWordFromLimbs<W>(x3))) bad |= 1;
        if (!(ECC_XORAND(wa, wb, wc) == eccWordFromLimbs<W>(xa))) bad |= 2;
        if (!(ECC_MAJ(wa, wb, wc) == eccWordFromLimbs<W>(mj))) bad |= 4;
        if (!(ECC_SEL(wa, wb, wc) == eccWordFromLimbs<W>(sl))) bad |= 8;

        // lane addressing has to agree with the limb layout, or a collision
        // would be reported against the wrong walk
        for (int lane = 0; lane < lanes; ++lane) {
            const int want = (int)((a[lane >> 6] >> (lane & 63)) & 1ull);
            if (laneBit<W>(wa, lane) != want) bad |= 16;
            if (laneBit<W>(laneMask<W>(lane), lane) != 1) bad |= 32;
        }
    }

    const W zero = ECC_ZERO;
    const W ones = ~zero;
    for (int lane = 0; lane < lanes; ++lane) {
        if (laneBit<W>(zero, lane) != 0) bad |= 64;
        if (laneBit<W>(ones, lane) != 1) bad |= 64;
    }

    printf("  %-24s %3d lanes  %s\n", name, lanes, bad ? "FAILED" : "ok");
    if (bad) printf("    failing checks mask 0x%x\n", bad);
    return bad ? 1 : 0;
}

int main() {
    unsigned long long seed = 0x243f6a8885a308d3ull;
    int failures = 0;
    printf("three-input logic against the scalar definitions\n");
    failures += checkWord<unsigned long long>("unsigned long long", seed);
#if !defined(__CUDACC__) && defined(__ARM_NEON) && defined(__aarch64__)
    failures += checkWord<Bits128>("Bits128 (NEON)", seed);
#if defined(__ARM_FEATURE_SHA3)
    printf("  EOR3 in use for ECC_XOR3\n");
#else
    printf("  no FEAT_SHA3: ECC_XOR3 is two EORs\n");
#endif
#endif
#if !defined(__CUDACC__) && defined(__AVX2__)
    failures += checkWord<Bits256>("Bits256 (AVX2)", seed);
#endif
#if !defined(__CUDACC__) && defined(__AVX512F__)
    failures += checkWord<Bits512>("Bits512 (AVX-512)", seed);
#endif
    printf("%s\n", failures ? "FAILED" : "all word types agree");
    return failures ? 1 : 0;
}
