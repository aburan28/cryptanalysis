// Explicit conductor-prime torsion, kernel lines and kernel polynomials for
// y^2 + xy = x^3 + b over F_(2^m), computed in F_(2^(m r)) (see tower.h).
//
// Everything is x-only.  For the Koblitz curve (b = 1) the 2-Frobenius tau
// satisfies tau^2 + tau + 2 = 0, so tau(P + tau P) = -2P and
//     x(P + tau P) = sqrt(x(2P)) = x_P + 1/x_P,
// which starts the differential chain P + v tau(P) without any y-coordinate.
//
// Commands (all field elements are hex, bit i = coefficient of z^i or of the
// tower basis z^i Y^j at bit i of word j; tower elements are raw binary files):
//   selftest   M FTAPS R GTAPS
//   torsion    M FTAPS R GTAPS B TWIST ELL COFHEX SEED OUT   -> x of [cof]R, orders
//   lines      M FTAPS R GTAPS ELL XFILE                     -> Tr_q x(P + v tau P)
//   kernel     M FTAPS R GTAPS ELL XFILE LINE                -> kernel polynomial
//              (lines past ELL/2 are reached from x(P - tau P) in the other direction)
//   frobcheck  M FTAPS R GTAPS B ELL C XFILE                 -> x(P)^q == x([C]P)
// FTAPS / GTAPS are comma lists of the middle exponents of f and g.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "tower.h"

static double now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + 1e-9 * ts.tv_nsec;
}

static int parse_taps(const char *s, int *taps) {
    int n = 0;
    char buf[256];
    strncpy(buf, s, sizeof buf - 1);
    buf[sizeof buf - 1] = 0;
    for (char *tok = strtok(buf, ","); tok; tok = strtok(NULL, ",")) taps[n++] = atoi(tok);
    return n;
}

static u128 parse_hex128(const char *s) {
    u128 v = 0;
    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) s += 2;
    for (; *s; s++) {
        int d = (*s >= '0' && *s <= '9') ? *s - '0' : (*s | 32) - 'a' + 10;
        v = (v << 4) | (u128)d;
    }
    return v;
}

static void print_hex128(FILE *f, u128 v) {
    u64 hi = (u64)(v >> 64), lo = (u64)v;
    if (hi) fprintf(f, "%llx%016llx", (unsigned long long)hi, (unsigned long long)lo);
    else fprintf(f, "%llx", (unsigned long long)lo);
}

// big-endian bit string of a hex integer
typedef struct {
    uint8_t *bits;
    long n;
} bitstr;

static bitstr hex_bits(const char *hex) {
    bitstr b;
    long len = (long)strlen(hex);
    b.bits = malloc(4 * len + 1);
    b.n = 0;
    int started = 0;
    for (long i = 0; i < len; i++) {
        int d = (hex[i] >= '0' && hex[i] <= '9') ? hex[i] - '0' : (hex[i] | 32) - 'a' + 10;
        for (int k = 3; k >= 0; k--) {
            int bit = (d >> k) & 1;
            if (bit) started = 1;
            if (started) b.bits[b.n++] = (uint8_t)bit;
        }
    }
    return b;
}

static bitstr int_bits(u64 v) {
    char buf[32];
    snprintf(buf, sizeof buf, "%llx", (unsigned long long)v);
    return hex_bits(buf);
}

static u64 rng_state;
static u64 rng_next(void) {
    u64 z = (rng_state += 0x9e3779b97f4a7c15ull);
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
    return z ^ (z >> 31);
}

static void tw_random(const tower *T, u128 *a) {
    for (int i = 0; i < T->r; i++) {
        u128 v = ((u128)rng_next() << 64) | rng_next();
        a[i] = v & T->mask;
    }
}

static int write_elem(const tower *T, const char *path, const u128 *a) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    fwrite(a, sizeof(u128), (size_t)T->r, f);
    fclose(f);
    return 0;
}

