/*
 * ca_perfbench.c - fixed-input kernels for the performance index, C library.
 *
 * Speaks the perfbench protocol of suite/examples/perfbench/harness.rs, so
 * scripts/perf/perfindex.py drives it exactly like the Rust harness:
 *
 *   ca_perfbench list [--full]
 *   ca_perfbench run  [--filter A,B] [--exact] [--full] [--samples N] [--min-samples N]
 *                     [--max-seconds S] [--warmup-seconds S] [--instr]
 *
 * Each kernel runs a fixed, seeded input through public entry points of
 * libcryptanalysis (plus the internal sparse solver that index calculus
 * calls, declared in src/linalg.h) and returns a 64-bit fingerprint of
 * everything it computed: recovered logarithms, the solvers' operation and
 * iteration counts, point coordinates, residues.  A kernel whose fingerprint
 * changes between samples aborts; perfindex.py refuses a comparison whose
 * baseline and candidate fingerprints differ.  See docs/perf/PERFORMANCE_INDEX.md.
 *
 * Kernels are single-threaded (the solvers take an explicit thread count and
 * it is 1 here) except dlp/c_rho_ec44_mt, which reads RAYON_NUM_THREADS so
 * the runner's --threads applies to it; its fingerprint covers the recovered
 * logarithms only, because the operation counts of a multi-threaded rho
 * depend on the schedule.
 *
 * Every ca_rng is zero-initialised before ca_rng_seed overwrites it: gcc
 * -fanalyzer (the CI's analyzer job) otherwise reports a false
 * use-of-uninitialised-value inside ca_rng_seed.
 *
 * Curve fixtures are hard-coded (found once with ca_ec_count_points, the
 * same search as tools/ca_bench.c) and re-checked in setup: n prime and
 * n*G = O, so a wrong constant aborts rather than benchmarks nonsense.
 */
#include "cryptanalysis/cryptanalysis.h"
#include "ca_internal.h"
#include "linalg.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* ---- fingerprint: FNV-1a over little-endian 64-bit words + avalanche -------
 * Bit-for-bit the Fp of suite/examples/perfbench/harness.rs. */

typedef struct pb_fp {
    uint64_t h;
} pb_fp;

static void fp_init(pb_fp *f) { f->h = 0xcbf29ce484222325ULL; }

static void fp_u64(pb_fp *f, uint64_t x)
{
    for (int i = 0; i < 8; i++) {
        f->h ^= (x >> (8 * i)) & 0xff;
        f->h *= 0x00000100000001b3ULL;
    }
}

static void fp_words(pb_fp *f, const uint64_t *xs, size_t n)
{
    fp_u64(f, (uint64_t)n);
    for (size_t i = 0; i < n; i++) fp_u64(f, xs[i]);
}

static void fp_bytes(pb_fp *f, const uint8_t *xs, size_t n)
{
    fp_u64(f, (uint64_t)n);
    for (size_t i = 0; i < n; i++) {
        f->h ^= xs[i];
        f->h *= 0x00000100000001b3ULL;
    }
}

static uint64_t fp_finish(const pb_fp *f)
{
    uint64_t z = f->h;
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}

/* A group element in the public word representation (canonical, so the
 * fingerprint does not depend on the internal Montgomery form). */
static void fp_elem(pb_fp *f, const ca_group *g, const ca_elem *e)
{
    uint64_t w[4];
    ca_group_decode(g, w, e);
    fp_u64(f, w[0]);
    fp_u64(f, w[1]);
    fp_u64(f, w[2]);
}

/* Solver work counters that are deterministic for one thread.  Left out:
 * seconds (a measurement) and bytes_peak (an estimate of the tables'
 * footprint, which a change of hash-table layout legitimately moves without
 * changing anything that was computed). */
static void fp_stats(pb_fp *f, const ca_stats *st)
{
    fp_u64(f, st->group_ops);
    fp_u64(f, st->iterations);
    fp_u64(f, st->table_entries);
    fp_u64(f, st->collisions);
    fp_u64(f, st->threads);
}

static void die(const char *id, const char *what)
{
    fprintf(stderr, "ca_perfbench: %s: %s\n", id, what);
    exit(3);
}

/* ---- kernel registry ------------------------------------------------------ */

typedef struct pb_kernel {
    const char *id;   /* area/name, never reused for different work */
    const char *area; /* weight group (docs/perf/PERFORMANCE_INDEX.md) */
    const char *desc; /* what one run computes */
    int full;         /* 0 = Quick, 1 = Full */
    void *(*setup)(void);
    void (*prepare)(void *);  /* untimed per-sample restore; NULL = none */
    uint64_t (*run)(void *);  /* the timed work; returns the fingerprint */
    void (*teardown)(void *); /* NULL = free() */
} pb_kernel;

/* ---- fixtures ------------------------------------------------------------- */

typedef struct curve_fix {
    uint64_t p, a, b, n;
} curve_fix;

/* Prime-order curves y^2 = x^3 + x + b over p = next_prime(2^(k-1) | 5),
 * b the first with prime #E (tools/ca_bench.c find_prime_order_curve). */
static const curve_fix EC32 = {2147483659ULL, 1, 230, 2147540641ULL};
static const curve_fix EC36 = {34359738421ULL, 1, 77, 34359573251ULL};
static const curve_fix EC44 = {8796093022237ULL, 1, 113, 8796096094351ULL};
static const curve_fix EC56 = {36028797018963979ULL, 1, 156, 36028796932550941ULL};
static const curve_fix EC60 = {576460752303423619ULL, 1, 110, 576460752498581429ULL};
/* Smooth order: #E = 2^2 * 31 * 100493 * 11294117 over the 48-bit prime. */
static const curve_fix EC48S = {140737488355337ULL, 1, 1, 140737482760444ULL};

/* Safe prime p = 2q + 1 of the given bit length (tools/ca_bench.c). */
static uint64_t safe_prime(unsigned bits, uint64_t *q_out)
{
    uint64_t p = (1ULL << (bits - 1)) | 3;
    for (;;) {
        p = ca_next_prime(p);
        if (ca_is_prime((p - 1) / 2)) {
            if (q_out) *q_out = (p - 1) / 2;
            return p;
        }
    }
}

/* EC group of prime order with a generator; checked, never trusted. */
static void ec_fixture(const char *id, const curve_fix *c, int prime_order, ca_group *g,
                       ca_elem *gen)
{
    if (ca_group_ec_init(g, c->p, c->a, c->b, c->n) != CA_OK) die(id, "curve init failed");
    if (prime_order) {
        if (!ca_is_prime(c->n)) die(id, "fixture order is not prime");
        g->cofactor = 1;
    }
    if (ca_group_find_generator(g, gen, 1) != CA_OK) die(id, "no generator");
    ca_elem t;
    ca_group_mul(g, &t, gen, c->n, NULL);
    if (!ca_group_is_identity(g, &t)) die(id, "n * G != O: fixture constants are wrong");
}

static void zp_fixture(const char *id, uint64_t p, uint64_t order, ca_group *g, ca_elem *gen)
{
    if (ca_group_zp_init(g, p, order) != CA_OK) die(id, "Z_p^* init failed");
    if (ca_group_find_generator(g, gen, 1) != CA_OK) die(id, "no generator");
}

/* Fixed targets x_i * gen, x_i drawn from a seeded stream (fixture
 * construction, outside the timer). */
#define MAX_TARGETS 64
typedef struct dlp_fix {
    const char *id;
    ca_group g;
    ca_elem gen;
    uint32_t nt;
    uint64_t x[MAX_TARGETS];
    ca_elem h[MAX_TARGETS];
    uint64_t lo[MAX_TARGETS], hi[MAX_TARGETS];
    uint64_t width;
    ca_precomp_table *tab;
} dlp_fix;

static void make_targets(dlp_fix *d, uint32_t nt, uint64_t seed, uint64_t width)
{
    if (nt > MAX_TARGETS) die(d->id, "too many targets");
    ca_rng rng = {{0}};
    ca_rng_seed(&rng, seed);
    uint64_t n = d->g.order;
    d->nt = nt;
    d->width = width;
    for (uint32_t i = 0; i < nt; i++) {
        if (width) {
            /* interval [lo, lo + width - 1] inside [0, n) containing x */
            uint64_t lo = ca_rng_below(&rng, n - width);
            d->lo[i] = lo;
            d->hi[i] = lo + width - 1;
            d->x[i] = lo + ca_rng_below(&rng, width);
        } else {
            d->x[i] = 1 + ca_rng_below(&rng, n - 1);
            d->lo[i] = d->hi[i] = 0;
        }
        ca_group_mul(&d->g, &d->h[i], &d->gen, d->x[i], NULL);
    }
}

