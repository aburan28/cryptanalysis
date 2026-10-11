#include "ec_tau_internal.h"
#include "generated/tau4_residue_atlas.h"
#include "generated/tau8_orbit_map.h"
#include "generated/tau8_hot_map.h"
#include "generated/tau8_pair_map.h"
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
    ca_tau4_pos_precomp global_pre;
    uint64_t prep_triples = 0;
    uint64_t global_triples = 0;
    CHECK(sizeof(positional_pre.point) == 36864);
    CHECK(ca_ec_tau4_pos_prepare(g, point, &positional_pre, &prep_triples));
    CHECK(ca_ec_tau4_pos_global_prepare(g, point, &global_pre, &global_triples));
    CHECK_EQ_U64(global_triples, prep_triples);
    CHECK(prep_triples > 0);
    for (size_t q = 0; q < CA_TAU_POS_Q; q++)
        for (size_t parity = 0; parity < 2; parity++)
            for (size_t j = 0; j < 9; j++) {
                const ca_elem *old = &positional_pre.point[q][parity][j];
                const ca_elem *fresh = &global_pre.point[q][parity][j];
                for (size_t word = 0; word < 4; word++) CHECK_EQ_U64(old->w[word], fresh->w[word]);
            }
    const uint64_t batch_scalars[] = {0, 1, 2, 3, g->order - 1, g->order, UINT64_MAX};
    const size_t batch_count = sizeof(batch_scalars) / sizeof(batch_scalars[0]);
    ca_elem batch_outputs[7], batch_expected[7];
    for (size_t i = 0; i < batch_count; i++)
        ca_group_mul(g, &batch_expected[i], point, batch_scalars[i] % g->order, NULL);
    const size_t blocks[] = {1, 2, 4, 7};
    for (size_t b = 0; b < sizeof(blocks) / sizeof(blocks[0]); b++) {
        uint64_t inversions = UINT64_MAX;
        CHECK(ca_ec_tau4_pos_mul_batch(g, &global_pre, batch_outputs, batch_scalars, batch_count,
                                       blocks[b], NULL, NULL, &inversions));
        uint64_t expected_inversions = 0;
        for (size_t offset = 0; offset < batch_count; offset += blocks[b]) {
            int nonidentity = 0;
            for (size_t i = offset; i < batch_count && i < offset + blocks[b]; i++) {
                CHECK(ca_group_equal(g, &batch_outputs[i], &batch_expected[i]));
                nonidentity |= !ca_group_is_identity(g, &batch_expected[i]);
            }
            expected_inversions += nonidentity;
        }
        CHECK_EQ_U64(inversions, expected_inversions);
    }
    ca_rng rng;
    ca_rng_seed(&rng, UINT64_C(0x20261004) ^ g->order);
    for (int i = 0; i < samples; i++) {
        uint64_t k =
            i < 8 ? (uint64_t[]){0, 1, 2, 3, g->order - 2, g->order - 1, g->order, UINT64_MAX}[i]
                  : ca_rng_next(&rng);
        ca_elem expected, baseline = *point, selected = *point, atlas = *point, tail = *point;
        ca_elem gated = *point, double_pair = *point;
        ca_elem positional = *point, global = *point;
        uint64_t base_triples = UINT64_MAX, base_adds = UINT64_MAX;
        uint64_t cost_triples = UINT64_MAX, cost_adds = UINT64_MAX;
        uint64_t atlas_triples = UINT64_MAX, atlas_adds = UINT64_MAX;
        uint64_t base_rotations = UINT64_MAX, atlas_rotations = UINT64_MAX;
        uint64_t tail_triples = UINT64_MAX, tail_adds = UINT64_MAX;
        uint64_t tail_rotations = UINT64_MAX;
        uint64_t gated_triples = UINT64_MAX, gated_adds = UINT64_MAX;
        uint64_t gated_rotations = UINT64_MAX;
        uint64_t double_triples = UINT64_MAX, double_adds = UINT64_MAX;
        uint64_t double_rotations = UINT64_MAX;
        ca_group_mul(g, &expected, point, k % g->order, NULL);
        CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &baseline, k, 0, &base_triples, &base_adds,
                                              &base_rotations));
        CHECK(ca_ec_tau4_mul_prepared_cost(g, &pre, &selected, k, &cost_triples, &cost_adds));
        CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &atlas, k, 2, &atlas_triples, &atlas_adds,
                                              &atlas_rotations));
        CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &tail, k, 3, &tail_triples, &tail_adds,
                                              &tail_rotations));
        CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &gated, k, 4, &gated_triples, &gated_adds,
                                              &gated_rotations));
        CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &double_pair, k, 5, &double_triples,
                                              &double_adds, &double_rotations));
        CHECK(ca_ec_tau4_tail_recode_compare_scalar(&pre, k));
        CHECK(ca_ec_tau4_double_recode_verify_scalar(&pre, k));
        uint64_t positional_adds = UINT64_MAX, positional_rotations = UINT64_MAX;
        CHECK(ca_ec_tau4_pos_mul(g, &positional_pre, &positional, k, &positional_adds,
                                 &positional_rotations));
        CHECK(ca_ec_tau4_pos_mul(g, &global_pre, &global, k, NULL, NULL));
        CHECK(ca_group_equal(g, &baseline, &expected));
        CHECK(ca_group_equal(g, &selected, &expected));
        CHECK(ca_group_equal(g, &atlas, &expected));
        CHECK(ca_group_equal(g, &tail, &expected));
        CHECK(ca_group_equal(g, &gated, &expected));
        CHECK(ca_group_equal(g, &double_pair, &expected));
        CHECK(10 * double_triples + 16 * double_adds + double_rotations <=
              10 * gated_triples + 16 * gated_adds + gated_rotations);
        CHECK_EQ_U64(gated_triples, tail_triples);
        CHECK_EQ_U64(gated_adds, tail_adds);
        CHECK_EQ_U64(gated_rotations, tail_rotations);
        CHECK(10 * tail_triples + 16 * tail_adds + tail_rotations <=
              10 * base_triples + 16 * base_adds + base_rotations);
        CHECK(ca_group_equal(g, &positional, &expected));
        CHECK(ca_group_equal(g, &global, &expected));
        CHECK_EQ_U64(base_triples, atlas_triples);
        CHECK_EQ_U64(base_adds, atlas_adds);
        CHECK_EQ_U64(base_rotations, atlas_rotations);
        CHECK(base_triples < 256 && base_adds < 256);
        CHECK(cost_triples < 256 && cost_adds < 256);
        CHECK(positional_adds < 256 && positional_rotations < 256);
        tau_cost_cases++;
    }
}

