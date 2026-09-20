#include "test_fixtures.h"

/* Build a table to `gen` and solve `reps` random targets; check every answer
 * and report the precomputation and online cost in the natural units
 * (n^{2/3} for the build, n^{1/3} per online solve). */
static void run(const ca_group *g, const ca_elem *gen, const ca_precomp_params *base_params,
                int reps, double *pre_S, double *online_S)
{
    uint64_t n = g->order;
    ca_precomp_params pp = *base_params;
    ca_stats build = {0};
    ca_precomp_table *tab = NULL;
    CHECK(ca_precomp_table_new(g, gen, &pp, &tab, &build) == CA_OK);
    if (!tab) return;

    int32_t dpb = -1;
    uint64_t chains = 0, pre_ops = 0;
    uint32_t rr = 0;
    ca_precomp_table_info(tab, &dpb, &chains, &rr, &pre_ops);
    CHECK(dpb >= 1);
    CHECK(chains >= 1);
    CHECK(rr >= 2);
    CHECK(pre_ops > 0);
    CHECK_EQ_U64(pre_ops, build.group_ops);

    ca_rng rng;
    ca_rng_seed(&rng, 0x20260920ULL ^ n);
    double online = 0;
    for (int k = 0; k < reps; k++) {
        uint64_t x = ca_rng_below(&rng, n);
        ca_elem h;
        ca_group_mul(g, &h, gen, x, NULL);
        uint64_t got = 0;
        ca_stats s = {0};
        ca_status rc = ca_precomp_table_solve(tab, &h, &got, &s);
        CHECK(rc == CA_OK);
        CHECK_EQ_U64(got, x);
        online += (double)s.group_ops;
    }
    if (pre_S) *pre_S = (double)pre_ops / pow((double)n, 2.0 / 3.0);
    if (online_S) *online_S = online / reps / cbrt((double)n);
    ca_precomp_table_free(tab);
}

/* smallest safe prime p = 2q + 1 with p >= 2^(bits-1). */
static void safe_prime(unsigned bits, uint64_t *p, uint64_t *q)
{
    uint64_t cand = ((uint64_t)1 << (bits - 1)) | 3;
    for (;;) {
        cand = ca_next_prime(cand);
        uint64_t half = (cand - 1) / 2;
        if (ca_is_prime(half)) {
            *p = cand;
            *q = half;
            return;
        }
    }
}