static dlp_fix *dlp_new(const char *id)
{
    dlp_fix *d = calloc(1, sizeof(*d));
    if (!d) die(id, "out of memory");
    d->id = id;
    return d;
}

static void dlp_free(void *p)
{
    dlp_fix *d = p;
    if (d->tab) ca_precomp_table_free(d->tab);
    free(d);
}

/* Common tail of every solve: the answer, the status, and the work counts.
 * A solve that returns a wrong logarithm is a broken library, not a slow one. */
static void fp_solve(pb_fp *f, const dlp_fix *d, uint32_t i, ca_status rc, uint64_t got,
                     const ca_stats *st)
{
    if (rc != CA_OK || got != d->x[i]) {
        char msg[160];
        snprintf(msg, sizeof msg, "target %u: rc=%d got=%" PRIu64 " want=%" PRIu64, i, (int)rc, got,
                 d->x[i]);
        die(d->id, msg);
    }
    fp_u64(f, (uint64_t)rc);
    fp_u64(f, got);
    fp_stats(f, st);
}

/* ======================= field_ec: F_p and E(F_p) arithmetic =============== */

/* --- Montgomery multiplication throughput (header-inline ca_mont_mul) --- */
typedef struct mont_fix {
    ca_mont m;
    uint64_t seed[8], mul[8];
    uint64_t iters;
} mont_fix;

static void *setup_mont_mul_x8(void)
{
    mont_fix *s = calloc(1, sizeof(*s));
    if (!s) die("field_ec/c_mont_mul_x8", "out of memory");
    uint64_t p = safe_prime(61, NULL);
    ca_mont_init(&s->m, p);
    ca_rng rng = {{0}};
    ca_rng_seed(&rng, 0x6d6f6e74ULL);
    for (int i = 0; i < 8; i++) {
        s->seed[i] = ca_mont_to(&s->m, 2 + ca_rng_below(&rng, p - 2));
        s->mul[i] = ca_mont_to(&s->m, 2 + ca_rng_below(&rng, p - 2));
    }
    s->iters = 1u << 21;
    return s;
}

static uint64_t run_mont_mul_x8(void *p)
{
    const mont_fix *s = p;
    uint64_t v[8];
    memcpy(v, s->seed, sizeof v);
    for (uint64_t it = 0; it < s->iters; it++) {
        /* eight independent chains: throughput, not latency */
        for (int i = 0; i < 8; i++) v[i] = ca_mont_mul(&s->m, v[i], s->mul[i]);
    }
    pb_fp f;
    fp_init(&f);
    for (int i = 0; i < 8; i++) fp_u64(&f, ca_mont_from(&s->m, v[i]));
    return fp_finish(&f);
}

/* --- Z_p^* group op through the vtable: one dependent chain (latency) --- */
typedef struct zpop_fix {
    ca_group g;
    ca_elem a, b0;
    uint64_t iters;
} zpop_fix;

static void *setup_zp_op_chain(void)
{
    zpop_fix *s = calloc(1, sizeof(*s));
    if (!s) die("field_ec/c_zp_op_chain", "out of memory");
    uint64_t q, p = safe_prime(61, &q);
    zp_fixture("field_ec/c_zp_op_chain", p, q, &s->g, &s->a);
    ca_group_mul(&s->g, &s->b0, &s->a, 12345, NULL);
    s->iters = 4u << 20;
    return s;
}

static uint64_t run_zp_op_chain(void *p)
{
    const zpop_fix *s = p;
    ca_elem b = s->b0;
    for (uint64_t i = 0; i < s->iters; i++) ca_group_op(&s->g, &b, &b, &s->a);
    ca_elem c = s->b0;
    for (uint64_t i = 0; i < s->iters / 4; i++) ca_group_dbl(&s->g, &c, &c);
    pb_fp f;
    fp_init(&f);
    fp_elem(&f, &s->g, &b);
    fp_elem(&f, &s->g, &c);
    return fp_finish(&f);
}

/* --- generic modular arithmetic on arrays of inputs --- */
#define MA_N 8192
typedef struct ma_fix {
    uint64_t m[4]; /* moduli */
    ca_mont mont[4];
    uint64_t a[MA_N], e[MA_N];
    uint32_t reps;
} ma_fix;

static void *setup_modarith(void)
{
    ma_fix *s = calloc(1, sizeof(*s));
    if (!s) die("field_ec/c_modarith", "out of memory");
    /* 61-bit safe prime, a 62-bit prime, a 40-bit prime, a 64-bit prime */
    s->m[0] = safe_prime(61, NULL);
    s->m[1] = ca_next_prime(3ULL << 60);
    s->m[2] = ca_next_prime(1ULL << 40);
    s->m[3] = ca_next_prime(0xfffffffffffff000ULL);
    for (int i = 0; i < 4; i++) ca_mont_init(&s->mont[i], s->m[i]);
    ca_rng rng = {{0}};
    ca_rng_seed(&rng, 0x706f776dULL);
    for (int i = 0; i < MA_N; i++) {
        s->a[i] = ca_rng_next(&rng);
        s->e[i] = ca_rng_next(&rng);
    }
    s->reps = 1;
    return s;
}

/* ca_powmod: the plain (128-bit remainder) exponentiation every group
 * constructor, primality test and square root goes through. */
static uint64_t run_powmod(void *p)
{
    const ma_fix *s = p;
    pb_fp f;
    fp_init(&f);
    for (int k = 0; k < 4; k++) {
        uint64_t acc = 0;
        for (int i = 0; i < MA_N; i++) {
            uint64_t r = ca_powmod(s->a[i], s->e[i], s->m[k]);
            acc = acc * 0x9E3779B97F4A7C15ULL + r;
        }
        fp_u64(&f, acc);
    }
    return fp_finish(&f);
}

/* ca_mont_pow on the four moduli (Montgomery-form exponentiation). */
static uint64_t run_mont_pow(void *p)
{
    const ma_fix *s = p;
    pb_fp f;
    fp_init(&f);
    for (int k = 0; k < 4; k++) {
        const ca_mont *m = &s->mont[k];
        uint64_t acc = 0;
        for (int i = 0; i < MA_N; i++) {
            uint64_t r = ca_mont_pow(m, ca_mont_to(m, s->a[i]), s->e[i]);
            acc = acc * 0x9E3779B97F4A7C15ULL + ca_mont_from(m, r);
        }
        fp_u64(&f, acc);
    }
    return fp_finish(&f);
}

/* ca_invmod and ca_mont_inv: the per-operation cost of affine EC. */
static uint64_t run_invmod(void *p)
{
    const ma_fix *s = p;
    pb_fp f;
    fp_init(&f);
    for (int k = 0; k < 4; k++) {
        uint64_t acc = 0, acc2 = 0;
        const ca_mont *m = &s->mont[k];
        for (int rep = 0; rep < 4; rep++) {
            for (int i = 0; i < MA_N; i++) {
                uint64_t a = s->a[i] ^ (uint64_t)rep;
                acc = acc * 0x9E3779B97F4A7C15ULL + ca_invmod(a, s->m[k]);
                if (rep == 0)
                    acc2 = acc2 * 0x9E3779B97F4A7C15ULL + ca_mont_inv(m, ca_mont_to(m, a | 1));
            }
        }
        fp_u64(&f, acc);
        fp_u64(&f, acc2);
    }
    return fp_finish(&f);
}

/* ca_sqrtmod_prime (Tonelli-Shanks for p = 1 mod 2^k, the (p+1)/4 power
 * otherwise) and ca_legendre, as used by ca_ec_lift_x / random points. */
typedef struct sqrt_fix {
    uint64_t p[3];
    uint64_t a[4096];
} sqrt_fix;

static void *setup_sqrtmod(void)
{
    sqrt_fix *s = calloc(1, sizeof(*s));
    if (!s) die("field_ec/c_sqrtmod", "out of memory");
    /* p = 3 mod 4; p = 1 mod 2^20 (long Tonelli-Shanks); a 61-bit safe prime */
    s->p[0] = EC60.p;
    uint64_t k = (1ULL << 40) + 1;
    while (!ca_is_prime(k * (1ULL << 20) + 1)) k++;
    s->p[1] = k * (1ULL << 20) + 1;
    s->p[2] = safe_prime(61, NULL);
    ca_rng rng = {{0}};
    ca_rng_seed(&rng, 0x73717274ULL);
    for (int i = 0; i < 4096; i++) s->a[i] = ca_rng_next(&rng);
    return s;
}