static int read_elem(const tower *T, const char *path, u128 *a) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    size_t got = fread(a, sizeof(u128), (size_t)T->r, f);
    fclose(f);
    return got == (size_t)T->r ? 0 : -1;
}

// x-only Montgomery ladder (Lopez-Dahab) on y^2 + xy = x^3 + a x^2 + b.
// Returns 1 and x([k]P) in out, or 0 if [k]P = O.  x is affine.
typedef struct {
    tower *T;
    u128 b;
    u128 *X1, *Z1, *X2, *Z2, *t1, *t2, *t3;
} ladder;

static void ladder_init(ladder *L, tower *T, u128 b) {
    L->T = T;
    L->b = b;
    L->X1 = tw_alloc(T);
    L->Z1 = tw_alloc(T);
    L->X2 = tw_alloc(T);
    L->Z2 = tw_alloc(T);
    L->t1 = tw_alloc(T);
    L->t2 = tw_alloc(T);
    L->t3 = tw_alloc(T);
}

static void ladder_free(ladder *L) {
    free(L->X1);
    free(L->Z1);
    free(L->X2);
    free(L->Z2);
    free(L->t1);
    free(L->t2);
    free(L->t3);
}

// (X,Z) <- 2(X,Z): X' = X^4 + b Z^4, Z' = X^2 Z^2
static void mdouble(ladder *L, u128 *X, u128 *Z) {
    tower *T = L->T;
    tw_sqr(T, L->t1, X);       // X^2
    tw_sqr(T, L->t2, Z);       // Z^2
    tw_mul(T, Z, L->t1, L->t2);
    tw_sqr(T, L->t1, L->t1);   // X^4
    tw_sqr(T, L->t2, L->t2);   // Z^4
    if (L->b != 1) tw_scale(T, L->t2, L->t2, L->b);
    tw_add(T, X, L->t1, L->t2);
}

// (X1,Z1) <- (X1,Z1) + (X2,Z2) with affine difference x
static void madd(ladder *L, u128 *X1, u128 *Z1, const u128 *X2, const u128 *Z2, const u128 *x) {
    tower *T = L->T;
    tw_mul(T, L->t1, X1, Z2);
    tw_mul(T, L->t2, X2, Z1);
    tw_add(T, L->t3, L->t1, L->t2);
    tw_sqr(T, Z1, L->t3);
    tw_mul(T, L->t1, L->t1, L->t2);
    tw_mul(T, L->t3, x, Z1);
    tw_add(T, X1, L->t3, L->t1);
}

static int ladder_run(ladder *L, u128 *out, const u128 *x, const bitstr *k, int progress) {
    tower *T = L->T;
    if (k->n == 0) return 0;
    tw_copy(T, L->X1, x);
    tw_one(T, L->Z1);
    tw_copy(T, L->X2, x);
    tw_one(T, L->Z2);
    mdouble(L, L->X2, L->Z2);
    double t0 = now();
    for (long i = 1; i < k->n; i++) {
        if (k->bits[i]) {
            madd(L, L->X1, L->Z1, L->X2, L->Z2, x);
            mdouble(L, L->X2, L->Z2);
        } else {
            madd(L, L->X2, L->Z2, L->X1, L->Z1, x);
            mdouble(L, L->X1, L->Z1);
        }
        if (progress && i % 4096 == 0) {
            double el = now() - t0;
            fprintf(stderr, "ladder %ld/%ld bits, %.1f s, eta %.0f s\n", i, k->n, el,
                    el / i * (k->n - i));
        }
    }
    if (tw_is_zero(T, L->Z1)) return 0;
    tw_inv(T, L->t1, L->Z1);
    tw_mul(T, out, L->X1, L->t1);
    return 1;
}

// Tr_(2^(mr)/2)(x + b/x^2) = 0 iff x lifts to the curve over the big field.
static int lifts(tower *T, const u128 *x, u128 b, u128 *tmp) {
    tw_inv(T, tmp, x);
    tw_sqr(T, tmp, tmp);
    tw_scale(T, tmp, tmp, b);
    tw_add(T, tmp, tmp, x);
    return tw_trace2(T, tmp) == 0;
}

