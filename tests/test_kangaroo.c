#include "test_fixtures.h"

static void run(const ca_group *g, const ca_elem *gen, uint64_t width, int reps, double *ratio)
{
    uint64_t n = g->order;
    ca_rng rng;
    ca_rng_seed(&rng, 5);
    double tot = 0;
    for (int k = 0; k < reps; k++) {
        uint64_t lo = ca_rng_below(&rng, n - width);
        uint64_t x = lo + ca_rng_below(&rng, width);
        ca_elem h;
        fx_instance(g, gen, x, &h);
        ca_kangaroo_params p;
        ca_kangaroo_params_default(&p);
        p.seed = 77 + k;
        uint64_t got = 0;
        ca_stats st = {0};
        ca_status rc = ca_kangaroo_solve(g, gen, &h, lo, lo + width - 1, &p, &got, &st);
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
    run(&g, &gen, 1ULL << 26, 8, &ratio);
    printf("zp  width 2^26 ops/sqrt(w) = %.2f\n", ratio);
    CHECK(ratio < 8.0);
    fx_ec(&g, &gen, 1000000007ULL, 3, 11);
    run(&g, &gen, 1ULL << 24, 8, &ratio);
    printf("ec  width 2^24 ops/sqrt(w) = %.2f\n", ratio);
    CHECK(ratio < 8.0);
    /* small widths and the linear-scan path */
    run(&g, &gen, 100, 5, NULL);
    run(&g, &gen, 5000, 5, NULL);
    run(&g, &gen, 100000, 5, NULL);
    /* interval near the top of the group so wraparound happens */
    uint64_t n = g.order;
    ca_elem h;
    uint64_t got;
    fx_instance(&g, &gen, n - 3, &h);
    CHECK(ca_kangaroo_solve(&g, &gen, &h, n - 100000, n - 1, NULL, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, n - 3);
    /* whole group */
    fx_instance(&g, &gen, 987654, &h);
    CHECK(ca_kangaroo_solve(&g, &gen, &h, 0, 0, NULL, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, 987654);
    TEST_MAIN_END();
}