static uint64_t run_sqrtmod(void *p)
{
    const sqrt_fix *s = p;
    pb_fp f;
    fp_init(&f);
    for (int k = 0; k < 3; k++) {
        uint64_t acc = 0, nres = 0;
        for (int i = 0; i < 4096; i++) {
            uint64_t r = 0;
            int ok = ca_sqrtmod_prime(s->a[i], s->p[k], &r);
            nres += (uint64_t)ok;
            /* canonical root: the smaller of r and p - r */
            if (ok && r > s->p[k] - r) r = s->p[k] - r;
            acc = acc * 0x9E3779B97F4A7C15ULL + (ok ? r : 0x5a5a);
        }
        fp_u64(&f, acc);
        fp_u64(&f, nres);
    }
    return fp_finish(&f);
}

/* ca_is_prime / ca_next_prime over a window near 2^62 and near 2^40. */
static void *setup_nothing(void) { return calloc(1, 16); }

static uint64_t run_is_prime(void *p)
{
    (void)p;
    pb_fp f;
    fp_init(&f);
    uint64_t start[2] = {(1ULL << 62) + 12345, (1ULL << 40) + 777};
    for (int k = 0; k < 2; k++) {
        uint64_t cnt = 0, acc = 0;
        for (uint64_t v = start[k]; v < start[k] + 30000; v++) {
            if (ca_is_prime(v)) {
                cnt++;
                acc = acc * 0x9E3779B97F4A7C15ULL + v;
            }
        }
        fp_u64(&f, cnt);
        fp_u64(&f, acc);
    }
    uint64_t q = (1ULL << 50) + 3;
    for (int i = 0; i < 200; i++) {
        q = ca_next_prime(q);
        fp_u64(&f, q);
    }
    return fp_finish(&f);
}

/* ca_factorize (trial division + Pollard-Brent) on semiprimes with ~24-bit
 * factors and on random 62-bit integers; ca_primitive_root on 60-bit primes. */
typedef struct fact_fix {
    uint64_t v[256];
    uint32_t nv;
    uint64_t pr[16];
} fact_fix;

static void *setup_factorize(void)
{
    fact_fix *s = calloc(1, sizeof(*s));
    if (!s) die("field_ec/c_factorize", "out of memory");
    ca_rng rng = {{0}};
    ca_rng_seed(&rng, 0x66616374ULL);
    uint32_t n = 0;
    for (int i = 0; i < 64; i++) {
        uint64_t a = ca_next_prime((1ULL << 25) + ca_rng_below(&rng, 1ULL << 25));
        uint64_t b = ca_next_prime((1ULL << 29) + ca_rng_below(&rng, 1ULL << 29));
        s->v[n++] = a * b;
    }
    for (int i = 0; i < 128; i++) s->v[n++] = (ca_rng_next(&rng) >> 2) | 1;
    s->nv = n;
    uint64_t q = 1ULL << 59;
    for (int i = 0; i < 16; i++) s->pr[i] = q = ca_next_prime(q + ca_rng_below(&rng, 1ULL << 30));
    return s;
}

static uint64_t run_factorize(void *p)
{
    const fact_fix *s = p;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < s->nv; i++) {
        ca_factorization fz;
        ca_factorize(s->v[i], &fz);
        fp_u64(&f, fz.count);
        for (unsigned k = 0; k < fz.count; k++) {
            fp_u64(&f, fz.f[k].p);
            fp_u64(&f, fz.f[k].e);
        }
    }
    for (int i = 0; i < 16; i++) fp_u64(&f, ca_primitive_root(s->pr[i]));
    return fp_finish(&f);
}

/* --- elliptic curve group operations on the 60-bit prime-order curve --- */
#define EC_BATCH 256
typedef struct ecop_fix {
    ca_group g;
    ca_elem gen, start;
    ca_elem A[EC_BATCH], B[EC_BATCH];
    uint64_t k[1024];
    uint64_t scratch[2 * EC_BATCH];
} ecop_fix;

static ecop_fix *ec_ops_setup(const char *id)
{
    ecop_fix *s = calloc(1, sizeof(*s));
    if (!s) die(id, "out of memory");
    ec_fixture(id, &EC60, 1, &s->g, &s->gen);
    ca_group_mul(&s->g, &s->start, &s->gen, 0x1234567ULL, NULL);
    for (int i = 0; i < EC_BATCH; i++) {
        ca_group_mul(&s->g, &s->A[i], &s->gen, 3 + (uint64_t)i * 1000003ULL, NULL);
        ca_group_mul(&s->g, &s->B[i], &s->gen, 7 + (uint64_t)i * 7919ULL, NULL);
    }
    ca_rng rng = {{0}};
    ca_rng_seed(&rng, 0x7363616cULL);
    for (int i = 0; i < 1024; i++) s->k[i] = ca_rng_below(&rng, EC60.n);
    return s;
}

static void *setup_ec_add_chain(void) { return ec_ops_setup("field_ec/c_ec_add_chain"); }
static void *setup_ec_batch_add(void) { return ec_ops_setup("field_ec/c_ec_batch_add"); }
static void *setup_ec_scalar_mul(void) { return ec_ops_setup("field_ec/c_ec_scalar_mul"); }

/* ca_group_op (affine add, one field inversion) and ca_group_dbl chains. */
static uint64_t run_ec_add_chain(void *p)
{
    const ecop_fix *s = p;
    ca_elem acc = s->start, d = s->start;
    for (int i = 0; i < 60000; i++) ca_group_op(&s->g, &acc, &acc, &s->gen);
    for (int i = 0; i < 30000; i++) ca_group_dbl(&s->g, &d, &d);
    pb_fp f;
    fp_init(&f);
    fp_elem(&f, &s->g, &acc);
    fp_elem(&f, &s->g, &d);
    return fp_finish(&f);
}

/* ca_group_batch_op, 256 independent adds per call (Montgomery's trick):
 * the inner loop of every rho / kangaroo / precomputation walk. */
static uint64_t run_ec_batch_add(void *p)
{
    ecop_fix *s = p;
    ca_elem A[EC_BATCH], R[EC_BATCH];
    memcpy(A, s->A, sizeof A);
    for (int it = 0; it < 6000; it++) {
        ca_group_batch_op(&s->g, R, A, s->B, EC_BATCH, s->scratch);
        memcpy(A, R, sizeof A);
    }
    pb_fp f;
    fp_init(&f);
    for (int i = 0; i < EC_BATCH; i++) fp_elem(&f, &s->g, &A[i]);
    return fp_finish(&f);
}

/* ca_group_mul, 60-bit scalars (double-and-add in affine coordinates):
 * walk starts, multiplier tables, verification, Pohlig-Hellman lifts. */
static uint64_t run_ec_scalar_mul(void *p)
{
    const ecop_fix *s = p;
    pb_fp f;
    fp_init(&f);
    for (int i = 0; i < 1024; i++) {
        ca_elem r;
        uint64_t ops = 0;
        ca_group_mul(&s->g, &r, i & 1 ? &s->start : &s->gen, s->k[i], &ops);
        fp_elem(&f, &s->g, &r);
        fp_u64(&f, ops);
    }
    return fp_finish(&f);
}

/* ca_ec_count_points (Mestre BSGS in the Hasse interval) on 56-bit curves. */
static uint64_t run_ec_count_points(void *p)
{
    (void)p;
    pb_fp f;
    fp_init(&f);
    for (uint64_t b = EC56.b; b < EC56.b + 4; b++) {
        uint64_t order = 0;
        ca_stats st = {0};
        ca_status rc = ca_ec_count_points(EC56.p, EC56.a, b, &order, &st);
        if (b == EC56.b && (rc != CA_OK || order != EC56.n))
            die("field_ec/c_ec_count_points", "wrong order for the fixture curve");
        fp_u64(&f, (uint64_t)rc);
        fp_u64(&f, order);
        fp_u64(&f, st.group_ops);
    }
    return fp_finish(&f);
}

/* ============================ dlp: generic DLP ============================= */