static void tau_atlas_recode_checks(void)
{
    const int offsets[] = {-162, -81, 0, 81, 162};
    for (int a = 0; a < 81; a++)
        for (int b = 0; b < 81; b++)
            for (size_t i = 0; i < 5; i++)
                for (size_t j = 0; j < 5; j++)
                    CHECK(ca_ec_tau4_recode_compare(a + offsets[i], b + offsets[j]));
    ca_rng rng;
    ca_rng_seed(&rng, UINT64_C(0x20261008));
    for (int i = 0; i < 10000; i++) {
        int64_t a = (int64_t)(ca_rng_next(&rng) >> 9);
        int64_t b = (int64_t)(ca_rng_next(&rng) >> 9);
        if (i & 1) a = -a;
        if (i & 2) b = -b;
        CHECK(ca_ec_tau4_recode_compare(a, b));
    }
    CHECK(ca_ec_tau4_recode_compare(INT64_MAX, INT64_MIN + 1));
    CHECK(ca_ec_tau4_recode_compare(0, 0));
}

/* Exercise the three direct tau evaluators and all six profile modes against
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
        for (int mode = 0; mode <= 5; mode++) {
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
    CHECK(!ca_ec_tau4_mul_prepared_profile(g, &pre, &got, 17, 6, NULL, NULL, NULL));
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
        ca_tau4_pos_precomp global_identity_pre;
        uint64_t triples = UINT64_MAX;
        CHECK(ca_ec_tau4_pos_prepare(&g, &identity, &identity_pre, &triples));
        CHECK_EQ_U64(triples, 0);
        triples = UINT64_MAX;
        CHECK(ca_ec_tau4_pos_global_prepare(&g, &identity, &global_identity_pre, &triples));
        CHECK_EQ_U64(triples, 0);
        CHECK(ca_ec_tau4_pos_mul(&g, &identity_pre, &got, 123, NULL, NULL));
        CHECK(ca_group_is_identity(&g, &got));
        CHECK(ca_ec_tau4_pos_mul(&g, &global_identity_pre, &got, 123, NULL, NULL));
        CHECK(ca_group_is_identity(&g, &got));
        const uint64_t identity_scalars[] = {0, 1, 123};
        ca_elem identity_outputs[3];
        uint64_t output_inversions = UINT64_MAX;
        CHECK(ca_ec_tau4_pos_mul_batch(&g, &global_identity_pre, identity_outputs, identity_scalars,
                                       3, 2, NULL, NULL, &output_inversions));
        CHECK_EQ_U64(output_inversions, 0);
        for (size_t j = 0; j < 3; j++) CHECK(ca_group_is_identity(&g, &identity_outputs[j]));
        CHECK(ca_ec_tau4_pos_mul_batch(NULL, NULL, NULL, NULL, 0, 0, NULL, NULL, NULL));
        CHECK(!ca_ec_tau4_pos_mul_batch(&g, &global_identity_pre, identity_outputs,
                                        identity_scalars, 3, 0, NULL, NULL, NULL));
    }
}

static void tau_fused_named(const char *name, size_t blocks)
{
    uint64_t p, a, b, order;
    if (strcmp(name, "j0-56") == 0) {
        p = UINT64_C(2305843009213693951);
        a = 0;
        b = 7;
        order = UINT64_C(53624256071278747);
    } else {
        CHECK(ca_curve_by_name(name, &p, &a, &b, &order) == CA_OK);
    }
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, p, a, b, order, &info) == CA_OK);
    ca_elem generator;
    CHECK(ca_group_find_generator(&g, &generator, 1) == CA_OK);
    for (int point_index = 0; point_index < 2; point_index++) {
        ca_elem point = generator;
        if (point_index) ca_group_mul(&g, &point, &generator, 37, NULL);
        ca_tau8_fused_precomp fused = {0};
        uint64_t triples = 0, prep_adds = 0, prep_rotations = 0;
        uint64_t prep_inversions = 0;
        CHECK(ca_ec_tau8_fused_prepare(&g, &point, blocks, &fused, &triples, &prep_adds,
                                       &prep_rotations, &prep_inversions));
        CHECK_EQ_U64(prep_adds, blocks * 29160);
        CHECK_EQ_U64(prep_inversions, blocks + 1);
        CHECK(triples > 0 && prep_rotations > 0);
        uint64_t scalars[256] = {0, 1, 2, 3, order - 2, order - 1, order, UINT64_MAX};
        ca_rng rng;
        ca_rng_seed(&rng, UINT64_C(0x20261010) ^ order ^ point_index);
        for (size_t i = 8; i < 256; i++) scalars[i] = ca_rng_next(&rng);
        ca_elem outputs[256], baseline[256], expected;
        uint64_t base_adds = 0, adds = 0, rotations = 0, inversions = 0;
        uint64_t fallbacks = 0;
        CHECK(ca_ec_tau4_pos_mul_batch(&g, &fused.pos, baseline, scalars, 256, 128, &base_adds,
                                       NULL, NULL));
        CHECK(ca_ec_tau8_fused_mul_batch(&g, &fused, outputs, scalars, 256, 128, &adds, &rotations,
                                         &inversions, &fallbacks));
        CHECK(adds < base_adds);
        CHECK_EQ_U64(rotations, 0);
        CHECK_EQ_U64(fallbacks, 0);
        CHECK(inversions <= 2);
        for (size_t i = 0; i < 256; i++) {
            ca_group_mul(&g, &expected, &point, scalars[i] % order, NULL);
            CHECK(ca_group_equal(&g, &outputs[i], &expected));
            CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        }
        ca_tau8_fused_precomp folded = {0};
        uint64_t folded_prep_adds = 0;
        CHECK(ca_ec_tau8_orbit_prepare(&g, &point, blocks, &folded, NULL, &folded_prep_adds, NULL,
                                       NULL));
        CHECK_EQ_U64(folded_prep_adds, blocks * 4860);
        uint64_t folded_adds = 0, folded_rotations = 0;
        uint64_t folded_inversions = 0, folded_fallbacks = 0;
        CHECK(ca_ec_tau8_fused_mul_batch(&g, &folded, outputs, scalars, 256, 128, &folded_adds,
                                         &folded_rotations, &folded_inversions, &folded_fallbacks));
        CHECK_EQ_U64(folded_adds, adds);
        CHECK(folded_rotations > 0);
        CHECK_EQ_U64(folded_inversions, inversions);
        CHECK_EQ_U64(folded_fallbacks, 0);
        for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        ca_tau8_fused_precomp hot = {0};
        uint64_t hot_prep_adds = 0, hot_adds = 0, hot_fallbacks = 0;
        CHECK(ca_ec_tau8_hot_prepare(&g, &point, blocks, &hot, NULL, &hot_prep_adds, NULL, NULL));
        CHECK_EQ_U64(hot_prep_adds, blocks * CA_TAU8_HOT_COUNT);
        CHECK(ca_ec_tau8_fused_mul_batch(&g, &hot, outputs, scalars, 256, 128, &hot_adds, NULL,
                                         NULL, &hot_fallbacks));
        CHECK(hot_adds >= folded_adds && hot_adds <= base_adds);
        CHECK(hot_fallbacks > 0);
        for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        ca_tau8_fused_precomp adapt2 = {0};
        uint64_t adapt2_prep_adds = 0, adapt2_adds = 0;
        uint64_t adapt2_recodes = 0;
        CHECK(ca_ec_tau8_hot_adapt2_prepare(&g, &point, blocks, &adapt2, NULL, &adapt2_prep_adds,
                                            NULL, NULL));
        CHECK_EQ_U64(adapt2_prep_adds, hot_prep_adds);
        CHECK(adapt2.selector == 1 && adapt2.orbit == 2);
        CHECK(ca_ec_tau8_fused_mul_batch_profile(&g, &adapt2, outputs, scalars, 256, 128,
                                                 &adapt2_adds, NULL, NULL, NULL, &adapt2_recodes,
                                                 NULL));
        CHECK(adapt2_adds < hot_adds);
        CHECK(adapt2_recodes > 0 && adapt2_recodes < 256);
        for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        ca_tau8_fused_precomp gated = {0};
        uint64_t gated_prep_adds = 0, gated_adds = 0, gated_recodes = 0;
        CHECK(ca_ec_tau8_hot_gated_prepare(&g, &point, blocks, &gated, NULL, &gated_prep_adds, NULL,
                                           NULL));
        CHECK_EQ_U64(gated_prep_adds, hot_prep_adds);
        CHECK(gated.selector == 2 && gated.orbit == 2);
        CHECK(ca_ec_tau8_fused_mul_batch_profile(&g, &gated, outputs, scalars, 256, 128,
                                                 &gated_adds, NULL, NULL, NULL, &gated_recodes,
                                                 NULL));
        CHECK(gated_adds >= adapt2_adds && gated_adds < hot_adds);
        CHECK(gated_recodes > 0 && gated_recodes < adapt2_recodes);
        for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        ca_tau8_fused_precomp steer = {0};
        uint64_t steer_prep_adds = 0, steer_adds = 0, steered_blocks = 0;
        CHECK(ca_ec_tau8_hot_steer_prepare(&g, &point, blocks, &steer, NULL, &steer_prep_adds, NULL,
                                           NULL));
        CHECK_EQ_U64(steer_prep_adds, hot_prep_adds);
        CHECK_EQ_U64(ca_ec_tau8_steer_static_bytes(), 13122);
        CHECK(steer.selector == 3 && steer.orbit == 2);
        CHECK(ca_ec_tau8_fused_mul_batch_profile(&g, &steer, outputs, scalars, 256, 128,
                                                 &steer_adds, NULL, NULL, NULL, NULL,
                                                 &steered_blocks));
        CHECK(steer_adds < hot_adds && steered_blocks > 0);
        for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        ca_tau8_fused_precomp gated2_steer = {0};
        uint64_t gated2_prep_adds = 0, gated2_adds = 0, gated2_recodes = 0;
        uint64_t gated2_steered_blocks = 0;
        CHECK(ca_ec_tau8_hot_gated2_steer_prepare(&g, &point, blocks, &gated2_steer, NULL,
                                                  &gated2_prep_adds, NULL, NULL));
        CHECK_EQ_U64(gated2_prep_adds, hot_prep_adds);
        CHECK(gated2_steer.selector == 4 && gated2_steer.orbit == 2);
        CHECK(ca_ec_tau8_fused_mul_batch_profile(&g, &gated2_steer, outputs, scalars, 256, 128,
                                                 &gated2_adds, NULL, NULL, NULL, &gated2_recodes,
                                                 &gated2_steered_blocks));
        CHECK(gated2_adds <= steer_adds);
        CHECK(gated2_recodes > 0 && gated2_recodes < 256);
        CHECK(gated2_steered_blocks > 0);
        for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        ca_tau_wide_precomp tapered = {0};
        int wide_schedule = strcmp(name, "j0-56") == 0 ? 1 : 0;
        uint64_t wide_prep_adds = 0, wide_adds = 0, wide_rotations = 0;
        uint64_t wide_inversions = 0, wide_fallbacks = 0;
        CHECK(ca_ec_tau_wide_prepare(&g, &point, wide_schedule, &tapered, NULL, &wide_prep_adds,
                                     NULL, NULL));
        CHECK(tapered.point != NULL && wide_prep_adds > gated2_prep_adds);
        CHECK_EQ_U64(tapered.point_offset[tapered.blocks], ca_ec_tau_wide_entries(wide_schedule));
        CHECK(ca_ec_tau_wide_static_bytes(wide_schedule) > 0);
        CHECK(ca_ec_tau_wide_mul_batch_profile(&g, &tapered, outputs, scalars, 256, 128, &wide_adds,
                                               &wide_rotations, &wide_inversions, &wide_fallbacks));
        CHECK(wide_adds > 0 && wide_rotations > 0);
        CHECK_EQ_U64(wide_inversions, 2);
        CHECK_EQ_U64(wide_fallbacks, 0);
        for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        ca_tau_wide_precomp graph = {0};
        uint64_t graph_prep_adds = 0, graph_adds = 0, graph_rotations = 0;
        uint64_t graph_inversions = 0, graph_fallbacks = 0;
        CHECK(ca_ec_tau_wide_prepare_graph(&g, &point, wide_schedule, &graph, NULL,
                                           &graph_prep_adds, NULL, &graph_inversions));
        CHECK_EQ_U64(graph_prep_adds, wide_schedule ? 267552 : 39096);
        CHECK_EQ_U64(graph_inversions, wide_schedule ? 6 : 5);
        CHECK(graph_prep_adds < wide_prep_adds);
        CHECK(ca_ec_tau_wide_graph_recipe_bytes(wide_schedule) > 0);
        if (point_index == 0)
            for (size_t i = 0; i < ca_ec_tau_wide_entries(wide_schedule); i++)
                CHECK(ca_group_equal(&g, &graph.point[i], &tapered.point[i]));
        CHECK(ca_ec_tau_wide_mul_batch_profile(&g, &graph, outputs, scalars, 256, 128, &graph_adds,
                                               &graph_rotations, NULL, &graph_fallbacks));
        CHECK_EQ_U64(graph_adds, wide_adds);
        CHECK_EQ_U64(graph_rotations, wide_rotations);
        CHECK_EQ_U64(graph_fallbacks, wide_fallbacks);
        for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        ca_tau_wide_precomp packed_graph = {0};
        uint64_t packed_prep_adds = 0, packed_adds = 0, packed_rotations = 0;
        uint64_t packed_inversions = 0, packed_fallbacks = 0, packed_slot_lookups = 0;
        CHECK(ca_ec_tau_wide_prepare_packed(&g, &point, wide_schedule, &packed_graph, NULL,
                                            &packed_prep_adds, NULL, &packed_inversions,
                                            &packed_slot_lookups));
        CHECK_EQ_U64(packed_prep_adds, graph_prep_adds);
        CHECK_EQ_U64(packed_inversions, graph_inversions);
        CHECK_EQ_U64(packed_slot_lookups, wide_schedule ? 267910 : 39368);
        CHECK_EQ_U64(ca_ec_tau_wide_packed_recipe_bytes(wide_schedule),
                     wide_schedule ? 358734 : 39426);
        if (point_index == 0)
            for (size_t i = 0; i < ca_ec_tau_wide_entries(wide_schedule); i++)
                CHECK(ca_group_equal(&g, &packed_graph.point[i], &graph.point[i]));
        CHECK(ca_ec_tau_wide_mul_batch_profile(&g, &packed_graph, outputs, scalars, 256, 128,
                                               &packed_adds, &packed_rotations, NULL,
                                               &packed_fallbacks));
        CHECK_EQ_U64(packed_adds, graph_adds);
        CHECK_EQ_U64(packed_rotations, graph_rotations);
        CHECK_EQ_U64(packed_fallbacks, graph_fallbacks);
        for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        ca_ec_tau_wide_clear(&packed_graph);
        ca_ec_tau_wide_clear(&graph);
        if (point_index == 0) {
            tapered.blocks = 1;
            wide_fallbacks = 0;
            CHECK(ca_ec_tau_wide_mul_batch_profile(&g, &tapered, outputs, scalars, 256, 128, NULL,
                                                   NULL, NULL, &wide_fallbacks));
            CHECK(wide_fallbacks > 0);
            for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
        }
        ca_ec_tau_wide_clear(&tapered);
        ca_ec_tau8_fused_clear(&gated2_steer);
        ca_ec_tau8_fused_clear(&steer);
        ca_ec_tau8_fused_clear(&gated);
        ca_ec_tau8_fused_clear(&adapt2);
        ca_ec_tau8_fused_clear(&hot);
        ca_ec_tau8_fused_clear(&folded);
        ca_ec_tau8_fused_clear(&fused);
        if (point_index == 0) {
            ca_tau8_fused_precomp short_table = {0};
            CHECK(ca_ec_tau8_fused_prepare(&g, &point, 1, &short_table, NULL, NULL, NULL, NULL));
            fallbacks = 0;
            CHECK(ca_ec_tau8_fused_mul_batch(&g, &short_table, outputs, scalars, 256, 128, NULL,
                                             NULL, NULL, &fallbacks));
            CHECK(fallbacks > 0);
            for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
            ca_ec_tau8_fused_clear(&short_table);
            ca_tau8_fused_precomp short_orbit = {0};
            CHECK(ca_ec_tau8_orbit_prepare(&g, &point, 1, &short_orbit, NULL, NULL, NULL, NULL));
            fallbacks = 0;
            CHECK(ca_ec_tau8_fused_mul_batch(&g, &short_orbit, outputs, scalars, 256, 128, NULL,
                                             NULL, NULL, &fallbacks));
            CHECK(fallbacks > 0);
            for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
            ca_ec_tau8_fused_clear(&short_orbit);
            ca_tau8_fused_precomp short_adapt2 = {0};
            CHECK(ca_ec_tau8_hot_adapt2_prepare(&g, &point, 1, &short_adapt2, NULL, NULL, NULL,
                                                NULL));
            fallbacks = 0;
            CHECK(ca_ec_tau8_fused_mul_batch(&g, &short_adapt2, outputs, scalars, 256, 128, NULL,
                                             NULL, NULL, &fallbacks));
            CHECK(fallbacks > 0);
            for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
            ca_ec_tau8_fused_clear(&short_adapt2);
            ca_tau8_fused_precomp short_gated = {0};
            CHECK(
                ca_ec_tau8_hot_gated_prepare(&g, &point, 1, &short_gated, NULL, NULL, NULL, NULL));
            fallbacks = 0;
            CHECK(ca_ec_tau8_fused_mul_batch(&g, &short_gated, outputs, scalars, 256, 128, NULL,
                                             NULL, NULL, &fallbacks));
            CHECK(fallbacks > 0);
            for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
            ca_ec_tau8_fused_clear(&short_gated);
            ca_tau8_fused_precomp short_steer = {0};
            CHECK(
                ca_ec_tau8_hot_steer_prepare(&g, &point, 1, &short_steer, NULL, NULL, NULL, NULL));
            fallbacks = 0;
            CHECK(ca_ec_tau8_fused_mul_batch(&g, &short_steer, outputs, scalars, 256, 128, NULL,
                                             NULL, NULL, &fallbacks));
            CHECK(fallbacks > 0);
            for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
            ca_ec_tau8_fused_clear(&short_steer);
            ca_tau8_fused_precomp short_gated2_steer = {0};
            CHECK(ca_ec_tau8_hot_gated2_steer_prepare(&g, &point, 1, &short_gated2_steer, NULL,
                                                      NULL, NULL, NULL));
            fallbacks = 0;
            CHECK(ca_ec_tau8_fused_mul_batch(&g, &short_gated2_steer, outputs, scalars, 256, 128,
                                             NULL, NULL, NULL, &fallbacks));
            CHECK(fallbacks > 0);
            for (size_t i = 0; i < 256; i++) CHECK(ca_group_equal(&g, &outputs[i], &baseline[i]));
            ca_ec_tau8_fused_clear(&short_gated2_steer);
        }
    }
    ca_elem identity;
    ca_group_identity(&g, &identity);
    ca_tau8_fused_precomp empty = {0};
    CHECK(ca_ec_tau8_fused_prepare(&g, &identity, blocks, &empty, NULL, NULL, NULL, NULL));
    CHECK(empty.point == NULL);
    const uint64_t scalars[] = {0, 1, UINT64_MAX};
    ca_elem outputs[3];
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &empty, outputs, scalars, 3, 2, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 3; i++) CHECK(ca_group_is_identity(&g, &outputs[i]));
    ca_ec_tau8_fused_clear(&empty);
    CHECK(ca_ec_tau8_hot_steer_prepare(&g, &identity, blocks, &empty, NULL, NULL, NULL, NULL));
    CHECK(empty.point == NULL && empty.selector == 3);
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &empty, outputs, scalars, 3, 2, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 3; i++) CHECK(ca_group_is_identity(&g, &outputs[i]));
    ca_ec_tau8_fused_clear(&empty);
    CHECK(
        ca_ec_tau8_hot_gated2_steer_prepare(&g, &identity, blocks, &empty, NULL, NULL, NULL, NULL));
    CHECK(empty.point == NULL && empty.selector == 4);
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &empty, outputs, scalars, 3, 2, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 3; i++) CHECK(ca_group_is_identity(&g, &outputs[i]));
    ca_ec_tau8_fused_clear(&empty);
    for (int schedule = 0; schedule < 2; schedule++) {
        ca_tau_wide_precomp empty_wide = {0};
        CHECK(ca_ec_tau_wide_prepare(&g, &identity, schedule, &empty_wide, NULL, NULL, NULL, NULL));
        CHECK(empty_wide.point == NULL);
        CHECK(ca_ec_tau_wide_mul_batch_profile(&g, &empty_wide, outputs, scalars, 3, 2, NULL, NULL,
                                               NULL, NULL));
        for (size_t i = 0; i < 3; i++) CHECK(ca_group_is_identity(&g, &outputs[i]));
        ca_ec_tau_wide_clear(&empty_wide);
        uint64_t packed_slot_lookups = 99;
        CHECK(ca_ec_tau_wide_prepare_packed(&g, &identity, schedule, &empty_wide, NULL, NULL, NULL,
                                            NULL, &packed_slot_lookups));
        CHECK(empty_wide.point == NULL);
        CHECK_EQ_U64(packed_slot_lookups, 0);
        CHECK(ca_ec_tau_wide_mul_batch_profile(&g, &empty_wide, outputs, scalars, 3, 2, NULL, NULL,
                                               NULL, NULL));
        for (size_t i = 0; i < 3; i++) CHECK(ca_group_is_identity(&g, &outputs[i]));
        ca_ec_tau_wide_clear(&empty_wide);
        ca_tau_wide_wavefront_stats wavefront_stats = {99, 99, 99, 99};
        CHECK(ca_ec_tau_wide_prepare_wavefront(&g, &identity, schedule, &empty_wide, NULL, NULL,
                                               NULL, NULL, &wavefront_stats));
        CHECK(empty_wide.point == NULL);
        CHECK_EQ_U64(wavefront_stats.slot_lookups, 0);
        CHECK_EQ_U64(wavefront_stats.denominators, 0);
        CHECK_EQ_U64(wavefront_stats.exceptional_edges, 0);
        CHECK_EQ_U64(wavefront_stats.doubling_edges, 0);
        ca_ec_tau_wide_clear(&empty_wide);
        CHECK(ca_ec_tau_wide_prepare_graph(&g, &identity, schedule, &empty_wide, NULL, NULL, NULL,
                                           NULL));
        CHECK(empty_wide.point == NULL);
        CHECK(ca_ec_tau_wide_mul_batch_profile(&g, &empty_wide, outputs, scalars, 3, 2, NULL, NULL,
                                               NULL, NULL));
        for (size_t i = 0; i < 3; i++) CHECK(ca_group_is_identity(&g, &outputs[i]));
        ca_ec_tau_wide_clear(&empty_wide);
    }
    CHECK(ca_ec_tau8_hot_adapt2_prepare(&g, &identity, blocks, &empty, NULL, NULL, NULL, NULL));
    CHECK(empty.point == NULL && empty.selector == 1);
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &empty, outputs, scalars, 3, 2, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 3; i++) CHECK(ca_group_is_identity(&g, &outputs[i]));
    ca_ec_tau8_fused_clear(&empty);
    CHECK(ca_ec_tau8_hot_gated_prepare(&g, &identity, blocks, &empty, NULL, NULL, NULL, NULL));
    CHECK(empty.point == NULL && empty.selector == 2);
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &empty, outputs, scalars, 3, 2, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 3; i++) CHECK(ca_group_is_identity(&g, &outputs[i]));
    ca_ec_tau8_fused_clear(&empty);
    CHECK(ca_ec_tau8_hot_prepare(&g, &identity, blocks, &empty, NULL, NULL, NULL, NULL));
    CHECK(empty.point == NULL);
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &empty, outputs, scalars, 3, 2, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 3; i++) CHECK(ca_group_is_identity(&g, &outputs[i]));
    ca_ec_tau8_fused_clear(&empty);
    CHECK(ca_ec_tau8_orbit_prepare(&g, &identity, blocks, &empty, NULL, NULL, NULL, NULL));
    CHECK(empty.point == NULL);
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &empty, outputs, scalars, 3, 2, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 3; i++) CHECK(ca_group_is_identity(&g, &outputs[i]));
    ca_ec_tau8_fused_clear(&empty);
}

static void tau_wavefront_tables(void)
{
    for (int curve_index = 0; curve_index < 2; curve_index++) {
        uint64_t p, a, b, order;
        if (curve_index) {
            p = UINT64_C(2305843009213693951);
            a = 0;
            b = 7;
            order = UINT64_C(53624256071278747);
        } else {
            CHECK(ca_curve_by_name("glv-j0-32", &p, &a, &b, &order) == CA_OK);
        }
        ca_group g;
        ca_curve_info info;
        CHECK(ca_curve_group(&g, p, a, b, order, &info) == CA_OK);
        ca_elem generator;
        CHECK(ca_group_find_generator(&g, &generator, 1) == CA_OK);
        int schedule = curve_index;
        const uint64_t multiples[] = {1, 37, 101, 103};
        for (size_t case_index = 0; case_index < 4; case_index++) {
            ca_elem point;
            ca_group_mul(&g, &point, &generator, multiples[case_index], NULL);
            ca_tau_wide_precomp packed = {0}, wavefront = {0};
            ca_tau_wide_wavefront_stats stats = {0};
            uint64_t packed_adds = 0, packed_rotations = 0, packed_inversions = 0;
            uint64_t wavefront_adds = 0, wavefront_rotations = 0, wavefront_inversions = 0;
            CHECK(ca_ec_tau_wide_prepare_packed(&g, &point, schedule, &packed, NULL, &packed_adds,
                                                &packed_rotations, &packed_inversions, NULL));
            CHECK(ca_ec_tau_wide_prepare_wavefront(&g, &point, schedule, &wavefront, NULL,
                                                   &wavefront_adds, &wavefront_rotations,
                                                   &wavefront_inversions, &stats));
            CHECK_EQ_U64(wavefront_adds, packed_adds);
            CHECK_EQ_U64(wavefront_rotations, packed_rotations);
            CHECK_EQ_U64(wavefront_inversions, 9);
            CHECK_EQ_U64(stats.slot_lookups, curve_index ? 267910 : 39368);
            CHECK_EQ_U64(stats.denominators, packed_adds);
            CHECK_EQ_U64(stats.exceptional_edges, 0);
            CHECK_EQ_U64(stats.doubling_edges, 0);
            CHECK(ca_ec_tau_wide_wavefront_temp_bytes(schedule) >
                  ca_ec_tau_wide_temp_bytes(schedule));
            for (size_t i = 0; i < ca_ec_tau_wide_entries(schedule); i++)
                CHECK(ca_group_equal(&g, &wavefront.point[i], &packed.point[i]));
            ca_ec_tau_wide_clear(&wavefront);
            ca_ec_tau_wide_clear(&packed);
        }
    }
}

static void tau_fused_small_order(void)
{
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, 97, 0, 2, 13, &info) == CA_OK);
    ca_elem point;
    CHECK(ca_group_find_generator(&g, &point, 1) == CA_OK);
    ca_tau8_fused_precomp pre = {0};
    CHECK(ca_ec_tau8_fused_prepare(&g, &point, 2, &pre, NULL, NULL, NULL, NULL));
    ca_tau8_fused_precomp orbit = {0};
    CHECK(ca_ec_tau8_orbit_prepare(&g, &point, 2, &orbit, NULL, NULL, NULL, NULL));
    ca_tau8_fused_precomp hot = {0};
    CHECK(ca_ec_tau8_hot_prepare(&g, &point, 2, &hot, NULL, NULL, NULL, NULL));
    ca_tau8_fused_precomp adapt2 = {0};
    CHECK(ca_ec_tau8_hot_adapt2_prepare(&g, &point, 2, &adapt2, NULL, NULL, NULL, NULL));
    ca_tau8_fused_precomp gated = {0};
    CHECK(ca_ec_tau8_hot_gated_prepare(&g, &point, 2, &gated, NULL, NULL, NULL, NULL));
    ca_tau8_fused_precomp steer = {0};
    CHECK(ca_ec_tau8_hot_steer_prepare(&g, &point, 2, &steer, NULL, NULL, NULL, NULL));
    ca_tau8_fused_precomp gated2_steer = {0};
    CHECK(
        ca_ec_tau8_hot_gated2_steer_prepare(&g, &point, 2, &gated2_steer, NULL, NULL, NULL, NULL));
    uint64_t beta = g.endo_c_mont;
    uint64_t beta2 = ca_mont_mul(&g.mont, beta, beta);
    uint64_t tau_lambda = (1 + g.endo_lambda) % g.order;
    uint64_t tau8 = 1;
    for (int i = 0; i < 8; i++) tau8 = ca_mulmod(tau8, tau_lambda, g.order);
    uint64_t factor = 1;
    for (size_t block = 0; block < 2; block++) {
        for (size_t u = 0; u < 217; u++) {
            for (size_t v = 0; v < 217; v++) {
                uint16_t id = ca_tau8_pair_map[217 * u + v];
                if (id == UINT16_MAX) continue;
                ca_tau4_atlas_pattern x = ca_tau4_atlas_patterns[u];
                ca_tau4_atlas_pattern y = ca_tau4_atlas_patterns[v];
                int64_t a = x.correction_a - 9 * (2 * y.correction_a + 3 * y.correction_b);
                int64_t b = x.correction_b + 9 * (y.correction_a + y.correction_b);
                int64_t scalar = (a + b * (int64_t)tau_lambda) % (int64_t)g.order;
                if (scalar < 0) scalar += (int64_t)g.order;
                scalar = (int64_t)ca_mulmod((uint64_t)scalar, factor, g.order);
                ca_elem want;
                ca_group_mul(&g, &want, &point, (uint64_t)scalar, NULL);
                CHECK(ca_group_equal(&g, &pre.point[block * CA_TAU8_PAIR_COUNT + id], &want));
                size_t pair = 217 * u + v;
                uint16_t orbit_id = ca_tau8_orbit_id[pair];
                uint8_t unit = ca_tau8_orbit_unit[pair];
                CHECK(orbit_id < CA_TAU8_ORBIT_COUNT && unit < 6);
                ca_elem transformed = orbit.point[block * CA_TAU8_ORBIT_COUNT + orbit_id];
                if (!transformed.w[2]) {
                    if (unit % 3 == 1)
                        transformed.w[0] = ca_mont_mul(&g.mont, beta, transformed.w[0]);
                    else if (unit % 3 == 2)
                        transformed.w[0] = ca_mont_mul(&g.mont, beta2, transformed.w[0]);
                    if (unit >= 3 && transformed.w[1]) transformed.w[1] = g.p - transformed.w[1];
                }
                CHECK(ca_group_equal(&g, &transformed, &want));
            }
        }
        factor = ca_mulmod(factor, tau8, g.order);
    }
    uint64_t scalars[27];
    ca_elem outputs[27], expected;
    for (size_t i = 0; i < 26; i++) scalars[i] = i;
    scalars[26] = UINT64_MAX;
    for (int wide_schedule = 0; wide_schedule < 2; wide_schedule++) {
        ca_tau_wide_precomp wavefront = {0};
        ca_tau_wide_wavefront_stats wavefront_stats = {0};
        CHECK(ca_ec_tau_wide_prepare_wavefront(&g, &point, wide_schedule, &wavefront, NULL, NULL,
                                               NULL, NULL, &wavefront_stats));
        CHECK(wavefront_stats.exceptional_edges > 0);
        CHECK(ca_ec_tau_wide_mul_batch_profile(&g, &wavefront, outputs, scalars, 27, 7, NULL, NULL,
                                               NULL, NULL));
        for (size_t i = 0; i < 27; i++) {
            ca_group_mul(&g, &expected, &point, scalars[i] % 13, NULL);
            CHECK(ca_group_equal(&g, &outputs[i], &expected));
        }
        ca_ec_tau_wide_clear(&wavefront);
    }
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &pre, outputs, scalars, 27, 7, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 27; i++) {
        ca_group_mul(&g, &expected, &point, scalars[i] % 13, NULL);
        CHECK(ca_group_equal(&g, &outputs[i], &expected));
    }
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &orbit, outputs, scalars, 27, 7, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 27; i++) {
        ca_group_mul(&g, &expected, &point, scalars[i] % 13, NULL);
        CHECK(ca_group_equal(&g, &outputs[i], &expected));
    }
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &hot, outputs, scalars, 27, 7, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 27; i++) {
        ca_group_mul(&g, &expected, &point, scalars[i] % 13, NULL);
        CHECK(ca_group_equal(&g, &outputs[i], &expected));
    }
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &adapt2, outputs, scalars, 27, 7, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 27; i++) {
        ca_group_mul(&g, &expected, &point, scalars[i] % 13, NULL);
        CHECK(ca_group_equal(&g, &outputs[i], &expected));
    }
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &gated, outputs, scalars, 27, 7, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 27; i++) {
        ca_group_mul(&g, &expected, &point, scalars[i] % 13, NULL);
        CHECK(ca_group_equal(&g, &outputs[i], &expected));
    }
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &steer, outputs, scalars, 27, 7, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 27; i++) {
        ca_group_mul(&g, &expected, &point, scalars[i] % 13, NULL);
        CHECK(ca_group_equal(&g, &outputs[i], &expected));
    }
    ca_ec_tau8_fused_clear(&steer);
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &gated2_steer, outputs, scalars, 27, 7, NULL, NULL, NULL,
                                     NULL));
    for (size_t i = 0; i < 27; i++) {
        ca_group_mul(&g, &expected, &point, scalars[i] % 13, NULL);
        CHECK(ca_group_equal(&g, &outputs[i], &expected));
    }
    ca_ec_tau8_fused_clear(&gated2_steer);
    for (int schedule = 0; schedule < 2; schedule++) {
        ca_tau_wide_precomp wide = {0};
        CHECK(ca_ec_tau_wide_prepare(&g, &point, schedule, &wide, NULL, NULL, NULL, NULL));
        CHECK(ca_ec_tau_wide_mul_batch_profile(&g, &wide, outputs, scalars, 27, 7, NULL, NULL, NULL,
                                               NULL));
        for (size_t i = 0; i < 27; i++) {
            ca_group_mul(&g, &expected, &point, scalars[i] % 13, NULL);
            CHECK(ca_group_equal(&g, &outputs[i], &expected));
        }
        ca_ec_tau_wide_clear(&wide);
    }
    ca_ec_tau8_fused_clear(&gated);
    ca_ec_tau8_fused_clear(&adapt2);
    ca_ec_tau8_fused_clear(&hot);
    ca_ec_tau8_fused_clear(&orbit);
    ca_ec_tau8_fused_clear(&pre);
}

int main(void)
{
    tau_atlas_recode_checks();
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
    tau_fused_named("glv-j0-32", 4);
    tau_fused_named("j0-56", 6);
    tau_wavefront_tables();
    tau_fused_small_order();
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
