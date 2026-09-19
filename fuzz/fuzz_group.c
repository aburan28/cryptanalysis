/*
 * fuzz_group.c - libFuzzer harness for the abstract group layer
 * (ca_group.h, src/group_zp.c, src/group_ec.c).
 *
 * A group of either kind is built from fuzzed parameters, then the element
 * API is driven with fuzzed words and the algebraic invariants that must
 * hold for every input the API *accepts* are asserted:
 *
 *   accepted element  => ca_group_is_valid
 *   encode/decode     => round-trips
 *   op(a, inv(a))     == identity
 *   dbl(a)            == op(a, a)
 *   mul(a, k1 + k2)   == op(mul(a,k1), mul(a,k2))
 *   batch_op          == the one-at-a-time results
 *   equal elements    => equal hashes
 *   canonicalize      is idempotent and identifies a with -a
 *   elem_order o      => o | group order and o*a == identity
 *
 * Moduli are masked to at most 24 bits so that one input costs microseconds.
 */
#include "cryptanalysis/cryptanalysis.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define CHK(cond)                                                                                  \
    do {                                                                                           \
        if (!(cond)) __builtin_trap();                                                             \
    } while (0)

#define MAX_BATCH 8

typedef struct {
    const uint8_t *d;
    size_t n, i;
} fz;

static uint8_t fz_u8(fz *f) { return f->i < f->n ? f->d[f->i++] : 0; }
static uint64_t fz_u64(fz *f)
{
    uint64_t v = 0;
    for (int k = 0; k < 8; k++) v |= (uint64_t)fz_u8(f) << (8 * k);
    return v;
}

/* Encode `w` if the group accepts it, else fall back to a known-good
 * element (the identity), so that later stages always have something to
 * work with.  Returns 1 when the fuzzed words were accepted. */
static int elem_from_words(const ca_group *g, ca_elem *e, const uint64_t w[4])
{
    if (ca_group_encode(g, e, w)) {
        /* Anything encode accepts must pass the membership test, and must
         * survive a decode/encode round trip unchanged. */
        CHK(ca_group_is_valid(g, e));
        uint64_t back[4];
        ca_elem again;
        ca_group_decode(g, back, e);
        CHK(ca_group_encode(g, &again, back));
        CHK(ca_group_equal(g, e, &again));
        CHK(ca_group_hash(g, e) == ca_group_hash(g, &again));
        return 1;
    }
    ca_group_identity(g, e);
    return 0;
}