static void rho_params(ca_rho_params *rp, uint64_t seed)
{
    ca_rho_params_default(rp);
    rp->seed = seed;
    rp->threads = 1;
}

/* --- Pollard rho, negation map, batched affine adds (36-bit curve) --- */
static void *setup_rho_ec36(void)
{
    dlp_fix *d = dlp_new("dlp/c_rho_ec36");
    ec_fixture(d->id, &EC36, 1, &d->g, &d->gen);
    make_targets(d, 4, 0x72686f36ULL, 0);
    return d;
}

static void *setup_rho_ec44(void)
{
    dlp_fix *d = dlp_new("dlp/c_rho_ec44");
    ec_fixture(d->id, &EC44, 1, &d->g, &d->gen);
    make_targets(d, 2, 0x72686f44ULL, 0);
    return d;
}

static uint64_t run_rho(void *p)
{
    const dlp_fix *d = p;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < d->nt; i++) {
        ca_rho_params rp;
        rho_params(&rp, 100 + i);
        ca_stats st = {0};
        uint64_t got = 0;
        ca_status rc = ca_rho_solve(&d->g, &d->gen, &d->h[i], &rp, &got, &st);
        fp_solve(&f, d, i, rc, got, &st);
    }
    return fp_finish(&f);
}

/* Multi-threaded rho: threads from RAYON_NUM_THREADS (the runner's
 * --threads).  Only the logarithms are fingerprinted: which walk collides
 * first, and so every counter, depends on the schedule. */
static void *setup_rho_ec44_mt(void)
{
    dlp_fix *d = dlp_new("dlp/c_rho_ec44_mt");
    ec_fixture(d->id, &EC44, 1, &d->g, &d->gen);
    make_targets(d, 4, 0x6d746877ULL, 0);
    return d;
}

static uint64_t run_rho_mt(void *p)
{
    const dlp_fix *d = p;
    const char *env = getenv("RAYON_NUM_THREADS");
    unsigned long want = env ? strtoul(env, NULL, 10) : 0;
    uint32_t threads = want > 0 && want <= 1024 ? (uint32_t)want : 1;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < d->nt; i++) {
        ca_rho_params rp;
        rho_params(&rp, 100 + i);
        rp.threads = threads;
        ca_stats st = {0};
        uint64_t got = 0;
        ca_status rc = ca_rho_solve(&d->g, &d->gen, &d->h[i], &rp, &got, &st);
        if (rc != CA_OK || got != d->x[i]) die(d->id, "wrong logarithm");
        fp_u64(&f, got);
    }
    return fp_finish(&f);
}

/* --- Pollard rho in Z_p^* (no negation map), safe prime p, q ~ 2^39 --- */
static void *setup_rho_zp40(void)
{
    dlp_fix *d = dlp_new("dlp/c_rho_zp40");
    uint64_t q, pp = safe_prime(40, &q);
    zp_fixture(d->id, pp, q, &d->g, &d->gen);
    make_targets(d, 3, 0x72686f7aULL, 0);
    return d;
}

/* --- kangaroo: interval of width 2^34 inside a large group --- */
static void *setup_kangaroo_ec56(void)
{
    dlp_fix *d = dlp_new("dlp/c_kangaroo_ec56_w34");
    ec_fixture(d->id, &EC56, 1, &d->g, &d->gen);
    make_targets(d, 4, 0x6b616e67ULL, 1ULL << 34);
    return d;
}

static void *setup_kangaroo_zp61(void)
{
    dlp_fix *d = dlp_new("dlp/c_kangaroo_zp61_w36");
    uint64_t q, pp = safe_prime(61, &q);
    zp_fixture(d->id, pp, q, &d->g, &d->gen);
    make_targets(d, 4, 0x6b7a7036ULL, 1ULL << 36);
    return d;
}

static uint64_t run_kangaroo(void *p)
{
    const dlp_fix *d = p;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < d->nt; i++) {
        ca_kangaroo_params kp;
        ca_kangaroo_params_default(&kp);
        kp.seed = 100 + i;
        ca_stats st = {0};
        uint64_t got = 0;
        ca_status rc =
            ca_kangaroo_solve(&d->g, &d->gen, &d->h[i], d->lo[i], d->hi[i], &kp, &got, &st);
        fp_solve(&f, d, i, rc, got, &st);
    }
    return fp_finish(&f);
}

/* --- baby-step giant-step over the whole group --- */
static void *setup_bsgs_ec32(void)
{
    dlp_fix *d = dlp_new("dlp/c_bsgs_ec32");
    ec_fixture(d->id, &EC32, 1, &d->g, &d->gen);
    make_targets(d, 2, 0x62736773ULL, 0);
    return d;
}

static void *setup_bsgs_zp36(void)
{
    dlp_fix *d = dlp_new("dlp/c_bsgs_zp36");
    uint64_t q, pp = safe_prime(36, &q);
    zp_fixture(d->id, pp, q, &d->g, &d->gen);
    make_targets(d, 3, 0x62737a70ULL, 0);
    return d;
}

static uint64_t run_bsgs(void *p)
{
    const dlp_fix *d = p;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < d->nt; i++) {
        ca_bsgs_params bp;
        ca_bsgs_params_default(&bp);
        ca_stats st = {0};
        uint64_t got = 0;
        ca_status rc = ca_bsgs_solve(&d->g, &d->gen, &d->h[i], 0, 0, &bp, &got, &st);
        fp_solve(&f, d, i, rc, got, &st);
    }
    return fp_finish(&f);
}

/* --- two grumpy giants and a baby --- */
static void *setup_grumpy_ec32(void)
{
    dlp_fix *d = dlp_new("dlp/c_grumpy_ec32");
    ec_fixture(d->id, &EC32, 1, &d->g, &d->gen);
    make_targets(d, 2, 0x6772756dULL, 0);
    return d;
}

static uint64_t run_grumpy(void *p)
{
    const dlp_fix *d = p;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < d->nt; i++) {
        ca_grumpy_params gp;
        ca_grumpy_params_default(&gp);
        ca_stats st = {0};
        uint64_t got = 0;
        ca_status rc = ca_grumpy_solve(&d->g, &d->gen, &d->h[i], 0, 0, &gp, &got, &st);
        fp_solve(&f, d, i, rc, got, &st);
    }
    return fp_finish(&f);
}

/* --- Pohlig-Hellman (auto solver: BSGS per prime) on smooth orders --- */
static void *setup_pohlig_ec48s(void)
{
    dlp_fix *d = dlp_new("dlp/c_pohlig_ec48s");
    ec_fixture(d->id, &EC48S, 0, &d->g, &d->gen);
    make_targets(d, 16, 0x706f6865ULL, 0);
    return d;
}

static void *setup_pohlig_zp61s(void)
{
    dlp_fix *d = dlp_new("dlp/c_pohlig_zp61s");
    /* p - 1 = 2^2 * 5 * 268436507 * 268536517 */
    const uint64_t pp = 1441700092508522381ULL;
    if (!ca_is_prime(pp)) die(d->id, "fixture modulus is not prime");
    zp_fixture(d->id, pp, pp - 1, &d->g, &d->gen);
    make_targets(d, 16, 0x706f687aULL, 0);
    return d;
}

static uint64_t run_pohlig(void *p)
{
    const dlp_fix *d = p;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < d->nt; i++) {
        ca_dlog_params dp;
        ca_dlog_params_default(&dp);
        ca_stats st = {0};
        uint64_t got = 0;
        ca_status rc = ca_pohlig_hellman(&d->g, &d->gen, &d->h[i], &dp, &got, &st);
        fp_solve(&f, d, i, rc, got, &st);
    }
    return fp_finish(&f);
}

/* --- Bernstein-Lange precomputation on a 32-bit curve --- */
static void precomp_params(ca_precomp_params *pp)
{
    ca_precomp_params_default(pp);
    pp->seed = 0x70726563ULL;
    pp->threads = 1;
}

static void *setup_precomp_build(void)
{
    dlp_fix *d = dlp_new("dlp/c_precomp_build_ec32");
    ec_fixture(d->id, &EC32, 1, &d->g, &d->gen);
    make_targets(d, 2, 0x62756c64ULL, 0);
    return d;
}

/* Table build (n^{2/3} walk steps, batched), then two online solves so the
 * table's content, not just its size, is covered by the fingerprint. */
