/* G1: floating-point CVP screening sweep (second, independent implementation).
 * For each job (d, k0, k1): iterate zeta = h^k (k in [k0,k1), gcd(k,d)=1) implicitly via
 * R1 = zeta*A1 mod N, R2 = zeta*A2 mod N (3-limb Montgomery arithmetic), f_i = R_i/N,
 * and compute min_{k1,k2} g11 a^2 + 2 g12 a b + g22 b^2, a = f1-k1, b = f2-k2 (= norm of the
 * minimum-norm element of the coset {ev = zeta}).
 * Input on stdin:
 *   line 1: N_hex nthreads g11 g12 g22 W flag_threshold_log2
 *   then jobs: d k0 k1 nprimes p1..pn R1_hex R2_hex hm_hex     (hm = h*2^192 mod N)
 * Output: per job "J d k0 k1 count minlog2 argk hist..." and "F d k norm_log2" for flagged. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <pthread.h>

typedef unsigned __int128 u128;
typedef struct { uint64_t w[3]; } u192;

static u192 NN; static uint64_t NINV; /* -N^{-1} mod 2^64 */
static double Nd, G11, G12, G22; static int W; static double FLAG;

static void parse_hex(const char *s, u192 *r) {
    memset(r, 0, sizeof *r);
    size_t L = strlen(s);
    for (size_t i = 0; i < L; i++) {
        char c = s[L - 1 - i]; int v;
        if (c >= '0' && c <= '9') v = c - '0'; else if (c >= 'a' && c <= 'f') v = c - 'a' + 10; else if (c >= 'A' && c <= 'F') v = c - 'A' + 10; else { fprintf(stderr, "bad hex\n"); exit(1); }
        r->w[i / 16] |= (uint64_t)v << (4 * (i % 16));
    }
}
static inline int geq(const uint64_t *a, const u192 *n) {
    for (int i = 2; i >= 0; i--) { if (a[i] != n->w[i]) return a[i] > n->w[i]; }
    return 1;
}
/* Montgomery product a*b*2^-192 mod N, inputs < N, output < N (CIOS). */
static inline u192 mont(const u192 a, const u192 b) {
    uint64_t t[5] = {0, 0, 0, 0, 0};
    for (int i = 0; i < 3; i++) {
        u128 C = 0;
        for (int j = 0; j < 3; j++) { C = (u128)t[j] + (u128)a.w[j] * b.w[i] + (C >> 64); t[j] = (uint64_t)C; }
        C = (u128)t[3] + (C >> 64); t[3] = (uint64_t)C; t[4] = (uint64_t)(C >> 64);
        uint64_t m = t[0] * NINV;
        C = (u128)t[0] + (u128)m * NN.w[0];
        for (int j = 1; j < 3; j++) { C = (u128)t[j] + (u128)m * NN.w[j] + (C >> 64); t[j - 1] = (uint64_t)C; }
        C = (u128)t[3] + (C >> 64); t[2] = (uint64_t)C;
        t[3] = t[4] + (uint64_t)(C >> 64);
    }
    u192 r;
    if (t[3] || geq(t, &NN)) {
        u128 B = 0;
        for (int j = 0; j < 3; j++) { u128 x = (u128)t[j] - NN.w[j] - B; r.w[j] = (uint64_t)x; B = (x >> 64) & 1; }
    } else { r.w[0] = t[0]; r.w[1] = t[1]; r.w[2] = t[2]; }
    return r;
}
static inline double todbl(const u192 a) {
    return ldexp((double)a.w[2], 128) + ldexp((double)a.w[1], 64) + (double)a.w[0];
}

typedef struct { long d, k0, k1; int np; long pr[8]; u192 R1, R2, hm; } job_t;
typedef struct { long count; double minv; long argk; long hist[200]; } res_t;
static job_t *JOBS; static res_t *RES; static int NJOBS; static int next_job = 0;
static pthread_mutex_t LOCK = PTHREAD_MUTEX_INITIALIZER;
typedef struct { long d, k; double v; } flag_t;
static flag_t *FLAGS; static long NFLAGS = 0, CAPFLAGS = 1 << 20;

