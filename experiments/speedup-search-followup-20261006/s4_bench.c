/* Two-product S4 evaluator benchmark over F_p, p = 2^61 - 1.
 *
 * Endpoints are Semaev S3 quadratics S3(x1, x2, z) = a2 z^2 + a1 z + a0 built
 * from random x1, x2 on y^2 = x^3 + A x + B; pairs (left, right) are tested
 * for S4 = Res_z = 0.  Four evaluators compute the same quantity (the monic
 * resultant R, or a2^2 b2^2 R for the projective one):
 *
 *   raw   : projective resultant from raw coefficients, 7M + 1S per pair, no
 *           per-endpoint work;
 *   monic : (C - F)^2 + (B - E)(B F - C E) after monic normalisation,
 *           3M + 1S per pair, 1 batched inversion + 2M per endpoint;
 *   dot6  : rank-six flattening as a 6-term dot product of stored monomials;
 *   twop  : (F - C)(UL + UR) + (E - B)(VR - VL), 2M per pair, endpoint
 *           features (B, C, B^2 - C, B C) / (E, F, F - E^2, E F).
 *
 * The timed interval for each evaluator includes its per-endpoint
 * precomputation (batch inversion with Montgomery's trick) and the pair loop;
 * the two parts are also reported separately.  Correctness: every evaluator's
 * per-pair output is folded into a checksum, the projective one after
 * multiplying the monic R by a2^2 b2^2 outside the timed loop, and the four
 * checksums must agree.
 *
 * usage: s4_bench nL nR W trials seed label
 * pairs: k = 0..W-1 -> (k mod nL, (k * 0x9E3779B97F4A7C15 >> 11) mod nR)
 * output: one JSON object per line.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/resource.h>

typedef unsigned __int128 u128;
typedef uint64_t u64;
static const u64 P = ((u64)1 << 61) - 1;

static inline u64 addm(u64 a, u64 b) { u64 r = a + b; return r >= P ? r - P : r; }
static inline u64 subm(u64 a, u64 b) { return a >= b ? a - b : a + P - b; }
static inline u64 mulm(u64 a, u64 b) {
    u128 p = (u128)a * b;
    u64 lo = (u64)p & P, hi = (u64)(p >> 61);
    u64 r = lo + hi;
    return r >= P ? r - P : r;
}
static u64 powm(u64 a, u64 e) { u64 r = 1; while (e) { if (e & 1) r = mulm(r, a); a = mulm(a, a); e >>= 1; } return r; }
static u64 invm(u64 a) { return powm(a, P - 2); }

static u64 rng_s;
static u64 rnd(void) { rng_s ^= rng_s << 13; rng_s ^= rng_s >> 7; rng_s ^= rng_s << 17; return rng_s % P; }

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + 1e-9 * t.tv_nsec; }

typedef struct { u64 a0, a1, a2; } Raw;
typedef struct { u64 B, C; } Monic;
typedef struct { u64 v[6]; } Six;
typedef struct { u64 B, C, U, V; } Feat;

static u64 CA, CB; /* curve coefficients */

static Raw s3_coeffs(u64 x1, u64 x2) {
    Raw r;
    u64 d = subm(x1, x2), s = addm(x1, x2), m = mulm(x1, x2);
    r.a2 = mulm(d, d);
    u64 t = addm(mulm(s, addm(m, CA)), addm(CB, CB));
    r.a1 = subm(0, addm(t, t));
    u64 u = subm(m, CA);
    r.a0 = subm(mulm(u, u), mulm(mulm(4, CB), s));
    return r;
}

/* Montgomery batch inversion of a2 into inv[]: 3M per element + 1 inversion. */
static void batch_inv(const Raw *e, u64 *inv, size_t n, u64 *scratch) {
    u64 acc = 1;
    for (size_t i = 0; i < n; i++) { scratch[i] = acc; acc = mulm(acc, e[i].a2); }
    acc = invm(acc);
    for (size_t i = n; i-- > 0;) { inv[i] = mulm(acc, scratch[i]); acc = mulm(acc, e[i].a2); }
}