static uint64_t run_precomp_build(void *p)
{
    const dlp_fix *d = p;
    ca_precomp_params pp;
    precomp_params(&pp);
    ca_stats bst = {0};
    ca_precomp_table *t = NULL;
    ca_status rc = ca_precomp_table_new(&d->g, &d->gen, &pp, &t, &bst);
    if (rc != CA_OK || !t) die(d->id, "table build failed");
    pb_fp f;
    fp_init(&f);
    fp_stats(&f, &bst);
    int32_t dpb = 0;
    uint64_t chains = 0, pops = 0;
    uint32_t r = 0;
    ca_precomp_table_info(t, &dpb, &chains, &r, &pops);
    fp_u64(&f, (uint64_t)(int64_t)dpb);
    fp_u64(&f, chains);
    fp_u64(&f, r);
    fp_u64(&f, pops);
    for (uint32_t i = 0; i < d->nt; i++) {
        ca_stats st = {0};
        uint64_t got = 0;
        ca_status sc = ca_precomp_table_solve(t, &d->h[i], &got, &st);
        fp_solve(&f, d, i, sc, got, &st);
    }
    ca_precomp_table_free(t);
    return fp_finish(&f);
}

static void *setup_precomp_online(void)
{
    dlp_fix *d = dlp_new("dlp/c_precomp_online_ec32");
    ec_fixture(d->id, &EC32, 1, &d->g, &d->gen);
    make_targets(d, 48, 0x6f6e6c6eULL, 0);
    ca_precomp_params pp;
    precomp_params(&pp);
    if (ca_precomp_table_new(&d->g, &d->gen, &pp, &d->tab, NULL) != CA_OK || !d->tab)
        die(d->id, "table build failed");
    return d;
}

static uint64_t run_precomp_online(void *p)
{
    const dlp_fix *d = p;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < d->nt; i++) {
        ca_stats st = {0};
        uint64_t got = 0;
        ca_status rc = ca_precomp_table_solve(d->tab, &d->h[i], &got, &st);
        fp_solve(&f, d, i, rc, got, &st);
    }
    return fp_finish(&f);
}

/* --- GLV endomorphism-accelerated rho (j = 0, order-6 automorphism) --- */
static void *setup_glv_j0(void)
{
    dlp_fix *d = dlp_new("dlp/c_glv_rho_j0_32");
    uint64_t p, a, b, order;
    if (ca_curve_by_name("glv-j0-32", &p, &a, &b, &order) != CA_OK) die(d->id, "no registry curve");
    ca_curve_info info;
    if (ca_curve_group(&d->g, p, a, b, order, &info) != CA_OK) die(d->id, "curve group failed");
    if (info.endo != CA_CURVE_ENDO_J0) die(d->id, "endomorphism not enabled");
    if (ca_group_find_generator(&d->g, &d->gen, 1) != CA_OK) die(d->id, "no generator");
    make_targets(d, 32, 0x676c7630ULL, 0);
    return d;
}

static uint64_t run_glv(void *p)
{
    const dlp_fix *d = p;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < d->nt; i++) {
        ca_stats st = {0};
        uint64_t got = 0;
        ca_curve_info info;
        ca_status rc = ca_curve_solve(&d->g, &d->gen, &d->h[i], 7 + i, &got, &info, &st);
        fp_solve(&f, d, i, rc, got, &st);
    }
    return fp_finish(&f);
}

/* --- GPU rho through the host emulator backend (CPU entry point) --- */
static void *setup_gpu_emulate(void)
{
    dlp_fix *d = dlp_new("dlp/c_gpu_rho_emulate_ec32");
    ec_fixture(d->id, &EC32, 1, &d->g, &d->gen);
    make_targets(d, 2, 0x67707565ULL, 0);
    return d;
}

static uint64_t run_gpu_emulate(void *p)
{
    const dlp_fix *d = p;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < d->nt; i++) {
        ca_gpu_rho_params gp;
        ca_gpu_rho_params_default(&gp);
        gp.backend = CA_GPU_BACKEND_EMULATE;
        gp.seed = 200 + i;
        ca_stats st = {0};
        uint64_t got = 0;
        ca_status rc = ca_gpu_rho_solve(&d->g, &d->gen, &d->h[i], &gp, &got, &st);
        fp_solve(&f, d, i, rc, got, &st);
        fp_u64(&f, st.reserved);
    }
    return fp_finish(&f);
}

/* --- Cheon's attack (d | p-1) in a Z_r^* subgroup of 56-bit prime order --- */
typedef struct cheon_fix {
    ca_group g;
    ca_elem gen, ga, gad;
    uint64_t d, alpha;
} cheon_fix;

static void *setup_cheon(void)
{
    const char *id = "dlp/c_cheon56";
    cheon_fix *s = calloc(1, sizeof(*s));
    if (!s) die(id, "out of memory");
    /* as tools/ca_bench.c run_cheon(56) */
    unsigned bits = 56;
    uint64_t half = 1ULL << (bits / 2), p = 0, r = 0;
    for (uint64_t k = half | 1; k < half * 4; k += 2)
        if (ca_is_prime(k * half + 1)) {
            p = k * half + 1;
            break;
        }
    for (uint64_t k = 1; p && k < 1000000; k++)
        if (ca_is_prime(2 * k * p + 1)) {
            r = 2 * k * p + 1;
            break;
        }
    if (!p || !r) die(id, "no instance");
    zp_fixture(id, r, p, &s->g, &s->gen);
    double cost;
    s->d = ca_cheon_best_divisor(p, &cost);
    s->alpha = 0x1234567 % (p - 1) + 1;
    if (ca_cheon_make_instance(&s->g, &s->gen, s->alpha, s->d, &s->ga, &s->gad) != CA_OK)
        die(id, "instance failed");
    return s;
}

static uint64_t run_cheon(void *p)
{
    const cheon_fix *s = p;
    ca_stats st = {0};
    uint64_t got = 0;
    ca_status rc = ca_cheon_solve(&s->g, &s->gen, &s->ga, &s->gad, s->d, NULL, &got, &st);
    if (rc != CA_OK || got != s->alpha) die("dlp/c_cheon56", "wrong answer");
    pb_fp f;
    fp_init(&f);
    fp_u64(&f, (uint64_t)rc);
    fp_u64(&f, got);
    fp_stats(&f, &st);
    return fp_finish(&f);
}

/* ================ relation: index calculus and relation algebra ============ */

typedef struct ic_fix {
    const char *id;
    uint64_t p, g;
    ca_ic_params pr;
    ca_ic_ctx *ctx; /* ic_log: rebuilt by prepare (ca_ic_log consumes its rng) */
    uint32_t nt;
    uint64_t x[64], h[64];
} ic_fix;

static ic_fix *ic_new(const char *id, unsigned bits, ca_ic_method method)
{
    ic_fix *s = calloc(1, sizeof(*s));
    if (!s) die(id, "out of memory");
    s->id = id;
    s->p = safe_prime(bits, NULL);
    s->g = ca_primitive_root(s->p);
    ca_ic_params_default(&s->pr);
    s->pr.method = method;
    s->pr.threads = 1;
    s->pr.seed = 1;
    return s;
}

static void ic_free(void *p)
{
    ic_fix *s = p;
    if (s->ctx) ca_ic_free(s->ctx);
    free(s);
}

static void *setup_ic_pre44(void)
{
    return ic_new("relation/c_ic_precompute_zp44", 44, CA_IC_LINEAR_SIEVE);
}
static void *setup_ic_pre52(void)
{
    return ic_new("relation/c_ic_precompute_zp52", 52, CA_IC_LINEAR_SIEVE);
}
static void *setup_ic_rexp(void)
{
    ic_fix *s = ic_new("relation/c_ic_randexp_zp36", 36, CA_IC_RANDOM_EXPONENT);
    return s;
}

/* Linear-sieve (or random-exponent) relation collection, the Lanczos solve
 * modulo the large prime of p-1, Pohlig-Hellman for the small part, and the
 * verification of every factor-base logarithm. */
