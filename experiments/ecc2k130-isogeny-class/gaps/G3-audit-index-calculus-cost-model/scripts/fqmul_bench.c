/* fqmul_bench.c -- time one multiplication in F_{2^131} = F_2[z]/(z^131 + z^13 + z^2 + z + 1)
 * (the ECC2K-130 polynomial basis) with ARM PMULL, single core, to convert solver CPU seconds
 * into F_q-multiplication equivalents.  Checks the product against a bit-serial reference.
 * Build: clang -O3 -march=armv8-a+aes -o fqmul_bench fqmul_bench.c */
#include <arm_neon.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

typedef struct {
    uint64_t w[3];
} fe; /* 131 bits: w[2] has 3 bits */

static inline void clmul64(uint64_t a, uint64_t b, uint64_t *lo, uint64_t *hi)
{
    poly128_t r = vmull_p64((poly64_t)a, (poly64_t)b);
    uint64x2_t v = vreinterpretq_u64_p128(r);
    *lo = vgetq_lane_u64(v, 0);
    *hi = vgetq_lane_u64(v, 1);
}
static inline fe fmul(fe a, fe b)
{
    uint64_t c[6] = {0};
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++) {
            uint64_t lo, hi;
            clmul64(a.w[i], b.w[j], &lo, &hi);
            c[i + j] ^= lo;
            c[i + j + 1] ^= hi;
        }
    /* reduce: c = L + z^131 H, z^131 = z^13 + z^2 + z + 1 (fold twice) */
    for (int pass = 0; pass < 2; pass++) {
        uint64_t H[3];
        H[0] = (c[2] >> 3) | (c[3] << 61);
        H[1] = (c[3] >> 3) | (c[4] << 61);
        H[2] = (c[4] >> 3) | (c[5] << 61);
        c[2] &= 7;
        c[3] = c[4] = c[5] = 0;
        uint64_t R[4] = {0, 0, 0, 0};
        int sh[4] = {0, 1, 2, 13};
        for (int k = 0; k < 4; k++) {
            int b = sh[k];
            for (int i = 0; i < 3; i++) {
                R[i] ^= H[i] << b;
                if (b) R[i + 1] ^= H[i] >> (64 - b);
            }
        }
        c[0] ^= R[0];
        c[1] ^= R[1];
        c[2] ^= R[2];
        c[3] ^= R[3];
    }
    fe r;
    r.w[0] = c[0];
    r.w[1] = c[1];
    r.w[2] = c[2];
    return r;
}
static fe ref_mul(fe a, fe b)
{ /* bit-serial */
    fe r = {{0, 0, 0}};
    for (int i = 130; i >= 0; i--) {
        /* r *= z */
        uint64_t top = r.w[2] >> 2 & 1;
        r.w[2] = (r.w[2] << 1 | r.w[1] >> 63) & 7;
        r.w[1] = r.w[1] << 1 | r.w[0] >> 63;
        r.w[0] <<= 1;
        if (top) { r.w[0] ^= (1ULL << 13) | 7; }
        if (b.w[i / 64] >> (i % 64) & 1) {
            r.w[0] ^= a.w[0];
            r.w[1] ^= a.w[1];
            r.w[2] ^= a.w[2];
        }
    }
    return r;
}
static uint64_t s = 0x243F6A8885A308D3ULL;
static uint64_t rnd(void)
{
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return s;
}
int main(void)
{
    for (int t = 0; t < 20000; t++) {
        fe a = {{rnd(), rnd(), rnd() & 7}}, b = {{rnd(), rnd(), rnd() & 7}};
        fe x = fmul(a, b), y = ref_mul(a, b);
        if (memcmp(&x, &y, sizeof x)) {
            printf("{\"error\":\"mismatch\"}\n");
            return 1;
        }
    }
    fe a = {{rnd(), rnd(), rnd() & 7}}, b = {{rnd(), rnd(), rnd() & 7}};
    fe c1 = a, c2 = b, c3 = {{1, 2, 3}}, c4 = {{5, 6, 1}};
    long iters = 200000000L;
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (long i = 0; i < iters; i++) c1 = fmul(c1, b);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double lat = ((t1.tv_sec - t0.tv_sec) + 1e-9 * (t1.tv_nsec - t0.tv_nsec)) / iters;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (long i = 0; i < iters / 4; i++) {
        c1 = fmul(c1, b);
        c2 = fmul(c2, a);
        c3 = fmul(c3, b);
        c4 = fmul(c4, a);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double thr = ((t1.tv_sec - t0.tv_sec) + 1e-9 * (t1.tv_nsec - t0.tv_nsec)) / iters;
    printf("{\"checked_vs_reference\":20000,\"ns_per_mul_latency\":%.3f,\"ns_per_mul_throughput4\":"
           "%.3f,\"sink\":%llu}\n",
           lat * 1e9, thr * 1e9, (unsigned long long)(c1.w[0] ^ c2.w[1] ^ c3.w[0] ^ c4.w[2]));
    return 0;
}
