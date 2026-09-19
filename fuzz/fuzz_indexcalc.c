/*
 * fuzz_indexcalc.c - libFuzzer harness for index calculus in (Z/pZ)^*
 * (ca_indexcalc.h: ca_ic_auto_params, ca_ic_precompute, ca_ic_log,
 * ca_ic_solve and the introspection accessors).
 *
 * p is kept to at most 20 bits and forced to an odd prime with ca_is_prime
 * / ca_next_prime, because the header documents "p must be an odd prime"
 * and everything else is a documented rejection.  The factor-base bound B
 * and the sieve radius C are fuzzed but capped: they size a sieve array and
 * the relation matrix, and an uncapped B would just allocate.
 *
 * Contracts asserted:
 *   CA_OK from ca_ic_log / ca_ic_solve => g^x == h (mod p)
 *   every verified factor-base log really is a log: g_zeta^log == prime
 *   ca_ic_modulus / ca_ic_primitive_root agree with the inputs
 *   a non-prime or out-of-range modulus is rejected, not crashed on
 */
#include "cryptanalysis/cryptanalysis.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define CHK(cond)                                                                                  \
    do {                                                                                           \
        if (!(cond)) __builtin_trap();                                                             \
    } while (0)

typedef struct {
    const uint8_t *d;
    size_t n, i;
} fz;

static uint8_t fz_u8(fz *f) { return f->i < f->n ? f->d[f->i++] : 0; }
static uint32_t fz_u32(fz *f)
{
    uint32_t v = 0;
    for (int k = 0; k < 4; k++) v |= (uint32_t)fz_u8(f) << (8 * k);
    return v;
}
static uint64_t fz_u64(fz *f)
{
    uint64_t v = 0;
    for (int k = 0; k < 8; k++) v |= (uint64_t)fz_u8(f) << (8 * k);
    return v;
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    if (size < 24) return 0;
    fz f = {data, size, 0};

    uint8_t flags = fz_u8(&f);
    uint8_t bits = 5 + (uint8_t)(fz_u8(&f) % 16); /* 5 .. 20 bit modulus */
    uint64_t praw = fz_u64(&f) & ((1ULL << bits) - 1);
    uint64_t gg = fz_u64(&f);
    uint64_t hh = fz_u64(&f);

    ca_ic_params pr;
    ca_ic_params_default(&pr);
    pr.method = (flags & 1) ? CA_IC_RANDOM_EXPONENT : CA_IC_LINEAR_SIEVE;
    /* Capped: B sizes the factor base (and a sieve of B bytes), C sizes the
     * relation matrix at 2C+1 extra unknowns and the sieve at 2C+1 bytes. */
    /* B is floored at 128: individual logarithms retry up to 50M times
     * before giving up, so a factor base too small to be hit would turn one
     * input into a multi-second run. */
    pr.factor_base_bound = (flags & 4) ? 0 : (128 + (fz_u32(&f) & 0x1FF));
    pr.sieve_radius = fz_u32(&f) & 0xFF; /* 0 => auto */
    pr.threads = 1 + ((flags >> 6) & 1); /* 1 or 2 */
    pr.extra_relations = fz_u32(&f) & 0x3F;
    pr.seed = fz_u64(&f) | 1;
    /* The random-exponent collector is otherwise unbounded. */
    pr.max_relation_tries = 1 + (fz_u64(&f) & 0xFFFFu);
    pr.verbose = 0;

    /* ca_ic_auto_params is total over every bit length. */
    {
        uint32_t B = 0, C = 0;
        ca_ic_auto_params((unsigned)(fz_u8(&f)), &B, &C);
        CHK(B > 0 && C > 0);
    }

    /* Documented rejections must be rejections, not crashes. */
    {
        uint64_t x;
        ca_ic_ctx *bad = NULL;
        if (!ca_is_prime(praw) || praw < 7) {
            CHK(ca_ic_precompute(praw, gg, &pr, &bad, NULL) != CA_OK);
            CHK(ca_ic_solve(praw, gg, hh, &pr, &x, NULL) != CA_OK);
        }
    }

    uint64_t p = ca_next_prime(6 + praw);
    if (p < 7) return 0;

    uint64_t g = gg % p;
    if (g == 0) g = 1;

    ca_ic_ctx *ctx = NULL;
    ca_ic_stats st;
    memset(&st, 0, sizeof(st));
    ca_status rc = ca_ic_precompute(p, g, &pr, &ctx, &st);
    if (rc != CA_OK) {
        CHK(ctx == NULL); /* no context handed back on failure => no leak */
        return 0;
    }
    CHK(ctx != NULL);

    CHK(ca_ic_modulus(ctx) == p);
    uint64_t zeta = ca_ic_primitive_root(ctx);
    CHK(zeta == ca_primitive_root(p));
    uint32_t nfb = ca_ic_factor_base_size(ctx);
    CHK(nfb == st.factor_base_size);
    CHK(st.verified_logs <= nfb);
    CHK(st.unknowns >= nfb);
    for (uint32_t i = 0; i < nfb; i++) {
        uint32_t prime = 0;
        int known = 0;
        uint64_t lg = ca_ic_factor_base_log(ctx, i, &prime, &known);
        CHK(ca_is_prime(prime));
        /* "Every factor-base logarithm is verified before use" */
        if (known)
            CHK(ca_powmod(zeta, lg, p) == prime % p);
        else
            CHK(lg == 0);
    }
    /* out-of-range index must not read past the array */
    {
        uint32_t prime = 0xdeadbeefu;
        int known = 1;
        (void)ca_ic_factor_base_log(ctx, nfb + (fz_u32(&f) & 0xFF), &prime, &known);
    }

    /* Individual logarithms: whatever comes back must satisfy g^x == h.
     * Only attempted on a fully verified factor base; with a partial one
     * the retry loop can run for a very long time before returning. */
    for (int t = 0; t < 2 && st.verified_logs == nfb; t++) {
        uint64_t h = (t == 0 ? hh : ca_powmod(g, hh, p)) % p;
        uint64_t x = ~0ULL;
        ca_stats s2;
        memset(&s2, 0, sizeof(s2));
        ca_status lrc = ca_ic_log(ctx, h, &x, &s2);
        if (lrc == CA_OK) {
            CHK(h != 0);
            CHK(ca_powmod(g, x, p) == h);
            CHK(x < p - 1);
        } else if (h != 0 && t == 1) {
            /* h = g^e is in <g> by construction, so the only legitimate
             * failures are resource limits, never NOT_FOUND. */
            CHK(lrc != CA_ERR_NOT_FOUND);
        }
    }
    ca_ic_free(ctx);

    /* One-shot wrapper on the same instance. */
    if ((flags & 2) && st.verified_logs == nfb) {
        uint64_t x = ~0ULL;
        uint64_t h = ca_powmod(g, hh, p);
        ca_ic_stats s3;
        memset(&s3, 0, sizeof(s3));
        if (ca_ic_solve(p, g, h, &pr, &x, &s3) == CA_OK) CHK(ca_powmod(g, x, p) == h);
    }
    ca_ic_free(NULL); /* documented no-op */
    return 0;
}
