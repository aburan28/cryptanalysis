/* relprob.c -- exact relation-probability measurement for m-term decompositions on the
 * Koblitz curve E: y^2 + xy = x^3 + 1 over F_{2^n} (n odd prime, n <= 31).
 *
 * Factor base F = {P in E : x(P) in V, x != 0}, V an l-dim F_2-subspace.
 *   plain   : every slot uses V_0; all m-MULTISETS of F are enumerated (|F|^m/m! sums).
 *   ordered : GGMP 2020 Sec 3.1 tau-slots, slot i uses V_i = tau^i(V_0) (x -> x^(2^i)), with
 *             V_i = span(beta^(2^(m j + i)) : j < l) for a normal element beta, so the V_i are
 *             pairwise disjoint (needs m*l <= n); all ordered m-TUPLES are enumerated (|F|^m sums).
 *   random  : plain, but V a uniformly random l-dim subspace (control for the normal-basis V_0).
 * Every sum S != O is marked in two bitmaps:
 *   BX[x(S)]            -> x-coverage  (the event "R or -R is a sum": what one PDP call on x(R) tests)
 *   BP[x(S), w0(S)]     -> point coverage (the event "R itself is a sum"), w0 = lowest bit of y/x
 * Model predictions (Poisson): x-coverage 1-exp(-2M/#E), point coverage 1-exp(-M/#E), M = #sums.
 * The index-calculus costmodel.py uses p = 2^(m l)/(m! 2^n) per call (no factor 2 for +-R).
 * Additionally K random targets are drawn from G = [4]E (the odd-order part, #E = 4N', which is
 * where ECDLP targets live) and from E \ 2E, and looked up in BX (tests uniformity over E/4E).
 *
 * usage: relprob n m l mode seed K
 * output: one JSON line.
 * Build: clang -O3 -march=armv8-a+aes -o relprob relprob.c -lm
 */
#include <arm_neon.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int N_;          /* field degree */
static uint64_t MOD;    /* modulus incl. z^n */
static uint64_t RED;    /* modulus without z^n */
static uint64_t MASKN;

static inline uint64_t clmul(uint64_t a, uint64_t b) {
    poly128_t r = vmull_p64((poly64_t)a, (poly64_t)b);
    return (uint64_t)r; /* products of < 32-bit operands fit in 64 bits */
}
static inline uint64_t fmul(uint64_t a, uint64_t b) {
    uint64_t c = clmul(a, b);
    uint64_t hi;
    while ((hi = c >> N_) != 0) c = (c & MASKN) ^ clmul(hi, RED);
    return c;
}
static inline uint64_t fsqr(uint64_t a) { return fmul(a, a); }
static uint64_t finv(uint64_t a) { /* a^(2^n - 2) */
    uint64_t r = 1, b = a;
    uint64_t e = (1ULL << N_) - 2;
    while (e) {
        if (e & 1) r = fmul(r, b);
        b = fsqr(b);
        e >>= 1;
    }
    return r;
}
static int ftrace(uint64_t a) {
    uint64_t t = a, s = a;
    for (int i = 1; i < N_; i++) {
        s = fsqr(s);
        t ^= s;
    }
    return (int)(t & 1);
}
static uint64_t fhalftrace(uint64_t a) { /* n odd: sum_{i=0}^{(n-1)/2} a^(4^i) */
    uint64_t h = a, s = a;
    for (int i = 1; i <= (N_ - 1) / 2; i++) {
        s = fsqr(fsqr(s));
        h ^= s;
    }
    return h;
}
/* irreducibility (Ben-Or) and modulus choice identical to pdp-scaling/gf2n.py */
static uint64_t pmod(uint64_t a, uint64_t m) {
    int dm = 63 - __builtin_clzll(m);
    while (a && (63 - __builtin_clzll(a)) >= dm) a ^= m << ((63 - __builtin_clzll(a)) - dm);
    return a;
}
static uint64_t pmulmod(uint64_t a, uint64_t b, uint64_t m) {
    uint64_t r = 0;
    int dm = 63 - __builtin_clzll(m);
    while (b) {
        if (b & 1) r ^= a;
        b >>= 1;
        a <<= 1;
        if (a >> dm & 1) a ^= m;
    }
    return r;
}
static uint64_t pgcd(uint64_t a, uint64_t b) {
    while (b) {
        uint64_t t = pmod(a, b);
        a = b;
        b = t;
    }
    return a;
}
static int is_irred(uint64_t f) {
    int n = 63 - __builtin_clzll(f);
    uint64_t z = 2;
    for (int i = 0; i < n / 2; i++) {
        z = pmulmod(z, z, f);
        if (pgcd(f, z ^ 2) != 1) return 0;
    }
    return 1;
}
static uint64_t find_modulus(int n) {
    for (int k = 1; k < n; k++) {
        uint64_t f = (1ULL << n) | (1ULL << k) | 1;
        if (is_irred(f)) return f;
    }
    for (int a = 1; a < n; a++)
        for (int b = a + 1; b < n; b++)
            for (int c = b + 1; c < n; c++) {
                uint64_t f = (1ULL << n) | (1ULL << a) | (1ULL << b) | (1ULL << c) | 1;
                if (is_irred(f)) return f;
            }
    return 0;
}

