#include "test_fixtures.h"

static void run(const ca_group *g, const ca_elem *gen, uint64_t d, int reps)
{
    uint64_t p = g->order;
    ca_rng rng;
    ca_rng_seed(&rng, 13 + d);
    for (int k = 0; k < reps; k++) {
        uint64_t alpha = 1 + ca_rng_below(&rng, p - 1);
        ca_elem ga, gad;
        CHECK(ca_cheon_make_instance(g, gen, alpha, d, &ga, &gad) == CA_OK);
        uint64_t got = 0;
        ca_stats st = {0};
        ca_status rc = ca_cheon_solve(g, gen, &ga, &gad, d, NULL, &got, &st);
        CHECK(rc == CA_OK);
        CHECK_EQ_U64(got, alpha);
        if (k == 0)
            printf("p=%" PRIu64 " d=%" PRIu64 ": %" PRIu64 " exps, %" PRIu64 " ops (sqrt p = %.0f)\n",
                   p, d, st.iterations, st.group_ops, sqrt((double)p));
    }
}


static void run_p_plus_1(const ca_group *g, const ca_elem *gen, uint64_t d,
                         const uint64_t *alphas, size_t nalpha)
{
    uint64_t p = g->order;
    size_t count = (size_t)(2 * d + 1);
    ca_elem *powers = calloc(count, sizeof(*powers));
    CHECK(powers != NULL);

    for (size_t i = 0; i < nalpha; i++) {
        uint64_t alpha = alphas[i] % p;
        CHECK(alpha != 0);
        CHECK(ca_cheon_make_instance_p_plus_1(g, gen, alpha, d, powers, count) == CA_OK);

        /* The helper must really produce P_i = [alpha^i]P. */
        ca_elem want;
        uint64_t scalar = 1;
        for (uint64_t j = 0; j <= 2 * d; j++) {
            ca_group_mul(g, &want, gen, scalar, NULL);
            CHECK(ca_group_equal(g, &want, &powers[j]));
            scalar = (uint64_t)(((ca_u128)scalar * alpha) % p);
        }

        uint64_t got = 0;
        ca_stats st = {0};
        ca_status rc = ca_cheon_solve_p_plus_1(g, powers, count, d, NULL, &got, &st);
        CHECK(rc == CA_OK);
        CHECK_EQ_U64(got, alpha);
        printf("p+1: p=%" PRIu64 " d=%" PRIu64 " alpha=%" PRIu64
               ": %" PRIu64 " exps, %" PRIu64 " ops\n",
               p, d, alpha, st.iterations, st.group_ops);
    }

    free(powers);
}

int main(void)
{
    ca_group g;
    ca_elem gen;
    /* Z_q^* subgroup of prime order p where p-1 has a balanced divisor.
     * p = 1000000009 - is it prime? p-1 = 2^3 * 3 * 41666667 */
    uint64_t p = 1000000009ULL;
    CHECK(ca_is_prime(p));
    /* find q = 2*k*p + 1 prime so the order-p subgroup of Z_q^* exists */
    uint64_t q = 0;
    for (uint64_t k = 1; k < 100000; k++) {
        if (ca_is_prime(2 * k * p + 1)) { q = 2 * k * p + 1; break; }
    }
    CHECK(q != 0);
    CHECK(ca_group_zp_init(&g, q, p) == CA_OK);
    CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);
    double cost;
    uint64_t best = ca_cheon_best_divisor(p, &cost);
    printf("best d for p=%" PRIu64 " is %" PRIu64 " (%.0f exps)\n", p, best, cost);
    run(&g, &gen, best, 3);
    run(&g, &gen, 24, 2);
    run(&g, &gen, 1, 1);     /* degenerates to a sqrt(p) exponentiation BSGS */
    run(&g, &gen, p - 1, 1); /* other extreme */

    /* A prime p with p-1 = 2 * 3 * 5 * 7 * 11 * 13 * 17 * 19 * 23 * k form to get d ~ sqrt(p) */
    uint64_t base = 2ULL * 3 * 5 * 7 * 11 * 13 * 17 * 19 * 23 * 29;
    uint64_t p2 = 0;
    for (uint64_t k = 1; k < 100000; k++) {
        if (ca_is_prime(base * k + 1)) { p2 = base * k + 1; break; }
    }
    CHECK(p2 != 0);
    uint64_t q2 = 0;
    for (uint64_t k = 1; k < 100000; k++) {
        if (ca_is_prime(2 * k * p2 + 1)) { q2 = 2 * k * p2 + 1; break; }
    }
    CHECK(q2 != 0);
    CHECK(ca_group_zp_init(&g, q2, p2) == CA_OK);
    CHECK(ca_group_find_generator(&g, &gen, 2) == CA_OK);
    best = ca_cheon_best_divisor(p2, &cost);
    printf("best d for p=%" PRIu64 " is %" PRIu64 " (%.0f exps)\n", p2, best, cost);
    run(&g, &gen, best, 3);

    /* Elliptic curve group of prime order */
    fx_ec(&g, &gen, 1000000007ULL, 3, 11);
    if (ca_is_prime(g.order)) {
        best = ca_cheon_best_divisor(g.order, &cost);
        printf("ec: p=%" PRIu64 " best d=%" PRIu64 " (%.0f exps)\n", g.order, best, cost);
        run(&g, &gen, best, 2);
    }
    /* invalid d */
    ca_elem ga, gad;
    uint64_t got;
    ca_group_zp_init(&g, q, p);
    ca_group_find_generator(&g, &gen, 1);
    ca_cheon_make_instance(&g, &gen, 5, 24, &ga, &gad);
    CHECK((p - 1) % 11 != 0);
    CHECK(ca_cheon_solve(&g, &gen, &ga, &gad, 11, NULL, &got, NULL) == CA_ERR_INVALID);

    /* Cheon's p+1 variant: p+1 = 2 * 5 * 17 * 5882353, so d=170
     * keeps the auxiliary sequence small while reducing the torus search
     * to order (p+1)/d = 5882353. */
    {
        const uint64_t pplus_d = 170;
        const uint64_t alphas[] = {2, 42424242, 987654321};
        CHECK((p + 1) % pplus_d == 0);
        run_p_plus_1(&g, &gen, pplus_d, alphas, sizeof(alphas) / sizeof(alphas[0]));

        size_t count = (size_t)(2 * pplus_d + 1);
        ca_elem *powers = calloc(count, sizeof(*powers));
        CHECK(powers != NULL);
        CHECK(ca_cheon_make_instance_p_plus_1(&g, &gen, 42424242, pplus_d,
                                              powers, count) == CA_OK);
        CHECK(ca_cheon_solve_p_plus_1(&g, powers, count - 1, pplus_d,
                                      NULL, &got, NULL) == CA_ERR_INVALID);
        CHECK((p + 1) % 11 != 0);
        CHECK(ca_cheon_solve_p_plus_1(&g, powers, count, 11,
                                      NULL, &got, NULL) == CA_ERR_INVALID);
        free(powers);
    }
    TEST_MAIN_END();
}
