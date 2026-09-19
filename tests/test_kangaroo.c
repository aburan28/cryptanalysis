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

    /* Regression, fuzz/crashes/grumpy_kangaroo_out_of_interval: a base that
     * generates a proper subgroup.  The solutions form a class modulo
     * ord(base), not modulo the group order, so the answer 2 is in [0, 2]
     * even though 5 is the representative modulo 6. */
    ca_group sg;
    ca_elem sbase, starget;
    CHECK(ca_group_zp_init(&sg, 7, 0) == CA_OK); /* Z_7^*, order 6 */
    const uint64_t w2[4] = {2, 0, 0, 0};         /* 2 has order 3 */
    CHECK(ca_group_encode(&sg, &sbase, w2));
    ca_group_mul(&sg, &starget, &sbase, 2, NULL);
    ca_kangaroo_params kp;
    ca_kangaroo_params_default(&kp);
    kp.seed = 1;
    kp.max_ops = 100000;
    uint64_t sub = 0;
    ca_status src = ca_kangaroo_solve(&sg, &sbase, &starget, 0, 2, &kp, &sub, NULL);
    CHECK(src == CA_OK || src == CA_ERR_LIMIT || src == CA_ERR_NOT_FOUND);
    if (src == CA_OK) CHECK(sub <= 2);

    /* Regression, fuzz/crashes/rho_kangaroo_dp_bits_shift: dp_bits at or above
     * the width of the mask used to be a shift by >= 64. */
    fx_instance(&g, &gen, 4242, &h);
    for (int32_t dpb = 62; dpb <= 200; dpb += 23) {
        ca_kangaroo_params dp;
        ca_kangaroo_params_default(&dp);
        dp.seed = 3;
        dp.dp_bits = dpb;
        dp.max_ops = 200000;
        uint64_t any = 0;
        ca_status r = ca_kangaroo_solve(&g, &gen, &h, 0, 100000, &dp, &any, NULL);
        CHECK(r == CA_OK || r == CA_ERR_LIMIT || r == CA_ERR_NOT_FOUND);
        if (r == CA_OK) CHECK_EQ_U64(any, 4242);
    }

    /* Regression, fuzz/crashes/kangaroo_herd_size_hang: 2 * herd_size used to
     * wrap to an empty herd, so the loop never advanced ops and max_ops never
     * fired.  This must terminate. */
    ca_kangaroo_params hp;
    ca_kangaroo_params_default(&hp);
    hp.seed = 1;
    hp.max_ops = 100000;
    hp.herd_size = 0x80000000u;
    uint64_t hx = 0;
    ca_status hrc = ca_kangaroo_solve(&g, &gen, &h, 0, 100000, &hp, &hx, NULL);
    CHECK(hrc == CA_OK || hrc == CA_ERR_LIMIT || hrc == CA_ERR_NOT_FOUND || hrc == CA_ERR_NOMEM);
    if (hrc == CA_OK) CHECK_EQ_U64(hx, 4242);
    TEST_MAIN_END();
}
