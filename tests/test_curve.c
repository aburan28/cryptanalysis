#include "test_fixtures.h"

/* Solve `reps` random logs on the group with ca_curve_solve and return the
 * mean group operations / sqrt(n). */
static double run(const ca_group *g, const ca_elem *gen, int reps)
{
    uint64_t n = g->order;
    ca_rng rng;
    ca_rng_seed(&rng, 4242 ^ n);
    double tot = 0;
    for (int k = 0; k < reps; k++) {
        uint64_t x = ca_rng_below(&rng, n);
        ca_elem h;
        ca_group_mul(g, &h, gen, x, NULL);
        uint64_t got = 0;
        ca_curve_info info;
        ca_stats st = {0};
        ca_status rc = ca_curve_solve(g, gen, &h, 7 + (uint64_t)k, &got, &info, &st);
        CHECK(rc == CA_OK);
        CHECK_EQ_U64(got, x);
        tot += (double)st.group_ops;
    }
    return tot / reps / sqrt((double)n);
}

/* Build a group by name, solve on its subgroup generator, and confirm the
 * detected endomorphism and that logs come out right. */
static void by_name(const char *name, ca_curve_endo want_endo, uint32_t want_m, double max_s)
{
    uint64_t p, a, b, order;
    CHECK(ca_curve_by_name(name, &p, &a, &b, &order) == CA_OK);
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, p, a, b, order, &info) == CA_OK);
    CHECK(info.endo == want_endo);
    CHECK(info.aut_order == want_m);
    if (want_endo != CA_CURVE_ENDO_NONE) {
        CHECK(info.lambda > 1);
        CHECK_EQ_U64(g.endo_lambda, info.lambda);
        /* lambda is a root of unity of the right order modulo n */
        uint64_t lp = 1 % order;
        for (uint32_t k = 0; k < want_m; k++) lp = ca_mulmod(lp, info.lambda, order);
        CHECK_EQ_U64(lp, 1 % order);
    }
    ca_elem gen;
    CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);
    double s = run(&g, &gen, 6);
    printf("%-14s endo=%d m=%u  S=ops/sqrt(n)=%.3f\n", name, (int)info.endo, info.aut_order, s);
    /* Sanity bound only (6 instances scatter ~+-30%); the endomorphism
     * speedup is measured properly in ca_bench glv. */
    CHECK(s < max_s);
}

int main(void)
{
    /* Detection from parameters, no group handling by the caller. */
    ca_curve_info info;
    CHECK(ca_curve_detect(67108933, 0, 7, 16773703, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J0);
    CHECK(info.aut_order == 6);
    CHECK(info.beta != 0);
    CHECK(info.lambda > 1);

    CHECK(ca_curve_detect(67108933, 6, 0, 6712457, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J1728);
    CHECK(info.aut_order == 4);

    /* A generic curve has only the negation map. */
    CHECK(ca_curve_detect(67108879, 2, 3, 0, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_NONE);
    CHECK(info.aut_order == 2);

    /* An unknown name is reported, not guessed. */
    CHECK(ca_curve_by_name("nope", NULL, NULL, NULL, NULL) == CA_ERR_NOT_FOUND);
    const char *names[8];
    size_t nc = ca_curve_list(names, 8);
    CHECK(nc >= 4);

    /* Named curves: the two GLV families and a generic one, all solved. */
    by_name("glv-j0-26", CA_CURVE_ENDO_J0, 6, 2.2);
    by_name("glv-j1728-26", CA_CURVE_ENDO_J1728, 4, 2.5);
    by_name("generic-26", CA_CURVE_ENDO_NONE, 2, 3.0);
    /* Challenge corpus: anomalous (trace 1, negation only), a j = 0 twist
     * whose subgroup is 1 mod 3, and a supersingular j = 0 curve.  p = 2 mod 3
     * so the order-6 automorphism is not rational and must not be reported. */
    /* Small orders: the walk's setup cost dominates sqrt(n), so S sits
     * well above the large-group constants used above. */
    by_name("pf-anomalous-b9", CA_CURVE_ENDO_NONE, 2, 40.0);
    by_name("pf-j0-twist-b27", CA_CURVE_ENDO_J0, 6, 40.0);
    by_name("pf-ssj0-b7", CA_CURVE_ENDO_NONE, 2, 40.0);

    /* The endomorphism must not change the answer: cross-check GLV against a
     * plain solve on the same instance. */
    uint64_t p, a, b, order;
    ca_curve_by_name("glv-j0-26", &p, &a, &b, &order);
    ca_group g;
    CHECK(ca_curve_group(&g, p, a, b, order, &info) == CA_OK);
    ca_elem gen, h;
    CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);
    uint64_t x = 12345678 % order;
    ca_group_mul(&g, &h, &gen, x, NULL);
    uint64_t got = 0;
    CHECK(ca_curve_solve(&g, &gen, &h, 3, &got, &info, NULL) == CA_OK);
    CHECK_EQ_U64(got, x);
    /* identity target */
    ca_elem id;
    ca_group_identity(&g, &id);
    CHECK(ca_curve_solve(&g, &gen, &id, 3, &got, NULL, NULL) == CA_OK);
    CHECK_EQ_U64(got, 0);

    TEST_MAIN_END();
}