/* xorshift rng */
static uint64_t rs = 88172645463325252ULL;
static uint64_t rnd(void) {
    rs ^= rs << 13;
    rs ^= rs >> 7;
    rs ^= rs << 17;
    return rs;
}

typedef struct { uint64_t x, y; int inf; } pt;
/* E: y^2 + x y = x^3 + 1 */
static int lift(uint64_t x, pt *P) { /* x != 0 */
    uint64_t xi = finv(x);
    uint64_t c = x ^ fsqr(xi); /* x + 1/x^2 */
    if (ftrace(c)) return 0;
    uint64_t w = fhalftrace(c);
    P->x = x;
    P->y = fmul(w, x);
    P->inf = 0;
    return 1;
}
static pt padd(pt P, pt Q) {
    pt R;
    if (P.inf) return Q;
    if (Q.inf) return P;
    if (P.x == Q.x) {
        if ((P.y ^ Q.y) == P.x || P.x == 0) { R.inf = 1; R.x = R.y = 0; return R; } /* Q = -P */
        /* doubling */
        uint64_t lam = P.x ^ fmul(P.y, finv(P.x));
        R.x = fsqr(lam) ^ lam;
        R.y = fsqr(P.x) ^ fmul(lam ^ 1, R.x);
        R.inf = 0;
        return R;
    }
    uint64_t lam = fmul(P.y ^ Q.y, finv(P.x ^ Q.x));
    R.x = fsqr(lam) ^ lam ^ P.x ^ Q.x;
    R.y = fmul(lam, P.x ^ R.x) ^ R.x ^ P.y;
    R.inf = 0;
    return R;
}
static pt pneg(pt P) { if (!P.inf) P.y ^= P.x; return P; }
static pt pmul(pt P, uint64_t k) {
    pt R = {0, 0, 1};
    while (k) {
        if (k & 1) R = padd(R, P);
        P = padd(P, P);
        k >>= 1;
    }
    return R;
}
static int w0bit(pt P) { /* lowest bit of y/x, distinguishes P from -P (x != 0) */
    return (int)(fmul(P.y, finv(P.x)) & 1);
}

static uint8_t *BX, *BP;
static inline void mark(uint64_t x, int w) {
    BX[x >> 3] |= (uint8_t)(1u << (x & 7));
    uint64_t k = (x << 1) | (uint64_t)w;
    BP[k >> 3] |= (uint8_t)(1u << (k & 7));
}

/* F_2-rank of a list of vectors */
static int rank_of(uint64_t *v, int k) {
    uint64_t a[64];
    memcpy(a, v, sizeof(uint64_t) * k);
    int r = 0;
    for (int bit = 63; bit >= 0 && r < k; bit--) {
        int piv = -1;
        for (int i = r; i < k; i++)
            if (a[i] >> bit & 1) { piv = i; break; }
        if (piv < 0) continue;
        uint64_t t = a[piv]; a[piv] = a[r]; a[r] = t;
        for (int i = 0; i < k; i++)
            if (i != r && (a[i] >> bit & 1)) a[i] ^= a[r];
        r++;
    }
    return r;
}

/* slot factor bases */
static pt *FB[8];
static int FBn[8];
static int M_, L_;
static double nsums = 0;
static uint64_t *scr_d, *scr_pref;

