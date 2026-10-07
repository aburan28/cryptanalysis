#include "ec_tau_internal.h"
#include "test_fixtures.h"
#include "../experiments/prime-j0-hot-orbit-table/hot64_selected.h"
#include <string.h>

static void check_pair(const ca_group *g, const ca_tau4_joint_precomp *pre,
                       const ca_tau4_orbit_precomp *orbit,
                       const ca_tau4_hot_precomp *hot,
                       const ca_elem *p, const ca_elem *q, uint64_t a, uint64_t b,
                       uint64_t *saved_tau, uint64_t *saved_full)
{
    ca_elem ap, bq, expected, separate, joint, fused, paired, paired_five, paired_two;
    ca_elem paired_gauge;
    ca_group_mul(g, &ap, p, a % g->order, NULL);
    ca_group_mul(g, &bq, q, b % g->order, NULL);
    ca_group_op(g, &expected, &ap, &bq);
    ca_tau4_joint_counts two = {0}, one = {0};
    CHECK(ca_ec_tau4_joint_mul_profile(g, pre, &separate, a, b, 0, &two));
    CHECK(ca_ec_tau4_joint_mul_profile(g, pre, &joint, a, b, 1, &one));
    CHECK(ca_group_equal(g, &separate, &expected));
    CHECK(ca_group_equal(g, &joint, &expected));
    ca_tau4_joint_counts paired_cost = {0};
    CHECK(ca_ec_tau4_paired_lattice_mul_profile(g, pre, &paired, a, b, &paired_cost));
    CHECK(ca_group_equal(g, &paired, &expected));
    CHECK(paired_cost.recode_attempts <= 50);
    CHECK(paired_cost.pair_scores <= 625);
    CHECK(paired_cost.selected_changed <= 1);
    ca_tau4_joint_counts five_cost = {0};
    CHECK(ca_ec_tau4_paired_five_mul_profile(g, pre, &paired_five, a, b, &five_cost));
    CHECK(ca_group_equal(g, &paired_five, &expected));
    CHECK(five_cost.recode_attempts <= 10);
    CHECK(five_cost.pair_scores <= 25);
    ca_tau4_joint_counts two_cost = {0};
    CHECK(ca_ec_tau4_paired_two_mul_profile(g, pre, &paired_two, a, b, &two_cost));
    CHECK(ca_group_equal(g, &paired_two, &expected));
    CHECK(two_cost.recode_attempts <= 4);
    CHECK(two_cost.pair_scores <= 4);
    ca_tau4_joint_counts gauge_cost = {0};
    CHECK(ca_ec_tau4_paired_two_gauge_mul_profile(g, pre, &paired_gauge,
                                                   a, b, &gauge_cost));
    CHECK(ca_group_equal(g, &paired_gauge, &expected));
    CHECK_EQ_U64(gauge_cost.recode_attempts, two_cost.recode_attempts);
    CHECK_EQ_U64(gauge_cost.pair_scores, two_cost.pair_scores);
    CHECK(gauge_cost.gauge_selected <= 1);
    if (orbit) {
        ca_tau4_joint_counts combined = {0};
        CHECK(ca_ec_tau4_orbit_mul_profile(g, orbit, &fused, a, b, &combined));
        CHECK(ca_group_equal(g, &fused, &expected));
        CHECK_EQ_U64(combined.tau_steps, one.tau_steps);
        CHECK_EQ_U64(combined.overlaps, one.overlaps);
        CHECK_EQ_U64(combined.fused_hits, one.overlaps);
        CHECK_EQ_U64(combined.inversions, one.inversions);
        CHECK(combined.mixed_adds <= one.mixed_adds);
        CHECK(combined.rotations <= one.rotations);
    }
    if (hot) {
        ca_tau4_joint_counts sparse = {0};
        ca_elem sparse_result;
        CHECK(ca_ec_tau4_hot_mul_profile(g, hot, &sparse_result, a, b, &sparse));
        CHECK(ca_group_equal(g, &sparse_result, &expected));
        CHECK_EQ_U64(sparse.tau_steps, one.tau_steps);
        CHECK_EQ_U64(sparse.overlaps, one.overlaps);
        CHECK_EQ_U64(sparse.inversions, one.inversions);
        CHECK(sparse.fused_hits <= one.overlaps);
        CHECK(sparse.mixed_adds <= one.mixed_adds);
    }
    CHECK_EQ_U64(one.mixed_adds, two.mixed_adds);
    CHECK_EQ_U64(one.full_adds, 0);
    CHECK_EQ_U64(one.inversions, two.inversions);
    if (two.tau_steps > one.tau_steps) *saved_tau += two.tau_steps - one.tau_steps;
    *saved_full += two.full_adds;
}

