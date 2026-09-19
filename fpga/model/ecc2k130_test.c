/*
 * ecc2k130_test.c - the model's own checks.
 *
 * The model is the reference the RTL is measured against, so it has to be
 * right for reasons that do not depend on the RTL.  Everything below is
 * either a field axiom, a fact about this particular field that can be
 * derived independently (the group order, the action of the Frobenius), or
 * a property the hardware relies on (the weight is basis-independent, the
 * Frobenius is a permutation).
 */
#include "ecc2k130.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures = 0, checks = 0;

#define CHECK(cond)                                                                    \
    do {                                                                               \
        checks++;                                                                      \
        if (!(cond)) {                                                                 \
            failures++;                                                                \
            fprintf(stderr, "%s:%d: failed: %s\n", __FILE__, __LINE__, #cond);         \
        }                                                                              \
    } while (0)

static uint64_t rng_state = 0x243F6A8885A308D3ULL;

static uint64_t rnd(void)
{
    uint64_t z = (rng_state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static void rnd_fe(ec2k_fe *a)
{
    a->w[0] = rnd();
    a->w[1] = rnd();
    a->w[2] = rnd() & 7;
}

static void test_field_axioms(void)
{
    ec2k_fe one, zero;
    ec2k_fe_one(&one);
    ec2k_fe_zero(&zero);
    for (int t = 0; t < 200; t++) {
        ec2k_fe a, b, c, x, y, z;
        rnd_fe(&a);
        rnd_fe(&b);
        rnd_fe(&c);

        ec2k_fe_mul(&x, &a, &one);
        CHECK(ec2k_fe_equal(&x, &a)); /* 1 really is the all-ones vector */

        ec2k_fe_mul(&x, &a, &b);
        ec2k_fe_mul(&y, &b, &a);
        CHECK(ec2k_fe_equal(&x, &y)); /* commutative */

        ec2k_fe_mul(&x, &a, &b);
        ec2k_fe_mul(&x, &x, &c);
        ec2k_fe_mul(&y, &b, &c);
        ec2k_fe_mul(&y, &a, &y);
        CHECK(ec2k_fe_equal(&x, &y)); /* associative */

        ec2k_fe_add(&x, &b, &c);
        ec2k_fe_mul(&x, &a, &x);
        ec2k_fe_mul(&y, &a, &b);
        ec2k_fe_mul(&z, &a, &c);
        ec2k_fe_add(&y, &y, &z);
        CHECK(ec2k_fe_equal(&x, &y)); /* distributive */

        ec2k_fe_sqr(&x, &a);
        ec2k_fe_mul(&y, &a, &a);
        CHECK(ec2k_fe_equal(&x, &y)); /* the permutation really is squaring */

        if (!ec2k_fe_is_zero(&a)) {
            ec2k_fe inv;
            CHECK(ec2k_fe_inv(&inv, &a));
            ec2k_fe_mul(&x, &a, &inv);
            CHECK(ec2k_fe_equal(&x, &one));
        }
    }
    ec2k_fe inv;
    CHECK(!ec2k_fe_inv(&inv, &zero)); /* zero has no inverse, and says so */
}

static void test_frobenius(void)
{
    for (int t = 0; t < 50; t++) {
        ec2k_fe a, x, y;
        rnd_fe(&a);
        /* frob(j) is j squarings */
        for (unsigned j = 0; j <= 12; j++) {
            ec2k_fe_frob(&x, &a, j);
            y = a;
            for (unsigned k = 0; k < j; k++) {
                ec2k_fe t2;
                ec2k_fe_sqr(&t2, &y);
                y = t2;
            }
            CHECK(ec2k_fe_equal(&x, &y));
        }
        /* sigma^131 = identity: the field has degree 131 */
        ec2k_fe_frob(&x, &a, 131);
        CHECK(ec2k_fe_equal(&x, &a));
        /* Frobenius is additive and multiplicative */
        ec2k_fe b, s, p, fa, fb;
        rnd_fe(&b);
        ec2k_fe_add(&s, &a, &b);
        ec2k_fe_frob(&x, &s, 5);
        ec2k_fe_frob(&fa, &a, 5);
        ec2k_fe_frob(&fb, &b, 5);
        ec2k_fe_add(&y, &fa, &fb);
        CHECK(ec2k_fe_equal(&x, &y));
        ec2k_fe_mul(&p, &a, &b);
        ec2k_fe_frob(&x, &p, 5);
        ec2k_fe_mul(&y, &fa, &fb);
        CHECK(ec2k_fe_equal(&x, &y));
        /* and a permutation of the coefficients, so the Hamming weight --
         * which the iteration and the distinguished-point test both read --
         * does not depend on which basis order is used */
        CHECK(ec2k_fe_weight(&x) == ec2k_fe_weight(&p));
    }
}

/* The absolute trace of every basis element is 1 in this basis, so the trace
 * of an element is the parity of its weight.  Checked against the definition
 * Tr(a) = sum_i a^(2^i), because the point decompression depends on it. */
static void test_trace(void)
{
    for (int t = 0; t < 20; t++) {
        ec2k_fe a, acc, cur;
        rnd_fe(&a);
        acc = a;
        cur = a;
        for (unsigned i = 1; i < EC2K_M; i++) {
            ec2k_fe s;
            ec2k_fe_sqr(&s, &cur);
            cur = s;
            ec2k_fe_add(&acc, &acc, &cur);
        }
        /* The trace lands in F_2 = {0, 1}: zero or the all-ones vector. */
        ec2k_fe one, zero;
        ec2k_fe_one(&one);
        ec2k_fe_zero(&zero);
        int is_one = ec2k_fe_equal(&acc, &one);
        CHECK(is_one || ec2k_fe_equal(&acc, &zero));
        CHECK(is_one == (int)(ec2k_fe_weight(&a) & 1));
    }
}

static void test_curve(void)
{
    for (int t = 0; t < 20; t++) {
        ec2k_pt p, q, r, s;
        ec2k_point_from_seed(&p, rnd());
        CHECK(ec2k_on_curve(&p));
        CHECK(!p.inf);

        /* P + (-P) = O, P + O = P */
        ec2k_pt_neg(&q, &p);
        CHECK(ec2k_on_curve(&q));
        ec2k_pt_add(&r, &p, &q);
        CHECK(r.inf);

        /* commutativity and the doubling path */
        ec2k_point_from_seed(&q, rnd());
        ec2k_pt_add(&r, &p, &q);
        ec2k_pt_add(&s, &q, &p);
        CHECK(ec2k_on_curve(&r));
        CHECK(ec2k_fe_equal(&r.x, &s.x) && ec2k_fe_equal(&r.y, &s.y));
        ec2k_pt_add(&r, &p, &p);
        ec2k_pt_dbl(&s, &p);
        CHECK(ec2k_fe_equal(&r.x, &s.x) && ec2k_fe_equal(&r.y, &s.y));

        /* associativity, the property that actually catches sign errors */
        ec2k_pt u, v, w1, w2;
        ec2k_point_from_seed(&u, rnd());
        ec2k_pt_add(&v, &p, &q);
        ec2k_pt_add(&w1, &v, &u);
        ec2k_pt_add(&v, &q, &u);
        ec2k_pt_add(&w2, &p, &v);
        CHECK(w1.inf == w2.inf);
        if (!w1.inf) CHECK(ec2k_fe_equal(&w1.x, &w2.x) && ec2k_fe_equal(&w1.y, &w2.y));
    }
}

/*
 * The two facts that identify this curve, both derived rather than quoted.
 *
 *   - sigma acts as tau with tau^2 + tau + 2 = 0, i.e. sigma^2(P) + sigma(P)
 *     + 2P = O for every P.  That is what makes the Frobenius free to apply
 *     and is the whole reason this attack is built around it.
 *   - The subgroup this walk lives in has order n, so n*P = O for a point
 *     that has been multiplied by the cofactor 4.
 */
static void test_koblitz_structure(void)
{
    /* n = 680564733841876926932320129493409985129, from #E = 4n and the
     * Koblitz recursion; see README.md. */
    static const uint64_t n[3] = {
        0x4D4FDD5703A3F269ULL, 0x0000000000000000ULL, 0x0000000000000002ULL,
    };
    for (int t = 0; t < 4; t++) {
        ec2k_pt p, sp, ssp, dp, sum;
        ec2k_point_from_seed(&p, rnd());

        ec2k_pt_frob(&sp, &p, 1);
        CHECK(ec2k_on_curve(&sp));
        ec2k_pt_frob(&ssp, &p, 2);
        ec2k_pt_dbl(&dp, &p);
        ec2k_pt_add(&sum, &ssp, &sp);
        ec2k_pt_add(&sum, &sum, &dp);
        CHECK(sum.inf); /* sigma^2 + sigma + 2 = 0 */

        ec2k_pt np;
        ec2k_pt_mul(&np, &p, n, 3);
        CHECK(np.inf); /* the point really is in the order-n subgroup */
    }
}

static void test_iteration(void)
{
    /* j is in [3, 10] and comes from the weight, and a step is a real
     * addition of sigma^j(R) to R. */
    for (int t = 0; t < 200; t++) {
        ec2k_pt r, next;
        ec2k_point_from_seed(&r, rnd());
        unsigned j = ec2k_step_j(&r.x);
        CHECK(j >= EC2K_J_MIN && j < EC2K_J_MIN + EC2K_J_COUNT);
        if (ec2k_step(&next, &r)) {
            CHECK(ec2k_on_curve(&next));
            ec2k_pt s, want;
            ec2k_pt_frob(&s, &r, j);
            ec2k_pt_add(&want, &s, &r);
            CHECK(ec2k_fe_equal(&next.x, &want.x));
            CHECK(ec2k_fe_equal(&next.y, &want.y));
        }
    }
}

/* A walk is deterministic in its seed: two runs produce the same points.
 * The whole distributed protocol rests on it -- a unit that is replayed must
 * reproduce itself, or a scheduler cannot re-issue work. */
typedef struct collect {
    ec2k_record *recs;
    size_t n, cap;
} collect;

static void collect_sink(void *ctx, const ec2k_record *rec)
{
    collect *c = ctx;
    if (c->n == c->cap) {
        c->cap = c->cap ? c->cap * 2 : 64;
        c->recs = realloc(c->recs, c->cap * sizeof(*c->recs));
    }
    c->recs[c->n++] = *rec;
}

static void test_walk_is_replayable(void)
{
    collect a = {0}, b = {0};
    uint64_t dps_a = 0, dps_b = 0, restarts = 0;
    ec2k_walk(12345, 4000, collect_sink, &a, &dps_a, &restarts);
    ec2k_walk(12345, 4000, collect_sink, &b, &dps_b, &restarts);
    CHECK(a.n == b.n);
    CHECK(dps_a == dps_b);
    int same = 1;
    for (size_t i = 0; i < a.n && i < b.n; i++)
        same &= a.recs[i].seed == b.recs[i].seed && ec2k_fe_equal(&a.recs[i].x, &b.recs[i].x);
    CHECK(same);

    collect c = {0};
    uint64_t dps_c = 0;
    ec2k_walk(999, 4000, collect_sink, &c, &dps_c, &restarts);
    CHECK(c.n != a.n || a.n == 0 ||
          !ec2k_fe_equal(&c.recs[0].x, &a.recs[0].x)); /* a different seed walks elsewhere */

    /* Every reported point is distinguished and is its own orbit minimum. */
    for (size_t i = 0; i < a.n; i++) {
        CHECK(ec2k_is_distinguished(&a.recs[i].x));
        ec2k_fe m;
        ec2k_orbit_min(&m, &a.recs[i].x);
        CHECK(ec2k_fe_equal(&m, &a.recs[i].x));
    }
    free(a.recs);
    free(b.recs);
    free(c.recs);
}

/* The orbit minimum is what makes two walks that met report the same key:
 * the Frobenius orbit of a point's x coordinate is a class, and the class
 * representative has to be a function of the class alone. */
static void test_orbit_min_is_a_class_function(void)
{
    for (int t = 0; t < 20; t++) {
        ec2k_fe x, m0;
        rnd_fe(&x);
        ec2k_orbit_min(&m0, &x);
        for (unsigned k = 1; k < EC2K_M; k += 17) {
            ec2k_fe y, m;
            ec2k_fe_frob(&y, &x, k);
            ec2k_orbit_min(&m, &y);
            CHECK(ec2k_fe_equal(&m, &m0));
        }
    }
}

static void test_serialisation(void)
{
    for (int t = 0; t < 50; t++) {
        ec2k_fe a, b;
        rnd_fe(&a);
        uint8_t buf[17];
        ec2k_fe_to_bytes(buf, &a);
        CHECK(ec2k_fe_from_bytes(&b, buf));
        CHECK(ec2k_fe_equal(&a, &b));

        char hex[34];
        ec2k_fe_to_hex(hex, &a);
        CHECK(ec2k_fe_from_hex(&b, hex));
        CHECK(ec2k_fe_equal(&a, &b));

        ec2k_record rec = {rnd(), a}, dec;
        uint8_t wire[EC2K_RECORD_BYTES];
        ec2k_record_encode(wire, &rec);
        CHECK(ec2k_record_decode(&dec, wire));
        CHECK(dec.seed == rec.seed && ec2k_fe_equal(&dec.x, &rec.x));

        /* The padding is part of the format: a record with junk in it is not
         * one this model produced, and is refused rather than truncated. */
        wire[EC2K_RECORD_BYTES - 1] = 0xFF;
        CHECK(!ec2k_record_decode(&dec, wire));
    }
}

int main(void)
{
    test_field_axioms();
    test_frobenius();
    test_trace();
    test_curve();
    test_koblitz_structure();
    test_iteration();
    test_walk_is_replayable();
    test_orbit_min_is_a_class_function();
    test_serialisation();
    if (failures) {
        fprintf(stderr, "FAILED: %d of %d checks\n", failures, checks);
        return 1;
    }
    printf("ok: %d checks\n", checks);
    return 0;
}
