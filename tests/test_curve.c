#include "ec_tau_internal.h"
#include "test_fixtures.h"

static int tau_cost_cases;

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

/* Compare complete point outputs for the baseline and schedule-selected
 * representatives.  These are correctness controls, not timing claims. */
static void tau_cost_checks(const ca_group *g, const ca_elem *point, int samples)
{
    ca_tau4_precomp pre;
    CHECK(ca_ec_tau4_prepare(g, point, &pre, NULL));
    ca_tau4_pos_precomp positional_pre;
    uint64_t prep_triples = 0;
    CHECK(sizeof(positional_pre.point) == 36864);
    CHECK(ca_ec_tau4_pos_prepare(g, point, &positional_pre, &prep_triples));
    CHECK(prep_triples > 0);
    ca_rng rng;
    ca_rng_seed(&rng, UINT64_C(0x20261004) ^ g->order);
    for (int i = 0; i < samples; i++) {
        uint64_t k =
            i < 8 ? (uint64_t[]){0, 1, 2, 3, g->order - 2, g->order - 1, g->order, UINT64_MAX}[i]
                  : ca_rng_next(&rng);
        ca_elem expected, baseline = *point, selected = *point, positional = *point;
        uint64_t base_triples = UINT64_MAX, base_adds = UINT64_MAX;
        uint64_t cost_triples = UINT64_MAX, cost_adds = UINT64_MAX;
        ca_group_mul(g, &expected, point, k % g->order, NULL);
        CHECK(ca_ec_tau4_mul_prepared(g, &pre, &baseline, k, &base_triples, &base_adds));
        CHECK(ca_ec_tau4_mul_prepared_cost(g, &pre, &selected, k, &cost_triples, &cost_adds));
        uint64_t positional_adds = UINT64_MAX, positional_rotations = UINT64_MAX;
        CHECK(ca_ec_tau4_pos_mul(g, &positional_pre, &positional, k, &positional_adds,
                                 &positional_rotations));
        CHECK(ca_group_equal(g, &baseline, &expected));
        CHECK(ca_group_equal(g, &selected, &expected));
        CHECK(ca_group_equal(g, &positional, &expected));
        CHECK(base_triples < 256 && base_adds < 256);
        CHECK(cost_triples < 256 && cost_adds < 256);
        CHECK(positional_adds < 256 && positional_rotations < 256);
        tau_cost_cases++;
    }
}

/* Exercise the three direct tau evaluators and both profile modes against
 * independently computed points, including the identity and scalar edges. */
static void tau_direct_checks(const ca_group *g, const ca_elem *point)
{
    const uint64_t scalars[] = {0, 1, 2, 3, 17, g->order - 1, UINT64_MAX};
    ca_tau4_precomp pre;
    CHECK(ca_ec_tau4_prepare(g, point, &pre, NULL));
    for (size_t i = 0; i < sizeof(scalars) / sizeof(scalars[0]); i++) {
        uint64_t k = scalars[i], steps, adds, triples;
        ca_elem expected, got;
        ca_group_mul(g, &expected, point, k % g->order, NULL);
        CHECK(ca_ec_mul_tau2(g, &got, point, k, &steps, &adds));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_mul_tau4(g, &got, point, k, &steps, &adds));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_mul_tau4_tripling(g, &got, point, k, &steps, &adds, &triples));
        CHECK(ca_group_equal(g, &got, &expected));
        for (int mode = 0; mode <= 1; mode++) {
            uint64_t rotations;
            CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &got, k, mode, &triples, &adds,
                                                  &rotations));
            CHECK(ca_group_equal(g, &got, &expected));
        }
    }
    ca_elem identity, got;
    ca_group_identity(g, &identity);
    uint64_t setup_ops = UINT64_MAX;
    CHECK(ca_ec_tau4_prepare(g, &identity, &pre, &setup_ops));
    CHECK_EQ_U64(setup_ops, 0);
    CHECK(ca_ec_tau4_mul_prepared_cost(g, &pre, &got, 17, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(!ca_ec_tau4_mul_prepared_profile(g, &pre, &got, 17, 2, NULL, NULL, NULL));
}

static void tau_cost_named(const char *name)
{
    uint64_t p, a, b, order;
    CHECK(ca_curve_by_name(name, &p, &a, &b, &order) == CA_OK);
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, p, a, b, order, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J0);
    ca_elem generator;
    CHECK(ca_group_find_generator(&g, &generator, 1) == CA_OK);
    tau_cost_checks(&g, &generator, 256);
    tau_direct_checks(&g, &generator);
    ca_elem second_point;
    ca_group_mul(&g, &second_point, &generator, 37, NULL);
    tau_cost_checks(&g, &second_point, 128);
}

static void tau_cost_boundary_curves(void)
{
    const struct {
        uint64_t p, b, order;
        int samples;
    } cases[] = {{97, 2, 13, 13},
                 {97, 10, 103, 103},
                 {UINT64_C(2305843009213693951), 7, UINT64_C(53624256071278747), 128}};
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        ca_group g;
        ca_curve_info info;
        CHECK(ca_curve_group(&g, cases[i].p, 0, cases[i].b, cases[i].order, &info) == CA_OK);
        CHECK(info.endo == CA_CURVE_ENDO_J0);
        ca_elem generator;
        CHECK(ca_group_find_generator(&g, &generator, 1) == CA_OK);
        tau_cost_checks(&g, &generator, cases[i].samples);
        ca_elem identity, got;
        ca_group_identity(&g, &identity);
        ca_tau4_pos_precomp identity_pre;
        uint64_t triples = UINT64_MAX;
        CHECK(ca_ec_tau4_pos_prepare(&g, &identity, &identity_pre, &triples));
        CHECK_EQ_U64(triples, 0);
        CHECK(ca_ec_tau4_pos_mul(&g, &identity_pre, &got, 123, NULL, NULL));
        CHECK(ca_group_is_identity(&g, &got));
    }
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
    tau_cost_named("glv-j0-26");
    tau_cost_named("glv-j0-32");
    tau_cost_boundary_curves();
    printf("cost-aware tau point cases=%d\n", tau_cost_cases);
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
