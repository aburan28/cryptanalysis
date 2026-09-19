#include "test_fixtures.h"

static void run(const ca_group *g, const ca_elem *gen, uint64_t width, int reps, double alpha,
                double *ratio)
{
    uint64_t n = g->order;
    ca_rng rng;
    ca_rng_seed(&rng, 11);
    double tot = 0;
    for (int k = 0; k < reps; k++) {
        uint64_t lo = ca_rng_below(&rng, n - width);
        uint64_t x = lo + ca_rng_below(&rng, width);
        ca_elem h;
        fx_instance(g, gen, x, &h);
        ca_grumpy_params p;
        ca_grumpy_params_default(&p);
        p.alpha = alpha;
        uint64_t got = 0;
        ca_stats st = {0};
        ca_status rc = ca_grumpy_solve(g, gen, &h, lo, lo + width - 1, &p, &got, &st);
        CHECK(rc == CA_OK);
        CHECK_EQ_U64(got, x);
        tot += (double)st.group_ops;
    }
    if (ratio) *ratio = tot / reps / sqrt((double)width);
}

int main(void)
{
    ca_group g;
    ca_elem gen;
    double ratio;
    fx_zp_safe(&g, &gen, 2000000579ULL);
    run(&g, &gen, 1ULL << 24, 40, 0.5, &ratio);
    printf("zp  width 2^24 ops/sqrt(w) = %.3f\n", ratio);
    CHECK(ratio < 2.5);
    fx_ec(&g, &gen, 1000000007ULL, 3, 11);
    run(&g, &gen, 1ULL << 22, 40, 0.5, &ratio);
    printf("ec  width 2^22 ops/sqrt(w) = %.3f\n", ratio);
    CHECK(ratio < 2.5);
    run(&g, &gen, 10, 10, 0.5, NULL);
    run(&g, &gen, 1000, 10, 0.5, NULL);
    /* whole group and edge cases */
    uint64_t n = g.order;
    ca_elem h;
    uint64_t got;
    fx_instance(&g, &gen, n - 1, &h);
    CHECK(ca_grumpy_solve(&g, &gen, &h, 0, 0, NULL, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, n - 1);
    fx_instance(&g, &gen, 0, &h);
    CHECK(ca_grumpy_solve(&g, &gen, &h, 0, 0, NULL, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, 0);
    /* even group order (full Z_p^*) exercises the 2x' = v branch */
    CHECK(ca_group_zp_init(&g, 1000003, 0) == CA_OK);
    const uint64_t w[4] = {2, 0, 0, 0};
    CHECK(ca_group_encode(&g, &gen, w));
    run(&g, &gen, 1ULL << 18, 20, 0.5, NULL);
    /* unknown group order: interval-only mode */
    g.order = 0;
    run(&g, &gen, 1ULL << 16, 5, 0.5, NULL);

    /* Regression, fuzz/crashes/grumpy_kangaroo_out_of_interval: a base that
     * generates a proper subgroup.  The solutions are a class modulo
     * ord(base), not modulo the group order, so shifting the found value by
     * multiples of the group order is not enough to land it in [lo, hi].
     * The answer 2 is in [0, 2]; the solver used to return 5. */
    CHECK(ca_group_zp_init(&g, 7, 0) == CA_OK); /* Z_7^*, order 6 */
    const uint64_t w2[4] = {2, 0, 0, 0};        /* 2 has order 3 */
    CHECK(ca_group_encode(&g, &gen, w2));
    ca_elem h2;
    ca_group_mul(&g, &h2, &gen, 2, NULL);
    ca_grumpy_params gp;
    ca_grumpy_params_default(&gp);
    gp.max_ops = 100000;
    uint64_t sub;
    CHECK(ca_grumpy_solve(&g, &gen, &h2, 0, 2, &gp, &sub, NULL) == CA_OK);
    CHECK_EQ_U64(sub, 2);
    /* and the contract itself: whatever comes back is inside the interval */
    CHECK(sub <= 2);
    TEST_MAIN_END();
}