int main(void)
{
    ca_precomp_params def;
    ca_precomp_params_default(&def);
    def.seed = 7;

    /* Z_p^* subgroup of a ~2^26 safe prime: the main correctness and cost
     * check, over 20 random targets sharing one precomputation. */
    uint64_t p = 0, q = 0;
    safe_prime(26, &p, &q);
    ca_group g;
    ca_elem gen;
    CHECK(ca_group_zp_init(&g, p, q) == CA_OK);
    CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);

    double pre_S = 0, online_S = 0;
    run(&g, &gen, &def, 20, &pre_S, &online_S);
    printf("zp  n=%" PRIu64 "  precomp S=%.3f n^2/3   online S=%.3f n^1/3\n", q, pre_S, online_S);
    CHECK(pre_S < 8.0);
    CHECK(online_S < 25.0);

    /* Edge targets against one shared table: the identity, the first few
     * exponents, and the last one. */
    ca_precomp_table *tab = NULL;
    CHECK(ca_precomp_table_new(&g, &gen, &def, &tab, NULL) == CA_OK);
    ca_elem h, id;
    uint64_t got = 12345;
    ca_group_identity(&g, &id);
    CHECK(ca_precomp_table_solve(tab, &id, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, 0);
    for (uint64_t x = 1; x <= 3; x++) {
        ca_group_mul(&g, &h, &gen, x, NULL);
        CHECK(ca_precomp_table_solve(tab, &h, &got, NULL) == CA_OK);
        CHECK_EQ_U64(got, x);
    }
    ca_group_mul(&g, &h, &gen, q - 1, NULL);
    CHECK(ca_precomp_table_solve(tab, &h, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, q - 1);

    /* A primitive root of Z_p^* has order p-1 = 2q, so it is not in the
     * order-q subgroup and has no logarithm to gen: a clean NOT_FOUND, and a
     * tight online budget turns the same query into a LIMIT. */
    uint64_t pr = ca_primitive_root(p);
    CHECK(pr != 0);
    ca_elem outside;
    const uint64_t w[4] = {pr, 0, 0, 0};
    CHECK(ca_group_encode(&g, &outside, w));
    CHECK(ca_precomp_table_solve(tab, &outside, &got, NULL) == CA_ERR_NOT_FOUND);
    ca_precomp_table_free(tab);

    ca_precomp_params lim = def;
    lim.max_online_ops = 32;
    CHECK(ca_precomp_solve(&g, &gen, &outside, &lim, &got, NULL) == CA_ERR_LIMIT);

    /* One-shot convenience on a fresh planted instance. */
    uint64_t x1 = 424242 % q;
    ca_group_mul(&g, &h, &gen, x1, NULL);
    CHECK(ca_precomp_solve(&g, &gen, &h, &def, &got, NULL) == CA_OK);
    CHECK_EQ_U64(got, x1);

    /* Explicit parameters: user-set dp_bits, table_size and r all still solve. */
    ca_precomp_params custom = def;
    custom.dp_bits = 7;
    custom.table_size = 512;
    custom.r = 16;
    run(&g, &gen, &custom, 8, NULL, NULL);

    /* max_precomp_ops caps the build to a smaller but still usable table. */
    ca_precomp_params capped = def;
    capped.max_precomp_ops = 2000;
    ca_stats cst = {0};
    ca_precomp_table *smalltab = NULL;
    CHECK(ca_precomp_table_new(&g, &gen, &capped, &smalltab, &cst) == CA_OK);
    CHECK(smalltab != NULL);
    uint64_t capped_ops = 0;
    ca_precomp_table_info(smalltab, NULL, NULL, NULL, &capped_ops);
    CHECK(capped_ops > 0);
    ca_precomp_table_free(smalltab);

    /* Threaded, batched build: many workers, a batch width for the inversion,
     * still every answer correct. */
    ca_precomp_params thr = def;
    thr.threads = 4;
    thr.walks = 64;
    run(&g, &gen, &thr, 8, NULL, NULL);

    /* Forced Bloom early-abort on an over-covered table: exercises the
     * filter and the merge accounting, and must not change any answer. */
    ca_precomp_params ea = def;
    ea.early_abort = 1;
    ea.coverage = 4.0;
    ea.threads = 2;
    ca_stats east = {0};
    ca_precomp_table *eatab = NULL;
    CHECK(ca_precomp_table_new(&g, &gen, &ea, &eatab, &east) == CA_OK);
    CHECK(eatab != NULL);
    for (uint64_t xx = 1; xx <= 8; xx++) {
        ca_group_mul(&g, &h, &gen, xx * 1000 % q, NULL);
        CHECK(ca_precomp_table_solve(eatab, &h, &got, NULL) == CA_OK);
        CHECK_EQ_U64(got, xx * 1000 % q);
    }
    ca_precomp_table_free(eatab);

    /* A known order is required. */
    ca_group g0 = g;
    g0.order = 0;
    ca_precomp_table *bad = NULL;
    CHECK(ca_precomp_table_new(&g0, &gen, &def, &bad, NULL) == CA_ERR_INVALID);

    /* Elliptic curve group with a large prime-order subgroup (~2^21+). */
    ca_group eg;
    ca_elem egen;
    uint64_t ep = ca_next_prime(((uint64_t)1 << 24) | 5);
    fx_ec(&eg, &egen, ep, 1, 1);
    double e_pre = 0, e_on = 0;
    run(&eg, &egen, &def, 12, &e_pre, &e_on);
    printf("ec  n=%" PRIu64 "  precomp S=%.3f n^2/3   online S=%.3f n^1/3\n", eg.order, e_pre,
           e_on);
    CHECK(e_pre < 12.0);
    CHECK(e_on < 30.0);

    TEST_MAIN_END();
}
