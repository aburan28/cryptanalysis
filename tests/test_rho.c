#include "test_fixtures.h"

static void run_rho(const ca_group *g, const ca_elem *gen, const ca_rho_params *p, int reps,
                    double *ratio_out)
{
    uint64_t n = g->order;
    ca_rng rng;
    ca_rng_seed(&rng, 99 + p->threads);
    double total_ops = 0;
    for (int k = 0; k < reps; k++) {
        uint64_t x = ca_rng_below(&rng, n);
        ca_elem h;
        fx_instance(g, gen, x, &h);
        uint64_t got = 0;
        ca_stats st = {0};
        ca_rho_params pp = *p;
        pp.seed = 1000 + k;
        ca_status rc = ca_rho_solve(g, gen, &h, &pp, &got, &st);
        CHECK(rc == CA_OK);
        CHECK_EQ_U64(got, x);
        total_ops += (double)st.group_ops;
    }
    if (ratio_out) *ratio_out = total_ops / reps / sqrt((double)n);
}

int main(void)
{
    ca_group g;
    ca_elem gen;
    ca_rho_params p;
    ca_rho_params_default(&p);

    /* Z_p^* subgroup of prime order ~2^30 */
    fx_zp_safe(&g, &gen, 2000000579ULL);
    double ratio;
    run_rho(&g, &gen, &p, 6, &ratio);
    printf("zp  serial   ops/sqrt(n) = %.2f\n", ratio);
    CHECK(ratio < 6.0);
    p.threads = 4;
    run_rho(&g, &gen, &p, 6, &ratio);
    printf("zp  4 thread ops/sqrt(n) = %.2f\n", ratio);
    CHECK(ratio < 8.0);

    /* Elliptic curve, prime-order subgroup, negation map on and off */
    fx_ec(&g, &gen, 1000000007ULL, 3, 11);
    printf("ec order %" PRIu64 " (cofactor %" PRIu64 ")\n", g.order, g.cofactor);
    ca_rho_params_default(&p);
    p.negation_map = 0;
    run_rho(&g, &gen, &p, 6, &ratio);
    printf("ec  no-neg   ops/sqrt(n) = %.2f\n", ratio);
    CHECK(ratio < 6.0);
    p.negation_map = 1;
    run_rho(&g, &gen, &p, 6, &ratio);
    printf("ec  negmap   ops/sqrt(n) = %.2f\n", ratio);
    CHECK(ratio < 6.0);
    p.threads = 4;
    run_rho(&g, &gen, &p, 4, &ratio);
    printf("ec  neg 4thr ops/sqrt(n) = %.2f\n", ratio);
    CHECK(ratio < 8.0);
    /* explicit small dp bits and few walks */
    ca_rho_params_default(&p);
    p.dp_bits = 2;
    p.walks_per_thread = 3;
    p.r = 16;
    run_rho(&g, &gen, &p, 3, NULL);

    /* tiny groups must still work (brute force path and dp_bits = 0) */
    fx_zp_safe(&g, &gen, 23);
    run_rho(&g, &gen, &p, 5, NULL);
    fx_zp_safe(&g, &gen, 1019);
    run_rho(&g, &gen, &p, 5, NULL);
    fx_ec(&g, &gen, 10007, 1, 1);
    run_rho(&g, &gen, &p, 5, NULL);

    /* composite order (full Z_p^*) */
    CHECK(ca_group_zp_init(&g, 1000003, 0) == CA_OK);
    const uint64_t w[4] = {2, 0, 0, 0};
    CHECK(ca_group_encode(&g, &gen, w));
    ca_rho_params_default(&p);
    run_rho(&g, &gen, &p, 5, NULL);

    /* limits */
    fx_zp_safe(&g, &gen, 2000000579ULL);
    p.max_ops = 100;
    ca_elem h;
    uint64_t got;
    fx_instance(&g, &gen, 424242, &h);
    CHECK(ca_rho_solve(&g, &gen, &h, &p, &got, NULL) == CA_ERR_LIMIT);
    TEST_MAIN_END();
}