static tower T;

static int setup(char **argv) {
    int ft[4], gt[4];
    int nf = parse_taps(argv[1], ft);
    int ng = parse_taps(argv[3], gt);
    int rc = tower_init(&T, atoi(argv[0]), ft, nf, atoi(argv[2]), gt, ng);
    const char *th = getenv("TOWER_THREADS");
    if (th) T.threads = atoi(th);
    return rc;
}

static int cmd_selftest(void) {
    rng_state = 12345;
    u128 *a = tw_alloc(&T), *b = tw_alloc(&T), *c = tw_alloc(&T), *d = tw_alloc(&T), *e = tw_alloc(&T);
    int ok = 1;
    for (int it = 0; it < 4; it++) {
        tw_random(&T, a);
        tw_random(&T, b);
        tw_random(&T, c);
        tw_mul(&T, d, a, b);
        tw_mul(&T, d, d, c);
        tw_mul(&T, e, b, c);
        tw_mul(&T, e, a, e);
        ok &= tw_equal(&T, d, e);
        tw_add(&T, d, b, c);
        tw_mul(&T, d, a, d);
        tw_mul(&T, e, a, b);
        tw_mul(&T, c, a, c);
        tw_add(&T, e, e, c);
        ok &= tw_equal(&T, d, e);
        tw_mul(&T, d, a, a);
        tw_sqr(&T, e, a);
        ok &= tw_equal(&T, d, e);
    }
    double t0 = now();
    int reps = 50;
    for (int i = 0; i < reps; i++) tw_mul(&T, d, a, b);
    double tmul = (now() - t0) / reps;
    t0 = now();
    for (int i = 0; i < reps; i++) tw_sqr(&T, d, a);
    double tsqr = (now() - t0) / reps;
    t0 = now();
    tw_inv(&T, c, a);
    double tinv = now() - t0;
    tw_mul(&T, d, a, c);
    tw_one(&T, e);
    ok &= tw_equal(&T, d, e);
    // Frobenius of order r on the tower over F_(2^m); the trace to F_q is fixed by it.
    tw_copy(&T, d, a);
    for (int i = 0; i < T.r; i++) tw_frob_q(&T, d, d);
    ok &= tw_equal(&T, d, a);
    u128 tq = tw_trace_q(&T, a);
    tw_zero(&T, d);
    tw_copy(&T, e, a);
    for (int i = 0; i < T.r; i++) {
        tw_add(&T, d, d, e);
        tw_frob_q(&T, e, e);
    }
    int trace_ok = (d[0] == tq);
    for (int i = 1; i < T.r; i++) trace_ok &= (d[i] == 0);
    ok &= trace_ok;
    printf("{\"selftest\":%s,\"trace_q_matches_frobenius_sum\":%s,\"mul_seconds\":%.6f,\"sqr_seconds\":%.6f,"
           "\"inv_seconds\":%.3f,\"words\":%zu}\n",
           ok ? "true" : "false", trace_ok ? "true" : "false", tmul, tsqr, tinv, T.nwords);
    return ok ? 0 : 1;
}

static int cmd_bench(void) {
    rng_state = 99;
    u128 *a = tw_alloc(&T), *b = tw_alloc(&T), *d = tw_alloc(&T);
    tw_random(&T, a);
    tw_random(&T, b);
    for (int i = 0; i < 20; i++) tw_mul(&T, d, a, b);
    int reps = 400;
    double t0 = now();
    for (int i = 0; i < reps; i++) tw_mul(&T, d, a, b);
    double tmul = (now() - t0) / reps;
    t0 = now();
    for (int i = 0; i < reps; i++) tw_sqr(&T, d, a);
    double tsqr = (now() - t0) / reps;
    printf("{\"mul_ms\":%.4f,\"sqr_ms\":%.4f,\"words\":%zu}\n", 1e3 * tmul, 1e3 * tsqr, T.nwords);
    return 0;
}