static void pre_monic(const Raw *e, Monic *m, size_t n, u64 *inv, u64 *scratch) {
    batch_inv(e, inv, n, scratch);
    for (size_t i = 0; i < n; i++) { m[i].B = mulm(e[i].a1, inv[i]); m[i].C = mulm(e[i].a0, inv[i]); }
}
static void pre_six_left(const Raw *e, Six *s, size_t n, u64 *inv, u64 *scratch) {
    batch_inv(e, inv, n, scratch);
    for (size_t i = 0; i < n; i++) {
        u64 B = mulm(e[i].a1, inv[i]), C = mulm(e[i].a0, inv[i]);
        s[i].v[0] = mulm(B, B); s[i].v[1] = C; s[i].v[2] = 1; s[i].v[3] = mulm(C, C); s[i].v[4] = mulm(B, C); s[i].v[5] = B;
    }
}
static void pre_six_right(const Raw *e, Six *s, size_t n, u64 *inv, u64 *scratch) {
    batch_inv(e, inv, n, scratch);
    for (size_t i = 0; i < n; i++) {
        u64 E = mulm(e[i].a1, inv[i]), F = mulm(e[i].a0, inv[i]);
        s[i].v[0] = F; s[i].v[1] = subm(mulm(E, E), addm(F, F)); s[i].v[2] = mulm(F, F); s[i].v[3] = 1; s[i].v[4] = subm(0, E); s[i].v[5] = subm(0, mulm(E, F));
    }
}
static void pre_feat_left(const Raw *e, Feat *f, size_t n, u64 *inv, u64 *scratch) {
    batch_inv(e, inv, n, scratch);
    for (size_t i = 0; i < n; i++) {
        u64 B = mulm(e[i].a1, inv[i]), C = mulm(e[i].a0, inv[i]);
        f[i].B = B; f[i].C = C; f[i].U = subm(mulm(B, B), C); f[i].V = mulm(B, C);
    }
}
static void pre_feat_right(const Raw *e, Feat *f, size_t n, u64 *inv, u64 *scratch) {
    batch_inv(e, inv, n, scratch);
    for (size_t i = 0; i < n; i++) {
        u64 E = mulm(e[i].a1, inv[i]), F = mulm(e[i].a0, inv[i]);
        f[i].B = E; f[i].C = F; f[i].U = subm(F, mulm(E, E)); f[i].V = mulm(E, F);
    }
}

static inline u64 ev_raw(const Raw *l, const Raw *r) {
    u64 t1 = subm(mulm(l->a2, r->a0), mulm(l->a0, r->a2));
    u64 t2 = subm(mulm(l->a2, r->a1), mulm(l->a1, r->a2));
    u64 t3 = subm(mulm(l->a1, r->a0), mulm(l->a0, r->a1));
    return subm(mulm(t1, t1), mulm(t2, t3));
}
static inline u64 ev_monic(const Monic *l, const Monic *r) {
    u64 d = subm(l->C, r->C), e = subm(l->B, r->B);
    u64 t = subm(mulm(l->B, r->C), mulm(l->C, r->B));
    return addm(mulm(d, d), mulm(e, t));
}
static inline u64 ev_six(const Six *l, const Six *r) {
    u64 s = 0;
    for (int k = 0; k < 6; k++) s = addm(s, mulm(l->v[k], r->v[k]));
    return s;
}
static inline u64 ev_twop(const Feat *l, const Feat *r) {
    return addm(mulm(subm(r->C, l->C), addm(l->U, r->U)), mulm(subm(r->B, l->B), subm(r->V, l->V)));
}

static inline size_t right_index(size_t k, size_t nR) { return (size_t)(((k * 0x9E3779B97F4A7C15ULL) >> 11) % nR); }

static int cmp_double(const void *a, const void *b) { double x = *(const double *)a, y = *(const double *)b; return (x > y) - (x < y); }
static double median(double *v, int n) { qsort(v, n, sizeof(double), cmp_double); return n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]); }