/* The full invariant battery for one element. */
static void check_elem(const ca_group *g, const ca_elem *a)
{
    ca_elem id, t, u, v;
    ca_group_identity(g, &id);
    CHK(ca_group_is_valid(g, &id));
    CHK(ca_group_is_identity(g, &id));

    CHK(ca_group_is_valid(g, a));

    /* a + 0 == a */
    ca_group_op(g, &t, a, &id);
    CHK(ca_group_equal(g, &t, a));

    /* a + (-a) == 0 */
    ca_group_inv(g, &u, a);
    CHK(ca_group_is_valid(g, &u));
    ca_group_op(g, &t, a, &u);
    CHK(ca_group_is_identity(g, &t));
    /* -(-a) == a */
    ca_group_inv(g, &v, &u);
    CHK(ca_group_equal(g, &v, a));

    /* 2a == a + a */
    ca_group_dbl(g, &t, a);
    ca_group_op(g, &u, a, a);
    CHK(ca_group_equal(g, &t, &u));
    CHK(ca_group_is_valid(g, &t));

    /* equal elements hash equal */
    CHK(ca_group_hash(g, &t) == ca_group_hash(g, &u));

    /* scalar multiplication */
    ca_group_mul(g, &t, a, 0, NULL);
    CHK(ca_group_is_identity(g, &t));
    ca_group_mul(g, &t, a, 1, NULL);
    CHK(ca_group_equal(g, &t, a));
    ca_group_mul(g, &t, a, 2, NULL);
    ca_group_dbl(g, &u, a);
    CHK(ca_group_equal(g, &t, &u));

    /* a/a == 0 and (a/b)*b == a for b = 2a */
    ca_group_div(g, &t, a, a);
    CHK(ca_group_is_identity(g, &t));
    ca_group_dbl(g, &u, a);
    ca_group_div(g, &t, a, &u);
    ca_group_op(g, &t, &t, &u);
    CHK(ca_group_equal(g, &t, a));

    /* canonicalize: idempotent, validity preserving, identifies a and -a */
    if (ca_group_has_negation_map(g)) {
        ca_elem ca = *a, cb;
        ca_group_canonicalize(g, &ca);
        CHK(ca_group_is_valid(g, &ca));
        cb = ca;
        CHK(ca_group_canonicalize(g, &cb) == 0); /* already canonical */
        CHK(ca_group_equal(g, &ca, &cb));
        ca_group_inv(g, &cb, a);
        ca_group_canonicalize(g, &cb);
        CHK(ca_group_equal(g, &ca, &cb));
    }

    /* element order */
    if (g->order) {
        uint64_t o = ca_group_elem_order(g, a);
        if (o) {
            CHK(g->order % o == 0);
            ca_group_mul(g, &t, a, o, NULL);
            CHK(ca_group_is_identity(g, &t));
        }
    }

    /* formatting must stay inside the buffer */
    char buf[64];
    ca_group_format(g, a, buf, sizeof(buf));
    CHK(memchr(buf, 0, sizeof(buf)) != NULL);
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    /* Struct-style decode: flags, curve/field parameters, then element
     * words for up to MAX_BATCH batch entries. */
    if (size < 40) return 0;
    fz f = {data, size, 0};
    uint8_t flags = fz_u8(&f);
    uint8_t bits = 3 + (uint8_t)(fz_u8(&f) % 22); /* 3 .. 24 bit modulus */
    uint64_t pmask = (1ULL << bits) - 1;          /* bits <= 24 by construction */
    uint64_t praw = fz_u64(&f) & pmask;
    uint64_t ca = fz_u64(&f);
    uint64_t cb = fz_u64(&f);
    uint64_t ordmask = fz_u64(&f);
    uint64_t w0 = fz_u64(&f), w1 = fz_u64(&f);

    int ec = flags & 1;
    ca_group g;

    /* First: hand the raw parameters straight to the constructor.  Almost
     * all of them are rejected; the point is that a rejection is clean and
     * an acceptance yields a usable group. */
    {
        ca_group raw;
        ca_status rc = ec ? ca_group_ec_init(&raw, praw, ca, cb, ordmask)
                          : ca_group_zp_init(&raw, praw, ordmask);
        if (rc == CA_OK) {
            ca_elem id;
            ca_group_identity(&raw, &id);
            CHK(ca_group_is_valid(&raw, &id));
            CHK(raw.p == praw);
        }
    }

    /* Then: a group that is guaranteed valid, so the deeper paths are
     * reached on every input. */
    uint64_t p = ca_next_prime(ec ? 4 + praw : 2 + praw);
    if (p == 0) return 0;
    if (ec) {
        /* step b until the curve is non-singular (4a^3 + 27b^2 != 0) */
        int ok = 0;
        for (int t = 0; t < 8 && !ok; t++, cb++) ok = ca_group_ec_init(&g, p, ca, cb, 0) == CA_OK;
        if (!ok) return 0;
    } else {
        if (ca_group_zp_init(&g, p, 0) != CA_OK) return 0;
    }

    /* Pick a subgroup order.  For Z_p^* any divisor of p-1 is legal; for a
     * curve the order is only meaningful when point counting says so, and
     * that is gated on a flag bit because it costs O(p^1/4). */
    if (!ec) {
        ca_factorization fac;
        CHK(ca_factorize(p - 1, &fac) == CA_OK);
        uint64_t ord = 1, mask = ordmask;
        for (unsigned i = 0; i < fac.count; i++) {
            for (unsigned e = 0; e < fac.f[i].e; e++) {
                if (mask & 1) ord *= fac.f[i].p;
                mask >>= 1;
            }
        }
        CHK((p - 1) % ord == 0);
        CHK(ca_group_zp_init(&g, p, ord) == CA_OK);
        CHK(g.order == ord);
        CHK(g.cofactor == (p - 1) / ord);
    } else if ((flags & 2) && p < (1u << 20)) {
        uint64_t n = 0;
        if (ca_ec_count_points(p, g.a, g.b, &n, NULL) == CA_OK && n) {
            /* Hasse: |#E - (p+1)| <= 2 sqrt(p) */
            uint64_t bound = 2 * ca_isqrt(p) + 1;
            CHK(n >= p + 1 - bound && n <= p + 1 + bound);
            ca_factorization fac;
            CHK(ca_factorize(n, &fac) == CA_OK);
            if (fac.count) {
                uint64_t q = fac.f[fac.count - 1].p;
                uint64_t ea = g.a, eb = g.b;
                CHK(ca_group_ec_init(&g, p, ea, eb, q) == CA_OK);
                g.cofactor = n / q;
            }
        }
    }

    /* ---- elements ------------------------------------------------------ */
    /* Zero-initialised: nothing below may read a slot the loop has not written. */
    ca_elem A[MAX_BATCH] = {{{0}}}, B[MAX_BATCH] = {{{0}}};
    ca_elem R[MAX_BATCH] = {{{0}}}, one[MAX_BATCH] = {{{0}}};
    uint64_t scratch[2 * MAX_BATCH];
    memset(A, 0, sizeof(A));
    memset(B, 0, sizeof(B));
    size_t nb = 1 + (size_t)(flags >> 4); /* 1 .. 16, clamped below */
    if (nb > MAX_BATCH) nb = MAX_BATCH;

    for (size_t i = 0; i < nb; i++) {
        uint64_t wa[4] = {0, 0, 0, 0}, wb[4] = {0, 0, 0, 0};
        wa[0] = fz_u64(&f);
        wa[1] = fz_u64(&f);
        wa[2] = (uint64_t)(fz_u8(&f) & 1);
        wb[0] = fz_u64(&f);
        wb[1] = fz_u64(&f);
        wb[2] = (uint64_t)(fz_u8(&f) & 1);
        /* A rejected encoding leaves the element untouched, so every branch
         * below has to put something valid there before it is read. */
        if (!elem_from_words(&g, &A[i], wa)) {
            if (ec) {
                /* Random (x, y) is almost never on the curve; lift instead so
                 * the curve arithmetic is exercised on every input. */
                if (!ca_ec_lift_x(&g, &A[i], wa[0])) ca_ec_random_point(&g, &A[i], wa[0] | 1);
            } else {
                ca_group_identity(&g, &A[i]);
            }
            CHK(ca_group_is_valid(&g, &A[i]));
        }
        if (!elem_from_words(&g, &B[i], wb)) {
            if (ec) {
                if (!ca_ec_lift_x(&g, &B[i], wb[0])) ca_ec_random_point(&g, &B[i], wb[0] | 1);
            } else {
                ca_group_identity(&g, &B[i]);
            }
            CHK(ca_group_is_valid(&g, &B[i]));
        }
    }

    check_elem(&g, &A[0]);
    check_elem(&g, &B[0]);

    /* ---- batch op == one at a time ------------------------------------- */
    ca_group_batch_op(&g, R, A, B, nb, scratch);
    for (size_t i = 0; i < nb; i++) {
        ca_elem t;
        ca_group_op(&g, &t, &A[i], &B[i]);
        CHK(ca_group_equal(&g, &R[i], &t));
        CHK(ca_group_is_valid(&g, &R[i]));
    }
    /* aliasing the output over the first input is how the solvers call it */
    memcpy(one, A, nb * sizeof(ca_elem));
    ca_group_batch_op(&g, one, one, B, nb, scratch);
    for (size_t i = 0; i < nb; i++) CHK(ca_group_equal(&g, &one[i], &R[i]));
    /* n == 0 must be a no-op, not a read of pre[-1] */
    ca_group_batch_op(&g, R, A, B, 0, scratch);

    /* ---- scalar multiplication is a homomorphism ------------------------ */
    {
        uint64_t k1 = w0 & 0x7FFFFFFFu, k2 = w1 & 0x7FFFFFFFu; /* no u64 wrap */
        ca_elem t, u, v;
        ca_group_mul(&g, &t, &A[0], k1, NULL);
        ca_group_mul(&g, &u, &A[0], k2, NULL);
        ca_group_op(&g, &t, &t, &u);
        ca_group_mul(&g, &v, &A[0], k1 + k2, NULL);
        CHK(ca_group_equal(&g, &t, &v));
        uint64_t ops = 0;
        ca_group_mul(&g, &t, &A[0], k1, &ops);
        CHK(k1 == 0 || ops > 0);
    }

    /* ---- generator / random power -------------------------------------- */
    if ((flags & 4) && g.order >= 3) {
        ca_elem gen;
        if (ca_group_find_generator(&g, &gen, 1 + (w0 | 1)) == CA_OK) {
            CHK(ca_group_is_valid(&g, &gen));
            CHK(ca_group_elem_order(&g, &gen) == g.order);
            ca_elem h;
            uint64_t kk = 0;
            ca_group_random_power(&g, &h, &gen, w1 | 1, &kk);
            CHK(ca_group_is_valid(&g, &h));
            ca_elem chk;
            ca_group_mul(&g, &chk, &gen, kk, NULL);
            CHK(ca_group_equal(&g, &h, &chk));
        }
    }

    /* ---- lift_x always lands on the curve ------------------------------- */
    if (ec) {
        ca_elem P;
        if (ca_ec_lift_x(&g, &P, w0)) {
            CHK(ca_group_is_valid(&g, &P));
            uint64_t wp[4];
            ca_group_decode(&g, wp, &P);
            CHK(wp[2] == 0 && wp[0] == w0 % g.p);
        }
    }
    return 0;
}