// [cof]R for a random R on the curve (TWIST=0) or its quadratic twist over
// the big field (TWIST=1); then report the order of the result modulo ELL^2.
static int cmd_torsion(char **argv) {
    u128 b = parse_hex128(argv[0]);
    int twist = atoi(argv[1]);
    u64 ell = strtoull(argv[2], 0, 10);
    FILE *cf = fopen(argv[3], "r");
    if (!cf) return 2;
    fseek(cf, 0, SEEK_END);
    long len = ftell(cf);
    fseek(cf, 0, SEEK_SET);
    char *hex = malloc(len + 1);
    long got = (long)fread(hex, 1, len, cf);
    hex[got] = 0;
    fclose(cf);
    while (got > 0 && (hex[got - 1] == '\n' || hex[got - 1] == ' ')) hex[--got] = 0;
    bitstr cof = hex_bits(hex), lb = int_bits(ell);
    rng_state = strtoull(argv[4], 0, 10);
    const char *out = argv[5];
    u128 *x = tw_alloc(&T), *tmp = tw_alloc(&T), *P = tw_alloc(&T), *P2 = tw_alloc(&T);
    ladder L;
    ladder_init(&L, &T, b);
    int tries = 0;
    double t0 = now();
    for (;;) {
        tries++;
        tw_random(&T, x);
        if (tw_is_zero(&T, x)) continue;
        int on_curve = lifts(&T, x, b, tmp);
        if (on_curve == twist) continue;
        fprintf(stderr, "sample %d accepted (twist=%d), ladder over %ld bits\n", tries, twist, cof.n);
        if (!ladder_run(&L, P, x, &cof, 1)) {
            fprintf(stderr, "cofactor multiple is infinity; resampling\n");
            continue;
        }
        break;
    }
    double tl = now() - t0;
    int order_ell = !ladder_run(&L, P2, P, &lb, 0);
    int order_ell2 = 0;
    if (!order_ell) order_ell2 = !ladder_run(&L, tmp, P2, &lb, 0);
    write_elem(&T, out, P);
    if (!order_ell && order_ell2) {
        char path2[4096];
        snprintf(path2, sizeof path2, "%s.ell", out);
        write_elem(&T, path2, P2);
    }
    printf("{\"samples\":%d,\"cofactor_bits\":%ld,\"ladder_seconds\":%.1f,\"order_is_ell\":%s,"
           "\"order_is_ell_squared\":%s,\"trace_q_x\":\"",
           tries, cof.n, tl, order_ell ? "true" : "false", order_ell2 ? "true" : "false");
    print_hex128(stdout, tw_trace_q(&T, P));
    printf("\"}\n");
    ladder_free(&L);
    return 0;
}

// x(P)^q == x([c]P), and x(P + tau P) = x_P + 1/x_P has order ELL.
static int cmd_frobcheck(char **argv) {
    u128 b = parse_hex128(argv[0]);
    u64 ell = strtoull(argv[1], 0, 10);
    u64 c = strtoull(argv[2], 0, 10);
    u128 *x = tw_alloc(&T), *y = tw_alloc(&T), *z = tw_alloc(&T), *s = tw_alloc(&T);
    if (read_elem(&T, argv[3], x)) return 2;
    ladder L;
    ladder_init(&L, &T, b);
    tw_frob_q(&T, y, x);
    bitstr cb = int_bits(c), lb = int_bits(ell);
    ladder_run(&L, z, x, &cb, 0);
    int frob_ok = tw_equal(&T, y, z);
    int lines_ok = -1;
    if (b == 1) {
        tw_inv(&T, s, x);
        tw_add(&T, s, s, x);                // x(P + tau P)
        lines_ok = !ladder_run(&L, z, s, &lb, 0);
        tw_sqr(&T, y, x);                   // x(tau P)
        lines_ok &= !ladder_run(&L, z, y, &lb, 0);
        lines_ok &= !tw_equal(&T, s, x) && !tw_equal(&T, s, y);
    }
    printf("{\"frobenius_scalar\":%llu,\"frobenius_matches\":%s,\"tau_sum_has_order_ell\":%s}\n",
           (unsigned long long)c, frob_ok ? "true" : "false",
           lines_ok < 0 ? "null" : (lines_ok ? "true" : "false"));
    ladder_free(&L);
    return frob_ok ? 0 : 1;
}