int main(int argc, char **argv) {
    if (argc < 7) { fprintf(stderr, "usage: s4_bench nL nR W trials seed label\n"); return 2; }
    size_t nL = strtoull(argv[1], 0, 10), nR = strtoull(argv[2], 0, 10), W = strtoull(argv[3], 0, 10);
    int trials = atoi(argv[4]);
    double t_start = now();
    rng_s = strtoull(argv[5], 0, 10) * 0x9E3779B97F4A7C15ULL + 1;
    const char *label = argv[6];
    CA = rnd(); CB = rnd();

    Raw *L = malloc(nL * sizeof(Raw)), *R = malloc(nR * sizeof(Raw));
    for (size_t i = 0; i < nL; i++) { u64 x1 = rnd(), x2; do x2 = rnd(); while (x2 == x1); L[i] = s3_coeffs(x1, x2); }
    for (size_t i = 0; i < nR; i++) { u64 x1 = rnd(), x2; do x2 = rnd(); while (x2 == x1); R[i] = s3_coeffs(x1, x2); }
    size_t nmax = nL > nR ? nL : nR;
    u64 *inv = malloc(nmax * sizeof(u64)), *scratch = malloc(nmax * sizeof(u64));
    Monic *mL = malloc(nL * sizeof(Monic)), *mR = malloc(nR * sizeof(Monic));
    Six *sL = malloc(nL * sizeof(Six)), *sR = malloc(nR * sizeof(Six));
    Feat *fL = malloc(nL * sizeof(Feat)), *fR = malloc(nR * sizeof(Feat));

    enum { RAW, MONIC, SIX, TWOP, NM };
    const char *names[NM] = { "raw_fused_7M1S", "monic_fused_3M1S", "rank_six_dot_6M", "two_product_2M" };
    double pre_t[NM][64], pair_t[NM][64];
    u64 check[NM] = { 0 };
    if (trials > 64) trials = 64;

    for (int t = 0; t < trials; t++) {
        for (int mi = 0; mi < NM; mi++) {
            int m = (mi + t) % NM; /* rotate evaluator order per trial */
            double t0 = now();
            switch (m) {
                case RAW: break;
                case MONIC: pre_monic(L, mL, nL, inv, scratch); pre_monic(R, mR, nR, inv, scratch); break;
                case SIX: pre_six_left(L, sL, nL, inv, scratch); pre_six_right(R, sR, nR, inv, scratch); break;
                case TWOP: pre_feat_left(L, fL, nL, inv, scratch); pre_feat_right(R, fR, nR, inv, scratch); break;
            }
            double t1 = now();
            u64 cs = 0;
            switch (m) {
                case RAW:   for (size_t k = 0; k < W; k++) cs = addm(cs, ev_raw(&L[k % nL], &R[right_index(k, nR)])); break;
                case MONIC: for (size_t k = 0; k < W; k++) cs = addm(cs, ev_monic(&mL[k % nL], &mR[right_index(k, nR)])); break;
                case SIX:   for (size_t k = 0; k < W; k++) cs = addm(cs, ev_six(&sL[k % nL], &sR[right_index(k, nR)])); break;
                case TWOP:  for (size_t k = 0; k < W; k++) cs = addm(cs, ev_twop(&fL[k % nL], &fR[right_index(k, nR)])); break;
            }
            double t2 = now();
            pre_t[m][t] = t1 - t0; pair_t[m][t] = t2 - t1;
            if (t == 0) check[m] = cs; else if (check[m] != cs) { fprintf(stderr, "checksum drift in %s\n", names[m]); return 1; }
        }
    }
    /* Correctness: monic R scaled by a2^2 b2^2 must reproduce the projective checksum, and the
       three monic evaluators must agree pairwise on every pair. */
    u64 proj_from_monic = 0; size_t mism = 0;
    for (size_t k = 0; k < W; k++) {
        size_t i = k % nL, j = right_index(k, nR);
        u64 r1 = ev_monic(&mL[i], &mR[j]), r2 = ev_six(&sL[i], &sR[j]), r3 = ev_twop(&fL[i], &fR[j]);
        if (r1 != r2 || r1 != r3) mism++;
        u64 sc = mulm(mulm(L[i].a2, L[i].a2), mulm(R[j].a2, R[j].a2));
        proj_from_monic = addm(proj_from_monic, mulm(sc, r3));
    }
    int ok = (mism == 0) && (proj_from_monic == check[RAW]) && (check[MONIC] == check[SIX]) && (check[MONIC] == check[TWOP]);

    printf("{\"label\":\"%s\",\"nL\":%zu,\"nR\":%zu,\"W\":%zu,\"trials\":%d,\"all_evaluators_agree\":%s,\"pair_mismatches\":%zu,\"checksum_monic\":%llu,\"checksum_projective\":%llu,\"evaluators\":[",
           label, nL, nR, W, trials, ok ? "true" : "false", mism, (unsigned long long)check[MONIC], (unsigned long long)check[RAW]);
    for (int m = 0; m < NM; m++) {
        double pre = median(pre_t[m], trials), pr = median(pair_t[m], trials);
        double tot[64]; for (int t = 0; t < trials; t++) tot[t] = pre_t[m][t] + pair_t[m][t];
        double tmed = median(tot, trials);
        double tmin = tot[0]; for (int t = 1; t < trials; t++) if (tot[t] < tmin) tmin = tot[t];
        printf("%s{\"name\":\"%s\",\"precompute_ms_median\":%.4f,\"pairs_ms_median\":%.4f,\"total_ms_median\":%.4f,\"total_ms_min\":%.4f,\"ns_per_pair_total_median\":%.3f,\"ns_per_pair_loop_median\":%.3f}",
               m ? "," : "", names[m], pre * 1e3, pr * 1e3, tmed * 1e3, tmin * 1e3, tmed * 1e9 / W, pr * 1e9 / W);
    }
    struct rusage ru;
    getrusage(RUSAGE_SELF, &ru);
    double cpu_s = ru.ru_utime.tv_sec + 1e-6 * ru.ru_utime.tv_usec + ru.ru_stime.tv_sec + 1e-6 * ru.ru_stime.tv_usec;
    printf("],\"process\":{\"cpu_time_s_user_plus_sys\":%.4f,\"wall_s_total\":%.4f,\"peak_rss_kB\":%ld,\"minor_faults\":%ld,\"major_faults\":%ld,\"voluntary_ctx_switches\":%ld,\"involuntary_ctx_switches\":%ld}}\n",
           cpu_s, now() - t_start, ru.ru_maxrss, ru.ru_minflt, ru.ru_majflt, ru.ru_nvcsw, ru.ru_nivcsw);
    return ok ? 0 : 1;
}