static void run_job(job_t *J, res_t *R) {
    u192 R1 = J->R1, R2 = J->R2;
    long ctr[8]; for (int i = 0; i < J->np; i++) ctr[i] = J->k0 % J->pr[i];
    R->count = 0; R->minv = INFINITY; R->argk = -1; memset(R->hist, 0, sizeof R->hist);
    double invN = 1.0 / Nd;
    for (long k = J->k0; k < J->k1; k++) {
        int ok = 1;
        for (int i = 0; i < J->np; i++) { if (ctr[i] == 0) ok = 0; if (++ctr[i] == J->pr[i]) ctr[i] = 0; }
        if (J->d == 1) ok = 1;
        if (ok) {
            double f1 = todbl(R1) * invN, f2 = todbl(R2) * invN;
            double best = INFINITY;
            for (int k2 = -W; k2 <= W + 1; k2++) {
                double b = f2 - k2;
                double k1s = f1 + G12 * b / G11;
                double k1f = floor(k1s);
                for (int e = 0; e < 2; e++) {
                    double a = f1 - (k1f + e);
                    double v = G11 * a * a + 2.0 * G12 * a * b + G22 * b * b;
                    if (v < best) best = v;
                }
            }
            R->count++;
            int bl = ilogb(best); if (bl < 0) bl = 0; if (bl > 199) bl = 199;
            R->hist[bl]++;
            if (best < R->minv) { R->minv = best; R->argk = k; }
            if (best < FLAG) {
                pthread_mutex_lock(&LOCK);
                if (NFLAGS < CAPFLAGS) { FLAGS[NFLAGS].d = J->d; FLAGS[NFLAGS].k = k; FLAGS[NFLAGS].v = best; }
                NFLAGS++;
                pthread_mutex_unlock(&LOCK);
            }
        }
        R1 = mont(R1, J->hm); R2 = mont(R2, J->hm);
    }
}
static void *worker(void *arg) {
    (void)arg;
    for (;;) {
        pthread_mutex_lock(&LOCK); int j = next_job++; pthread_mutex_unlock(&LOCK);
        if (j >= NJOBS) break;
        run_job(&JOBS[j], &RES[j]);
    }
    return NULL;
}
int main(int argc, char **argv) {
    char nh[128]; int nth; double flog;
    if (scanf("%127s %d %lf %lf %lf %d %lf", nh, &nth, &G11, &G12, &G22, &W, &flog) != 7) return 1;
    parse_hex(nh, &NN); Nd = todbl(NN); FLAG = ldexp(1.0, 0) * pow(2.0, flog);
    uint64_t inv = 1; for (int i = 0; i < 7; i++) inv *= 2 - NN.w[0] * inv; NINV = -inv;
    if (argc > 1 && strcmp(argv[1], "--selftest") == 0) {
        /* read pairs a b and print mont(a,b) in hex */
        char ah[128], bh[128];
        while (scanf("%127s %127s", ah, bh) == 2) {
            u192 a, b; parse_hex(ah, &a); parse_hex(bh, &b); u192 r = mont(a, b);
            printf("%016llx%016llx%016llx\n", (unsigned long long)r.w[2], (unsigned long long)r.w[1], (unsigned long long)r.w[0]);
        }
        return 0;
    }
    int cap = 1024; JOBS = malloc(cap * sizeof *JOBS); NJOBS = 0;
    for (;;) {
        job_t J; char r1[128], r2[128], hm[128];
        if (scanf("%ld %ld %ld %d", &J.d, &J.k0, &J.k1, &J.np) != 4) break;
        for (int i = 0; i < J.np; i++) if (scanf("%ld", &J.pr[i]) != 1) return 2;
        if (scanf("%127s %127s %127s", r1, r2, hm) != 3) return 3;
        parse_hex(r1, &J.R1); parse_hex(r2, &J.R2); parse_hex(hm, &J.hm);
        if (NJOBS == cap) { cap *= 2; JOBS = realloc(JOBS, cap * sizeof *JOBS); }
        JOBS[NJOBS++] = J;
    }
    RES = calloc(NJOBS, sizeof *RES); FLAGS = malloc(CAPFLAGS * sizeof *FLAGS);
    pthread_t th[64]; if (nth > 64) nth = 64;
    for (int i = 0; i < nth; i++) pthread_create(&th[i], NULL, worker, NULL);
    for (int i = 0; i < nth; i++) pthread_join(th[i], NULL);
    for (int j = 0; j < NJOBS; j++) {
        printf("J %ld %ld %ld %ld %.17g %ld", JOBS[j].d, JOBS[j].k0, JOBS[j].k1, RES[j].count,
               RES[j].count ? log2(RES[j].minv) : -1.0, RES[j].argk);
        for (int b = 0; b < 200; b++) if (RES[j].hist[b]) printf(" %d:%ld", b, RES[j].hist[b]);
        printf("\n");
    }
    long nf = NFLAGS < CAPFLAGS ? NFLAGS : CAPFLAGS;
    for (long i = 0; i < nf; i++) printf("F %ld %ld %.17g\n", FLAGS[i].d, FLAGS[i].k, log2(FLAGS[i].v));
    printf("NFLAGS %ld\n", NFLAGS);
    return 0;
}