static void check_paired_batch(const ca_group *g, const ca_tau4_joint_precomp *pre,
                                const ca_elem *p, const ca_elem *q,
                                const uint64_t pairs[8][2], uint64_t expected_inversions)
{
    uint64_t a[8], b[8];
    ca_elem outputs[8], plane_outputs[8];
    for (size_t i = 0; i < 8; i++) { a[i] = pairs[i][0]; b[i] = pairs[i][1]; }
    ca_tau4_joint_counts batch = {0};
    CHECK(ca_ec_tau4_paired_two_batch_profile(g, pre, outputs, a, b, 8, &batch));
    CHECK_EQ_U64(batch.inversions, expected_inversions);
    ca_tau4_joint_plane_precomp plane;
    ca_tau4_joint_counts plane_prep = {0}, plane_batch = {0};
    CHECK(ca_ec_tau4_joint_plane_prepare(g, p, q, &plane, &plane_prep));
    CHECK(ca_ec_tau4_paired_two_plane_batch_profile(g, &plane,
                                                      plane_outputs, a, b, 8,
                                                      &plane_batch));
    CHECK_EQ_U64(plane_batch.inversions, expected_inversions);
    CHECK_EQ_U64(plane_batch.rotations, 0);
    CHECK_EQ_U64(plane_batch.tau_steps, batch.tau_steps);
    CHECK_EQ_U64(plane_batch.mixed_adds, batch.mixed_adds);
    CHECK_EQ_U64(plane_batch.recode_attempts, batch.recode_attempts);
    CHECK_EQ_U64(plane_batch.pair_scores, batch.pair_scores);
    if (ca_group_is_identity(g, p) && ca_group_is_identity(g, q))
        CHECK_EQ_U64(plane_prep.rotations, 0);
    else CHECK(plane_prep.rotations > 0);
    ca_tau4_joint_counts separate = {0};
    for (size_t i = 0; i < 8; i++) {
        ca_elem one, ap, bq, expected;
        ca_tau4_joint_counts counts = {0};
        CHECK(ca_ec_tau4_paired_two_mul_profile(g, pre, &one, a[i], b[i], &counts));
        ca_group_mul(g, &ap, p, a[i] % g->order, NULL);
        ca_group_mul(g, &bq, q, b[i] % g->order, NULL);
        ca_group_op(g, &expected, &ap, &bq);
        CHECK(ca_group_equal(g, &outputs[i], &one));
        CHECK(ca_group_equal(g, &outputs[i], &expected));
        CHECK(ca_group_equal(g, &plane_outputs[i], &expected));
        ca_elem plane_one;
        ca_tau4_joint_counts plane_counts = {0};
        CHECK(ca_ec_tau4_paired_two_plane_mul_profile(g, &plane,
                                                       &plane_one, a[i], b[i],
                                                       &plane_counts));
        CHECK(ca_group_equal(g, &plane_one, &expected));
        CHECK_EQ_U64(plane_counts.rotations, 0);
        separate.tau_steps += counts.tau_steps;
        separate.mixed_adds += counts.mixed_adds;
        separate.rotations += counts.rotations;
        separate.recode_attempts += counts.recode_attempts;
        separate.pair_scores += counts.pair_scores;
    }
    CHECK_EQ_U64(batch.tau_steps, separate.tau_steps);
    CHECK_EQ_U64(batch.mixed_adds, separate.mixed_adds);
    CHECK_EQ_U64(batch.rotations, separate.rotations);
    CHECK_EQ_U64(batch.recode_attempts, separate.recode_attempts);
    CHECK_EQ_U64(batch.pair_scores, separate.pair_scores);
}