static uint64_t run_ic_precompute(void *p)
{
    ic_fix *s = p;
    ca_ic_ctx *ctx = NULL;
    ca_ic_stats st;
    ca_status rc = ca_ic_precompute(s->p, s->g, &s->pr, &ctx, &st);
    if (rc != CA_OK || !ctx) die(s->id, "precompute failed");
    pb_fp f;
    fp_init(&f);
    fp_u64(&f, st.factor_base_size);
    fp_u64(&f, st.unknowns);
    fp_u64(&f, st.relations);
    fp_u64(&f, st.verified_logs);
    fp_u64(&f, st.sieve_candidates);
    fp_u64(&f, st.smooth_tests);
    fp_u64(&f, st.lanczos_iterations);
    uint32_t nfb = ca_ic_factor_base_size(ctx);
    for (uint32_t i = 0; i < nfb; i++) {
        uint32_t prime = 0;
        int known = 0;
        uint64_t lg = ca_ic_factor_base_log(ctx, i, &prime, &known);
        fp_u64(&f, prime);
        fp_u64(&f, (uint64_t)known);
        fp_u64(&f, lg);
    }
    ca_ic_free(ctx);
    return fp_finish(&f);
}

static void *setup_ic_log(void)
{
    ic_fix *s = ic_new("relation/c_ic_log_zp44", 44, CA_IC_LINEAR_SIEVE);
    ca_rng rng = {{0}};
    ca_rng_seed(&rng, 0x69636c67ULL);
    s->nt = 48;
    for (uint32_t i = 0; i < s->nt; i++) {
        s->x[i] = 1 + ca_rng_below(&rng, s->p - 2);
        s->h[i] = ca_powmod(s->g, s->x[i], s->p);
    }
    return s;
}

static void prepare_ic_log(void *p)
{
    ic_fix *s = p;
    if (s->ctx) ca_ic_free(s->ctx);
    s->ctx = NULL;
    if (ca_ic_precompute(s->p, s->g, &s->pr, &s->ctx, NULL) != CA_OK || !s->ctx)
        die(s->id, "precompute failed");
}

/* Individual logarithms: h * g^e smooth over the verified factor base. */
static uint64_t run_ic_log(void *p)
{
    ic_fix *s = p;
    pb_fp f;
    fp_init(&f);
    for (uint32_t i = 0; i < s->nt; i++) {
        ca_stats st = {0};
        uint64_t got = 0;
        ca_status rc = ca_ic_log(s->ctx, s->h[i], &got, &st);
        if (rc != CA_OK || got != s->x[i]) die(s->id, "wrong logarithm");
        fp_u64(&f, got);
        fp_u64(&f, st.iterations);
    }
    return fp_finish(&f);
}

/* --- sparse relation matrix mod a 61-bit prime: singleton removal + Lanczos --- */
typedef struct ls_fix {
    const char *id;
    ca_spmat A;
    uint64_t *b, *x;
    uint8_t *known;
    uint64_t q;
    uint32_t cols;
    /* dense */
    uint32_t n;
    uint64_t *M0, *rhs0, *M, *rhs, *xd;
} ls_fix;

static void *setup_linsolve(void)
{
    const char *id = "relation/c_linsolve_sparse";
    ls_fix *s = calloc(1, sizeof(*s));
    if (!s) die(id, "out of memory");
    s->id = id;
    s->q = safe_prime(61, NULL);
    /* index-calculus shaped: column weights skewed towards small primes,
     * 2-14 entries per row with small coefficients, 12% more rows than
     * columns; right-hand side from a planted solution. */
    uint32_t C = 700, R = 784;
    s->cols = C;
    ca_rng rng = {{0}};
    ca_rng_seed(&rng, 0x6c696e73ULL);
    uint64_t *x0 = malloc(C * sizeof(uint64_t));
    if (!x0 || ca_spmat_init(&s->A, C, R, R * 16) != CA_OK) die(id, "out of memory");
    for (uint32_t j = 0; j < C; j++) x0[j] = ca_rng_below(&rng, s->q);
    s->b = calloc(R, sizeof(uint64_t));
    s->x = calloc(C, sizeof(uint64_t));
    s->known = calloc(C, 1);
    if (!s->b || !s->x || !s->known) die(id, "out of memory");
    for (uint32_t i = 0; i < R; i++) {
        uint32_t cols[16];
        int32_t vals[16];
        uint32_t k = 2 + (uint32_t)ca_rng_below(&rng, 13);
        for (uint32_t t = 0; t < k; t++) {
            /* square a uniform draw: small columns are denser */
            uint64_t u = ca_rng_below(&rng, C);
            cols[t] = (uint32_t)((u * u) / C);
            vals[t] = (int32_t)ca_rng_below(&rng, 7) - 3;
            if (vals[t] == 0) vals[t] = 1;
        }
        if (ca_spmat_add_row(&s->A, cols, vals, k) != CA_OK) die(id, "out of memory");
    }
    for (uint32_t i = 0; i < R; i++) {
        uint64_t acc = 0;
        for (uint32_t k = s->A.row_ptr[i]; k < s->A.row_ptr[i + 1]; k++) {
            int32_t v = s->A.val[k];
            uint64_t c = v >= 0 ? (uint64_t)v : s->q - (uint64_t)(-v);
            acc = ca_addmod(acc, ca_mulmod(c, x0[s->A.col[k]], s->q), s->q);
        }
        s->b[i] = acc;
    }
    free(x0);
    return s;
}

static void free_linsolve(void *p)
{
    ls_fix *s = p;
    ca_spmat_free(&s->A);
    free(s->b);
    free(s->x);
    free(s->known);
    free(s->M0);
    free(s->rhs0);
    free(s->M);
    free(s->rhs);
    free(s->xd);
    free(s);
}

static uint64_t run_linsolve(void *p)
{
    ls_fix *s = p;
    ca_linsolve_report rep;
    ca_status rc = ca_linsolve_mod_prime(&s->A, s->b, s->q, s->x, s->known, 0x5eedULL, &rep);
    pb_fp f;
    fp_init(&f);
    fp_u64(&f, (uint64_t)rc);
    fp_u64(&f, rep.active_rows);
    fp_u64(&f, rep.active_cols);
    fp_u64(&f, rep.lanczos_iters);
    fp_u64(&f, rep.attempts);
    fp_u64(&f, (uint64_t)rep.used_dense);
    fp_words(&f, s->x, s->cols);
    fp_bytes(&f, s->known, s->cols);
    return fp_finish(&f);
}

/* --- dense Gauss-Jordan mod a 61-bit prime (the small-system fallback) --- */
static void *setup_dense(void)
{
    const char *id = "relation/c_dense_solve";
    ls_fix *s = calloc(1, sizeof(*s));
    if (!s) die(id, "out of memory");
    s->id = id;
    s->q = safe_prime(61, NULL);
    s->n = 150;
    size_t nn = (size_t)s->n * s->n;
    s->M0 = malloc(nn * sizeof(uint64_t));
    s->M = malloc(nn * sizeof(uint64_t));
    s->rhs0 = malloc(s->n * sizeof(uint64_t));
    s->rhs = malloc(s->n * sizeof(uint64_t));
    s->xd = malloc(s->n * sizeof(uint64_t));
    if (!s->M0 || !s->M || !s->rhs0 || !s->rhs || !s->xd) die(id, "out of memory");
    ca_rng rng = {{0}};
    ca_rng_seed(&rng, 0x64656e73ULL);
    for (size_t i = 0; i < nn; i++) s->M0[i] = ca_rng_below(&rng, s->q);
    for (uint32_t i = 0; i < s->n; i++) s->rhs0[i] = ca_rng_below(&rng, s->q);
    return s;
}

static void prepare_dense(void *p)
{
    ls_fix *s = p;
    memcpy(s->M, s->M0, (size_t)s->n * s->n * sizeof(uint64_t));
    memcpy(s->rhs, s->rhs0, s->n * sizeof(uint64_t));
}

static uint64_t run_dense(void *p)
{
    ls_fix *s = p;
    ca_status rc = ca_dense_solve_mod_prime(s->M, s->n, s->rhs, s->q, s->xd);
    pb_fp f;
    fp_init(&f);
    fp_u64(&f, (uint64_t)rc);
    fp_words(&f, s->xd, s->n);
    return fp_finish(&f);
}

/* ---- the registry --------------------------------------------------------- */