// Chain G_v = P + v tau(P): x(G_{v+1}) = x(G_{v-1}) + x_v x_T / (x_v + x_T)^2.
// Projective update with Z's batched: U = (X_v + x_T Z_v)^2,
//   X_{v+1} = X_{v-1} U + Z_{v-1} X_v Z_v x_T,  Z_{v+1} = Z_{v-1} U.
typedef struct {
    u128 *xT, *Xp, *Zp, *Xc, *Zc, *Xn, *Zn, *t1, *t2;
    long v;   // index of (Xc, Zc)
} chain;

static void chain_init(chain *C, const u128 *xP) {
    C->xT = tw_alloc(&T);
    C->Xp = tw_alloc(&T);
    C->Zp = tw_alloc(&T);
    C->Xc = tw_alloc(&T);
    C->Zc = tw_alloc(&T);
    C->Xn = tw_alloc(&T);
    C->Zn = tw_alloc(&T);
    C->t1 = tw_alloc(&T);
    C->t2 = tw_alloc(&T);
    tw_sqr(&T, C->xT, xP);
    tw_copy(&T, C->Xp, xP);
    tw_one(&T, C->Zp);
    tw_inv(&T, C->Xc, xP);
    tw_add(&T, C->Xc, C->Xc, xP);
    tw_one(&T, C->Zc);
    C->v = 1;
}

// Chain G_-u = P - u tau(P) from x(P - tau P) = x(P + tau P) + x_P x_T / (x_P + x_T)^2.
static void chain_init_neg(chain *C, const u128 *xP) {
    chain_init(C, xP);
    u128 *s = C->t1, *t = C->t2;
    tw_add(&T, s, xP, C->xT);
    tw_sqr(&T, s, s);
    tw_inv(&T, s, s);
    tw_mul(&T, t, xP, C->xT);
    tw_mul(&T, t, t, s);
    tw_add(&T, C->Xc, C->Xc, t);
}

static void chain_step(chain *C) {
    tw_mul(&T, C->t1, C->xT, C->Zc);
    tw_add(&T, C->t1, C->t1, C->Xc);
    tw_sqr(&T, C->t1, C->t1);            // U
    tw_mul(&T, C->Zn, C->Zp, C->t1);
    tw_mul(&T, C->Xn, C->Xp, C->t1);
    tw_mul(&T, C->t2, C->Xc, C->Zc);
    tw_mul(&T, C->t2, C->t2, C->xT);
    tw_mul(&T, C->t2, C->t2, C->Zp);
    tw_add(&T, C->Xn, C->Xn, C->t2);
    u128 *s;
    s = C->Xp; C->Xp = C->Xc; C->Xc = C->Xn; C->Xn = s;
    s = C->Zp; C->Zp = C->Zc; C->Zc = C->Zn; C->Zn = s;
    C->v++;
}

