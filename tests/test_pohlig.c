#include "test_fixtures.h"

int main(void)
{
    ca_group g;
    ca_elem gen, h;
    uint64_t got;
    /* full Z_p^* for a p-1 with many small factors and one large one */
    uint64_t p = 1000003; /* p-1 = 2 * 3 * 166667 */
    CHECK(ca_group_zp_init(&g, p, 0) == CA_OK);
    uint64_t w[4] = {ca_primitive_root(p), 0, 0, 0};
    CHECK(ca_group_encode(&g, &gen, w));
    for (uint64_t x = 0; x < p - 1; x += 99991) {
        fx_instance(&g, &gen, x, &h);
        ca_stats st = {0};
        CHECK(ca_dlog(&g, &gen, &h, &got, &st) == CA_OK);
        CHECK_EQ_U64(got, x);
    }
    /* prime power factors: p = 2^16 * 3^4 * 5 + 1? find a prime with such structure */
    uint64_t q = 256ULL * 81 * 25 * 49 * 11 * 13 + 1; /* check primality below */
    while (!ca_is_prime(q)) q += 2 * 3 * 5 * 7 * 11 * 13 * 2;
    CHECK(ca_group_zp_init(&g, q, 0) == CA_OK);
    w[0] = ca_primitive_root(q);
    CHECK(ca_group_encode(&g, &gen, w));
    ca_rng rng;
    ca_rng_seed(&rng, 3);
    for (int k = 0; k < 10; k++) {
        uint64_t x = ca_rng_below(&rng, q - 1);
        fx_instance(&g, &gen, x, &h);
        CHECK(ca_dlog(&g, &gen, &h, &got, NULL) == CA_OK);
        CHECK_EQ_U64(got, x);
    }
    /* each explicit solver through the dispatcher */
    ca_solver solvers[] = {CA_SOLVER_BSGS, CA_SOLVER_RHO, CA_SOLVER_KANGAROO, CA_SOLVER_GRUMPY};
    uint64_t p2 = 2000000579ULL;
    CHECK(ca_group_zp_init(&g, p2, 0) == CA_OK); /* order 2 * 1000000289 */
    w[0] = ca_primitive_root(p2);
    CHECK(ca_group_encode(&g, &gen, w));
    for (size_t s = 0; s < 4; s++) {
        ca_dlog_params dp;
        ca_dlog_params_default(&dp);
        dp.solver = solvers[s];
        dp.rho.seed = 5;
        uint64_t x = 1234567891ULL;
        fx_instance(&g, &gen, x, &h);
        ca_stats st = {0};
        ca_status rc = ca_pohlig_hellman(&g, &gen, &h, &dp, &got, &st);
        CHECK(rc == CA_OK);
        CHECK_EQ_U64(got, x);
        printf("%-9s ops=%" PRIu64 " time=%.3fs\n", ca_solver_name(solvers[s]), st.group_ops, st.seconds);
    }
    /* EC group with cofactor: dlog in full group order */
    uint64_t n;
    CHECK(ca_ec_count_points(1000003, 1, 7, &n, NULL) == CA_OK);
    CHECK(ca_group_ec_init(&g, 1000003, 1, 7, n) == CA_OK);
    ca_elem P;
    ca_ec_random_point(&g, &P, 9);
    uint64_t ordP = ca_group_elem_order(&g, &P);
    g.order = ordP;
    for (int k = 0; k < 10; k++) {
        uint64_t x = ca_rng_below(&rng, ordP);
        fx_instance(&g, &P, x, &h);
        CHECK(ca_dlog(&g, &P, &h, &got, NULL) == CA_OK);
        CHECK_EQ_U64(got, x);
    }
    /* target outside <base> is rejected */
    CHECK(ca_group_zp_init(&g, 1000003, 166667) == CA_OK);
    CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);
    w[0] = 2; /* order 1000002/... 2 generates the whole group, not the subgroup */
    CHECK(ca_group_encode(&g, &h, w));
    if (ca_group_elem_order(&g, &h) == 0) CHECK(ca_dlog(&g, &gen, &h, &got, NULL) != CA_OK);
    TEST_MAIN_END();
}
