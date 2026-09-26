#include "test_fixtures.h"

static void run_matrix(const ca_group *g, const ca_elem *gen, const char *name)
{
    uint64_t n = g->order;
    ca_rng rng;
    ca_rng_seed(&rng, 7);
    for (int k = 0; k < 20; k++) {
        uint64_t x = ca_rng_below(&rng, n);
        ca_elem h;
        fx_instance(g, gen, x, &h);
        uint64_t got = 0;
        ca_stats st = {0};
        ca_status rc = ca_bsgs_solve(g, gen, &h, 0, 0, NULL, &got, &st);
        CHECK(rc == CA_OK);
        CHECK_EQ_U64(got, x);
        if (rc != CA_OK) fprintf(stderr, "  (%s) x=%" PRIu64 "\n", name, x);
        /* interval variant around x */
        uint64_t lo = x > 1000 ? x - 1000 : 0;
        uint64_t hi = x + 5000 < n ? x + 5000 : n - 1;
        CHECK(ca_bsgs_solve(g, gen, &h, lo, hi, NULL, &got, NULL) == CA_OK);
        CHECK_EQ_U64(got, x);
        /* interval that excludes x must fail cleanly */
        if (x > 10 && x + 100 < n) {
            CHECK(ca_bsgs_solve(g, gen, &h, x + 1, x + 100, NULL, &got, NULL) == CA_ERR_NOT_FOUND);
        }
    }
    /* edge: x = 0 and x = n-1 */
    ca_elem h;
    uint64_t got;
    fx_instance(g, gen, 0, &h);
    CHECK(ca_bsgs_solve(g, gen, &h, 0, 0, NULL, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, 0);
    fx_instance(g, gen, n - 1, &h);
    CHECK(ca_bsgs_solve(g, gen, &h, 0, 0, NULL, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, n - 1);
}

int main(void)
{
    ca_group g;
    ca_elem gen;
    fx_zp_safe(&g, &gen, 2000000579ULL); /* 2q+1 with q = 1000000289 */
    run_matrix(&g, &gen, "zp");
    fx_ec(&g, &gen, 1000003, 1, 7);
    run_matrix(&g, &gen, "ec");
    /* amortised table reuse */
    ca_bsgs_table *t;
    CHECK(ca_bsgs_table_new(&g, &gen, 4096, &t) == CA_OK);
    for (uint64_t x = 1; x < g.order; x += g.order / 13) {
        ca_elem h;
        uint64_t got;
        fx_instance(&g, &gen, x, &h);
        CHECK(ca_bsgs_table_solve(t, &h, 0, 0, &got, NULL) == CA_OK);
        CHECK_EQ_U64(got, x);
    }
    ca_bsgs_table_free(t);
    /* explicit small table forces many giant steps */
    ca_bsgs_params p;
    ca_bsgs_params_default(&p);
    p.table_size = 16;
    ca_elem h;
    uint64_t got;
    fx_instance(&g, &gen, 123456, &h);
    CHECK(ca_bsgs_solve(&g, &gen, &h, 0, 0, &p, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, 123456);
    p.max_ops = 100;
    CHECK(ca_bsgs_solve(&g, &gen, &h, 0, 0, &p, &got, NULL) == CA_ERR_LIMIT);
    /* Counts are the one-step loops' at every table size around the batch
     * width: x = lo + i m + j is found at giant step i, after m baby-step
     * ops, the lo * base shift and i giant-step ops. */
    {
        const uint64_t sizes[] = {1, 2, 63, 64, 65, 127, 128, 129, 300};
        ca_rng rng;
        ca_rng_seed(&rng, 11);
        for (size_t si = 0; si < sizeof sizes / sizeof sizes[0]; si++) {
            ca_bsgs_params_default(&p);
            p.table_size = sizes[si];
            for (int k = 0; k < 40; k++) {
                uint64_t lo = ca_rng_below(&rng, g.order / 2);
                uint64_t x = lo + ca_rng_below(&rng, 64 * sizes[si] + 50);
                uint64_t hi = x + ca_rng_below(&rng, 1000);
                if (hi >= g.order) continue;
                ca_stats st = {0};
                fx_instance(&g, &gen, x, &h);
                CHECK(ca_bsgs_solve(&g, &gen, &h, lo, hi, &p, &got, &st) == CA_OK);
                CHECK_EQ_U64(got, x);
                uint64_t i = (x - lo) / sizes[si];
                /* plus the lo * base shift: popcount + bit length - 1 */
                uint64_t shift = lo ? (uint64_t)__builtin_popcountll(lo) + (63 - __builtin_clzll(lo)) : 0;
                CHECK_EQ_U64(st.iterations, i + 1);
                CHECK_EQ_U64(st.group_ops, sizes[si] + shift + i);
                CHECK_EQ_U64(st.table_entries, sizes[si]);
            }
        }
    }
    /* full multiplicative group of Z_p^* (composite order) */
    CHECK(ca_group_zp_init(&g, 1000003, 0) == CA_OK);
    const uint64_t w[4] = {2, 0, 0, 0};
    CHECK(ca_group_encode(&g, &gen, w));
    fx_instance(&g, &gen, 999999, &h);
    CHECK(ca_bsgs_solve(&g, &gen, &h, 0, 0, NULL, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, 999999);
    /* a base of order 3 stops the baby steps at j = 3, mid-block */
    {
        ca_elem b3;
        ca_group_mul(&g, &b3, &gen, (1000003 - 1) / 3, NULL);
        for (uint64_t x = 0; x < 3; x++) {
            ca_stats st = {0};
            fx_instance(&g, &b3, x, &h);
            CHECK(ca_bsgs_solve(&g, &b3, &h, 0, 2, NULL, &got, &st) == CA_OK);
            CHECK_EQ_U64(got, x);
        }
        ca_bsgs_table *t3;
        ca_bsgs_params_default(&p);
        CHECK(ca_bsgs_table_new(&g, &b3, 100, &t3) == CA_OK);
        for (uint64_t x = 0; x < 3; x++) {
            fx_instance(&g, &b3, x, &h);
            CHECK(ca_bsgs_table_solve(t3, &h, 0, 2, &got, NULL) == CA_OK);
            CHECK_EQ_U64(got, x);
        }
        ca_bsgs_table_free(t3);
    }
    TEST_MAIN_END();
}