static const pb_kernel KERNELS[] = {
    {"field_ec/c_mont_mul_x8", "field_ec",
     "2^24 Montgomery multiplications (header ca_mont_mul), 8 independent chains, 61-bit prime", 0,
     setup_mont_mul_x8, NULL, run_mont_mul_x8, NULL},
    {"field_ec/c_zp_op_chain", "field_ec",
     "4M dependent Z_p^* group ops + 1M squarings through the vtable, 61-bit safe prime", 0,
     setup_zp_op_chain, NULL, run_zp_op_chain, NULL},
    {"field_ec/c_powmod", "field_ec",
     "4 x 8192 ca_powmod (64-bit exponents) over 61/62/41/64-bit moduli", 0, setup_modarith, NULL,
     run_powmod, NULL},
    {"field_ec/c_mont_pow", "field_ec",
     "4 x 8192 ca_mont_pow (64-bit exponents) over 61/62/41/64-bit moduli", 0, setup_modarith, NULL,
     run_mont_pow, NULL},
    {"field_ec/c_invmod", "field_ec",
     "4 x 32768 ca_invmod + 4 x 8192 ca_mont_inv over 61/62/41/64-bit moduli", 0, setup_modarith,
     NULL, run_invmod, NULL},
    {"field_ec/c_sqrtmod", "field_ec",
     "3 x 4096 ca_sqrtmod_prime: p = 3 mod 4 (60-bit), p = 1 mod 2^20 (61-bit), 61-bit safe prime",
     0, setup_sqrtmod, NULL, run_sqrtmod, NULL},
    {"field_ec/c_is_prime", "field_ec",
     "ca_is_prime over 30000 integers near 2^62 and 2^40, then 200 ca_next_prime near 2^50", 0,
     setup_nothing, NULL, run_is_prime, NULL},
    {"field_ec/c_factorize", "field_ec",
     "ca_factorize of 64 semiprimes (26x30-bit) and 128 random 62-bit integers; 16 primitive roots",
     0, setup_factorize, NULL, run_factorize, NULL},
    {"field_ec/c_ec_add_chain", "field_ec",
     "60000 affine EC adds + 30000 doublings (one inversion each), 60-bit prime-order curve", 0,
     setup_ec_add_chain, NULL, run_ec_add_chain, NULL},
    {"field_ec/c_ec_batch_add", "field_ec",
     "6000 x ca_group_batch_op of 256 affine adds (simultaneous inversion), 60-bit curve", 0,
     setup_ec_batch_add, NULL, run_ec_batch_add, NULL},
    {"field_ec/c_ec_scalar_mul", "field_ec",
     "1024 ca_group_mul with 60-bit scalars (affine double-and-add), 60-bit curve", 0,
     setup_ec_scalar_mul, NULL, run_ec_scalar_mul, NULL},
    {"field_ec/c_ec_count_points", "field_ec",
     "ca_ec_count_points (Mestre BSGS) on four 56-bit curves", 0, setup_nothing, NULL,
     run_ec_count_points, NULL},

    {"dlp/c_rho_ec36", "dlp",
     "Pollard rho, negation map, 4 targets on a 36-bit prime-order curve, 1 thread", 0,
     setup_rho_ec36, NULL, run_rho, dlp_free},
    {"dlp/c_rho_ec44", "dlp",
     "Pollard rho, negation map, 2 targets on a 44-bit prime-order curve, 1 thread", 1,
     setup_rho_ec44, NULL, run_rho, dlp_free},
    {"dlp/c_rho_ec44_mt", "dlp",
     "Pollard rho on a 44-bit curve, RAYON_NUM_THREADS threads, 4 targets (fingerprint: logs only)",
     1, setup_rho_ec44_mt, NULL, run_rho_mt, dlp_free},
    {"dlp/c_rho_zp40", "dlp", "Pollard rho in Z_p^*, 3 targets, safe prime p (40-bit), 1 thread", 0,
     setup_rho_zp40, NULL, run_rho, dlp_free},
    {"dlp/c_kangaroo_ec56_w34", "dlp",
     "kangaroo, 4 interval targets of width 2^34 on a 56-bit prime-order curve", 0,
     setup_kangaroo_ec56, NULL, run_kangaroo, dlp_free},
    {"dlp/c_kangaroo_zp61_w36", "dlp",
     "kangaroo, 4 interval targets of width 2^36 in Z_p^* (61-bit safe prime)", 0,
     setup_kangaroo_zp61, NULL, run_kangaroo, dlp_free},
    {"dlp/c_bsgs_ec32", "dlp", "BSGS over the whole group, 2 targets, 32-bit prime-order curve", 0,
     setup_bsgs_ec32, NULL, run_bsgs, dlp_free},
    {"dlp/c_bsgs_zp36", "dlp", "BSGS over the whole group, 3 targets, Z_p^* safe prime (36-bit)", 0,
     setup_bsgs_zp36, NULL, run_bsgs, dlp_free},
    {"dlp/c_grumpy_ec32", "dlp", "two grumpy giants and a baby, 2 targets, 32-bit curve", 0,
     setup_grumpy_ec32, NULL, run_grumpy, dlp_free},
    {"dlp/c_pohlig_ec48s", "dlp",
     "Pohlig-Hellman + BSGS, 16 targets, 48-bit curve of order 2^2*31*100493*11294117", 0,
     setup_pohlig_ec48s, NULL, run_pohlig, dlp_free},
    {"dlp/c_pohlig_zp61s", "dlp",
     "Pohlig-Hellman + BSGS, 16 targets, Z_p^* with p-1 = 2^2*5*268436507*268536517", 0,
     setup_pohlig_zp61s, NULL, run_pohlig, dlp_free},
    {"dlp/c_precomp_build_ec32", "dlp",
     "Bernstein-Lange table build (1 thread) on a 32-bit curve + 2 online solves", 0,
     setup_precomp_build, NULL, run_precomp_build, dlp_free},
    {"dlp/c_precomp_online_ec32", "dlp",
     "48 online solves against a prebuilt Bernstein-Lange table, 32-bit curve", 0,
     setup_precomp_online, NULL, run_precomp_online, dlp_free},
    {"dlp/c_glv_rho_j0_32", "dlp",
     "ca_curve_solve (GLV order-6 folded rho) on glv-j0-32, 32 targets", 0, setup_glv_j0, NULL,
     run_glv, dlp_free},
    {"dlp/c_gpu_rho_emulate_ec32", "dlp",
     "GPU rho kernel through the host emulator backend, 2 targets, 32-bit curve", 0,
     setup_gpu_emulate, NULL, run_gpu_emulate, dlp_free},
    {"dlp/c_cheon56", "dlp", "Cheon's attack (d | p-1), 56-bit prime-order subgroup of Z_r^*", 0,
     setup_cheon, NULL, run_cheon, NULL},

    {"relation/c_ic_precompute_zp44", "relation",
     "index calculus precompute in Z_p^* (44-bit safe prime): linear sieve + Lanczos, 1 thread", 0,
     setup_ic_pre44, NULL, run_ic_precompute, ic_free},
    {"relation/c_ic_precompute_zp52", "relation",
     "index calculus precompute in Z_p^* (52-bit safe prime): linear sieve + Lanczos, 1 thread", 1,
     setup_ic_pre52, NULL, run_ic_precompute, ic_free},
    {"relation/c_ic_randexp_zp36", "relation",
     "index calculus precompute, random-exponent collector, 36-bit safe prime, 1 thread", 0,
     setup_ic_rexp, NULL, run_ic_precompute, ic_free},
    {"relation/c_ic_log_zp44", "relation",
     "48 individual logs against a fresh index-calculus context (44-bit safe prime)", 0,
     setup_ic_log, prepare_ic_log, run_ic_log, ic_free},
    {"relation/c_linsolve_sparse", "relation",
     "ca_linsolve_mod_prime: 784x700 IC-shaped sparse system mod a 61-bit prime (SGE + Lanczos)", 0,
     setup_linsolve, NULL, run_linsolve, free_linsolve},
    {"relation/c_dense_solve", "relation",
     "ca_dense_solve_mod_prime: 150x150 dense Gauss-Jordan mod a 61-bit prime", 0, setup_dense,
     prepare_dense, run_dense, free_linsolve},
};

#define NKERNELS (sizeof(KERNELS) / sizeof(KERNELS[0]))

/* ---- harness ------------------------------------------------------------- */

/* The region `perfindex.py instr` restricts callgrind to
 * (--toggle-collect=*perfbench_measured_region*).  Not static and not
 * inlinable, so the symbol exists under exactly this name. */
#if defined(__clang__)
#    define PB_NOINLINE __attribute__((noinline))
#else
#    define PB_NOINLINE __attribute__((noinline, noclone))
#endif
uint64_t perfbench_measured_region(const pb_kernel *k, void *state);
PB_NOINLINE uint64_t perfbench_measured_region(const pb_kernel *k, void *state)
{
    uint64_t fp = k->run(state);
    __asm__ volatile("" : : "r"(fp) : "memory");
    return fp;
}

