#include "test_fixtures.h"
#include "ec_tau_internal.h"
#include "curve_internal.h"

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

static void check_j0_coord_orbit(const ca_group *g, const ca_elem *point)
{
    ca_elem orbit = *point, representative = *point;
    CHECK(ca_ec_j0_coord_canonicalize(g, &representative) < 6);
    for (int j = 0; j < 6; j++) {
        ca_elem reduced = orbit, replay = orbit;
        uint32_t power = ca_ec_j0_coord_canonicalize(g, &reduced);
        CHECK(power < 6);
        for (uint32_t t = 0; t < power; t++) {
            ca_elem next;
            ca_ec_endo(g, &next, &replay);
            replay = next;
        }
        CHECK(ca_group_equal(g, &reduced, &representative));
        CHECK(ca_group_equal(g, &reduced, &replay));
        ca_elem next;
        ca_ec_endo(g, &next, &orbit);
        orbit = next;
    }
}

/* The tau digit path uses the -omega eigenvalue of the rho automorphism;
 * compare the actual points over the subgroup, including aliasing and
 * boundary scalars. */
static void tau_scalar_checks(const char *name)
{
    uint64_t p, a, b, order;
    CHECK(ca_curve_by_name(name, &p, &a, &b, &order) == CA_OK);
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, p, a, b, order, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J0);
    ca_elem gen;
    CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);
    ca_tau4_precomp pre;
    uint64_t prep_ops = 0;
    CHECK(ca_ec_tau4_prepare(&g, &gen, &pre, &prep_ops));
    CHECK(prep_ops == 19);
    ca_rng rng;
    ca_rng_seed(&rng, 0x74a2ULL ^ order);
    for (int i = 0; i < 256; i++) {
        uint64_t k = i < 8 ? (uint64_t[]){0, 1, 2, 3, order - 2, order - 1, order, UINT64_MAX}[i]
                           : ca_rng_next(&rng);
        ca_elem want, got = gen;
        uint64_t nt = UINT64_MAX, na = UINT64_MAX;
        ca_group_mul(&g, &want, &gen, k % order, NULL);
        CHECK(ca_ec_mul_tau2(&g, &got, &got, k, &nt, &na));
        CHECK(ca_group_equal(&g, &got, &want));
        CHECK(nt < 256 && na < 256);
        got = gen;
        CHECK(ca_ec_mul_tau4(&g, &got, &got, k, &nt, &na));
        CHECK(ca_group_equal(&g, &got, &want));
        CHECK(nt < 256 && na < 256);
        uint64_t n3 = UINT64_MAX;
        got = gen;
        CHECK(ca_ec_mul_tau4_tripling(&g, &got, &got, k, &nt, &na, &n3));
        CHECK(ca_group_equal(&g, &got, &want));
        CHECK(nt < 256 && na < 256 && n3 < 256);
        got = gen;
        CHECK(ca_ec_tau4_mul_prepared(&g, &pre, &got, k, &n3, &na));
        CHECK(ca_group_equal(&g, &got, &want));
        CHECK(na < 256 && n3 < 256);
        if (i < 64) check_j0_coord_orbit(&g, &want);
        if (i < 32) {
            ca_elem triple = want, ref;
            ca_group_mul(&g, &ref, &want, 3, NULL);
            CHECK(ca_ec_triple_j0(&g, &triple, &triple));
            CHECK(ca_group_equal(&g, &triple, &ref));
        }
    }
    ca_elem id, got;
    ca_group_identity(&g, &id);
    CHECK(ca_ec_mul_tau2(&g, &got, &id, 123, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_mul_tau4(&g, &got, &id, 123, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_mul_tau4_tripling(&g, &got, &id, 123, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_tau4_prepare(&g, &id, &pre, &prep_ops));
    CHECK(prep_ops == 0);
    CHECK(ca_ec_tau4_mul_prepared(&g, &pre, &got, 123, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_triple_j0(&g, &got, &id));
    CHECK(ca_group_is_identity(&g, &got));
}

static void tau_small_curve_checks(void)
{
    const uint64_t cases[][3] = {{7, 3, 13}, {13, 2, 19}, {37, 5, 37}, {79, 3, 97}};
    for (size_t c = 0; c < sizeof(cases) / sizeof(cases[0]); c++) {
        ca_group g;
        ca_curve_info info;
        CHECK(ca_curve_group(&g, cases[c][0], 0, cases[c][1], cases[c][2], &info) == CA_OK);
        CHECK(info.endo == CA_CURVE_ENDO_J0);
        ca_elem gen;
        CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);
        ca_tau4_precomp pre;
        CHECK(ca_ec_tau4_prepare(&g, &gen, &pre, NULL));
        for (uint64_t k = 0; k < cases[c][2]; k++) {
            ca_elem want, got;
            ca_group_mul(&g, &want, &gen, k, NULL);
            CHECK(ca_ec_mul_tau2(&g, &got, &gen, k, NULL, NULL));
            CHECK(ca_group_equal(&g, &got, &want));
            CHECK(ca_ec_mul_tau4(&g, &got, &gen, k, NULL, NULL));
            CHECK(ca_group_equal(&g, &got, &want));
            CHECK(ca_ec_mul_tau4_tripling(&g, &got, &gen, k, NULL, NULL, NULL));
            CHECK(ca_group_equal(&g, &got, &want));
            CHECK(ca_ec_tau4_mul_prepared(&g, &pre, &got, k, NULL, NULL));
            CHECK(ca_group_equal(&g, &got, &want));
        }
    }
    /* Exceptional kernels: x=0 has order 3; y=0 has order 2. */
    ca_group g;
    ca_elem point, got, want;
    CHECK(ca_group_ec_init(&g, 7, 0, 1, 0) == CA_OK);
    CHECK(ca_ec_lift_x(&g, &point, 0));
    CHECK(ca_ec_triple_j0(&g, &got, &point));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_group_ec_init(&g, 7, 0, 6, 0) == CA_OK);
    CHECK(ca_ec_lift_x(&g, &point, 1));
    ca_group_mul(&g, &want, &point, 3, NULL);
    CHECK(ca_ec_triple_j0(&g, &got, &point));
    CHECK(ca_group_equal(&g, &got, &want));
    /* Ineligible families leave the output untouched. */
    CHECK(ca_group_ec_init(&g, 7, 1, 0, 0) == CA_OK);
    got = point;
    CHECK(!ca_ec_mul_tau2(&g, &got, &point, 3, NULL, NULL));
    CHECK(memcmp(&got, &point, sizeof(got)) == 0);
    CHECK(!ca_ec_triple_j0(&g, &got, &point));
    CHECK(memcmp(&got, &point, sizeof(got)) == 0);
}

static void tau_large_curve_checks(void)
{
    /* 2^61-1 is prime; E: y^2=x^3+7 has order 43 * r, with this
     * 56-bit prime r.  This exercises the signed-128 lattice path beyond
     * the much smaller registered subgroups. */
    const uint64_t p = UINT64_C(2305843009213693951);
    const uint64_t order = UINT64_C(53624256071278747);
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, p, 0, 7, order, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J0);
    ca_elem gen;
    CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);
    ca_tau4_precomp pre;
    CHECK(ca_ec_tau4_prepare(&g, &gen, &pre, NULL));
    ca_rng rng;
    ca_rng_seed(&rng, UINT64_C(0x56c0ffee));
    for (int i = 0; i < 128; i++) {
        uint64_t k = i < 6 ? (uint64_t[]){0, 1, order - 1, order, order + 1, UINT64_MAX}[i]
                           : ca_rng_next(&rng);
        ca_elem want, got;
        ca_group_mul(&g, &want, &gen, k % order, NULL);
        CHECK(ca_ec_mul_tau2(&g, &got, &gen, k, NULL, NULL));
        CHECK(ca_group_equal(&g, &got, &want));
        CHECK(ca_ec_mul_tau4(&g, &got, &gen, k, NULL, NULL));
        CHECK(ca_group_equal(&g, &got, &want));
        CHECK(ca_ec_mul_tau4_tripling(&g, &got, &gen, k, NULL, NULL, NULL));
        CHECK(ca_group_equal(&g, &got, &want));
        got = gen;
        CHECK(ca_ec_tau4_mul_prepared(&g, &pre, &got, k, NULL, NULL));
        CHECK(ca_group_equal(&g, &got, &want));
        if (i < 16) check_j0_coord_orbit(&g, &want);
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
    tau_scalar_checks("glv-j0-26");
    tau_scalar_checks("glv-j0-32");
    tau_small_curve_checks();
    tau_large_curve_checks();

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
