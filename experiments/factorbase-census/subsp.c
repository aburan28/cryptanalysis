// For F_{2^n}, n prime, and curve parameter c = sqrt(a6):
// rational x-coordinates of y^2+xy=x^3+a2x^2+a6 are {x : Tr(x) + Tr(c/x) = Tr(a2)}.
// Factor base density on an F_2-subspace V is 1 iff g_c(y)=Tr(1/y)+Tr(c y) is constant on V\{0}
// (after the scaling y = x/c; see write-up). Enumerate, for each Frobenius class of c,
// the number of d-dimensional subspaces V with V\{0} inside S_eps = {y!=0 : g_c(y)=eps}.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
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
static unsigned *inv;
static int *trv;
#define MAXD 8
static long long cnt[MAXD + 1];
static uint64_t *stackbuf;
// bitset translate by XOR w: dst[y] = src[y^w]
static void xlat(const uint64_t *src, uint64_t *dst, unsigned w)
{
    unsigned wh = w >> 6, wl = w & 63;
    for (int i = 0; i < W; i++) {
        uint64_t x = src[i ^ wh];
        if (wl & 1) x = ((x >> 1) & 0x5555555555555555ULL) | ((x & 0x5555555555555555ULL) << 1);
        if (wl & 2) x = ((x >> 2) & 0x3333333333333333ULL) | ((x & 0x3333333333333333ULL) << 2);
        if (wl & 4) x = ((x >> 4) & 0x0F0F0F0F0F0F0F0FULL) | ((x & 0x0F0F0F0F0F0F0F0FULL) << 4);
        if (wl & 8) x = ((x >> 8) & 0x00FF00FF00FF00FFULL) | ((x & 0x00FF00FF00FF00FFULL) << 8);
        if (wl & 16) x = ((x >> 16) & 0x0000FFFF0000FFFFULL) | ((x & 0x0000FFFF0000FFFFULL) << 16);
        if (wl & 32) x = (x >> 32) | (x << 32);
        dst[i] = x;
    }
}
static void dfs(int d, const uint64_t *C, unsigned pivmask, unsigned last)
{
    if (d >= MAXD) return;
    uint64_t *T = stackbuf + (size_t)d * W, *N = stackbuf + (size_t)(d + MAXD) * W;
    for (int i = 0; i < W; i++) {
        uint64_t x = C[i];
        while (x) {
            int b = __builtin_ctzll(x);
            x &= x - 1;
            unsigned w = (i << 6) | b;
            if (w <= last || (w & pivmask)) continue;
            cnt[d + 1]++;
            xlat(C, T, w);
            int nz = 0;
            for (int j = 0; j < W; j++) {
                N[j] = C[j] & T[j];
                nz |= (N[j] != 0);
            }
            if (nz) dfs(d + 1, N, pivmask | (1u << (31 - __builtin_clz(w))), w);
        }
    }
}
int main(int argc, char **argv)
{
    n = atoi(argv[1]);
    poly = strtoul(argv[2], 0, 0);
    int cmax = argc > 3 ? atoi(argv[3]) : 0;
    int rnd = argc > 4 ? atoi(argv[4]) : 0;
    char *clist = argc > 5 ? argv[5] : 0;
    Q = 1 << n;
    W = Q / 64;
    inv = malloc(Q * 4);
    trv = malloc(Q * 4);
    for (unsigned y = 1; y < (unsigned)Q; y++) {
        inv[y] = pw(y, Q - 2);
        trv[y] = tr(y);
    }
    uint64_t *S = calloc(W, 8);
    stackbuf = calloc((size_t)2 * MAXD * W, 8);
    // random baseline sets
    srand(12345);
    if (rnd) {
        for (int t = 0; t < rnd; t++) {
            memset(S, 0, W * 8);
            int sz = 0;
            for (unsigned y = 1; y < (unsigned)Q; y++)
                if (rand() & 1) {
                    S[y >> 6] |= 1ULL << (y & 63);
                    sz++;
                }
            memset(cnt, 0, sizeof cnt);
            dfs(0, S, 0, 0);
            printf("random %d size %d :", t, sz);
            for (int d = 1; d <= MAXD; d++) printf(" %lld", cnt[d]);
            printf("\n");
        }
        return 0;
    }
    // Frobenius class reps of c
    char *seen = calloc(Q, 1);
    int done = 0;
    unsigned cl[4096];
    int ncl = 0;
    if (clist) {
        char *s = strdup(clist), *tok = strtok(s, ",");
        while (tok) {
            cl[ncl++] = strtoul(tok, 0, 10);
            tok = strtok(0, ",");
        }
    }
    for (unsigned ci = 1; ci < (unsigned)(clist ? ncl + 1 : Q); ci++) {
        unsigned c = clist ? cl[ci - 1] : ci;
        if (!clist && seen[c]) continue;
        unsigned x = c;
        do {
            seen[x] = 1;
            x = mul(x, x);
        } while (x != c);
        for (int eps = 0; eps < 2; eps++) {
            memset(S, 0, W * 8);
            int sz = 0;
            for (unsigned y = 1; y < (unsigned)Q; y++) {
                int g = trv[inv[y]] ^ trv[mul(c, y)];
                if (g == eps) {
                    S[y >> 6] |= 1ULL << (y & 63);
                    sz++;
                }
            }
            memset(cnt, 0, sizeof cnt);
            dfs(0, S, 0, 0);
            printf("c %u eps %d size %d :", c, eps, sz);
            for (int d = 1; d <= MAXD; d++) printf(" %lld", cnt[d]);
            printf("\n");
            fflush(stdout);
        }
        if (cmax && ++done >= cmax) break;
    }
    return 0;
}
