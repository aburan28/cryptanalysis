/*
 * ca_bench.c - benchmark matrix, reported the way the sibling research
 * repository asks for it: one table, one unit.
 *
 *   ca_bench generic  [--bits 24,28,32,36] [--reps 5] [--threads 4] [--group zp|ec|both]
 *       whole-group DLP: bsgs, rho (1 and T threads), kangaroo, grumpy; the
 *       unit is S = group operations / sqrt(n).
 *   ca_bench interval [--bits 24,28,32,36] [--reps 5] [--group zp|ec]
 *       interval DLP of width 2^bits inside a ~2^60 group: bsgs, kangaroo,
 *       grumpy; unit S = group operations / sqrt(width).
 *   ca_bench ic       [--bits 32,40,48,56] [--threads 4]
 *       index calculus in Z_p^*: stage timings.
 *   ca_bench cheon    [--bits 32,40,48]
 *       Cheon vs generic sqrt(p) cost in group operations.
 *   ca_bench precomp  [--bits 24,28,32,36] [--reps 5] [--group zp|ec|both]
 *       discrete logs with precomputation (Bernstein-Lange): the one-time
 *       precomputation cost in n^{2/3}, the table size, and the per-target
 *       online cost in n^{1/3}, with the per-target speedup over sqrt(n).
 *   ca_bench complexity [--bits 20,24,28,32,36] [--reps 5] [--group zp|ec|both]
 *       measured time complexity: fits each algorithm's group-operation cost
 *       to C * N^alpha across the size sweep, reporting the fitted exponent
 *       (global for a whole algorithm, per-step for a method's phases such as
 *       precomputation build vs online) with its R^2 and the normalised
 *       constant, so the O() is measured rather than assumed.
 *   ca_bench glv      GLV endomorphism-accelerated rho vs the negation-map rho
 *       on the registry's CM curves (j=0, j=1728) and a generic curve, in
 *       S = group ops / sqrt(n), with the measured speedup.
 *   ca_bench ops      raw group operation throughput.
 *   ca_bench gpu      [--bits 24,28,32] [--reps 3] [--group zp|ec|both]
 *       CPU rho vs the GPU rho kernel (CUDA when a device is present,
 *       otherwise the host emulator) in S = group ops / sqrt(n).
 *
 *   --json FILE (generic and complexity): besides the table, write one JSON
 *       object per solved instance with the raw ca_stats counters, after a
 *       header object naming the binary, commit, command line and host
 *       (JSON Lines).  experiments/bounds/emit_bounds.py reads it.
 */
#include "cryptanalysis/cryptanalysis.h"
#include "ca_internal.h"
#include "ca_device.cuh"

#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>

static int argc_g;
static char **argv_g;

static const char *opt(const char *name, const char *def)
{
    for (int i = 2; i + 1 < argc_g; i++)
        if (strcmp(argv_g[i], name) == 0) return argv_g[i + 1];
    return def;
}

static int parse_list(const char *s, unsigned *out, int cap)
{
    int n = 0;
    while (*s && n < cap) {
        char *end;
        out[n++] = (unsigned)strtoul(s, &end, 10);
        s = end;
        while (*s == ',' || *s == ' ') s++;
    }
    return n;
}

/* ---- --json FILE: raw per-instance counters --------------------------- */
/* generic and complexity write one JSON object per solved instance (JSON
 * Lines, a header object first), so that a sweep can be re-read by
 * experiments/bounds/emit_bounds.py without parsing the human tables.  The
 * header names the exact binary (SHA-256 of the executable), the commit the
 * build was configured at, the command line and the host; a row carries the
 * ca_stats counters as the solver reported them.  The tables are unchanged. */

static FILE *json_g; /* NULL unless --json FILE was given */

/* SHA-256 (FIPS 180-4), used only to hash the running executable. */
typedef struct sha256_ctx {
    uint32_t h[8];
    uint64_t len;
    uint8_t buf[64];
    size_t n;
} sha256_ctx;