static void check_curve(uint64_t p, uint64_t b, uint64_t order,
                        uint64_t base_x, uint64_t base_y)
{
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, p, 0, b, order, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J0);
    uint64_t words[4] = {base_x, base_y, 0, 0};
    ca_elem base, other, id;
    CHECK(ca_group_encode(&g, &base, words));
    ca_group_mul(&g, &other, &base, 37, NULL);
    ca_group_identity(&g, &id);
    ca_tau4_joint_precomp pre;
    ca_tau4_joint_counts prep = {0};
    CHECK(ca_ec_tau4_joint_prepare(&g, &base, &other, &pre, &prep));
    CHECK_EQ_U64(prep.tau_steps, 2);
    CHECK_EQ_U64(prep.doubles, 10);
    CHECK_EQ_U64(prep.mixed_adds, 8);
    CHECK_EQ_U64(prep.inversions, 1);
    ca_tau4_orbit_precomp orbit;
    ca_tau4_joint_counts orbit_prep = {0};
    CHECK(ca_ec_tau4_orbit_prepare(&g, &base, &other, &orbit, &orbit_prep));
    CHECK_EQ_U64(orbit_prep.mixed_adds, 8 + 486);
    CHECK_EQ_U64(orbit_prep.inversions, 2);
    const uint16_t *selected = order == UINT64_C(23729779)
        ? ca_hot64_j0_32 : ca_hot64_j0_56;
    ca_tau4_hot_precomp hot;
    ca_tau4_joint_counts hot_prep = {0};
    CHECK(ca_ec_tau4_hot_prepare(&g, &base, &other, selected, &hot, &hot_prep));
    CHECK_EQ_U64(hot_prep.mixed_adds, 8 + 64);
    CHECK_EQ_U64(hot_prep.inversions, 2);
    uint16_t duplicate[64];
    memcpy(duplicate, selected, sizeof(duplicate));
    duplicate[1] = duplicate[0];
    ca_tau4_hot_precomp untouched;
    memset(&untouched, 0x5a, sizeof(untouched));
    ca_tau4_hot_precomp before = untouched;
    CHECK(!ca_ec_tau4_hot_prepare(&g, &base, &other, duplicate, &untouched, NULL));
    CHECK(memcmp(&untouched, &before, sizeof(untouched)) == 0);

    uint64_t saved_tau = 0, saved_full = 0;
    const uint64_t edge[][2] = {
        {0, 0}, {1, 0}, {0, 1}, {1, 1}, {2, 3},
        {order - 1, order - 1}, {order, 2 * order},
        {UINT64_MAX, UINT64_MAX}, {UINT64_MAX, order - 1},
    };
    check_paired_batch(&g, &pre, &base, &other, edge, 1);
    for (size_t i = 0; i < sizeof(edge) / sizeof(edge[0]); i++)
        check_pair(&g, &pre, &orbit, &hot, &base, &other, edge[i][0], edge[i][1],
                   &saved_tau, &saved_full);
    ca_rng rng;
    ca_rng_seed(&rng, UINT64_C(0x20261007) ^ order);
    for (int i = 0; i < 512; i++) {
        uint64_t scalar_a = ca_rng_next(&rng), scalar_b = ca_rng_next(&rng);
        check_pair(&g, &pre, &orbit, &hot, &base, &other, scalar_a, scalar_b,
                   &saved_tau, &saved_full);
    }
    CHECK(saved_tau > 0);
    CHECK(saved_full > 0);

    ca_tau4_joint_precomp with_identity;
    CHECK(ca_ec_tau4_joint_prepare(&g, &base, &id, &with_identity, &prep));
    CHECK_EQ_U64(prep.inversions, 1);
    CHECK_EQ_U64(prep.tau_steps, 1);
    CHECK(ca_ec_tau4_orbit_prepare(&g, &base, &id, &orbit, &orbit_prep));
    CHECK(ca_ec_tau4_hot_prepare(&g, &base, &id, selected, &hot, &hot_prep));
    check_pair(&g, &with_identity, &orbit, &hot, &base, &id, 123, 987,
               &saved_tau, &saved_full);
    CHECK(ca_ec_tau4_joint_prepare(&g, &id, &id, &with_identity, &prep));
    CHECK_EQ_U64(prep.inversions, 0);
    CHECK(ca_ec_tau4_orbit_prepare(&g, &id, &id, &orbit, &orbit_prep));
    CHECK(ca_ec_tau4_hot_prepare(&g, &id, &id, selected, &hot, &hot_prep));
    check_pair(&g, &with_identity, &orbit, &hot, &id, &id, UINT64_MAX, UINT64_MAX,
               &saved_tau, &saved_full);
    check_paired_batch(&g, &with_identity, &id, &id, edge, 0);

    CHECK(ca_ec_tau4_joint_prepare(&g, &base, &base, &with_identity, &prep));
    CHECK(ca_ec_tau4_orbit_prepare(&g, &base, &base, &orbit, &orbit_prep));
    CHECK(ca_ec_tau4_hot_prepare(&g, &base, &base, selected, &hot, &hot_prep));
    check_pair(&g, &with_identity, &orbit, &hot, &base, &base, 178, 178,
               &saved_tau, &saved_full);
    check_paired_batch(&g, &with_identity, &base, &base, edge, 1);
    ca_elem negative;
    ca_group_inv(&g, &negative, &base);
    CHECK(ca_ec_tau4_joint_prepare(&g, &base, &negative, &with_identity, &prep));
    CHECK(ca_ec_tau4_orbit_prepare(&g, &base, &negative, &orbit, &orbit_prep));
    CHECK(ca_ec_tau4_hot_prepare(&g, &base, &negative, selected, &hot, &hot_prep));
    check_pair(&g, &with_identity, &orbit, &hot, &base, &negative, 178, 178,
               &saved_tau, &saved_full);
    const uint64_t cancel[8][2] = {
        {178, 178}, {1, 1}, {0, 0}, {2, 3},
        {order - 1, order - 1}, {UINT64_MAX, UINT64_MAX},
        {1, 0}, {0, 1},
    };
    check_paired_batch(&g, &with_identity, &base, &negative, cancel, 1);
}

int main(void)
{
    check_curve(UINT64_C(4294967377), 15, UINT64_C(23729779),
                UINT64_C(481899190), UINT64_C(1998487369));
    check_curve(UINT64_C(2305843009213693951), 7, UINT64_C(53624256071278747),
                UINT64_C(1839617427631136375), UINT64_C(725584580046817702));

    ca_group generic;
    CHECK(ca_group_ec_init(&generic, 97, 2, 3, 0) == CA_OK);
    ca_elem id;
    ca_group_identity(&generic, &id);
    ca_tau4_joint_precomp invalid = {0};
    CHECK(!ca_ec_tau4_joint_prepare(&generic, &id, &id, &invalid, NULL));
    ca_elem sentinel = {{11, 12, 13, 14}}, output = sentinel;
    CHECK(!ca_ec_tau4_joint_mul_profile(&generic, &invalid, &output, 1, 2, 1, NULL));
    CHECK(memcmp(&output, &sentinel, sizeof(output)) == 0);
    TEST_MAIN_END();
}