static int cmd_lines(char **argv) {
    u64 ell = strtoull(argv[0], 0, 10);
    u128 *x = tw_alloc(&T);
    if (read_elem(&T, argv[1], x)) return 2;
    const long block = 512;
    u128 **X = malloc(block * sizeof(u128 *)), **Z = malloc(block * sizeof(u128 *));
    for (long i = 0; i < block; i++) {
        X[i] = tw_alloc(&T);
        Z[i] = tw_alloc(&T);
    }
    u128 *acc = tw_alloc(&T), *inv = tw_alloc(&T), *t = tw_alloc(&T);
    chain C;
    chain_init(&C, x);
    // line 0 is <P>, lines 1..ell-1 are <P + v tau P>, line "inf" is <tau P>.
    printf("{\"line\":\"inf\",\"trace\":\"");
    print_hex128(stdout, fm_sqr(&T, tw_trace_q(&T, x)));
    printf("\"}\n{\"line\":0,\"trace\":\"");
    print_hex128(stdout, tw_trace_q(&T, x));
    printf("\"}\n");
    double t0 = now();
    long next = 1;
    while (next < (long)ell) {
        long n = 0;
        while (n < block && next + n < (long)ell) {
            if (C.v != next + n) return 3;
            tw_copy(&T, X[n], C.Xc);
            tw_copy(&T, Z[n], C.Zc);
            chain_step(&C);
            n++;
        }
        // batch inversion of Z[0..n)
        tw_copy(&T, acc, Z[0]);
        u128 **pre = malloc(n * sizeof(u128 *));
        pre[0] = tw_alloc(&T);
        tw_copy(&T, pre[0], Z[0]);
        for (long i = 1; i < n; i++) {
            pre[i] = tw_alloc(&T);
            tw_mul(&T, pre[i], pre[i - 1], Z[i]);
        }
        tw_inv(&T, inv, pre[n - 1]);
        for (long i = n - 1; i >= 0; i--) {
            if (i > 0) {
                tw_mul(&T, t, inv, pre[i - 1]);     // 1/Z_i
                tw_mul(&T, inv, inv, Z[i]);
            } else {
                tw_copy(&T, t, inv);
            }
            tw_mul(&T, X[i], X[i], t);             // affine x(G_{next+i})
        }
        for (long i = 0; i < n; i++) {
            printf("{\"line\":%ld,\"trace\":\"", next + i);
            print_hex128(stdout, tw_trace_q(&T, X[i]));
            printf("\"}\n");
            free(pre[i]);
        }
        free(pre);
        fflush(stdout);
        next += n;
        fprintf(stderr, "lines %ld/%llu, %.1f s\n", next, (unsigned long long)ell, now() - t0);
    }
    // G_ell = P closes the chain: x(G_ell) must equal x_P.
    tw_inv(&T, t, C.Zc);
    tw_mul(&T, t, t, C.Xc);
    int closed = (C.v == (long)ell) && tw_equal(&T, t, x);
    fprintf(stderr, "chain closes at v=%ld: %s\n", C.v, closed ? "yes" : "NO");
    printf("{\"chain_closes\":%s,\"seconds\":%.1f}\n", closed ? "true" : "false", now() - t0);
    return closed ? 0 : 1;
}

// Berlekamp-Massey over F_(2^m): minimal connection polynomial of s[0..n).
static int bm(const u128 *s, long n, u128 *C, long *Lout) {
    u128 *B = calloc(n + 1, sizeof(u128)), *Tt = calloc(n + 1, sizeof(u128));
    memset(C, 0, (n + 1) * sizeof(u128));
    C[0] = 1;
    B[0] = 1;
    long L = 0, mm = 1;
    u128 bb = 1;
    for (long i = 0; i < n; i++) {
        u128 d = s[i];
        for (long j = 1; j <= L; j++) d ^= fm_mul(&T, C[j], s[i - j]);
        if (d == 0) {
            mm++;
        } else if (2 * L <= i) {
            memcpy(Tt, C, (n + 1) * sizeof(u128));
            u128 coef = fm_mul(&T, d, fm_inv(&T, bb));
            for (long j = 0; j + mm <= n; j++) C[j + mm] ^= fm_mul(&T, coef, B[j]);
            L = i + 1 - L;
            memcpy(B, Tt, (n + 1) * sizeof(u128));
            bb = d;
            mm = 1;
        } else {
            u128 coef = fm_mul(&T, d, fm_inv(&T, bb));
            for (long j = 0; j + mm <= n; j++) C[j + mm] ^= fm_mul(&T, coef, B[j]);
            mm++;
        }
    }
    free(B);
    free(Tt);
    *Lout = L;
    return 0;
}