static uint64_t now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

typedef struct options {
    const char *filters[256];
    int nfilters;
    int exact, full, instr;
    unsigned samples, min_samples;
    double max_seconds, warmup_seconds;
} options;

static char filter_buf[8192];
static size_t filter_used;

static void usage(void)
{
    fputs("ca_perfbench - fixed-input kernels for the performance index (C library)\n\n"
          "USAGE:\n"
          "  ca_perfbench list [--full]\n"
          "  ca_perfbench run  [--filter A,B] [--exact] [--full] [--samples N] [--min-samples N]\n"
          "                    [--max-seconds S] [--warmup-seconds S] [--instr]\n\n"
          "Compare builds with scripts/perf/perfindex.py (build --c).\n",
          stderr);
    exit(2);
}

static void add_filters(options *o, const char *arg)
{
    size_t len = strlen(arg);
    if (filter_used + len + 1 > sizeof filter_buf) usage();
    char *s = filter_buf + filter_used;
    memcpy(s, arg, len + 1);
    filter_used += len + 1;
    for (char *tok = strtok(s, ","); tok; tok = strtok(NULL, ",")) {
        if (o->nfilters >= 256) usage();
        o->filters[o->nfilters++] = tok;
    }
}

static void parse_options(options *o, int argc, char **argv)
{
    memset(o, 0, sizeof(*o));
    o->samples = 11;
    o->min_samples = 3;
    o->max_seconds = 3.0;
    o->warmup_seconds = 0.2;
    for (int i = 0; i < argc; i++) {
        const char *a = argv[i];
        const char *v = i + 1 < argc ? argv[i + 1] : NULL;
        if (!a) break;
        if (!strcmp(a, "--filter") && v) {
            add_filters(o, v);
            i++;
        } else if (!strcmp(a, "--exact"))
            o->exact = 1;
        else if (!strcmp(a, "--full"))
            o->full = 1;
        else if (!strcmp(a, "--instr"))
            o->instr = 1;
        else if (!strcmp(a, "--samples") && v) {
            o->samples = (unsigned)strtoul(v, NULL, 10);
            i++;
        } else if (!strcmp(a, "--min-samples") && v) {
            o->min_samples = (unsigned)strtoul(v, NULL, 10);
            i++;
        } else if (!strcmp(a, "--max-seconds") && v) {
            o->max_seconds = strtod(v, NULL);
            i++;
        } else if (!strcmp(a, "--warmup-seconds") && v) {
            o->warmup_seconds = strtod(v, NULL);
            i++;
        } else {
            fprintf(stderr, "unknown option %s\n", a);
            usage();
        }
    }
    if (o->samples == 0) o->samples = 1;
}

static int selected(const pb_kernel *k, const options *o)
{
    if (!(o->full || !k->full || o->nfilters > 0)) return 0;
    if (o->nfilters == 0) return 1;
    for (int i = 0; i < o->nfilters; i++) {
        if (o->exact ? !strcmp(k->id, o->filters[i]) : strstr(k->id, o->filters[i]) != NULL)
            return 1;
    }
    return 0;
}

static void json_str(const char *s)
{
    putchar('"');
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"')
            fputs("\\\"", stdout);
        else if (c == '\\')
            fputs("\\\\", stdout);
        else if (c == '\n')
            fputs("\\n", stdout);
        else if (c < 0x20)
            printf("\\u%04x", c);
        else
            putchar(c);
    }
    putchar('"');
}

static int cmp_u64(const void *a, const void *b)
{
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return x < y ? -1 : x > y;
}

static void check_fp(const pb_kernel *k, uint64_t want, uint64_t got)
{
    if (want != got) {
        fprintf(stderr,
                "ca_perfbench: %s: fingerprint changed between runs (%016" PRIx64 " vs %016" PRIx64
                ")\n",
                k->id, want, got);
        exit(4);
    }
}

static void measure(const pb_kernel *k, const options *o)
{
    uint64_t t0 = now_ns();
    void *st = k->setup();
    uint64_t setup_ns = now_ns() - t0;

    if (o->instr) {
        /* one warm run outside the region, one measured run inside it */
        if (k->prepare) k->prepare(st);
        uint64_t fp0 = k->run(st);
        if (k->prepare) k->prepare(st);
        uint64_t fp = perfbench_measured_region(k, st);
        check_fp(k, fp0, fp);
        printf("{\"id\":");
        json_str(k->id);
        printf(",\"area\":");
        json_str(k->area);
        printf(",\"fingerprint\":\"%016" PRIx64 "\",\"setup_ns\":%" PRIu64 "}\n", fp, setup_ns);
        fflush(stdout);
    } else {
        /* warm-up: at least one run, until warmup_seconds has passed */
        uint64_t warm0 = now_ns();
        if (k->prepare) k->prepare(st);
        uint64_t fp = k->run(st);
        while ((double)(now_ns() - warm0) * 1e-9 < o->warmup_seconds) {
            if (k->prepare) k->prepare(st);
            check_fp(k, fp, k->run(st));
        }
        uint64_t *samples = malloc((size_t)o->samples * sizeof(uint64_t));
        if (!samples) die(k->id, "out of memory");
        unsigned ns = 0;
        uint64_t start = now_ns();
        while (ns < o->samples &&
               (ns < o->min_samples || (double)(now_ns() - start) * 1e-9 < o->max_seconds)) {
            if (k->prepare) k->prepare(st);
            uint64_t s0 = now_ns();
            uint64_t got = k->run(st);
            uint64_t dt = now_ns() - s0;
            check_fp(k, fp, got);
            samples[ns++] = dt;
        }
        uint64_t *sorted = malloc((size_t)ns * sizeof(uint64_t));
        if (!sorted) die(k->id, "out of memory");
        memcpy(sorted, samples, (size_t)ns * sizeof(uint64_t));
        qsort(sorted, ns, sizeof(uint64_t), cmp_u64);
        uint64_t med = ns % 2 ? sorted[ns / 2] : (sorted[ns / 2 - 1] + sorted[ns / 2]) / 2;
        printf("{\"id\":");
        json_str(k->id);
        printf(",\"area\":");
        json_str(k->area);
        printf(",\"fingerprint\":\"%016" PRIx64 "\",\"setup_ns\":%" PRIu64 ",\"median_ns\":%" PRIu64
               ",\"min_ns\":%" PRIu64 ",\"samples_ns\":[",
               fp, setup_ns, med, sorted[0]);
        for (unsigned i = 0; i < ns; i++) printf("%s%" PRIu64, i ? "," : "", samples[i]);
        printf("]}\n");
        fflush(stdout);
        free(samples);
        free(sorted);
    }
    if (k->teardown)
        k->teardown(st);
    else
        free(st);
}

static void check_registry(void)
{
    for (size_t i = 0; i < NKERNELS; i++) {
        const pb_kernel *k = &KERNELS[i];
        size_t al = strlen(k->area);
        if (strncmp(k->id, k->area, al) != 0 || k->id[al] != '/') {
            fprintf(stderr, "kernel id %s must start with its area %s/\n", k->id, k->area);
            exit(5);
        }
        for (size_t j = 0; j < i; j++) {
            if (!strcmp(KERNELS[j].id, k->id)) {
                fprintf(stderr, "duplicate kernel id %s\n", k->id);
                exit(5);
            }
        }
    }
}

int main(int argc, char **argv)
{
    check_registry();
    if (argc < 2) usage();
    options o;
    parse_options(&o, argc - 2, argv + 2);
    if (!strcmp(argv[1], "list")) {
        for (size_t i = 0; i < NKERNELS; i++) {
            const pb_kernel *k = &KERNELS[i];
            if (!selected(k, &o)) continue;
            printf("{\"id\":");
            json_str(k->id);
            printf(",\"area\":");
            json_str(k->area);
            printf(",\"tier\":\"%s\",\"desc\":", k->full ? "Full" : "Quick");
            json_str(k->desc);
            printf("}\n");
        }
        return 0;
    }
    if (!strcmp(argv[1], "run")) {
        int any = 0;
        for (size_t i = 0; i < NKERNELS; i++) {
            if (!selected(&KERNELS[i], &o)) continue;
            any = 1;
            measure(&KERNELS[i], &o);
        }
        if (!any) {
            fprintf(stderr, "no kernel matches\n");
            return 2;
        }
        return 0;
    }
    usage();
    return 2;
}
