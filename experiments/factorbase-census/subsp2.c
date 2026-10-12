// Monte-Carlo (Knuth tree-size) census of full-density F_2-subspaces of S_eps(c) = {y != 0 :
// Tr(1/y)+Tr(c y) = eps} in F_{2^n}. N_d = number of d-dim subspaces V with V\{0} subset S.
// Unbiased estimator over ordered bases: N_d = E[ |C_0||C_1|...|C_{d-1}| ] / |GL(d,2)|, where C_k =
// candidates after k chosen vectors. N_1 and N_2 are computed exactly. Usage: subsp2 n poly probes
// c <c1,c2,...>   |   subsp2 n poly probes r <count>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
typedef uint64_t u64;
static int n, Q, W;
static unsigned poly;
static unsigned mul(unsigned a, unsigned b)
{
    unsigned r = 0;
    while (b) {
        if (b & 1) r ^= a;
        b >>= 1;
        a <<= 1;
        if (a >> n) a ^= poly;
    }
    return r;
}
static unsigned pw(unsigned a, unsigned e)
{
    unsigned r = 1;
    while (e) {
        if (e & 1) r = mul(r, a);
        a = mul(a, a);
        e >>= 1;
    }
    return r;
}
static int tr(unsigned a)
{
    unsigned s = 0, x = a;
    for (int i = 0; i < n; i++) {
        s ^= x;
        x = mul(x, x);
    }
    return s & 1;
}
static u64 rng = 88172645463325252ULL;
static inline u64 xr()
{
    rng ^= rng << 13;
    rng ^= rng >> 7;
    rng ^= rng << 17;
    return rng;
}
static void xlat_and(const u64 *src, u64 *dst, unsigned w)
{ // dst = src & (src translated by XOR w)
    unsigned wh = w >> 6, wl = w & 63;
    for (int i = 0; i < W; i++) {
        u64 x = src[i ^ wh];
        if (wl & 1) x = ((x >> 1) & 0x5555555555555555ULL) | ((x & 0x5555555555555555ULL) << 1);
        if (wl & 2) x = ((x >> 2) & 0x3333333333333333ULL) | ((x & 0x3333333333333333ULL) << 2);
        if (wl & 4) x = ((x >> 4) & 0x0F0F0F0F0F0F0F0FULL) | ((x & 0x0F0F0F0F0F0F0F0FULL) << 4);
        if (wl & 8) x = ((x >> 8) & 0x00FF00FF00FF00FFULL) | ((x & 0x00FF00FF00FF00FFULL) << 8);
        if (wl & 16) x = ((x >> 16) & 0x0000FFFF0000FFFFULL) | ((x & 0x0000FFFF0000FFFFULL) << 16);
        if (wl & 32) x = (x >> 32) | (x << 32);
        dst[i] = src[i] & x;
    }
}
static long popc(const u64 *a)
{
    long s = 0;
    for (int i = 0; i < W; i++) s += __builtin_popcountll(a[i]);
    return s;
}
static unsigned pick(const u64 *a, long cnt)
{
    long k = xr() % cnt;
    for (int i = 0; i < W; i++) {
        int pc = __builtin_popcountll(a[i]);
        if (k < pc) {
            u64 x = a[i];
            for (int j = 0; j < k; j++) x &= x - 1;
            return (unsigned)((i << 6) | __builtin_ctzll(x));
        }
        k -= pc;
    }
    return 0;
}
static inline int in(const u64 *a, unsigned y) { return (a[y >> 6] >> (y & 63)) & 1; }
static const double GL[8] = {1, 1, 6, 168, 20160, 9999360, 20158709760.0, 163849992929280.0};
static void census(const u64 *S, long probes, const char *label)
{
    u64 *C1 = malloc(W * 8), *C2 = malloc(W * 8), *C3 = malloc(W * 8), *C4 = malloc(W * 8);
    long s0 = popc(S);
    // exact N_2
    long double n2 = 0;
    for (int i = 0; i < W; i++) {
        u64 x = S[i];
        while (x) {
            int b = __builtin_ctzll(x);
            x &= x - 1;
            unsigned u = (i << 6) | b;
            xlat_and(S, C1, u);
            n2 += popc(C1);
        }
    }
    n2 /= 6;
    long double sum[8] = {0}, sq[8] = {0};
    long reach5 = 0, reach6 = 0, found6 = 0, found7 = 0;
    unsigned *L = malloc(4096 * 4), *L5 = malloc(4096 * 4);
    for (long p = 0; p < probes; p++) {
        unsigned v1 = pick(S, s0);
        xlat_and(S, C1, v1);
        long s1 = popc(C1);
        double w[8] = {0};
        w[3] = w[4] = w[5] = w[6] = w[7] = 0;
        if (s1) {
            unsigned v2 = pick(C1, s1);
            xlat_and(C1, C2, v2);
            long s2 = popc(C2);
            w[3] = (double)s0 * s1 * s2;
            if (s2) {
                unsigned v3 = pick(C2, s2);
                xlat_and(C2, C3, v3);
                long s3 = popc(C3);
                w[4] = w[3] * s3;
                if (s3) {
                    unsigned v4 = pick(C3, s3);
                    xlat_and(C3, C4, v4);
                    long s4 = popc(C4);
                    w[5] = w[4] * s4;
                    if (s4) {
                        reach5++;
                        int m = 0;
                        for (int i = 0; i < W && m < 4096; i++) {
                            u64 x = C4[i];
                            while (x) {
                                int b = __builtin_ctzll(x);
                                x &= x - 1;
                                L[m++] = (i << 6) | b;
                            }
                        }
                        double sum5 = 0, sum6 = 0;
                        for (int a = 0; a < m; a++) {
                            int m5 = 0;
                            for (int b = 0; b < m; b++)
                                if (in(C4, L[b] ^ L[a])) L5[m5++] = L[b];
                            sum5 += m5;
                            if (m5) found6++;
                            for (int c = 0; c < m5; c++) {
                                int m6 = 0;
                                for (int d = 0; d < m5; d++)
                                    if (in(C4,
                                           L5[d] ^
                                               L5[c])) { // need u^v6 in C5 = {u in C4 : u^v5 in C4}
                                        unsigned u = L5[d] ^ L5[c];
                                        if (in(C4, u ^ L[a])) m6++;
                                    }
                                sum6 += m6;
                                if (m6) found7++;
                            }
                        }
                        w[6] = w[4] * sum5;
                        w[7] = w[4] * sum6;
                        if (sum5 > 0) reach6++;
                    }
                }
            }
        }
        for (int d = 3; d <= 7; d++) {
            sum[d] += w[d];
            sq[d] += (long double)w[d] * w[d];
        }
    }
    printf("%s size %ld N1 %ld N2 %.0Lf", label, s0, s0, n2);
    for (int d = 3; d <= 7; d++) {
        long double m = sum[d] / probes, v = sq[d] / probes - m * m;
        long double se = sqrtl(v > 0 ? v : 0) / sqrtl((long double)probes);
        printf(" N%d %.6Lg se %.3Lg", d, m / GL[d], se / GL[d]);
    }
    printf(" probes %ld reach5 %ld reach6 %ld bases6 %ld bases7 %ld\n", probes, reach5, reach6,
           found6, found7);
    fflush(stdout);
    free(C1);
    free(C2);
    free(C3);
    free(C4);
    free(L);
    free(L5);
}
int main(int argc, char **argv)
{
    n = atoi(argv[1]);
    poly = strtoul(argv[2], 0, 0);
    long probes = atol(argv[3]);
    char mode = argv[4][0];
    Q = 1 << n;
    W = Q / 64;
    unsigned *inv = malloc((size_t)Q * 4);
    unsigned char *trv = malloc(Q);
    for (unsigned y = 1; y < (unsigned)Q; y++) {
        inv[y] = pw(y, Q - 2);
        trv[y] = tr(y);
    }
    u64 *S = calloc(W, 8);
    char label[64];
    if (mode == 'r') {
        int cnt = atoi(argv[5]);
        rng ^= 0x9E3779B97F4A7C15ULL * (n + 1);
        for (int t = 0; t < cnt; t++) {
            memset(S, 0, W * 8);
            for (unsigned y = 1; y < (unsigned)Q; y++)
                if (xr() & 1) S[y >> 6] |= 1ULL << (y & 63);
            snprintf(label, 64, "random %d", t);
            census(S, probes, label);
        }
        return 0;
    }
    char *s = strdup(argv[5]), *tok = strtok(s, ",");
    while (tok) {
        unsigned c = strtoul(tok, 0, 10);
        for (int eps = 0; eps < 2; eps++) {
            memset(S, 0, W * 8);
            for (unsigned y = 1; y < (unsigned)Q; y++) {
                int g = trv[inv[y]] ^ trv[mul(c, y)];
                if (g == eps) S[y >> 6] |= 1ULL << (y & 63);
            }
            snprintf(label, 64, "c %u eps %d", c, eps);
            census(S, probes, label);
        }
        tok = strtok(0, ",");
    }
    return 0;
}