/* last level: add S to every point of slot s from index j0, batch inversion, mark x (and w0) */
static void last_level(pt S, int s, int j0) {
    int cnt = FBn[s] - j0;
    if (cnt <= 0) return;
    pt *Fs = FB[s] + j0;
    if (S.inf) {
        for (int j = 0; j < cnt; j++) { mark(Fs[j].x, w0bit(Fs[j])); }
        nsums += cnt;
        return;
    }
    /* d_j = S.x + F_j.x; zero d_j handled separately */
    uint64_t acc = 1;
    for (int j = 0; j < cnt; j++) {
        uint64_t d = S.x ^ Fs[j].x;
        scr_d[j] = d;
        scr_pref[j] = acc;
        if (d) acc = fmul(acc, d);
    }
    uint64_t inv = finv(acc);
    for (int j = cnt - 1; j >= 0; j--) {
        uint64_t d = scr_d[j];
        if (!d) {
            pt R = padd(S, Fs[j]);
            if (!R.inf) mark(R.x, w0bit(R));
            continue;
        }
        uint64_t dinv = fmul(inv, scr_pref[j]);
        inv = fmul(inv, d);
        uint64_t lam = fmul(S.y ^ Fs[j].y, dinv);
        uint64_t x3 = fsqr(lam) ^ lam ^ S.x ^ Fs[j].x;
        if (x3 == 0) { mark(0, 0); continue; }
        uint64_t y3 = fmul(lam, S.x ^ x3) ^ x3 ^ S.y;
        /* w0 = lowest bit of y3/x3 : needs an inversion; batch-free fallback is slow, so use
           the identity: w = y/x, and bit0(w) computed via one more mult with x^-1.  To keep the
           cost low we mark BP only for a 1/16 subsample of sums (deterministic on x3). */
        if ((x3 & 15) == 0) {
            uint64_t w = fmul(y3, finv(x3));
            uint64_t k = (x3 << 1) | (w & 1);
            BP[k >> 3] |= (uint8_t)(1u << (k & 7));
        }
        BX[x3 >> 3] |= (uint8_t)(1u << (x3 & 7));
    }
    nsums += cnt;
}

static int ordered_mode;
static void rec(pt S, int depth, int jmin) {
    if (depth == M_ - 1) {
        if (ordered_mode) last_level(S, depth, 0);
        else last_level(S, 0, jmin);
        return;
    }
    int s = ordered_mode ? depth : 0;
    int j0 = ordered_mode ? 0 : jmin;
    for (int j = j0; j < FBn[s]; j++) {
        pt T = padd(S, FB[s][j]);
        rec(T, depth + 1, j);
    }
}

