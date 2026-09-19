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
 *   ca_bench ops      raw group operation throughput.
 *   ca_bench gpu      [--bits 24,28,32] [--reps 3] [--group zp|ec|both]
 *       CPU rho vs the GPU rho kernel (CUDA when a device is present,
 *       otherwise the host emulator) in S = group ops / sqrt(n).
 */
#include "cryptanalysis/cryptanalysis.h"
#include "ca_internal.h"
#include "ca_device.cuh"

#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

static void run_generic(unsigned bits, unsigned reps, unsigned threads, int ec)
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
    enum { NALG = 5 };
    const char *names[NALG] = {"bsgs", "rho-1", "rho-T", "kangaroo", "grumpy"};
    double ops[NALG] = {0}, secs[NALG] = {0};
    unsigned ok[NALG] = {0};
    ca_rng rng;
    ca_rng_seed(&rng, 1234 + bits);
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
            case 2: dp.rho.threads = threads; rc = ca_rho_solve(&g, &gen, &h, &dp.rho, &got, &st); break;
            case 3: rc = ca_kangaroo_solve(&g, &gen, &h, 0, 0, &dp.kangaroo, &got, &st); break;
            default: rc = ca_grumpy_solve(&g, &gen, &h, 0, 0, &dp.grumpy, &got, &st); break;
            }
            ops[a] += (double)st.group_ops;
            secs[a] += st.seconds;
            ok[a] += (rc == CA_OK && got == x);
        }
    }
    for (int a = 0; a < NALG; a++) {
        printf("| %-4s | %3u | %-9s | %8.3f | %10.4f | %8.0f | %u/%u |\n", ec ? "ec" : "zp", bits, names[a],
               ops[a] / reps / sq, secs[a] / reps, ops[a] / reps / (secs[a] / reps + 1e-12) / 1e6,
               ok[a], reps);
    }
}

static void run_interval(unsigned wbits, unsigned reps, int ec)
{
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
    uint64_t width = 1ULL << wbits;
    double sq = sqrt((double)width);
    enum { NALG = 3 };
    const char *names[NALG] = {"bsgs", "kangaroo", "grumpy"};
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
            case 0: rc = ca_bsgs_solve(&g, &gen, &h, lo, lo + width - 1, &dp.bsgs, &got, &st); break;
            case 1: rc = ca_kangaroo_solve(&g, &gen, &h, lo, lo + width - 1, &dp.kangaroo, &got, &st); break;
            default: rc = ca_grumpy_solve(&g, &gen, &h, lo, lo + width - 1, &dp.grumpy, &got, &st); break;
            }
            ops[a] += (double)st.group_ops;
            secs[a] += st.seconds;
            ok[a] += (rc == CA_OK && got == x);
        }
    }
    for (int a = 0; a < NALG; a++) {
        printf("| %-4s | 2^%-3u | %-9s | %8.3f | %10.4f | %u/%u |\n", ec ? "ec" : "zp", wbits, names[a],
               ops[a] / reps / sq, secs[a] / reps, ok[a], reps);
    }
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
    printf("libcryptanalysis %s benchmark: %s\n\n", ca_version(), cmd);
    if (!strcmp(cmd, "generic")) {
        int nb = parse_list(opt("--bits", "24,28,32,36"), bits, 16);
        printf("Whole-group DLP, prime order n.  S = group ops / sqrt(n) (rho reference ~1.3).\n\n");
        printf("| grp | bits | algorithm | S=ops/√n | seconds    | Mops/s   | ok  |\n");
        printf("|-----|------|-----------|----------|------------|----------|-----|\n");
        for (int i = 0; i < nb; i++) {
            if (strcmp(group, "ec")) run_generic(bits[i], reps, threads, 0);
            if (strcmp(group, "zp")) run_generic(bits[i], reps, threads, 1);
        }
    } else if (!strcmp(cmd, "interval")) {
        int nb = parse_list(opt("--bits", "24,28,32,36"), bits, 16);
        printf("Interval DLP of width 2^w inside a large prime-order group.  S = group ops / sqrt(width).\n\n");
        printf("| grp | width | algorithm | S=ops/√w | seconds    | ok  |\n");
        printf("|-----|-------|-----------|----------|------------|-----|\n");
        for (int i = 0; i < nb; i++) {
            if (strcmp(group, "ec")) run_interval(bits[i], reps, 0);
            if (strcmp(group, "zp")) run_interval(bits[i], reps, 1);
        }
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
    } else if (!strcmp(cmd, "ops")) {
        run_ops();
    } else {
        fprintf(stderr, "unknown benchmark %s\n", cmd);
        return 2;
    }
    return 0;
}