static const uint32_t sha256_k[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

static uint32_t rotr32(uint32_t x, unsigned k) { return (x >> k) | (x << (32 - k)); }

static void sha256_init(sha256_ctx *c)
{
    static const uint32_t iv[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                   0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    memcpy(c->h, iv, sizeof iv);
    c->len = 0;
    c->n = 0;
}

static void sha256_block(sha256_ctx *c, const uint8_t *p)
{
    uint32_t w[64];
    for (size_t i = 0; i < 16; i++)
        w[i] = (uint32_t)p[4 * i] << 24 | (uint32_t)p[4 * i + 1] << 16 |
               (uint32_t)p[4 * i + 2] << 8 | (uint32_t)p[4 * i + 3];
    for (int i = 16; i < 64; i++) {
        const uint32_t s0 = rotr32(w[i - 15], 7) ^ rotr32(w[i - 15], 18) ^ (w[i - 15] >> 3);
        const uint32_t s1 = rotr32(w[i - 2], 17) ^ rotr32(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = c->h[0], b = c->h[1], cc = c->h[2], d = c->h[3];
    uint32_t e = c->h[4], f = c->h[5], g = c->h[6], h = c->h[7];
    for (int i = 0; i < 64; i++) {
        const uint32_t t1 = h + (rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25)) +
                            ((e & f) ^ (~e & g)) + sha256_k[i] + w[i];
        const uint32_t t2 =
            (rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22)) + ((a & b) ^ (a & cc) ^ (b & cc));
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = cc;
        cc = b;
        b = a;
        a = t1 + t2;
    }
    c->h[0] += a;
    c->h[1] += b;
    c->h[2] += cc;
    c->h[3] += d;
    c->h[4] += e;
    c->h[5] += f;
    c->h[6] += g;
    c->h[7] += h;
}

static void sha256_update(sha256_ctx *c, const uint8_t *data, size_t len)
{
    c->len += len;
    while (len > 0) {
        size_t take = sizeof c->buf - c->n;
        if (take > len) take = len;
        memcpy(c->buf + c->n, data, take);
        c->n += take;
        data += take;
        len -= take;
        if (c->n == sizeof c->buf) {
            sha256_block(c, c->buf);
            c->n = 0;
        }
    }
}

static void sha256_final(sha256_ctx *c, char hex[65])
{
    static const uint8_t one = 0x80, zero = 0;
    const uint64_t bits = c->len * 8;
    sha256_update(c, &one, 1);
    while (c->n != 56) sha256_update(c, &zero, 1);
    uint8_t lenb[8];
    for (int i = 0; i < 8; i++) lenb[i] = (uint8_t)(bits >> (56 - 8 * i));
    sha256_update(c, lenb, sizeof lenb);
    for (size_t i = 0; i < 8; i++) snprintf(hex + 8 * i, 9, "%08" PRIx32, c->h[i]);
}

/* 0 and the lowercase digest of the file at path in hex; -1 if unreadable. */
static int sha256_file(const char *path, char hex[65])
{
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    sha256_ctx c;
    sha256_init(&c);
    uint8_t buf[1 << 16];
    size_t got;
    while ((got = fread(buf, 1, sizeof buf, f)) > 0) sha256_update(&c, buf, got);
    const int err = ferror(f);
    fclose(f);
    if (err) return -1;
    sha256_final(&c, hex);
    return 0;
}

/* A JSON string: quotes, backslashes and control characters escaped, every
 * other byte written as it is (the strings here are ASCII or UTF-8). */
static void json_str(FILE *f, const char *s)
{
    fputc('"', f);
    for (; *s; s++) {
        const unsigned char ch = (unsigned char)*s;
        switch (ch) {
        case '"': fputs("\\\"", f); break;
        case '\\': fputs("\\\\", f); break;
        case '\n': fputs("\\n", f); break;
        case '\r': fputs("\\r", f); break;
        case '\t': fputs("\\t", f); break;
        default:
            if (ch < 0x20)
                fprintf(f, "\\u%04x", ch);
            else
                fputc(ch, f);
        }
    }
    fputc('"', f);
}

static void json_str_or_null(FILE *f, const char *s)
{
    if (s)
        json_str(f, s);
    else
        fputs("null", f);
}

/* The header line: what produced the rows that follow. */
static void json_header(const char *mode)
{
    char hex[65];
    const char *digest = NULL;
    if (sha256_file("/proc/self/exe", hex) == 0 || sha256_file(argv_g[0], hex) == 0) digest = hex;
    /* uname(2) fields in `uname -a` order: sysname nodename release version machine. */
    char host[1024] = "";
    struct utsname u;
    if (uname(&u) == 0)
        snprintf(host, sizeof host, "%s %s %s %s %s", u.sysname, u.nodename, u.release, u.version,
                 u.machine);
    /* argv joined by single spaces: what the shell passed, less its quoting. */
    size_t len = 0;
    for (int i = 0; i < argc_g; i++) len += strlen(argv_g[i]) + 1;
    char *cmdline = malloc(len + 1);
    if (cmdline) {
        size_t at = 0;
        for (int i = 0; i < argc_g; i++) {
            const size_t l = strlen(argv_g[i]);
            if (i) cmdline[at++] = ' ';
            memcpy(cmdline + at, argv_g[i], l);
            at += l;
        }
        cmdline[at] = '\0';
    }
    FILE *f = json_g;
    fputs("{\"record\":\"header\",\"schema\":\"ca_bench.sweep/v1\",\"mode\":", f);
    json_str(f, mode);
    fputs(",\"library_version\":", f);
    json_str(f, ca_version());
    fputs(",\"binary_sha256\":", f);
    json_str_or_null(f, digest);
    fputs(",\"git_commit\":", f);
#ifdef CA_GIT_COMMIT
    json_str(f, CA_GIT_COMMIT);
#else
    fputs("null", f);
#endif
    fputs(",\"command_line\":", f);
    json_str_or_null(f, cmdline);
    fputs(",\"host\":", f);
    json_str_or_null(f, host[0] ? host : NULL);
    fputs("}\n", f);
    free(cmdline);
}

typedef struct json_group {
    int ec;
    unsigned bits;
    uint64_t n, p, a, b; /* a, b: the curve coefficients, 0 in Z_p^* */
} json_group;

/* One solved instance.  seed is NULL for the deterministic solvers; extra is
 * an optional pre-formatted ",\"key\":value" tail. */
static void json_row(const json_group *jg, const char *alg, unsigned instance, uint64_t x,
                     const uint64_t *seed, const ca_stats *st, ca_status rc, uint64_t got,
                     const char *extra)
{
    FILE *f = json_g;
    if (!f) return;
    const int ok = rc == CA_OK && got == x;
    const char *status = rc != CA_OK ? ca_status_string(rc) : ok ? "ok" : "wrong answer";
    fputs("{\"record\":\"instance\",\"algorithm\":", f);
    json_str(f, alg);
    fprintf(f, ",\"group\":\"%s\",\"bits\":%u,\"n\":\"%" PRIu64 "\",\"p\":\"%" PRIu64 "\"",
            jg->ec ? "ec" : "zp", jg->bits, jg->n, jg->p);
    if (jg->ec)
        fprintf(f, ",\"a\":\"%" PRIu64 "\",\"b\":\"%" PRIu64 "\"", jg->a, jg->b);
    else
        fputs(",\"a\":null,\"b\":null", f);
    fprintf(f, ",\"instance\":%u,\"x\":\"%" PRIu64 "\",\"seed\":", instance, x);
    if (seed)
        fprintf(f, "%" PRIu64, *seed);
    else
        fputs("null", f);
    fputs(",\"status\":", f);
    json_str(f, status);
    fprintf(f,
            ",\"ok\":%s,\"group_ops\":%" PRIu64 ",\"iterations\":%" PRIu64
            ",\"table_entries\":%" PRIu64 ",\"collisions\":%" PRIu64 ",\"bytes_peak\":%" PRIu64
            ",\"seconds\":%.9g,\"threads\":%" PRIu32,
            ok ? "true" : "false", st->group_ops, st->iterations, st->table_entries, st->collisions,
            st->bytes_peak, st->seconds, st->threads ? st->threads : 1U);
    if (extra) fputs(extra, f);
    fputs("}\n", f);
}

/* safe prime p = 2q+1 with p of the given bit length; returns q */
static uint64_t find_safe_prime(unsigned bits, uint64_t *p_out)
{
    uint64_t p = (1ULL << (bits - 1)) | 3;
    for (;;) {
        p = ca_next_prime(p);
        if (ca_is_prime((p - 1) / 2)) { *p_out = p; return (p - 1) / 2; }
    }
}

/* curve over a prime of the given bit length with prime order */
static void find_prime_order_curve(unsigned bits, uint64_t *p, uint64_t *a, uint64_t *b, uint64_t *n)
{
    *p = ca_next_prime((1ULL << (bits - 1)) | 5);
    *a = 1;
    for (*b = 1;; (*b)++) {
        if (ca_ec_count_points(*p, *a, *b, n, NULL) != CA_OK) continue;
        if (ca_is_prime(*n)) return;
    }
}

/* Empirical time complexity.  fit_power_law (defined below) fits measured
 * cost ~ C * N^alpha; cx_summary prints the fitted exponent for a table's
 * algorithms, so every mode reports the measured O(), not an assumed one. */
typedef struct cx_fit {
    double alpha;
    double c_fit;
    double r2;
    double c_theory;
    int npts;
} cx_fit;

static cx_fit fit_power_law(const double *N, const double *cost, int m, double theory);

static void cx_summary(const char *label, const char *var, const char **names, const double *theory,
                       const double *Nv, double (*cost)[16], int nalg, int nb)
{
    printf("  %s: fitted cost ~ C * %s^alpha (the measured exponent)\n", label, var);
    printf("  | algorithm      | theory  | fitted alpha |  R^2   | const @ %s^theory |\n", var);
    printf("  |----------------|---------|--------------|--------|------------------|\n");
    for (int a = 0; a < nalg; a++) {
        cx_fit f = fit_power_law(Nv, cost[a], nb, theory[a]);
        printf("  | %-14s | %s^%.3f | %12.3f | %6.4f | %16.3f |\n", names[a], var, theory[a],
               f.alpha, f.r2, f.c_theory);
    }
}

static void run_generic(const unsigned *bits, int nb, unsigned reps, unsigned threads, int ec)
{
    enum { NALG = 5 };
    static const char *names[NALG] = {"bsgs", "rho-1", "rho-T", "kangaroo", "grumpy"};
    static const double theory[NALG] = {0.5, 0.5, 0.5, 0.5, 0.5};
    double Nv[16], cost[NALG][16];
    if (nb > 16) nb = 16;
    printf("| grp | bits | algorithm | S=ops/sqrtn | seconds    | Mops/s   | ok  |\n");
    printf("|-----|------|-----------|-------------|------------|----------|-----|\n");
    for (int si = 0; si < nb; si++) {
        ca_group g;
        ca_elem gen;
        uint64_t n, p, ea = 0, eb = 0;
        if (!ec) {
            n = find_safe_prime(bits[si], &p);
            ca_group_zp_init(&g, p, n);
        } else {
            find_prime_order_curve(bits[si], &p, &ea, &eb, &n);
            ca_group_ec_init(&g, p, ea, eb, n);
            g.cofactor = 1;
        }
        ca_group_find_generator(&g, &gen, 1);
        const json_group jg = {ec, bits[si], n, p, ea, eb};
        Nv[si] = (double)n;
        double sq = sqrt((double)n);
        double ops[NALG] = {0}, secs[NALG] = {0};
        unsigned ok[NALG] = {0};
        ca_rng rng;
        ca_rng_seed(&rng, 1234 + bits[si]);
        for (unsigned r = 0; r < reps; r++) {
            uint64_t x = ca_rng_below(&rng, n);
            ca_elem h;
            ca_group_mul(&g, &h, &gen, x, NULL);
            for (int a = 0; a < NALG; a++) {
                ca_stats st = {0};
                uint64_t got = 0;
                ca_status rc;
                ca_dlog_params dp;
                ca_dlog_params_default(&dp);
                dp.rho.seed = 100 + r;
                dp.kangaroo.seed = 100 + r;
                switch (a) {
                case 0: rc = ca_bsgs_solve(&g, &gen, &h, 0, 0, &dp.bsgs, &got, &st); break;
                case 1: rc = ca_rho_solve(&g, &gen, &h, &dp.rho, &got, &st); break;
                case 2:
                    dp.rho.threads = threads;
                    rc = ca_rho_solve(&g, &gen, &h, &dp.rho, &got, &st);
                    break;
                case 3: rc = ca_kangaroo_solve(&g, &gen, &h, 0, 0, &dp.kangaroo, &got, &st); break;
                default: rc = ca_grumpy_solve(&g, &gen, &h, 0, 0, &dp.grumpy, &got, &st); break;
                }
                const uint64_t seed = 100 + r;
                json_row(&jg, names[a], r, x, (a == 1 || a == 2) ? &seed : NULL, &st, rc, got,
                         NULL);
                ops[a] += (double)st.group_ops;
                secs[a] += st.seconds;
                ok[a] += (rc == CA_OK && got == x);
            }
        }
        for (int a = 0; a < NALG; a++) {
            printf("| %-4s | %3u | %-9s | %8.3f | %10.4f | %8.0f | %u/%u |\n", ec ? "ec" : "zp",
                   bits[si], names[a], ops[a] / reps / sq, secs[a] / reps,
                   ops[a] / reps / (secs[a] / reps + 1e-12) / 1e6, ok[a], reps);
            cost[a][si] = ops[a] / reps;
        }
    }
    cx_summary(ec ? "ec" : "zp", "n", names, theory, Nv, cost, NALG, nb);
}

static void run_interval(const unsigned *bits, int nb, unsigned reps, int ec)
{
    enum { NALG = 3 };
    static const char *names[NALG] = {"bsgs", "kangaroo", "grumpy"};
    static const double theory[NALG] = {0.5, 0.5, 0.5};
    ca_group g;
    ca_elem gen;
    uint64_t n;
    if (!ec) {
        uint64_t p;
        n = find_safe_prime(60, &p);
        ca_group_zp_init(&g, p, n);
    } else {
        uint64_t p, a, b;
        find_prime_order_curve(56, &p, &a, &b, &n);
        ca_group_ec_init(&g, p, a, b, n);
        g.cofactor = 1;
    }
    ca_group_find_generator(&g, &gen, 1);
    double Nv[16], cost[NALG][16];
    if (nb > 16) nb = 16;
    printf("| grp | width | algorithm | S=ops/sqrtw | seconds    | ok  |\n");
    printf("|-----|-------|-----------|-------------|------------|-----|\n");
    for (int si = 0; si < nb; si++) {
        unsigned wbits = bits[si];
        uint64_t width = 1ULL << wbits;
        double sq = sqrt((double)width);
        Nv[si] = (double)width;
        double ops[NALG] = {0}, secs[NALG] = {0};
        unsigned ok[NALG] = {0};
        ca_rng rng;
        ca_rng_seed(&rng, 99 + wbits);
        for (unsigned r = 0; r < reps; r++) {
            uint64_t lo = ca_rng_below(&rng, n - width);
            uint64_t x = lo + ca_rng_below(&rng, width);
            ca_elem h;
            ca_group_mul(&g, &h, &gen, x, NULL);
            for (int a = 0; a < NALG; a++) {
                ca_stats st = {0};
                uint64_t got = 0;
                ca_status rc;
                ca_dlog_params dp;
                ca_dlog_params_default(&dp);
                dp.kangaroo.seed = 100 + r;
                switch (a) {
                case 0:
                    rc = ca_bsgs_solve(&g, &gen, &h, lo, lo + width - 1, &dp.bsgs, &got, &st);
                    break;
                case 1:
                    rc = ca_kangaroo_solve(&g, &gen, &h, lo, lo + width - 1, &dp.kangaroo, &got,
                                           &st);
                    break;
                default:
                    rc = ca_grumpy_solve(&g, &gen, &h, lo, lo + width - 1, &dp.grumpy, &got, &st);
                    break;
                }
                ops[a] += (double)st.group_ops;
                secs[a] += st.seconds;
                ok[a] += (rc == CA_OK && got == x);
            }
        }
        for (int a = 0; a < NALG; a++) {
            printf("| %-4s | 2^%-3u | %-9s | %8.3f | %10.4f | %u/%u |\n", ec ? "ec" : "zp", wbits,
                   names[a], ops[a] / reps / sq, secs[a] / reps, ok[a], reps);
            cost[a][si] = ops[a] / reps;
        }
    }
    cx_summary(ec ? "ec" : "zp", "w", names, theory, Nv, cost, NALG, nb);
}

static void run_ic(unsigned bits, unsigned threads)
{
    uint64_t p;
    find_safe_prime(bits, &p);
    uint64_t g = ca_primitive_root(p);
    ca_ic_params pr;
    ca_ic_params_default(&pr);
    pr.threads = threads;
    pr.seed = 1;
    ca_ic_ctx *ctx;
    ca_ic_stats st;
    double t0 = ca_now();
    ca_status rc = ca_ic_precompute(p, g, &pr, &ctx, &st);
    double pre = ca_now() - t0;
    if (rc != CA_OK) {
        printf("| %3u | %" PRIu64 " | failed: %s |\n", bits, p, ca_status_string(rc));
        return;
    }
    /* 5 individual logs */
    double tl = 0;
    uint64_t tries = 0;
    for (int k = 0; k < 5; k++) {
        uint64_t x = 12345 + 777 * (uint64_t)k, got;
        uint64_t h = ca_powmod(g, x, p);
        ca_stats s2 = {0};
        t0 = ca_now();
        rc = ca_ic_log(ctx, h, &got, &s2);
        tl += ca_now() - t0;
        tries += s2.iterations;
        if (rc != CA_OK || got != x) printf("  !! individual log failed\n");
    }
    /* reference: rho in the order-q subgroup, S ~ 1.3 sqrt(q) ops */
    uint64_t q = (p - 1) / 2;
    printf("| %3u | %" PRIu64 " | %5u | %6u | %6u | %7.3f | %7.3f | %7.3f | %6.3f | %6.0f | %9.2e |\n", bits, p,
           st.factor_base_size, st.unknowns, st.relations, st.sieve_seconds, st.linalg_seconds, pre,
           tl / 5, (double)tries / 5, 1.3 * sqrt((double)q));
    ca_ic_free(ctx);
}

static void run_cheon(unsigned bits)
{
    /* prime-order subgroup of Z_r^* with order p of the given size where
     * p-1 has a balanced divisor: pick p = k*2^(bits/2) + 1 style */
    uint64_t half = 1ULL << (bits / 2);
    uint64_t p = 0;
    for (uint64_t k = half | 1; k < half * 4; k += 2) {
        if (ca_is_prime(k * half + 1)) { p = k * half + 1; break; }
    }
    if (!p) return;
    uint64_t r = 0;
    for (uint64_t k = 1; k < 1000000; k++) {
        if (ca_is_prime(2 * k * p + 1)) { r = 2 * k * p + 1; break; }
    }
    if (!r) return;
    ca_group g;
    ca_group_zp_init(&g, r, p);
    ca_elem gen, ga, gad;
    ca_group_find_generator(&g, &gen, 1);
    double cost;
    uint64_t d = ca_cheon_best_divisor(p, &cost);
    uint64_t alpha = 0x1234567 % (p - 1) + 1;
    ca_cheon_make_instance(&g, &gen, alpha, d, &ga, &gad);
    ca_stats st = {0};
    uint64_t got;
    ca_status rc = ca_cheon_solve(&g, &gen, &ga, &gad, d, NULL, &got, &st);
    /* generic reference: rho on the same instance */
    ca_stats sr = {0};
    uint64_t gr;
    ca_rho_params rp;
    ca_rho_params_default(&rp);
    rp.seed = 3;
    ca_rho_solve(&g, &gen, &ga, &rp, &gr, &sr);
    printf("| %3u | %" PRIu64 " | %10" PRIu64 " | %8" PRIu64 " | %10" PRIu64 " | %8.3f | %10" PRIu64 " | %8.3f | %5.2f | %s |\n",
           bits, p, d, st.iterations, st.group_ops, st.seconds, sr.group_ops, sr.seconds,
           (double)sr.group_ops / (double)st.group_ops, (rc == CA_OK && got == alpha) ? "ok" : "FAIL");
}

static void run_gpu(unsigned bits, unsigned reps, int ec)
{
    ca_group g;
    ca_elem gen;
    uint64_t n;
    if (!ec) {
        uint64_t p;
        n = find_safe_prime(bits, &p);
        ca_group_zp_init(&g, p, n);
    } else {
        uint64_t p, a, b;
        find_prime_order_curve(bits, &p, &a, &b, &n);
        ca_group_ec_init(&g, p, a, b, n);
        g.cofactor = 1;
    }
    ca_group_find_generator(&g, &gen, 1);
    double sq = sqrt((double)n);
    int have_dev = ca_gpu_cuda_compiled() && ca_gpu_device_count() > 0;
    const char *names[2] = {"cpu-rho", have_dev ? "gpu-rho (cuda)" : "gpu-rho (emulate)"};
    double ops[2] = {0}, secs[2] = {0};
    uint64_t walks[2] = {0}, launches = 0;
    unsigned ok[2] = {0};
    ca_rng rng;
    ca_rng_seed(&rng, 777 + bits);
    for (unsigned r = 0; r < reps; r++) {
        uint64_t x = ca_rng_below(&rng, n);
        ca_elem h;
        ca_group_mul(&g, &h, &gen, x, NULL);
        for (int which = 0; which < 2; which++) {
            ca_stats st = {0};
            uint64_t got = 0;
            ca_status rc;
            if (which == 0) {
                ca_rho_params rp;
                ca_rho_params_default(&rp);
                rp.seed = 200 + r;
                rc = ca_rho_solve(&g, &gen, &h, &rp, &got, &st);
                walks[0] = st.threads;
            } else {
                ca_gpu_rho_params gp;
                ca_gpu_rho_params_default(&gp);
                gp.seed = 200 + r;
                rc = ca_gpu_rho_solve(&g, &gen, &h, &gp, &got, &st);
                walks[1] = (uint64_t)st.threads * CA_GPU_W;
                launches += st.reserved;
            }
            ops[which] += (double)st.group_ops;
            secs[which] += st.seconds;
            ok[which] += (rc == CA_OK && got == x);
        }
    }
    for (int which = 0; which < 2; which++) {
        printf("| %-4s | %3u | %-18s | %8.3f | %10.4f | %7" PRIu64 " | %8.1f | %u/%u |\n",
               ec ? "ec" : "zp", bits, names[which], ops[which] / reps / sq, secs[which] / reps,
               walks[which], which == 0 ? 0.0 : (double)launches / reps, ok[which], reps);
    }
}

static void run_precomp(const unsigned *bits, int nb, unsigned reps, unsigned threads, int ec)
{
    static const char *names[2] = {"precomp build", "precomp online"};
    static const double theory[2] = {2.0 / 3.0, 1.0 / 3.0};
    double Nv[16], cost[2][16];
    if (nb > 16) nb = 16;
    printf("| grp | bits |  t |   chains | precomp ops | P/n^2/3 | build s | online ops | T/n^1/3 |"
           " sqrtN/T | ok  |\n");
    printf("|-----|-----:|---:|---------:|------------:|--------:|--------:|-----------:|--------:|"
           "--------:|-----|\n");
    for (int si = 0; si < nb; si++) {
        ca_group g;
        ca_elem gen;
        uint64_t n;
        if (!ec) {
            uint64_t p;
            n = find_safe_prime(bits[si], &p);
            ca_group_zp_init(&g, p, n);
        } else {
            uint64_t p, a, b;
            find_prime_order_curve(bits[si], &p, &a, &b, &n);
            ca_group_ec_init(&g, p, a, b, n);
            g.cofactor = 1;
        }
        ca_group_find_generator(&g, &gen, 1);
        Nv[si] = (double)n;
        cost[0][si] = 0;
        cost[1][si] = 0;
        ca_precomp_params pp;
        ca_precomp_params_default(&pp);
        pp.seed = 1234 + bits[si];
        pp.threads = threads;
        ca_stats build = {0};
        ca_precomp_table *tab = NULL;
        ca_status rc = ca_precomp_table_new(&g, &gen, &pp, &tab, &build);
        if (rc != CA_OK || !tab) {
            printf("| %-4s | %3u | build failed: %s |\n", ec ? "ec" : "zp", bits[si],
                   ca_status_string(rc));
            continue;
        }
        int32_t dpb = 0;
        uint64_t chains = 0, precomp_ops = 0;
        uint32_t rr = 0;
        ca_precomp_table_info(tab, &dpb, &chains, &rr, &precomp_ops);
        double sq = sqrt((double)n), c23 = pow((double)n, 2.0 / 3.0), c13 = cbrt((double)n);
        ca_rng rng;
        ca_rng_seed(&rng, 55 + bits[si]);
        double on_ops = 0;
        unsigned ok = 0;
        for (unsigned r = 0; r < reps; r++) {
            uint64_t x = ca_rng_below(&rng, n);
            ca_elem h;
            ca_group_mul(&g, &h, &gen, x, NULL);
            uint64_t got = 0;
            ca_stats s = {0};
            ca_status sc = ca_precomp_table_solve(tab, &h, &got, &s);
            on_ops += (double)s.group_ops;
            ok += (sc == CA_OK && got == x);
        }
        ca_precomp_table_free(tab);
        double online = on_ops / reps;
        printf("| %-4s | %3u | %2d | %8" PRIu64 " | %11" PRIu64
               " | %7.3f | %8.4f | %10.1f | %7.3f | %7.1f | %u/%u |\n",
               ec ? "ec" : "zp", bits[si], dpb, chains, precomp_ops, (double)precomp_ops / c23,
               build.seconds, online, online / c13, sq / online, ok, reps);
        cost[0][si] = (double)precomp_ops;
        cost[1][si] = online;
    }
    cx_summary(ec ? "ec" : "zp", "n", names, theory, Nv, cost, 2, nb);
}

/* ---- empirical time complexity ---------------------------------------- */
/* Fit measured cost ~ C * N^alpha by least squares in log-log space, so the
 * exponent (the O()) is measured rather than assumed.  c_theory is the mean
 * of cost / N^theory: the familiar normalised constant (rho's ops/sqrt(n),
 * precomp's T/n^{1/3}, ...) that only makes sense once the exponent is known
 * to match, which the fitted alpha and R^2 confirm. */
static cx_fit fit_power_law(const double *N, const double *cost, int m, double theory)
{
    cx_fit f;
    memset(&f, 0, sizeof f);
    double sx = 0, sy = 0, sxx = 0, sxy = 0, ct = 0;
    int used = 0;
    for (int i = 0; i < m; i++) {
        if (N[i] <= 0 || cost[i] <= 0) continue;
        double x = log(N[i]), y = log(cost[i]);
        sx += x;
        sy += y;
        sxx += x * x;
        sxy += x * y;
        ct += cost[i] / pow(N[i], theory);
        used++;
    }
    f.npts = used;
    f.c_theory = used ? ct / used : 0;
    if (used < 2) return f;
    double denom = (double)used * sxx - sx * sx;
    if (denom == 0) return f;
    f.alpha = ((double)used * sxy - sx * sy) / denom;
    double b = (sy - f.alpha * sx) / used;
    f.c_fit = exp(b);
    double ybar = sy / used, ss_res = 0, ss_tot = 0;
    for (int i = 0; i < m; i++) {
        if (N[i] <= 0 || cost[i] <= 0) continue;
        double x = log(N[i]), y = log(cost[i]);
        double yh = f.alpha * x + b;
        ss_res += (y - yh) * (y - yh);
        ss_tot += (y - ybar) * (y - ybar);
    }
    f.r2 = ss_tot > 0 ? 1.0 - ss_res / ss_tot : 1.0;
    return f;
}

enum { CX_BSGS, CX_RHO, CX_KANG, CX_GRUMPY, CX_PBUILD, CX_PONLINE, CX_NALG };

static void run_complexity(const unsigned *bits, int nb, unsigned reps, int ec)
{
    static const char *names[CX_NALG] = {"bsgs",   "rho",           "kangaroo",
                                         "grumpy", "precomp build", "precomp online"};
    static const char *scope[CX_NALG] = {"global", "global", "global", "global", "step", "step"};
    static const double theory[CX_NALG] = {0.5, 0.5, 0.5, 0.5, 2.0 / 3.0, 1.0 / 3.0};
    double Nv[16];
    double cost[CX_NALG][16];
    if (nb > 16) nb = 16;

    for (int si = 0; si < nb; si++) {
        ca_group g;
        ca_elem gen;
        uint64_t n, p, ea = 0, eb = 0;
        if (!ec) {
            n = find_safe_prime(bits[si], &p);
            ca_group_zp_init(&g, p, n);
        } else {
            find_prime_order_curve(bits[si], &p, &ea, &eb, &n);
            ca_group_ec_init(&g, p, ea, eb, n);
            g.cofactor = 1;
        }
        ca_group_find_generator(&g, &gen, 1);
        const json_group jg = {ec, bits[si], n, p, ea, eb};
        Nv[si] = (double)n;

        ca_precomp_params pp;
        ca_precomp_params_default(&pp);
        pp.seed = 99 + bits[si];
        ca_stats pbuild = {0};
        ca_precomp_table *tab = NULL;
        ca_precomp_table_new(&g, &gen, &pp, &tab, &pbuild);
        cost[CX_PBUILD][si] = (double)pbuild.group_ops;
        /* The online rows carry the table they were solved against. */
        char precomp_extra[160] = "";
        if (tab) {
            int32_t dpb = 0;
            uint64_t chains = 0, pops = 0;
            uint32_t rr = 0;
            ca_precomp_table_info(tab, &dpb, &chains, &rr, &pops);
            snprintf(precomp_extra, sizeof precomp_extra,
                     ",\"precomp\":{\"build_group_ops\":%" PRIu64 ",\"chains\":%" PRIu64
                     ",\"dp_bits\":%" PRId32 ",\"table_seed\":%" PRIu64 "}",
                     pops, chains, dpb, (uint64_t)pp.seed);
        }

        double acc[CX_NALG] = {0};
        ca_rng rng;
        ca_rng_seed(&rng, 7 + bits[si]);
        for (unsigned r = 0; r < reps; r++) {
            uint64_t x = ca_rng_below(&rng, n), got = 0;
            ca_elem h;
            ca_group_mul(&g, &h, &gen, x, NULL);
            ca_dlog_params dp;
            ca_dlog_params_default(&dp);
            dp.rho.seed = dp.kangaroo.seed = 100 + r;
            const uint64_t seed = 100 + r;
            ca_stats st;
            ca_status rc;
            st = (ca_stats){0};
            got = 0;
            rc = ca_bsgs_solve(&g, &gen, &h, 0, 0, &dp.bsgs, &got, &st);
            if (rc == CA_OK) acc[CX_BSGS] += (double)st.group_ops;
            json_row(&jg, names[CX_BSGS], r, x, NULL, &st, rc, got, NULL);
            st = (ca_stats){0};
            got = 0;
            rc = ca_rho_solve(&g, &gen, &h, &dp.rho, &got, &st);
            if (rc == CA_OK) acc[CX_RHO] += (double)st.group_ops;
            json_row(&jg, names[CX_RHO], r, x, &seed, &st, rc, got, NULL);
            st = (ca_stats){0};
            got = 0;
            rc = ca_kangaroo_solve(&g, &gen, &h, 0, 0, &dp.kangaroo, &got, &st);
            if (rc == CA_OK) acc[CX_KANG] += (double)st.group_ops;
            json_row(&jg, names[CX_KANG], r, x, &seed, &st, rc, got, NULL);
            st = (ca_stats){0};
            got = 0;
            rc = ca_grumpy_solve(&g, &gen, &h, 0, 0, &dp.grumpy, &got, &st);
            if (rc == CA_OK) acc[CX_GRUMPY] += (double)st.group_ops;
            json_row(&jg, names[CX_GRUMPY], r, x, NULL, &st, rc, got, NULL);
            if (tab) {
                st = (ca_stats){0};
                got = 0;
                rc = ca_precomp_table_solve(tab, &h, &got, &st);
                if (rc == CA_OK) acc[CX_PONLINE] += (double)st.group_ops;
                json_row(&jg, "precomp-online", r, x, NULL, &st, rc, got, precomp_extra);
            }
        }
        cost[CX_BSGS][si] = acc[CX_BSGS] / reps;
        cost[CX_RHO][si] = acc[CX_RHO] / reps;
        cost[CX_KANG][si] = acc[CX_KANG] / reps;
        cost[CX_GRUMPY][si] = acc[CX_GRUMPY] / reps;
        cost[CX_PONLINE][si] = acc[CX_PONLINE] / reps;
        ca_precomp_table_free(tab);
    }

    printf("\n%s:  cost ~ C * N^alpha, fitted over %d sizes (N = group order).\n",
           ec ? "E(F_p)" : "Z_p^*", nb);
    printf("| algorithm       | scope  | theory   | fitted alpha | R^2    | const @ N^theory |\n");
    printf("|-----------------|--------|----------|--------------|--------|------------------|\n");
    for (int a = 0; a < CX_NALG; a++) {
        cx_fit f = fit_power_law(Nv, cost[a], nb, theory[a]);
        printf("| %-15s | %-6s | N^%.3f | %12.3f | %6.4f | %16.3f |\n", names[a], scope[a],
               theory[a], f.alpha, f.r2, f.c_theory);
    }
}

static void run_glv(void)
{
    const char *names[32];
    size_t nc = ca_curve_list(names, 32);
    size_t nuse = nc < 32 ? nc : 32;
    printf("| curve                        | endo  | m | GLV S=ops/sqrtn |  rho S | speedup | ok  "
           "|\n");
    printf("|------------------------------|-------|---|-----------------|-------:|--------:|-----|"
           "\n");
    for (size_t i = 0; i < nuse; i++) {
        uint64_t p, a, b, order;
        if (ca_curve_by_name(names[i], &p, &a, &b, &order) != CA_OK) continue;
        ca_group g;
        ca_curve_info info;
        if (ca_curve_group(&g, p, a, b, order, &info) != CA_OK) continue;
        ca_elem gen;
        if (ca_group_find_generator(&g, &gen, 1) != CA_OK) continue;
        double sq = sqrt((double)order);
        ca_rng rng;
        ca_rng_seed(&rng, 123 + (unsigned)i);
        const unsigned reps = 20;
        double glv_ops = 0, rho_ops = 0;
        unsigned ok = 0;
        for (unsigned r = 0; r < reps; r++) {
            uint64_t x = ca_rng_below(&rng, order);
            ca_elem h;
            ca_group_mul(&g, &h, &gen, x, NULL);
            uint64_t got = 0;
            ca_stats s1 = {0};
            ca_curve_solve(&g, &gen, &h, 7 + r, &got, NULL, &s1);
            glv_ops += (double)s1.group_ops;
            ok += (got == x);
            /* plain negation-map rho on the same curve for comparison */
            ca_group pg;
            ca_group_ec_init(&pg, p, a, b, order);
            pg.cofactor = g.cofactor;
            uint64_t got2 = 0;
            ca_stats s2 = {0};
            ca_rho_params rp;
            ca_rho_params_default(&rp);
            rp.seed = 7 + r;
            ca_rho_solve(&pg, &gen, &h, &rp, &got2, &s2);
            rho_ops += (double)s2.group_ops;
        }
        const char *ek = info.endo == CA_CURVE_ENDO_J0      ? "j0"
                         : info.endo == CA_CURVE_ENDO_J1728 ? "j1728"
                                                            : "none";
        double gs = glv_ops / reps / sq, rs = rho_ops / reps / sq;
        printf("| %-28s | %-5s | %u | %15.3f | %6.3f | %6.2fx | %u/%u |\n", names[i], ek,
               info.aut_order, gs, rs, gs > 0 ? rs / gs : 0.0, ok, reps);
    }
}

static void run_ops(void)
{
    uint64_t p;
    uint64_t q = find_safe_prime(61, &p);
    ca_group g;
    ca_group_zp_init(&g, p, q);
    ca_elem a, b;
    ca_group_find_generator(&g, &a, 1);
    b = a;
    const uint64_t N = 20000000;
    double t0 = ca_now();
    for (uint64_t i = 0; i < N; i++) ca_group_op(&g, &b, &b, &a);
    double t = ca_now() - t0;
    const double n_ops = (double)N;
    printf("| zp 61-bit mulmod (Montgomery)      | %7.1f Mops/s | %6.1f ns/op |\n", n_ops / t / 1e6,
           t / n_ops * 1e9);
    uint64_t ep, ea, eb, en;
    find_prime_order_curve(60, &ep, &ea, &eb, &en);
    ca_group_ec_init(&g, ep, ea, eb, en);
    ca_group_find_generator(&g, &a, 1);
    b = a;
    const uint64_t M = 2000000;
    t0 = ca_now();
    for (uint64_t i = 0; i < M; i++) ca_group_op(&g, &b, &b, &a);
    t = ca_now() - t0;
    const double m_ops = (double)M;
    printf("| ec 60-bit affine add (1 inversion) | %7.2f Mops/s | %6.1f ns/op |\n", m_ops / t / 1e6,
           t / m_ops * 1e9);
    /* batched */
    enum { W = 256 };
    ca_elem A[W], B[W], R[W];
    uint64_t scratch[2 * W];
    for (int i = 0; i < W; i++) { ca_group_mul(&g, &A[i], &a, 3 + i, NULL); B[i] = a; }
    t0 = ca_now();
    for (uint64_t i = 0; i < M / W; i++) {
        ca_group_batch_op(&g, R, A, B, W, scratch);
        memcpy(A, R, sizeof(A));
    }
    t = ca_now() - t0;
    /* M is rounded down to a whole number of batches, so count what really ran. */
    const uint64_t batched = M / W * W;
    const double b_ops = (double)batched;
    printf("| ec 60-bit affine add (batch 256)   | %7.2f Mops/s | %6.1f ns/op |\n", b_ops / t / 1e6,
           t / b_ops * 1e9);
}

int main(int argc, char **argv)
{
    argc_g = argc;
    argv_g = argv;
    const char *cmd = argc > 1 ? argv[1] : "generic";
    unsigned bits[16];
    unsigned reps = (unsigned)strtoul(opt("--reps", strcmp(cmd, "gpu") ? "5" : "3"), NULL, 10);
    unsigned threads = (unsigned)strtoul(opt("--threads", "4"), NULL, 10);
    const char *group = opt("--group", "both");
    const char *json_path = opt("--json", NULL);
    if (json_path) {
        json_g = fopen(json_path, "w");
        if (!json_g) {
            fprintf(stderr, "cannot open %s for writing\n", json_path);
            return 2;
        }
        if (strcmp(cmd, "generic") && strcmp(cmd, "complexity"))
            fprintf(stderr,
                    "note: --json writes per-instance rows for generic and complexity only\n");
        json_header(cmd);
    }
    printf("libcryptanalysis %s benchmark: %s\n\n", ca_version(), cmd);
    if (!strcmp(cmd, "generic")) {
        int nb = parse_list(opt("--bits", "24,28,32,36"), bits, 16);
        printf("Whole-group DLP, prime order n.  S = group ops / sqrt(n) (rho reference ~1.3).\n"
               "Each table ends with the measured exponent (fitted cost ~ C n^alpha).\n\n");
        if (strcmp(group, "ec")) run_generic(bits, nb, reps, threads, 0);
        if (strcmp(group, "zp")) run_generic(bits, nb, reps, threads, 1);
    } else if (!strcmp(cmd, "interval")) {
        int nb = parse_list(opt("--bits", "24,28,32,36"), bits, 16);
        printf("Interval DLP of width 2^w inside a large prime-order group.  S = group ops / "
               "sqrt(width).\nEach table ends with the measured exponent (fitted cost ~ C w^alpha)."
               "\n\n");
        if (strcmp(group, "ec")) run_interval(bits, nb, reps, 0);
        if (strcmp(group, "zp")) run_interval(bits, nb, reps, 1);
    } else if (!strcmp(cmd, "ic")) {
        int nb = parse_list(opt("--bits", "32,40,48,56"), bits, 16);
        printf("Index calculus in Z_p^* (safe primes), linear sieve, %u threads.\n\n", threads);
        printf("| bits | p | fb | unknowns | rels | sieve s | linalg s | precomp s | log s | tries | rho ops ref |\n");
        printf("|------|---|----|----------|------|---------|----------|-----------|-------|-------|-------------|\n");
        for (int i = 0; i < nb; i++) run_ic(bits[i], threads);
    } else if (!strcmp(cmd, "cheon")) {
        int nb = parse_list(opt("--bits", "32,40,48"), bits, 16);
        printf("Cheon's attack (d | p-1) vs Pollard rho on the same instance.\n\n");
        printf("| bits | p | d | cheon exps | cheon ops | cheon s | rho ops | rho s | speedup | ok |\n");
        printf("|------|---|---|------------|-----------|---------|---------|-------|---------|----|\n");
        for (int i = 0; i < nb; i++) run_cheon(bits[i]);
    } else if (!strcmp(cmd, "gpu")) {
        int nb = parse_list(opt("--bits", "24,28,32"), bits, 16);
        printf("GPU rho kernel vs the CPU solver.  S = group ops / sqrt(n); \"walks\" is the\n"
               "number of concurrent walks (CPU: threads; GPU: threads x %d).\n",
               CA_GPU_W);
        printf("CUDA compiled: %s, devices: %d\n", ca_gpu_cuda_compiled() ? "yes" : "no",
               ca_gpu_device_count());
        for (int i = 0; i < ca_gpu_device_count(); i++) {
            char name[256] = "";
            if (ca_gpu_device_name(i, name, sizeof(name)) == 0)
                printf("  device %d: %s\n", i, name);
        }
        printf("\n| grp | bits | solver             | S=ops/√n | seconds    |   walks | launches | "
               "ok  |\n");
        printf("|-----|------|--------------------|----------|------------|---------|----------|---"
               "--|\n");
        for (int i = 0; i < nb; i++) {
            if (strcmp(group, "ec")) run_gpu(bits[i], reps, 0);
            if (strcmp(group, "zp")) run_gpu(bits[i], reps, 1);
        }
        printf("\nThe emulator runs the kernel body one thread at a time on the CPU, so its\n"
               "seconds column is not a GPU measurement; the operation counts are.\n");
    } else if (!strcmp(cmd, "precomp")) {
        int nb = parse_list(opt("--bits", "24,28,32,36"), bits, 16);
        printf(
            "Discrete logs with precomputation (Bernstein-Lange).  One table per (group, base);\n"
            "P = precomputation ops (paid once), T = per-target online ops over --reps "
            "targets.\n");
        printf("Build threads: %u.  Each table ends with the measured build (n^2/3) and online\n"
               "(n^1/3) exponents.\n\n",
               threads);
        if (strcmp(group, "ec")) run_precomp(bits, nb, reps, threads, 0);
        if (strcmp(group, "zp")) run_precomp(bits, nb, reps, threads, 1);
    } else if (!strcmp(cmd, "complexity")) {
        int nb = parse_list(opt("--bits", "20,24,28,32,36"), bits, 16);
        printf("Empirical time complexity.  The measured group-operation cost of each\n"
               "algorithm is fitted to C * N^alpha, so the exponent (the O()) is measured\n"
               "rather than assumed and the constant is comparable across algorithms.\n"
               "scope: global = whole algorithm, step = one phase of a method.\n");
        if (strcmp(group, "ec")) run_complexity(bits, nb, reps, 0);
        if (strcmp(group, "zp")) run_complexity(bits, nb, reps, 1);
        printf("\nIndex calculus in Z_p^* is omitted here: it is subexponential (L_p[1/2]),\n"
               "not a power law, so no single exponent describes it (see the ic mode).\n");
    } else if (!strcmp(cmd, "glv")) {
        printf("GLV endomorphism-accelerated rho vs the plain negation-map rho on the same\n"
               "curve (S = group ops / sqrt(n)).  CM curves fold the walk by the automorphism\n"
               "group order m (6 for j=0, 4 for j=1728); a generic curve has only negation.\n\n");
        run_glv();
    } else if (!strcmp(cmd, "ops")) {
        run_ops();
    } else {
        fprintf(stderr, "unknown benchmark %s\n", cmd);
        return 2;
    }
    if (json_g && fclose(json_g) != 0) {
        fprintf(stderr, "error writing %s\n", json_path);
        return 2;
    }
    return 0;
}