int main(int argc, char **argv) {
    if (argc < 7) { fprintf(stderr, "usage: relprob n m l mode(plain|ordered|random) seed K\n"); return 1; }
    N_ = atoi(argv[1]); M_ = atoi(argv[2]); L_ = atoi(argv[3]);
    const char *mode = argv[4];
    uint64_t seed = strtoull(argv[5], 0, 10);
    long K = atol(argv[6]);
    rs ^= seed * 0x9E3779B97F4A7C15ULL; for (int i = 0; i < 20; i++) rnd();
    MOD = find_modulus(N_); RED = MOD ^ (1ULL << N_); MASKN = (1ULL << N_) - 1;
    /* mode = "<plain|ordered>:<normal|random|kertr>" ; legacy "random" = plain:random */
    char enumm[16] = "plain", bas[16] = "normal";
    if (strchr(mode, ':')) { sscanf(mode, "%15[^:]:%15s", enumm, bas); }
    else if (strcmp(mode, "random") == 0) { strcpy(bas, "random"); }
    else strcpy(enumm, mode);
    ordered_mode = strcmp(enumm, "ordered") == 0;
    int random_mode = strcmp(bas, "random") == 0;
    int kertr_mode = strcmp(bas, "kertr") == 0;
    clock_t t0 = clock();
    /* #E via Lucas: tau^2 + tau + 2 = 0, t1 = -1 */
    long double ta = 2, tb = -1; /* s_0, s_1 */
    long long s0 = 2, s1 = -1;
    for (int k = 2; k <= N_; k++) { long long s2 = -s1 - 2 * s0; s0 = s1; s1 = s2; }
    long long cardE = (1LL << N_) + 1 - s1;
    (void)ta; (void)tb;
    /* normal element */
    uint64_t beta = 0;
    for (int tries = 0; tries < 10000; tries++) {
        uint64_t b = rnd() & MASKN;
        uint64_t v[64]; uint64_t s = b;
        for (int i = 0; i < N_; i++) { v[i] = s; s = fsqr(s); }
        if (rank_of(v, N_) == N_) { beta = b; break; }
    }
    if (!beta) { fprintf(stderr, "no normal element\n"); return 1; }
    uint64_t conj[64]; { uint64_t s = beta; for (int i = 0; i < N_; i++) { conj[i] = s; s = fsqr(s); } }
    int nslots = ordered_mode ? M_ : 1;
    if (ordered_mode && M_ * L_ > N_) { fprintf(stderr, "m*l > n\n"); return 1; }
    uint64_t basis[8][64];
    for (int i = 0; i < nslots; i++)
        for (int j = 0; j < L_; j++) basis[i][j] = conj[(M_ * j + i) % N_];
    if (random_mode || kertr_mode) {
        /* random l-dim V_0 (inside ker Tr for kertr); ordered slots V_i = V_0^(2^i) */
        for (;;) {
            for (int j = 0; j < L_; j++) {
                uint64_t v;
                do { v = rnd() & MASKN; } while (kertr_mode && ftrace(v));
                basis[0][j] = v;
            }
            if (rank_of(basis[0], L_) != L_) continue;
            for (int i = 1; i < nslots; i++)
                for (int j = 0; j < L_; j++) basis[i][j] = fsqr(basis[i - 1][j]);
            if (ordered_mode) {
                uint64_t all[64]; int k = 0;
                for (int i = 0; i < nslots; i++) for (int j = 0; j < L_; j++) all[k++] = basis[i][j];
                if (rank_of(all, k) != k) continue;
            }
            break;
        }
    }
    /* check disjointness of slot subspaces (ordered): rank of union = nslots*l */
    int union_rank = -1;
    if (ordered_mode) {
        uint64_t all[64]; int k = 0;
        for (int i = 0; i < nslots; i++) for (int j = 0; j < L_; j++) all[k++] = basis[i][j];
        union_rank = rank_of(all, k);
    }
    /* enumerate slot factor bases; slot i>0 must equal tau^i(slot 0) : check */
    for (int i = 0; i < nslots; i++) {
        FB[i] = malloc(sizeof(pt) * (2u << L_));
        FBn[i] = 0;
        for (uint64_t c = 1; c < (1ULL << L_); c++) {
            uint64_t x = 0;
            for (int j = 0; j < L_; j++) if (c >> j & 1) x ^= basis[i][j];
            pt P;
            if (lift(x, &P)) { FB[i][FBn[i]++] = P; FB[i][FBn[i]++] = pneg(P); }
        }
    }
    int tau_ok = 1;
    if (ordered_mode) {
        for (int i = 1; i < nslots; i++) {
            if (FBn[i] != FBn[0]) tau_ok = 0;
            for (int j = 0; j < FBn[0] && tau_ok; j++) {
                uint64_t x = FB[0][j].x; for (int r = 0; r < i; r++) x = fsqr(x);
                int found = 0;
                for (int k2 = 0; k2 < FBn[i]; k2++) if (FB[i][k2].x == x) { found = 1; break; }
                if (!found) tau_ok = 0;
            }
        }
    }
    size_t bxbytes = (size_t)1 << (N_ - 3 > 0 ? N_ - 3 : 0);
    BX = calloc(bxbytes, 1); BP = calloc(bxbytes * 2, 1);
    int maxf = 0; for (int i = 0; i < nslots; i++) if (FBn[i] > maxf) maxf = FBn[i];
    scr_d = malloc(sizeof(uint64_t) * (maxf + 1)); scr_pref = malloc(sizeof(uint64_t) * (maxf + 1));
    pt O = {0, 0, 1};
    rec(O, 0, 0);
    /* coverage */
    uint64_t covx = 0, covp_sub = 0, xsub = 0;
    for (size_t i = 0; i < bxbytes; i++) covx += __builtin_popcount(BX[i]);
    if (BX[0] & 1) covx -= 1; /* drop x = 0 */
    /* point coverage on the 1/16 subsample of x (x & 15 == 0, x != 0): both signs present in BP */
    for (uint64_t x = 16; x <= MASKN; x += 16) {
        uint64_t k0 = x << 1, k1 = k0 | 1;
        if (ftrace(x ^ fsqr(finv(x)))) continue; /* x not an abscissa */
        covp_sub += (BP[k0 >> 3] >> (k0 & 7) & 1) + (BP[k1 >> 3] >> (k1 & 7) & 1);
        xsub++; /* liftable x in the subsample: 2 points each */
    }
    long long nx = (cardE - 2) / 2; /* x != 0 values with points */
    /* random targets: G = [4]E and E\2E */
    long hitG = 0, hitOdd = 0, nG = 0, nOdd = 0, hitE = 0, nE = 0, n2 = 0, hit2 = 0;
    for (long t = 0; t < K; t++) {
        pt P;
        uint64_t x;
        do { x = rnd() & MASKN; } while (!x || !lift(x, &P));
        if (rnd() & 1) P = pneg(P);
        pt Q = pmul(P, 4);
        nE++; hitE += BX[P.x >> 3] >> (P.x & 7) & 1;
        if (!Q.inf && Q.x) { nG++; hitG += BX[Q.x >> 3] >> (Q.x & 7) & 1; }
        if (ftrace(P.x)) { nOdd++; hitOdd += BX[P.x >> 3] >> (P.x & 7) & 1; }
        /* a point of 2E \ 4E: 2P with P in E \ 2E (2-Sylow is Z/4 when #E = 4 * odd) */
        if (ftrace(P.x)) { pt D = padd(P, P); if (!D.inf && D.x) { n2++; hit2 += BX[D.x >> 3] >> (D.x & 7) & 1; } }
    }
    double M = nsums;
    double lam2 = 2.0 * M / (double)cardE, lam1 = M / (double)cardE;
    double lgf = 0; for (int i = 2; i <= M_; i++) lgf += log2((double)i);
    double lam_cm = pow(2.0, M_ * L_ - (ordered_mode ? 0 : lgf) - N_);
    double secs = (double)(clock() - t0) / CLOCKS_PER_SEC;
    printf("{\"n\":%d,\"m\":%d,\"l\":%d,\"mode\":\"%s\",\"seed\":%llu,\"modulus\":%llu,\"beta\":%llu,"
           "\"cardE\":%lld,\"F_size\":%d,\"F_size_over_2^l\":%.4f,\"union_rank\":%d,\"tau_slots_ok\":%d,"
           "\"sums\":%.0f,\"x_values\":%lld,\"x_covered\":%llu,\"x_cov_frac\":%.6f,"
           "\"pred_x_cov_2M\":%.6f,\"pred_x_cov_M\":%.6f,\"pred_costmodel_p\":%.6f,"
           "\"point_cov_sub\":%.6f,\"pred_point_cov_M\":%.6f,\"sub_x\":%llu,"
           "\"K\":%ld,\"hit_E\":%.6f,\"n_G\":%ld,\"hit_G\":%.6f,\"n_E_minus_2E\":%ld,\"hit_E_minus_2E\":%.6f,\"n_2E_minus_4E\":%ld,\"hit_2E_minus_4E\":%.6f,\"basis\":\"%s\","
           "\"lambda_2M\":%.6f,\"lambda_costmodel\":%.6f,\"seconds\":%.2f}\n",
           N_, M_, L_, mode, (unsigned long long)seed, (unsigned long long)MOD, (unsigned long long)beta,
           cardE, FBn[0], FBn[0] / pow(2.0, L_), union_rank, tau_ok, M, nx, (unsigned long long)covx,
           covx / (double)nx, 1 - exp(-lam2), 1 - exp(-lam1), 1 - exp(-lam_cm),
           covp_sub / (2.0 * xsub), 1 - exp(-lam1), (unsigned long long)xsub,
           K, hitE / (double)nE, nG, nG ? hitG / (double)nG : -1, nOdd, nOdd ? hitOdd / (double)nOdd : -1, n2, n2 ? hit2 / (double)n2 : -1, bas,
           lam2, lam_cm, secs);
    return 0;
}