// Kernel polynomial of line LINE: the minimal polynomial over F_q of x(G),
// from the sequence Tr_q(x^i), i < 2d, with d = (ELL-1)/2.
static int cmd_kernel(char **argv) {
    u64 ell = strtoull(argv[0], 0, 10);
    u128 *x = tw_alloc(&T), *g = tw_alloc(&T), *p = tw_alloc(&T);
    if (read_elem(&T, argv[1], x)) return 2;
    const char *line = argv[2];
    double t0 = now();
    if (!strcmp(line, "inf")) {
        tw_sqr(&T, g, x);
    } else {
        long v = atol(line);
        if (v == 0) {
            tw_copy(&T, g, x);
        } else if (2 * v <= (long)ell) {
            chain C;
            chain_init(&C, x);
            while (C.v < v) chain_step(&C);
            tw_inv(&T, g, C.Zc);
            tw_mul(&T, g, g, C.Xc);
        } else {                       // walk P - u tau(P), u = ell - v
            long u = (long)ell - v;
            chain C;
            chain_init_neg(&C, x);
            while (C.v < u) chain_step(&C);
            tw_inv(&T, g, C.Zc);
            tw_mul(&T, g, g, C.Xc);
        }
    }
    double tchain = now() - t0;
    long d = (long)(ell - 1) / 2, n = 2 * d;
    u128 *s = malloc(n * sizeof(u128)), *C = malloc((n + 1) * sizeof(u128));
    tw_one(&T, p);
    for (long i = 0; i < n; i++) {
        s[i] = tw_trace_q(&T, p);
        tw_mul(&T, p, p, g);
    }
    double tseq = now() - t0 - tchain;
    long L;
    bm(s, n, C, &L);
    // connection polynomial C(X) = 1 + c1 X + ... + cL X^L; minimal polynomial is its reverse.
    // verify: K(x) = sum_k C[L-k] x^k = 0 in the tower (Horner from the top).
    tw_zero(&T, p);
    for (long k = L; k >= 0; k--) {
        tw_mul(&T, p, p, g);
        p[0] ^= C[L - k];
    }
    int vanishes = tw_is_zero(&T, p);
    printf("{\"line\":\"%s\",\"degree\":%ld,\"vanishes_at_x\":%s,\"chain_seconds\":%.1f,"
           "\"sequence_seconds\":%.1f,\"total_seconds\":%.1f,\"coefficients_ascending\":[",
           line, L, vanishes ? "true" : "false", tchain, tseq, now() - t0);
    for (long k = 0; k <= L; k++) {
        printf(k ? ",\"" : "\"");
        print_hex128(stdout, C[L - k]);
        printf("\"");
    }
    printf("]}\n");
    return (vanishes && L == d) ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc < 6) {
        fprintf(stderr, "usage: isogeny CMD M FTAPS R GTAPS ...\n");
        return 2;
    }
    if (setup(argv + 2)) {
        fprintf(stderr, "bad field parameters\n");
        return 2;
    }
    const char *cmd = argv[1];
    char **rest = argv + 6;
    int nrest = argc - 6;
    if (!strcmp(cmd, "selftest")) return cmd_selftest();
    if (!strcmp(cmd, "bench")) return cmd_bench();
    if (!strcmp(cmd, "torsion") && nrest == 6) return cmd_torsion(rest);
    if (!strcmp(cmd, "frobcheck") && nrest == 4) return cmd_frobcheck(rest);
    if (!strcmp(cmd, "lines") && nrest == 2) return cmd_lines(rest);
    if (!strcmp(cmd, "kernel") && nrest == 3) return cmd_kernel(rest);
    fprintf(stderr, "unknown command or wrong arguments\n");
    return 2;
}
