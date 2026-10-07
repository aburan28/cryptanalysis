#include "ec_tau_internal.h"
#include "curve_internal.h"
#include "generated/tau4_residue_atlas.h"
#include "generated/tau8_orbit_map.h"
#include "generated/tau8_hot_map.h"
#include "generated/tau8_pair_map.h"
#include "test_fixtures.h"

static int tau_cost_cases;

static uint32_t j0_hash_reference(const ca_group *g, ca_elem *point)
{
    ca_elem cur = *point, best = *point;
    uint64_t best_hash = ca_group_hash(g, point);
    uint32_t best_k = 0;
    for (uint32_t k = 1; k < 6; k++) {
        ca_elem next;
        ca_ec_endo(g, &next, &cur);
        cur = next;
        uint64_t h = ca_group_hash(g, &cur);
        if (h < best_hash) {
            best_hash = h;
            best = cur;
            best_k = k;
        }
    }
    *point = best;
    return best_k;
}

static void j0_orbit_checks(void)
{
    const char *names[] = {"glv-j0-26", "glv-j0-32", "pf-j0-twist-b27"};
    for (size_t t = 0; t < sizeof(names) / sizeof(names[0]); t++) {
        uint64_t p, a, b, order;
        CHECK(ca_curve_by_name(names[t], &p, &a, &b, &order) == CA_OK);
        ca_group g;
        CHECK(ca_curve_group(&g, p, a, b, order, NULL) == CA_OK);
        CHECK(g.endo_kind == CA_CURVE_ENDO_J0 && g.aut_order == 6);
        ca_elem gen;
        CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);
        ca_elem id;
        ca_group_identity(&g, &id);
        CHECK_EQ_U64(ca_j0_coordinate_class_reduce(&g, &id), 0);
        CHECK_EQ_U64(ca_j0_factored_hash_class_reduce(&g, &id), 0);
        CHECK(ca_group_is_identity(&g, &id));

        ca_rng rng;
        ca_rng_seed(&rng, UINT64_C(0x20261007) ^ order);
        for (int i = 0; i < 128; i++) {
            uint64_t scalar = i < 5 ? (uint64_t[]){1, 2, 3, order - 2, order - 1}[i]
                                    : 1 + ca_rng_below(&rng, order - 1);
            ca_elem point, rotated, expected;
            ca_group_mul(&g, &point, &gen, scalar, NULL);
            rotated = point;
            for (uint32_t h = 0; h < 6; h++) {
                ca_elem reference = rotated, factored = rotated;
                uint32_t ref_k = j0_hash_reference(&g, &reference);
                uint32_t factored_k = ca_j0_factored_hash_class_reduce(&g, &factored);
                CHECK_EQ_U64(factored_k, ref_k);
                for (size_t word = 0; word < 4; word++)
                    CHECK_EQ_U64(factored.w[word], reference.w[word]);
                ca_elem got = rotated, replay = rotated;
                uint32_t k = ca_j0_coordinate_class_reduce(&g, &got);
                CHECK(k < 6);
                for (uint32_t q = 0; q < k; q++) {
                    ca_elem next;
                    ca_ec_endo(&g, &next, &replay);
                    replay = next;
                }
                CHECK(ca_group_equal(&g, &got, &replay));
                CHECK(ca_group_is_valid(&g, &got));
                if (h == 0) expected = got;
                else CHECK(ca_group_equal(&g, &got, &expected));

                uint64_t input_coeff = ca_mulmod(scalar, ca_powmod(g.endo_lambda, h, order), order);
                uint64_t output_coeff = ca_mulmod(input_coeff, ca_powmod(g.endo_lambda, k, order), order);
                ca_elem coeff_point;
                ca_group_mul(&g, &coeff_point, &gen, output_coeff, NULL);
                CHECK(ca_group_equal(&g, &coeff_point, &got));
                ca_elem next;
                ca_ec_endo(&g, &next, &rotated);
                rotated = next;
            }
        }
    }

    /* The orbit can have fewer than six distinct points outside the prime
     * subgroup. The same rule must also cover x=0 and y=0. */
    ca_group tiny;
    CHECK(ca_group_ec_init(&tiny, 7, 0, 1, 0) == CA_OK);
    tiny.endo_kind = CA_CURVE_ENDO_J0;
    tiny.aut_order = 6;
    tiny.endo_c_mont = ca_mont_to(&tiny.mont, 2); /* 2^3=1 mod 7 */
    const uint64_t words[][4] = {{0, 1, 0, 0}, {3, 0, 0, 0}};
    for (size_t i = 0; i < 2; i++) {
        ca_elem point, rotated, expected;
        CHECK(ca_group_encode(&tiny, &point, words[i]));
        rotated = point;
        for (uint32_t h = 0; h < 6; h++) {
            ca_elem reference = rotated, factored = rotated;
            uint32_t ref_k = j0_hash_reference(&tiny, &reference);
            uint32_t factored_k = ca_j0_factored_hash_class_reduce(&tiny, &factored);
            CHECK_EQ_U64(factored_k, ref_k);
            for (size_t word = 0; word < 4; word++)
                CHECK_EQ_U64(factored.w[word], reference.w[word]);
            ca_elem got = rotated, replay = rotated;
            uint32_t k = ca_j0_coordinate_class_reduce(&tiny, &got);
            CHECK(k < 6);
            for (uint32_t q = 0; q < k; q++) {
                ca_elem next;
                ca_ec_endo(&tiny, &next, &replay);
                replay = next;
            }
            CHECK(ca_group_equal(&tiny, &got, &replay));
            if (h == 0) expected = got;
            else CHECK(ca_group_equal(&tiny, &got, &expected));
            ca_elem next;
            ca_ec_endo(&tiny, &next, &rotated);
            rotated = next;
        }
    }
}

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
    ca_tau_pair_fused_precomp pair_pre;
    uint64_t pair_seed_ops = 0, pair_prep_adds = 0, pair_prep_rotations = 0;
    uint64_t pair_prep_inversions = 0;
    CHECK(ca_ec_tau_pair_fused_prepare(g, point, &pair_pre, &pair_seed_ops, &pair_prep_adds,
                                       &pair_prep_rotations, &pair_prep_inversions));
    CHECK(ca_ec_tau_pair_fused_prepare_verify(&pair_pre));
    CHECK_EQ_U64(sizeof(pair_pre.orbit), 3872);
    CHECK_EQ_U64(ca_ec_tau_pair_fused_static_bytes(), 33289);
    CHECK(pair_seed_ops > 0 && pair_prep_adds > 0 && pair_prep_rotations > 0);
    CHECK_EQ_U64(pair_prep_inversions, 2);
    ca_tau_pair_complete_precomp complete_pre;
    uint64_t complete_seed_ops = 0, complete_prep_adds = 0, complete_prep_rotations = 0;
    uint64_t complete_prep_inversions = 0;
    CHECK(ca_ec_tau_pair_complete_prepare(g, point, &complete_pre, &complete_seed_ops,
                                          &complete_prep_adds, &complete_prep_rotations,
                                          &complete_prep_inversions));
    CHECK(ca_ec_tau_pair_complete_prepare_verify(&complete_pre));
    CHECK_EQ_U64(sizeof(complete_pre.exact), 23232);
    CHECK_EQ_U64(ca_ec_tau_pair_complete_static_bytes(), 33289);
    CHECK(ca_ec_tau_pair_periodic_static_bytes() > ca_ec_tau_pair_complete_static_bytes());
    CHECK_EQ_U64(ca_ec_tau_pair_mixed_static_bytes(),
                 ca_ec_tau_pair_complete_static_bytes() + 33282 + 33282);
    CHECK_EQ_U64(ca_ec_tau_pair_mixed_full_static_bytes(),
                 ca_ec_tau_pair_mixed_static_bytes());
    CHECK_EQ_U64(complete_seed_ops, pair_seed_ops);
    CHECK_EQ_U64(complete_prep_adds, pair_prep_adds);
    CHECK(complete_prep_rotations >= pair_prep_rotations);
    CHECK_EQ_U64(complete_prep_inversions, pair_prep_inversions);
    ca_tau4_pos_precomp positional_pre;
    ca_tau4_pos_precomp global_pre;
    uint64_t prep_triples = 0;
    uint64_t global_triples = 0;
    CHECK(sizeof(positional_pre.point) == 36864);
    CHECK(ca_ec_tau4_pos_prepare(g, point, &positional_pre, &prep_triples));
    CHECK(ca_ec_tau4_pos_global_prepare(g, point, &global_pre, &global_triples));
    CHECK_EQ_U64(global_triples, prep_triples);
    CHECK(prep_triples > 0);
    ca_tau4_pos_compact_precomp compact_pre = {0};
    uint64_t compact_triples = 0, compact_inversions = 0;
    CHECK(ca_ec_tau4_pos_compact_prepare(g, point, &compact_pre, &compact_triples,
                                         &compact_inversions));
    CHECK_EQ_U64(compact_inversions, 1);
    CHECK(compact_triples > 0 && compact_triples <= 18 * (compact_pre.layers - 1));
    CHECK(compact_pre.layers < CA_TAU_POS_Q);
    for (size_t q = 0; q < compact_pre.layers; q++)
        for (size_t slot = 0; slot < 18; slot++)
            for (size_t word = 0; word < 4; word++)
                CHECK_EQ_U64(compact_pre.point[q * 18 + slot].w[word],
                             (&global_pre.point[0][0][0])[q * 18 + slot].w[word]);
    ca_ec_tau4_pos_compact_clear(&compact_pre);
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
        ca_elem gated = *point, double_pair = *point, folded_pair = *point;
        ca_elem residue_pair = *point;
        ca_elem fused_pair = *point;
        ca_elem complete_pair = *point;
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
        uint64_t fold_triples = UINT64_MAX, fold_adds = UINT64_MAX;
        uint64_t fold_rotations = UINT64_MAX;
        uint64_t residue_triples = UINT64_MAX, residue_adds = UINT64_MAX;
        uint64_t residue_rotations = UINT64_MAX;
        uint64_t fused_triples = UINT64_MAX, fused_adds = UINT64_MAX;
        uint64_t fused_rotations = UINT64_MAX;
        uint64_t complete_triples = UINT64_MAX, complete_adds = UINT64_MAX;
        uint64_t complete_rotations = UINT64_MAX;
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
        CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &folded_pair, k, 6, &fold_triples,
                                              &fold_adds, &fold_rotations));
        CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &residue_pair, k, 7, &residue_triples,
                                              &residue_adds, &residue_rotations));
        CHECK(ca_ec_tau4_tail_recode_compare_scalar(&pre, k));
        CHECK(ca_ec_tau4_double_recode_verify_scalar(&pre, k));
        CHECK(ca_ec_tau4_fold_recode_verify_scalar(&pre, k));
        CHECK(ca_ec_tau4_residue_recode_verify_scalar(&pre, k));
        CHECK(ca_ec_tau_pair_fused_mul_profile(g, &pair_pre, &fused_pair, k, &fused_triples,
                                               &fused_adds, &fused_rotations));
        CHECK(ca_ec_tau_pair_fused_recode_verify_scalar(&pair_pre, k));
        CHECK(ca_ec_tau_pair_complete_mul_profile(g, &complete_pre, &complete_pair, k,
                                                  &complete_triples, &complete_adds,
                                                  &complete_rotations));
        CHECK(ca_ec_tau_pair_complete_recode_verify_scalar(&complete_pre, k));
        ca_elem mixed_pair;
        uint64_t mixed_triples = 0, mixed_tau_steps = 0, mixed_doubles = 0;
        uint64_t mixed_adds = 0, mixed_lookups = 0, mixed_fallbacks = 0;
        CHECK(ca_ec_tau_pair_mixed_mul_profile(g, &complete_pre, &mixed_pair, k,
                                               &mixed_triples, &mixed_tau_steps, &mixed_doubles,
                                               &mixed_adds, &mixed_lookups, &mixed_fallbacks));
        CHECK(ca_ec_tau_pair_mixed_recode_verify_scalar(&complete_pre, k));
        CHECK(ca_group_equal(g, &mixed_pair, &expected));
        CHECK(mixed_fallbacks <= 1);
        CHECK(ca_ec_tau_pair_mixed_full_mul_profile(g, &complete_pre, &mixed_pair, k,
                                                    NULL, NULL, NULL, NULL, NULL, NULL));
        CHECK(ca_ec_tau_pair_mixed_full_recode_verify_scalar(&complete_pre, k));
        CHECK(ca_group_equal(g, &mixed_pair, &expected));
        if (i < 24) {
            ca_elem periodic_reference, periodic_candidate, periodic_firstword;
            uint64_t reference_triples = 0, reference_adds = 0;
            uint64_t candidate_triples = 0, candidate_adds = 0, lookups = 0;
            uint64_t accepted = 0, fallbacks = 0;
            CHECK(ca_ec_tau_pair_periodic_mul_profile(g, &complete_pre, &periodic_reference, k, 0,
                                                      &reference_triples, &reference_adds, NULL,
                                                      NULL, NULL));
            CHECK(ca_ec_tau_pair_periodic_mul_profile(g, &complete_pre, &periodic_candidate, k, 1,
                                                      &candidate_triples, &candidate_adds, &lookups,
                                                      &accepted, &fallbacks));
            CHECK(ca_ec_tau_pair_periodic_mul_profile(g, &complete_pre, &periodic_firstword, k, 2,
                                                      NULL, NULL, NULL, NULL, NULL));
            CHECK(ca_ec_tau_pair_periodic_recode_verify_scalar(&complete_pre, k, 0));
            CHECK(ca_ec_tau_pair_periodic_recode_verify_scalar(&complete_pre, k, 1));
            CHECK(ca_ec_tau_pair_periodic_recode_verify_scalar(&complete_pre, k, 2));
            CHECK(ca_group_equal(g, &periodic_reference, &expected));
            CHECK(ca_group_equal(g, &periodic_candidate, &expected));
            CHECK(ca_group_equal(g, &periodic_firstword, &expected));
            CHECK(10 * candidate_triples + 16 * candidate_adds <=
                  10 * reference_triples + 16 * reference_adds);
            CHECK(accepted <= 1 && fallbacks <= 1);
            if (k % g->order == 0) CHECK_EQ_U64(lookups, 0);
        }
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
        CHECK(ca_group_equal(g, &folded_pair, &expected));
        CHECK(ca_group_equal(g, &residue_pair, &expected));
        CHECK(ca_group_equal(g, &fused_pair, &expected));
        CHECK(ca_group_equal(g, &complete_pair, &expected));
        CHECK_EQ_U64(complete_triples, fused_triples);
        CHECK_EQ_U64(complete_adds, fused_adds);
        CHECK_EQ_U64(complete_rotations, 0);
        CHECK(10 * fused_triples + 16 * fused_adds + fused_rotations <=
              10 * residue_triples + 16 * residue_adds + residue_rotations);
        CHECK_EQ_U64(10 * fold_triples + 16 * fold_adds + fold_rotations,
                     10 * double_triples + 16 * double_adds + double_rotations);
        CHECK_EQ_U64(10 * residue_triples + 16 * residue_adds + residue_rotations,
                     10 * fold_triples + 16 * fold_adds + fold_rotations);
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

static unsigned tau3_matching_brute(uint32_t mask, const uint32_t edge[20], uint8_t memo[4096])
{
    if (!mask) return 0;
    if (memo[mask] != UINT8_MAX) return memo[mask];
    unsigned i = (unsigned)__builtin_ctz(mask);
    uint32_t rest = mask & ~(UINT32_C(1) << i);
    unsigned best = tau3_matching_brute(rest, edge, memo);
    for (uint32_t choices = edge[i] & rest; choices; choices &= choices - 1) {
        unsigned j = (unsigned)__builtin_ctz(choices);
        unsigned candidate = 1 + tau3_matching_brute(rest & ~(UINT32_C(1) << j), edge, memo);
        if (candidate > best) best = candidate;
    }
    memo[mask] = (uint8_t)best;
    return best;
}

static void tau3_scatter_graph_checks(void)
{
    ca_rng rng;
    ca_rng_seed(&rng, UINT64_C(0x20261006));
    for (unsigned n = 2; n <= 12; n++)
        for (unsigned trial = 0; trial < 32; trial++) {
            uint32_t edge[20] = {0};
            int8_t mate[20];
            for (unsigned i = 0; i < n; i++)
                for (unsigned j = i + 1; j < n; j++)
                    if (ca_rng_next(&rng) % 4 != 0) {
                        edge[i] |= UINT32_C(1) << j;
                        edge[j] |= UINT32_C(1) << i;
                    }
            uint8_t memo[4096];
            memset(memo, UINT8_MAX, sizeof(memo));
            unsigned want = tau3_matching_brute((UINT32_C(1) << n) - 1, edge, memo);
            unsigned got = ca_ec_tau3_scatter_match_graph(edge, n, mate);
            CHECK_EQ_U64(got, want);
            unsigned matched = 0;
            for (unsigned i = 0; i < n; i++)
                if (mate[i] >= 0) {
                    unsigned j = (unsigned)mate[i];
                    CHECK(j < n && mate[j] == (int8_t)i && (edge[i] & (UINT32_C(1) << j)));
                    matched++;
                }
            CHECK_EQ_U64(matched, (uint64_t)2 * want);
        }
}

/* Exercise the three direct tau evaluators and all six profile modes against
 * independently computed points, including the identity and scalar edges. */
static void tau_direct_checks(const ca_group *g, const ca_elem *point)
{
    const uint64_t scalars[] = {0, 1, 2, 3, 17, g->order - 1, UINT64_MAX};
    ca_tau3_fused_precomp tau3_pre = {0};
    CHECK(ca_ec_tau3_fused_prepare(g, point, &tau3_pre, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau3_fused_prepare_verify(&tau3_pre));
    CHECK(ca_ec_tau3_scatter_verify_map());
    CHECK(ca_ec_tau3_scatter_atlas_verify_map());
    ca_tau3_scatter_precomp scatter_pre = {0};
    CHECK(ca_ec_tau3_scatter_prepare(g, point, &scatter_pre, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau3_scatter_prepare_verify(&scatter_pre));
    ca_tau3_sparse_precomp sparse_pre = {0};
    CHECK(ca_ec_tau3_sparse_prepare(g, point, &sparse_pre, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau3_sparse_prepare_verify(&sparse_pre));
    ca_tau4_pos_compact_precomp compact_pre = {0};
    CHECK(ca_ec_tau4_pos_compact_prepare(g, point, &compact_pre, NULL, NULL));
    ca_fixed_comb_precomp comb_pre;
    uint64_t comb_doubles = 0, comb_adds = 0, comb_inversions = 0;
    CHECK(ca_ec_fixed_comb_prepare(g, point, &comb_pre, &comb_doubles, &comb_adds,
                                    &comb_inversions));
    CHECK_EQ_U64(comb_doubles, (uint64_t)8 * comb_pre.depth);
    CHECK_EQ_U64(comb_adds, CA_FIXED_COMB_ENTRIES - 1 - CA_FIXED_COMB_WIDTH);
    CHECK_EQ_U64(comb_inversions, 1);
    ca_endo_radix8_precomp endo_pre = {0};
    uint64_t endo_doubles = 0, endo_adds = 0, endo_inversions = 0;
    CHECK(ca_ec_endo_radix8_prepare(g, point, &endo_pre, &endo_doubles, &endo_adds,
                                    &endo_inversions));
    CHECK(ca_ec_endo_radix8_prepare_verify(&endo_pre));
    CHECK_EQ_U64(endo_doubles, 8 * (endo_pre.positions - 1));
    CHECK_EQ_U64(endo_adds, 127 * endo_pre.positions);
    CHECK_EQ_U64(endo_inversions, 1);
    CHECK(ca_ec_joint_window4_verify_map());
    ca_joint_window4_precomp joint_pre = {0};
    uint64_t joint_doubles = 0, joint_adds = 0, joint_rotations = 0, joint_inversions = 0;
    CHECK(ca_ec_joint_window4_prepare(g, point, &joint_pre, &joint_doubles, &joint_adds,
                                      &joint_rotations, &joint_inversions));
    CHECK(ca_ec_joint_window4_prepare_verify(&joint_pre));
    CHECK_EQ_U64(joint_doubles, 4 * (joint_pre.positions - 1));
    CHECK_EQ_U64(joint_adds, 85 * joint_pre.positions);
    CHECK_EQ_U64(joint_rotations, 8 * joint_pre.positions);
    CHECK_EQ_U64(joint_inversions, 1);
    CHECK(ca_ec_joint_window4_hot_verify_map());
    ca_joint_window4_precomp hot_joint_pre = {0};
    int hot_supported =
        (g->p == UINT64_C(4294967377) && g->b == 15 && g->order == UINT64_C(23729779) &&
         g->endo_lambda == UINT64_C(16027563)) ||
        (g->p == UINT64_C(2305843009213693951) && g->b == 7 &&
         g->order == UINT64_C(53624256071278747) && g->endo_lambda == UINT64_C(1212946466324730));
    if (hot_supported) {
        CHECK(ca_ec_joint_window4_hot_prepare(g, point, &hot_joint_pre, NULL, NULL, NULL, NULL));
        CHECK(ca_ec_joint_window4_prepare_verify(&hot_joint_pre));
    } else {
        CHECK(!ca_ec_joint_window4_hot_prepare(g, point, &hot_joint_pre, NULL, NULL, NULL, NULL));
    }
    ca_joint_window4_precomp plane_joint_pre = {0};
    if (hot_supported) {
        uint64_t plane_muls = 0;
        CHECK(ca_ec_joint_window4_xplane_prepare(g, point, &plane_joint_pre, NULL, NULL, NULL, NULL,
                                                 &plane_muls));
        CHECK_EQ_U64(plane_muls, ca_ec_joint_window4_point_entries(g));
        CHECK(ca_ec_joint_window4_prepare_verify(&plane_joint_pre));
    } else {
        CHECK(!ca_ec_joint_window4_xplane_prepare(g, point, &plane_joint_pre, NULL, NULL, NULL,
                                                  NULL, NULL));
    }
    ca_tau4_precomp pre;
    CHECK(ca_ec_tau4_prepare(g, point, &pre, NULL));
    ca_tau_pair_fused_precomp pair_pre;
    CHECK(ca_ec_tau_pair_fused_prepare(g, point, &pair_pre, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau_pair_fused_prepare_verify(&pair_pre));
    ca_tau_pair_complete_precomp complete_pre;
    CHECK(ca_ec_tau_pair_complete_prepare(g, point, &complete_pre, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau_pair_complete_prepare_verify(&complete_pre));
    for (size_t i = 0; i < sizeof(scalars) / sizeof(scalars[0]); i++) {
        uint64_t k = scalars[i], steps, adds, triples;
        ca_elem expected, got;
        ca_group_mul(g, &expected, point, k % g->order, NULL);
        CHECK(ca_ec_fixed_comb_mul_profile(g, &comb_pre, &got, k, NULL, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        uint64_t endo_fallbacks = UINT64_MAX;
        CHECK(ca_ec_endo_radix8_mul_profile(g, &endo_pre, &got, k, NULL, NULL, &endo_fallbacks));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK_EQ_U64(endo_fallbacks, 0);
        uint64_t joint_fallbacks = UINT64_MAX;
        CHECK(
            ca_ec_joint_window4_mul_profile(g, &joint_pre, &got, k, NULL, NULL, &joint_fallbacks));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK_EQ_U64(joint_fallbacks, 0);
        if (hot_supported) {
            uint64_t hot_joint_fallbacks = UINT64_MAX;
            CHECK(ca_ec_joint_window4_mul_profile(g, &hot_joint_pre, &got, k, NULL, NULL,
                                                  &hot_joint_fallbacks));
            CHECK(ca_group_equal(g, &got, &expected));
            CHECK_EQ_U64(hot_joint_fallbacks, 0);
            uint64_t plane_joint_fallbacks = UINT64_MAX;
            CHECK(ca_ec_joint_window4_xplane_mul_profile(g, &plane_joint_pre, &got, k, NULL, NULL,
                                                         NULL, &plane_joint_fallbacks));
            CHECK(ca_group_equal(g, &got, &expected));
            CHECK_EQ_U64(plane_joint_fallbacks, 0);
        }
        CHECK(ca_ec_tau3_fused_mul_profile(g, &tau3_pre, &got, k, NULL, NULL, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_tau3_fused_recode_verify_scalar(&tau3_pre, k));
        uint64_t scatter_exact_adds = 0, scatter_direct_adds = 0;
        CHECK(ca_ec_tau3_scatter_mul_profile(g, &scatter_pre, &got, k, &scatter_exact_adds, NULL,
                                             NULL, NULL, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_tau3_scatter_direct_mul_profile(g, &scatter_pre, &got, k, &scatter_direct_adds,
                                                    NULL, NULL, NULL, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(scatter_direct_adds >= scatter_exact_adds);
        uint64_t scatter_atlas_adds = 0;
        CHECK(ca_ec_tau3_scatter_atlas_mul_profile(g, &scatter_pre, &got, k, &scatter_atlas_adds,
                                                   NULL, NULL, NULL, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK_EQ_U64(scatter_atlas_adds, scatter_direct_adds);
        CHECK(ca_ec_tau3_atlas_mul_profile(g, &tau3_pre, &got, k, NULL, NULL, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_tau3_atlas_recode_verify_scalar(&tau3_pre, k));
        CHECK(ca_ec_tau3_sparse_mul_profile(g, &sparse_pre, &got, k, NULL, NULL, NULL, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_tau3_radix27_mul_profile(g, &sparse_pre, &got, k, NULL, NULL, NULL, NULL, NULL,
                                             NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        uint64_t compact_fallbacks = UINT64_MAX;
        CHECK(ca_ec_tau4_pos_compact_mul_profile(g, &compact_pre, &got, k, NULL, NULL,
                                                 &compact_fallbacks));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK_EQ_U64(compact_fallbacks, 0);
        CHECK(ca_ec_mul_tau2(g, &got, point, k, &steps, &adds));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_mul_tau4(g, &got, point, k, &steps, &adds));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_mul_tau4_tripling(g, &got, point, k, &steps, &adds, &triples));
        CHECK(ca_group_equal(g, &got, &expected));
        for (int mode = 0; mode <= 7; mode++) {
            uint64_t rotations;
            CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &got, k, mode, &triples, &adds,
                                                  &rotations));
            CHECK(ca_group_equal(g, &got, &expected));
        }
        CHECK(ca_ec_tau_pair_fused_mul_profile(g, &pair_pre, &got, k, &triples, &adds, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_tau_pair_fused_recode_verify_scalar(&pair_pre, k));
        CHECK(
            ca_ec_tau_pair_complete_mul_profile(g, &complete_pre, &got, k, &triples, &adds, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_tau_pair_complete_recode_verify_scalar(&complete_pre, k));
        CHECK(ca_ec_tau_pair_mixed_mul_profile(g, &complete_pre, &got, k, NULL, NULL, NULL,
                                               NULL, NULL, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_tau_pair_mixed_recode_verify_scalar(&complete_pre, k));
        CHECK(ca_ec_tau_pair_mixed_full_mul_profile(g, &complete_pre, &got, k, NULL, NULL, NULL,
                                                    NULL, NULL, NULL));
        CHECK(ca_group_equal(g, &got, &expected));
        CHECK(ca_ec_tau_pair_mixed_full_recode_verify_scalar(&complete_pre, k));
    }
    ca_elem identity, got;
    size_t tau3_saved_blocks = tau3_pre.blocks;
    tau3_pre.blocks = 1;
    uint64_t tau3_fallback = 0;
    CHECK(
        ca_ec_tau3_fused_mul_profile(g, &tau3_pre, &got, g->order / 2, NULL, NULL, &tau3_fallback));
    ca_elem tau3_expected_fallback;
    ca_group_mul(g, &tau3_expected_fallback, point, g->order / 2, NULL);
    CHECK(ca_group_equal(g, &got, &tau3_expected_fallback));
    CHECK_EQ_U64(tau3_fallback, 1);
    unsigned saved_endo_positions = endo_pre.positions;
    endo_pre.positions = 1;
    uint64_t endo_fallbacks = 0;
    CHECK(ca_ec_endo_radix8_mul_profile(g, &endo_pre, &got, g->order / 2, NULL, NULL,
                                        &endo_fallbacks));
    CHECK(ca_group_equal(g, &got, &tau3_expected_fallback));
    CHECK_EQ_U64(endo_fallbacks, 1);
    endo_pre.positions = saved_endo_positions;
    ca_ec_endo_radix8_clear(&endo_pre);
    unsigned saved_joint_positions = joint_pre.positions;
    joint_pre.positions = 1;
    uint64_t joint_fallbacks = 0;
    CHECK(ca_ec_joint_window4_mul_profile(g, &joint_pre, &got, g->order / 2, NULL, NULL,
                                          &joint_fallbacks));
    CHECK(ca_group_equal(g, &got, &tau3_expected_fallback));
    CHECK_EQ_U64(joint_fallbacks, 1);
    joint_pre.positions = saved_joint_positions;
    ca_ec_joint_window4_clear(&joint_pre);
    ca_ec_joint_window4_clear(&hot_joint_pre);
    ca_ec_joint_window4_clear(&plane_joint_pre);
    size_t sparse_saved_blocks = sparse_pre.blocks;
    sparse_pre.blocks = 1;
    uint64_t sparse_fallback = 0;
    CHECK(ca_ec_tau3_sparse_mul_profile(g, &sparse_pre, &got, g->order / 2, NULL, NULL, NULL,
                                        &sparse_fallback));
    CHECK(ca_group_equal(g, &got, &tau3_expected_fallback));
    CHECK_EQ_U64(sparse_fallback, 1);
    uint64_t radix_fallback = 0;
    CHECK(ca_ec_tau3_radix27_mul_profile(g, &sparse_pre, &got, g->order / 2, NULL, NULL, NULL,
                                         &radix_fallback, NULL, NULL));
    CHECK(ca_group_equal(g, &got, &tau3_expected_fallback));
    CHECK_EQ_U64(radix_fallback, 1);
    sparse_pre.blocks = sparse_saved_blocks;
    ca_ec_tau3_sparse_clear(&sparse_pre);
    tau3_fallback = 0;
    CHECK(
        ca_ec_tau3_atlas_mul_profile(g, &tau3_pre, &got, g->order / 2, NULL, NULL, &tau3_fallback));
    CHECK(ca_group_equal(g, &got, &tau3_expected_fallback));
    CHECK_EQ_U64(tau3_fallback, 1);
    tau3_pre.blocks = tau3_saved_blocks;
    ca_ec_tau3_fused_clear(&tau3_pre);
    size_t scatter_saved_blocks = scatter_pre.full.blocks;
    scatter_pre.full.blocks = 1;
    uint64_t scatter_fallback = 0;
    CHECK(ca_ec_tau3_scatter_mul_profile(g, &scatter_pre, &got, g->order / 2, NULL, NULL,
                                         &scatter_fallback, NULL, NULL));
    CHECK(ca_group_equal(g, &got, &tau3_expected_fallback));
    CHECK_EQ_U64(scatter_fallback, 1);
    scatter_fallback = 0;
    CHECK(ca_ec_tau3_scatter_atlas_mul_profile(g, &scatter_pre, &got, g->order / 2, NULL, NULL,
                                               &scatter_fallback, NULL, NULL));
    CHECK(ca_group_equal(g, &got, &tau3_expected_fallback));
    CHECK_EQ_U64(scatter_fallback, 1);
    scatter_fallback = 0;
    CHECK(ca_ec_tau3_scatter_direct_mul_profile(g, &scatter_pre, &got, g->order / 2, NULL, NULL,
                                                &scatter_fallback, NULL, NULL));
    CHECK(ca_group_equal(g, &got, &tau3_expected_fallback));
    CHECK_EQ_U64(scatter_fallback, 1);
    scatter_pre.full.blocks = scatter_saved_blocks;
    ca_ec_tau3_scatter_clear(&scatter_pre);
    size_t saved_layers = compact_pre.layers;
    compact_pre.layers = 1;
    uint64_t compact_fallbacks = 0;
    uint64_t fallback_scalar = g->order / 2;
    CHECK(ca_ec_tau4_pos_compact_mul_profile(g, &compact_pre, &got, fallback_scalar,
                                             NULL, NULL, &compact_fallbacks));
    ca_elem expected_fallback;
    ca_group_mul(g, &expected_fallback, point, fallback_scalar, NULL);
    CHECK(ca_group_equal(g, &got, &expected_fallback));
    CHECK_EQ_U64(compact_fallbacks, 1);
    compact_pre.layers = saved_layers;
    ca_ec_tau4_pos_compact_clear(&compact_pre);
    ca_group_identity(g, &identity);
    CHECK(ca_ec_tau3_fused_prepare(g, &identity, &tau3_pre, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau3_fused_prepare_verify(&tau3_pre));
    CHECK(ca_ec_tau3_fused_mul_profile(g, &tau3_pre, &got, 17, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau3_atlas_mul_profile(g, &tau3_pre, &got, 17, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(
        ca_ec_tau3_scatter_prepare(g, &identity, &scatter_pre, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau3_scatter_prepare_verify(&scatter_pre));
    CHECK(ca_ec_tau3_scatter_mul_profile(g, &scatter_pre, &got, 17, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau3_scatter_direct_mul_profile(g, &scatter_pre, &got, 17, NULL, NULL, NULL, NULL,
                                                NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau3_scatter_atlas_mul_profile(g, &scatter_pre, &got, 17, NULL, NULL, NULL, NULL,
                                               NULL));
    CHECK(ca_group_is_identity(g, &got));
    ca_ec_tau3_scatter_clear(&scatter_pre);
    CHECK(ca_ec_tau3_sparse_prepare(g, &identity, &sparse_pre, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau3_sparse_prepare_verify(&sparse_pre));
    CHECK(ca_ec_tau3_sparse_mul_profile(g, &sparse_pre, &got, 17, NULL, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau3_radix27_mul_profile(g, &sparse_pre, &got, 17, NULL, NULL, NULL, NULL, NULL,
                                         NULL));
    CHECK(ca_group_is_identity(g, &got));
    ca_ec_tau3_sparse_clear(&sparse_pre);
    ca_ec_tau3_fused_clear(&tau3_pre);
    CHECK(ca_ec_tau4_pos_compact_prepare(g, &identity, &compact_pre, NULL, NULL));
    CHECK(ca_ec_tau4_pos_compact_mul_profile(g, &compact_pre, &got, 17, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    ca_ec_tau4_pos_compact_clear(&compact_pre);
    CHECK(ca_ec_fixed_comb_prepare(g, &identity, &comb_pre, &comb_doubles, &comb_adds,
                                    &comb_inversions));
    CHECK_EQ_U64(comb_doubles, 0);
    CHECK_EQ_U64(comb_adds, 0);
    CHECK_EQ_U64(comb_inversions, 0);
    CHECK(ca_ec_fixed_comb_mul_profile(g, &comb_pre, &got, 17, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_endo_radix8_prepare(g, &identity, &endo_pre, &endo_doubles, &endo_adds,
                                    &endo_inversions));
    CHECK(ca_ec_endo_radix8_prepare_verify(&endo_pre));
    CHECK_EQ_U64(endo_doubles, 0);
    CHECK_EQ_U64(endo_adds, 0);
    CHECK_EQ_U64(endo_inversions, 0);
    CHECK(ca_ec_endo_radix8_mul_profile(g, &endo_pre, &got, 17, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    ca_ec_endo_radix8_clear(&endo_pre);
    CHECK(ca_ec_joint_window4_prepare(g, &identity, &joint_pre, &joint_doubles, &joint_adds,
                                      &joint_rotations, &joint_inversions));
    CHECK(ca_ec_joint_window4_prepare_verify(&joint_pre));
    CHECK_EQ_U64(joint_doubles, 0);
    CHECK_EQ_U64(joint_adds, 0);
    CHECK_EQ_U64(joint_rotations, 0);
    CHECK_EQ_U64(joint_inversions, 0);
    CHECK(ca_ec_joint_window4_mul_profile(g, &joint_pre, &got, 17, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    ca_ec_joint_window4_clear(&joint_pre);
    if (hot_supported) {
        CHECK(
            ca_ec_joint_window4_hot_prepare(g, &identity, &hot_joint_pre, NULL, NULL, NULL, NULL));
        CHECK(ca_ec_joint_window4_prepare_verify(&hot_joint_pre));
        CHECK(ca_ec_joint_window4_mul_profile(g, &hot_joint_pre, &got, 17, NULL, NULL, NULL));
        CHECK(ca_group_is_identity(g, &got));
        CHECK(ca_ec_joint_window4_xplane_prepare(g, &identity, &plane_joint_pre, NULL, NULL, NULL,
                                                 NULL, NULL));
        CHECK(ca_ec_joint_window4_prepare_verify(&plane_joint_pre));
        CHECK(ca_ec_joint_window4_xplane_mul_profile(g, &plane_joint_pre, &got, 17, NULL, NULL,
                                                     NULL, NULL));
        CHECK(ca_group_is_identity(g, &got));
    }
    ca_ec_joint_window4_clear(&hot_joint_pre);
    ca_ec_joint_window4_clear(&plane_joint_pre);
    uint64_t setup_ops = UINT64_MAX;
    CHECK(ca_ec_tau4_prepare(g, &identity, &pre, &setup_ops));
    CHECK_EQ_U64(setup_ops, 0);
    CHECK(ca_ec_tau4_mul_prepared_cost(g, &pre, &got, 17, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau_pair_complete_prepare(g, &identity, &complete_pre, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau_pair_complete_prepare_verify(&complete_pre));
    CHECK(ca_ec_tau_pair_complete_mul_profile(g, &complete_pre, &got, 17, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau_pair_mixed_mul_profile(g, &complete_pre, &got, 17, NULL, NULL, NULL,
                                           NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau_pair_mixed_full_mul_profile(g, &complete_pre, &got, 17, NULL, NULL, NULL,
                                                NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau_pair_periodic_mul_profile(g, &complete_pre, &got, 17, 0, NULL, NULL, NULL, NULL,
                                              NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau_pair_periodic_mul_profile(g, &complete_pre, &got, 17, 1, NULL, NULL, NULL, NULL,
                                              NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau_pair_periodic_mul_profile(g, &complete_pre, &got, 17, 2, NULL, NULL, NULL, NULL,
                                              NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(ca_ec_tau_pair_fused_prepare(g, &identity, &pair_pre, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau_pair_fused_prepare_verify(&pair_pre));
    CHECK(ca_ec_tau_pair_fused_mul_profile(g, &pair_pre, &got, 17, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(g, &got));
    CHECK(!ca_ec_tau4_mul_prepared_profile(g, &pre, &got, 17, 8, NULL, NULL, NULL));
}

static void joint_plane_named(uint64_t p, uint64_t b, uint64_t order)
{
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, p, 0, b, order, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J0);
    ca_elem generator;
    CHECK(ca_group_find_generator(&g, &generator, 1) == CA_OK);
    for (uint64_t multiple = 1; multiple <= 37; multiple += 36) {
        ca_elem point;
        ca_group_mul(&g, &point, &generator, multiple, NULL);
        ca_joint_window4_precomp pre = {0};
        uint64_t plane_muls = 0;
        CHECK(ca_ec_joint_window4_xplane_prepare(&g, &point, &pre, NULL, NULL, NULL, NULL,
                                                 &plane_muls));
        CHECK(pre.plane_format && !pre.point && pre.plane_point);
        CHECK_EQ_U64(plane_muls, ca_ec_joint_window4_point_entries(&g));
        CHECK(ca_ec_joint_window4_prepare_verify(&pre));
        pre.plane_point[0].x_beta ^= 1;
        CHECK(!ca_ec_joint_window4_prepare_verify(&pre));
        pre.plane_point[0].x_beta ^= 1;
        const uint64_t scalars[] = {0, 1, 2, 3, order / 2, order - 1};
        for (size_t i = 0; i < sizeof(scalars) / sizeof(scalars[0]); i++) {
            ca_elem got, expected;
            ca_group_mul(&g, &expected, &point, scalars[i], NULL);
            CHECK(ca_ec_joint_window4_xplane_mul_profile(&g, &pre, &got, scalars[i], NULL, NULL,
                                                         NULL, NULL));
            CHECK(ca_group_equal(&g, &got, &expected));
        }
        unsigned saved_positions = pre.positions;
        pre.positions = 1;
        ca_elem got, expected;
        uint64_t fallbacks = 0;
        ca_group_mul(&g, &expected, &point, order / 2, NULL);
        CHECK(ca_ec_joint_window4_xplane_mul_profile(&g, &pre, &got, order / 2, NULL, NULL, NULL,
                                                     &fallbacks));
        CHECK(ca_group_equal(&g, &got, &expected));
        CHECK_EQ_U64(fallbacks, 1);
        pre.positions = saved_positions;
        ca_ec_joint_window4_clear(&pre);
    }
    ca_elem identity, got;
    ca_group_identity(&g, &identity);
    ca_joint_window4_precomp identity_pre = {0};
    CHECK(ca_ec_joint_window4_xplane_prepare(&g, &identity, &identity_pre, NULL, NULL, NULL, NULL,
                                             NULL));
    CHECK(ca_ec_joint_window4_prepare_verify(&identity_pre));
    CHECK(ca_ec_joint_window4_xplane_mul_profile(&g, &identity_pre, &got, 17, NULL, NULL, NULL,
                                                 NULL));
    CHECK(ca_group_is_identity(&g, &got));
    ca_ec_joint_window4_clear(&identity_pre);
}

static void joint_zero_named(uint64_t p, uint64_t b, uint64_t order, uint64_t witness)
{
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, p, 0, b, order, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J0);
    ca_elem point;
    CHECK(ca_group_find_generator(&g, &point, 1) == CA_OK);
    ca_joint_window4_precomp pre = {0};
    CHECK(ca_ec_joint_window4_zero_prepare(&g, &point, &pre, NULL, NULL, NULL, NULL, NULL));
    CHECK(pre.zero_mode && pre.plane_format && pre.det_inverse16);
    CHECK(ca_ec_joint_window4_prepare_verify(&pre));
    pre.det_inverse16 ^= 2;
    CHECK(!ca_ec_joint_window4_prepare_verify(&pre));
    pre.det_inverse16 ^= 2;
    const uint64_t scalars[] = {0, 1, 2, witness, order / 2, order - 1};
    for (size_t i = 0; i < sizeof(scalars) / sizeof(scalars[0]); i++) {
        ca_elem got, expected;
        uint64_t attempts = UINT64_MAX, feasible = 0, selected = 0;
        ca_group_mul(&g, &expected, &point, scalars[i], NULL);
        CHECK(ca_ec_joint_window4_zero_mul_profile(&g, &pre, &got, scalars[i], NULL, NULL, NULL,
                                                   &attempts, &feasible, &selected));
        CHECK(ca_group_equal(&g, &got, &expected));
        CHECK_EQ_U64(attempts, scalars[i] != 0);
        if (i == 3) {
            CHECK_EQ_U64(feasible, 1);
            CHECK_EQ_U64(selected, 1);
        }
    }
    unsigned saved_positions = pre.positions;
    pre.positions = 1;
    ca_elem got, expected;
    uint64_t fallback = 0;
    ca_group_mul(&g, &expected, &point, order / 2, NULL);
    CHECK(ca_ec_joint_window4_zero_mul_profile(&g, &pre, &got, order / 2, NULL, NULL, &fallback,
                                               NULL, NULL, NULL));
    CHECK(ca_group_equal(&g, &got, &expected));
    CHECK_EQ_U64(fallback, 1);
    pre.positions = saved_positions;
    ca_ec_joint_window4_clear(&pre);
    ca_elem identity;
    ca_group_identity(&g, &identity);
    CHECK(ca_ec_joint_window4_zero_prepare(&g, &identity, &pre, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_joint_window4_prepare_verify(&pre));
    CHECK(ca_ec_joint_window4_zero_mul_profile(&g, &pre, &got, 17, NULL, NULL, NULL, NULL, NULL,
                                               NULL));
    CHECK(ca_group_is_identity(&g, &got));
    ca_ec_joint_window4_clear(&pre);
}

static void joint_pair_hex_named(uint64_t p, uint64_t b, uint64_t order, unsigned pairs,
                                 int top_compressed)
{
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, p, 0, b, order, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J0);
    CHECK(top_compressed ? ca_ec_joint_pair_top_verify_map() : ca_ec_joint_pair_verify_map());
    CHECK_EQ_U64(top_compressed ? ca_ec_joint_pair_top_static_bytes()
                                : ca_ec_joint_pair_static_bytes(),
                 top_compressed ? 353076 : 306900);
    size_t entries = top_compressed ? ca_ec_joint_pair_top_point_entries(&g)
                                    : ca_ec_joint_pair_point_entries(&g);
    CHECK_EQ_U64(entries, (uint64_t)(pairs - 1) * 11061 +
                              (top_compressed ? (pairs == 2 ? 756 : 210) : 11061));
    ca_elem point;
    CHECK(ca_group_find_generator(&g, &point, 1) == CA_OK);
    ca_joint_pair_precomp pre = {0};
    uint64_t inversions = 0, plane_muls = 0;
    CHECK(top_compressed
              ? ca_ec_joint_pair_top_prepare(&g, &point, &pre, NULL, NULL, &inversions, &plane_muls)
              : ca_ec_joint_pair_prepare(&g, &point, &pre, NULL, NULL, &inversions, &plane_muls));
    CHECK_EQ_U64(pre.pairs, pairs);
    CHECK_EQ_U64(pre.top_compressed, top_compressed);
    CHECK_EQ_U64(inversions, pairs);
    CHECK_EQ_U64(plane_muls, entries);
    CHECK(ca_ec_joint_pair_prepare_verify(&pre));
    pre.plane_point[0].x_beta ^= 1;
    CHECK(!ca_ec_joint_pair_prepare_verify(&pre));
    pre.plane_point[0].x_beta ^= 1;
    const uint64_t scalars[] = {0, 1, 2, 3, 17, order / 2, order - 1};
    for (size_t i = 0; i < sizeof(scalars) / sizeof(scalars[0]); i++) {
        ca_elem got, expected;
        uint64_t fallbacks = UINT64_MAX;
        ca_group_mul(&g, &expected, &point, scalars[i], NULL);
        CHECK(ca_ec_joint_pair_mul_profile(&g, &pre, &got, scalars[i], NULL, NULL, &fallbacks));
        CHECK(ca_group_equal(&g, &got, &expected));
        CHECK_EQ_U64(fallbacks, 0);
    }
    unsigned saved_pairs = pre.pairs;
    pre.pairs = 1;
    ca_elem got, expected;
    uint64_t fallbacks = 0;
    ca_group_mul(&g, &expected, &point, order / 2, NULL);
    CHECK(ca_ec_joint_pair_mul_profile(&g, &pre, &got, order / 2, NULL, NULL, &fallbacks));
    CHECK(ca_group_equal(&g, &got, &expected));
    CHECK_EQ_U64(fallbacks, 1);
    pre.pairs = saved_pairs;
    ca_ec_joint_pair_clear(&pre);
    ca_elem identity;
    ca_group_identity(&g, &identity);
    CHECK(top_compressed ? ca_ec_joint_pair_top_prepare(&g, &identity, &pre, NULL, NULL, NULL, NULL)
                         : ca_ec_joint_pair_prepare(&g, &identity, &pre, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_joint_pair_prepare_verify(&pre));
    CHECK(ca_ec_joint_pair_mul_profile(&g, &pre, &got, 17, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    ca_ec_joint_pair_clear(&pre);
}

static void joint_pair_width_named(uint64_t p, uint64_t b, uint64_t order, unsigned pairs,
                                   unsigned words)
{
    CHECK_EQ_U64(sizeof(ca_joint_pair_triple_point), 3 * sizeof(uint64_t));
    CHECK_EQ_U64(sizeof(ca_joint_pair_double_point), 2 * sizeof(uint64_t));
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, p, 0, b, order, &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J0);
    ca_elem point;
    CHECK(ca_group_find_generator(&g, &point, 1) == CA_OK);
    ca_joint_pair_precomp pre = {0};
    uint64_t inversions = 0, plane_muls = UINT64_MAX;
    CHECK(!ca_ec_joint_pair_width_prepare(&g, &point, &pre, 1, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_joint_pair_width_prepare(&g, &point, &pre, words, NULL, NULL, &inversions,
                                         &plane_muls));
    size_t entries = ca_ec_joint_pair_top_point_entries(&g);
    CHECK_EQ_U64(pre.point_words, words);
    CHECK_EQ_U64(pre.pairs, pairs);
    CHECK_EQ_U64(inversions, pairs);
    CHECK_EQ_U64(plane_muls, words == 3 ? entries : 0);
    CHECK(ca_ec_joint_pair_prepare_verify(&pre));
    if (words == 3) {
        pre.triple_point[0].x_beta ^= 1;
        CHECK(!ca_ec_joint_pair_prepare_verify(&pre));
        pre.triple_point[0].x_beta ^= 1;
    } else {
        pre.double_point[0].x ^= 1;
        CHECK(!ca_ec_joint_pair_prepare_verify(&pre));
        pre.double_point[0].x ^= 1;
    }
    const uint64_t scalars[] = {0, 1, 2, 3, 17, order / 2, order - 1};
    uint64_t serial_adds = 0, serial_rotations = 0, serial_unit_adds = 0;
    uint64_t serial_guard_hits = 0, serial_qcorr_corrections = 0;
    for (size_t i = 0; i < sizeof(scalars) / sizeof(scalars[0]); i++) {
        ca_elem got, expected;
        uint64_t adds = UINT64_MAX, rotations = UINT64_MAX;
        uint64_t unit_adds = UINT64_MAX, fallbacks = UINT64_MAX;
        ca_group_mul(&g, &expected, &point, scalars[i], NULL);
        CHECK(ca_ec_joint_pair_width_mul_profile(&g, &pre, &got, scalars[i], &adds, &rotations,
                                                 &unit_adds, &fallbacks));
        CHECK(ca_group_equal(&g, &got, &expected));
        ca_elem five_got;
        uint64_t five_adds = UINT64_MAX, five_rotations = UINT64_MAX;
        uint64_t five_unit_adds = UINT64_MAX, five_fallbacks = UINT64_MAX;
        CHECK(ca_ec_joint_pair_width_five_mul_profile(&g, &pre, &five_got, scalars[i], &five_adds,
                                                      &five_rotations, &five_unit_adds,
                                                      &five_fallbacks));
        CHECK(ca_group_equal(&g, &five_got, &expected));
        CHECK_EQ_U64(five_adds, adds);
        CHECK_EQ_U64(five_rotations, rotations);
        CHECK_EQ_U64(five_unit_adds, unit_adds);
        CHECK_EQ_U64(five_fallbacks, fallbacks);
        ca_elem guard_got;
        uint64_t guard_adds = UINT64_MAX, guard_rotations = UINT64_MAX;
        uint64_t guard_unit_adds = UINT64_MAX, guard_fallbacks = UINT64_MAX;
        uint64_t guard_hit = UINT64_MAX;
        CHECK(ca_ec_joint_pair_width_guard_mul_profile(
            &g, &pre, &guard_got, scalars[i], &guard_adds, &guard_rotations, &guard_unit_adds,
            &guard_fallbacks, &guard_hit));
        CHECK(ca_group_equal(&g, &guard_got, &expected));
        CHECK_EQ_U64(guard_adds, adds);
        CHECK_EQ_U64(guard_rotations, rotations);
        CHECK_EQ_U64(guard_unit_adds, unit_adds);
        CHECK_EQ_U64(guard_fallbacks, fallbacks);
        CHECK(guard_hit <= 1);
        ca_elem qcorr_got;
        uint64_t qcorr_adds = UINT64_MAX, qcorr_rotations = UINT64_MAX;
        uint64_t qcorr_unit_adds = UINT64_MAX, qcorr_fallbacks = UINT64_MAX;
        uint64_t qcorr_hit = UINT64_MAX, qcorr_corrections = UINT64_MAX;
        CHECK(ca_ec_joint_pair_width_qcorr_mul_profile(
            &g, &pre, &qcorr_got, scalars[i], &qcorr_adds, &qcorr_rotations, &qcorr_unit_adds,
            &qcorr_fallbacks, &qcorr_hit, &qcorr_corrections));
        CHECK(ca_group_equal(&g, &qcorr_got, &expected));
        CHECK_EQ_U64(qcorr_adds, adds);
        CHECK_EQ_U64(qcorr_rotations, rotations);
        CHECK_EQ_U64(qcorr_unit_adds, unit_adds);
        CHECK_EQ_U64(qcorr_fallbacks, fallbacks);
        CHECK_EQ_U64(qcorr_hit, guard_hit);
        serial_qcorr_corrections += qcorr_corrections;
        serial_guard_hits += guard_hit;
        serial_adds += adds;
        serial_rotations += rotations;
        serial_unit_adds += unit_adds;
        CHECK_EQ_U64(fallbacks, 0);
        if (words == 3) CHECK_EQ_U64(rotations, 0);
        if (words == 2) CHECK_EQ_U64(unit_adds, 0);
        CHECK(!ca_ec_joint_pair_mul_profile(&g, &pre, &got, scalars[i], NULL, NULL, NULL));
    }
    CHECK(ca_ec_joint_pair_width_mul_wave_batch_profile(NULL, NULL, NULL, NULL, 0, 0, NULL, NULL,
                                                        NULL, NULL, NULL));
    ca_elem wave_outputs[7];
    const size_t blocks[] = {1, 2, 7, 128};
    for (size_t j = 0; j < sizeof(blocks) / sizeof(blocks[0]); j++) {
        uint64_t adds = UINT64_MAX, rotations = UINT64_MAX, unit_adds = UINT64_MAX;
        uint64_t wave_inversions = UINT64_MAX, fallbacks = UINT64_MAX;
        CHECK(ca_ec_joint_pair_width_mul_wave_batch_profile(
            &g, &pre, wave_outputs, scalars, 7, blocks[j], &adds, &rotations, &unit_adds,
            &wave_inversions, &fallbacks));
        CHECK_EQ_U64(adds, serial_adds);
        CHECK_EQ_U64(rotations, serial_rotations);
        CHECK_EQ_U64(unit_adds, serial_unit_adds);
        CHECK_EQ_U64(fallbacks, 0);
        CHECK(wave_inversions <= (pairs - 1) * ((7 + blocks[j] - 1) / blocks[j]));
        for (size_t i = 0; i < 7; i++) {
            ca_elem expected;
            ca_group_mul(&g, &expected, &point, scalars[i], NULL);
            CHECK(ca_group_equal(&g, &wave_outputs[i], &expected));
        }
        uint64_t wave_guard_hits = UINT64_MAX;
        CHECK(ca_ec_joint_pair_width_guard_mul_wave_batch_profile(
            &g, &pre, wave_outputs, scalars, 7, blocks[j], &adds, &rotations, &unit_adds,
            &wave_inversions, &fallbacks, &wave_guard_hits));
        CHECK_EQ_U64(adds, serial_adds);
        CHECK_EQ_U64(rotations, serial_rotations);
        CHECK_EQ_U64(unit_adds, serial_unit_adds);
        CHECK_EQ_U64(fallbacks, 0);
        CHECK_EQ_U64(wave_guard_hits, serial_guard_hits);
        for (size_t i = 0; i < 7; i++) {
            ca_elem expected;
            ca_group_mul(&g, &expected, &point, scalars[i], NULL);
            CHECK(ca_group_equal(&g, &wave_outputs[i], &expected));
        }
        uint64_t qcorr_wave_hits = UINT64_MAX, qcorr_wave_corrections = UINT64_MAX;
        CHECK(ca_ec_joint_pair_width_qcorr_mul_wave_batch_profile(
            &g, &pre, wave_outputs, scalars, 7, blocks[j], &adds, &rotations, &unit_adds,
            &wave_inversions, &fallbacks, &qcorr_wave_hits, &qcorr_wave_corrections));
        CHECK_EQ_U64(adds, serial_adds);
        CHECK_EQ_U64(rotations, serial_rotations);
        CHECK_EQ_U64(unit_adds, serial_unit_adds);
        CHECK_EQ_U64(fallbacks, 0);
        CHECK_EQ_U64(qcorr_wave_hits, serial_guard_hits);
        CHECK_EQ_U64(qcorr_wave_corrections, serial_qcorr_corrections);
        for (size_t i = 0; i < 7; i++) {
            ca_elem expected;
            ca_group_mul(&g, &expected, &point, scalars[i], NULL);
            CHECK(ca_group_equal(&g, &wave_outputs[i], &expected));
        }
        CHECK(ca_ec_joint_pair_width_five_mul_wave_batch_profile(
            &g, &pre, wave_outputs, scalars, 7, blocks[j], &adds, &rotations, &unit_adds,
            &wave_inversions, &fallbacks));
        CHECK_EQ_U64(adds, serial_adds);
        CHECK_EQ_U64(rotations, serial_rotations);
        CHECK_EQ_U64(unit_adds, serial_unit_adds);
        CHECK_EQ_U64(fallbacks, 0);
        for (size_t i = 0; i < 7; i++) {
            ca_elem expected;
            ca_group_mul(&g, &expected, &point, scalars[i], NULL);
            CHECK(ca_group_equal(&g, &wave_outputs[i], &expected));
        }
    }
    const uint64_t small_boundary[4] = {UINT64_C(3161587), UINT64_C(11524340), UINT64_C(12205439),
                                        UINT64_C(20568192)};
    const uint64_t large_boundary[4] = {UINT64_C(17646112125357037), UINT64_C(22907377955199485),
                                        UINT64_C(30716878116079262), UINT64_C(35978143945921710)};
    const uint64_t *boundary = order == UINT64_C(23729779) ? small_boundary : large_boundary;
    uint64_t boundary_hits = 0, boundary_corrections = 0;
    for (size_t i = 0; i < 4; i++) {
        ca_elem expected, actual, control;
        uint64_t hit = UINT64_MAX, corrections = UINT64_MAX;
        ca_group_mul(&g, &expected, &point, boundary[i], NULL);
        CHECK(ca_ec_joint_pair_width_qcorr_mul_profile(&g, &pre, &actual, boundary[i], NULL, NULL,
                                                       NULL, NULL, &hit, &corrections));
        CHECK(ca_ec_joint_pair_width_guard_mul_profile(&g, &pre, &control, boundary[i], NULL, NULL,
                                                       NULL, NULL, NULL));
        CHECK(ca_group_equal(&g, &actual, &expected));
        CHECK(ca_group_equal(&g, &actual, &control));
        boundary_hits += hit;
        boundary_corrections += corrections;
    }
    ca_elem boundary_outputs[4];
    uint64_t wave_boundary_hits = UINT64_MAX, wave_boundary_corrections = UINT64_MAX;
    CHECK(ca_ec_joint_pair_width_qcorr_mul_wave_batch_profile(
        &g, &pre, boundary_outputs, boundary, 4, 4, NULL, NULL, NULL, NULL, NULL,
        &wave_boundary_hits, &wave_boundary_corrections));
    CHECK_EQ_U64(wave_boundary_hits, boundary_hits);
    CHECK_EQ_U64(wave_boundary_corrections, boundary_corrections);
    for (size_t i = 0; i < 4; i++) {
        ca_elem expected;
        ca_group_mul(&g, &expected, &point, boundary[i], NULL);
        CHECK(ca_group_equal(&g, &boundary_outputs[i], &expected));
    }
    CHECK(!ca_ec_joint_pair_width_mul_wave_batch_profile(&g, &pre, wave_outputs, scalars, 7, 0,
                                                         NULL, NULL, NULL, NULL, NULL));
    CHECK(!ca_ec_joint_pair_width_five_mul_wave_batch_profile(&g, &pre, wave_outputs, scalars, 7, 0,
                                                              NULL, NULL, NULL, NULL, NULL));
    CHECK(!ca_ec_joint_pair_width_guard_mul_wave_batch_profile(
        &g, &pre, wave_outputs, scalars, 7, 0, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(!ca_ec_joint_pair_width_qcorr_mul_wave_batch_profile(
        &g, &pre, wave_outputs, scalars, 7, 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL));
    __int128 saved_v1x = pre.v1x;
    pre.v1x++;
    CHECK(!ca_ec_joint_pair_width_five_mul_profile(&g, &pre, &wave_outputs[0], 17, NULL, NULL, NULL,
                                                   NULL));
    CHECK(!ca_ec_joint_pair_width_five_mul_wave_batch_profile(&g, &pre, wave_outputs, scalars, 7, 7,
                                                              NULL, NULL, NULL, NULL, NULL));
    CHECK(!ca_ec_joint_pair_width_guard_mul_profile(&g, &pre, &wave_outputs[0], 17, NULL, NULL,
                                                    NULL, NULL, NULL));
    CHECK(!ca_ec_joint_pair_width_guard_mul_wave_batch_profile(
        &g, &pre, wave_outputs, scalars, 7, 7, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(!ca_ec_joint_pair_width_qcorr_mul_profile(&g, &pre, &wave_outputs[0], 17, NULL, NULL,
                                                    NULL, NULL, NULL, NULL));
    CHECK(!ca_ec_joint_pair_width_qcorr_mul_wave_batch_profile(
        &g, &pre, wave_outputs, scalars, 7, 7, NULL, NULL, NULL, NULL, NULL, NULL, NULL));
    pre.v1x = saved_v1x;
    unsigned saved_pairs = pre.pairs;
    pre.pairs = 1;
    ca_elem got, expected;
    uint64_t fallbacks = 0;
    ca_group_mul(&g, &expected, &point, order / 2, NULL);
    CHECK(ca_ec_joint_pair_width_mul_profile(&g, &pre, &got, order / 2, NULL, NULL, NULL,
                                             &fallbacks));
    CHECK(ca_group_equal(&g, &got, &expected));
    CHECK_EQ_U64(fallbacks, 1);
    fallbacks = 0;
    CHECK(ca_ec_joint_pair_width_guard_mul_profile(&g, &pre, &got, order / 2, NULL, NULL, NULL,
                                                   &fallbacks, NULL));
    CHECK(ca_group_equal(&g, &got, &expected));
    CHECK_EQ_U64(fallbacks, 1);
    fallbacks = 0;
    CHECK(ca_ec_joint_pair_width_qcorr_mul_profile(&g, &pre, &got, order / 2, NULL, NULL, NULL,
                                                   &fallbacks, NULL, NULL));
    CHECK(ca_group_equal(&g, &got, &expected));
    CHECK_EQ_U64(fallbacks, 1);
    fallbacks = 0;
    CHECK(ca_ec_joint_pair_width_five_mul_profile(&g, &pre, &got, order / 2, NULL, NULL, NULL,
                                                  &fallbacks));
    CHECK(ca_group_equal(&g, &got, &expected));
    CHECK_EQ_U64(fallbacks, 1);
    fallbacks = 0;
    CHECK(ca_ec_joint_pair_width_mul_wave_batch_profile(&g, &pre, &got, (uint64_t[]){order / 2}, 1,
                                                        1, NULL, NULL, NULL, NULL, &fallbacks));
    CHECK(ca_group_equal(&g, &got, &expected));
    CHECK_EQ_U64(fallbacks, 1);
    fallbacks = 0;
    CHECK(ca_ec_joint_pair_width_five_mul_wave_batch_profile(
        &g, &pre, &got, (uint64_t[]){order / 2}, 1, 1, NULL, NULL, NULL, NULL, &fallbacks));
    CHECK(ca_group_equal(&g, &got, &expected));
    CHECK_EQ_U64(fallbacks, 1);
    fallbacks = 0;
    CHECK(ca_ec_joint_pair_width_guard_mul_wave_batch_profile(
        &g, &pre, &got, (uint64_t[]){order / 2}, 1, 1, NULL, NULL, NULL, NULL, &fallbacks, NULL));
    CHECK(ca_group_equal(&g, &got, &expected));
    CHECK_EQ_U64(fallbacks, 1);
    fallbacks = 0;
    CHECK(ca_ec_joint_pair_width_qcorr_mul_wave_batch_profile(
        &g, &pre, &got, (uint64_t[]){order / 2}, 1, 1, NULL, NULL, NULL, NULL, &fallbacks, NULL,
        NULL));
    CHECK(ca_group_equal(&g, &got, &expected));
    CHECK_EQ_U64(fallbacks, 1);
    pre.pairs = saved_pairs;
    ca_ec_joint_pair_clear(&pre);
    ca_elem identity;
    ca_group_identity(&g, &identity);
    CHECK(ca_ec_joint_pair_width_prepare(&g, &identity, &pre, words, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_joint_pair_prepare_verify(&pre));
    CHECK(ca_ec_joint_pair_width_mul_profile(&g, &pre, &got, 17, NULL, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_joint_pair_width_five_mul_profile(&g, &pre, &got, 17, NULL, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(
        ca_ec_joint_pair_width_guard_mul_profile(&g, &pre, &got, 17, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_joint_pair_width_qcorr_mul_profile(&g, &pre, &got, 17, NULL, NULL, NULL, NULL, NULL,
                                                   NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_joint_pair_width_mul_wave_batch_profile(&g, &pre, &got, (uint64_t[]){17}, 1, 1,
                                                        NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_joint_pair_width_five_mul_wave_batch_profile(&g, &pre, &got, (uint64_t[]){17}, 1, 1,
                                                             NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_joint_pair_width_guard_mul_wave_batch_profile(
        &g, &pre, &got, (uint64_t[]){17}, 1, 1, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_joint_pair_width_qcorr_mul_wave_batch_profile(
        &g, &pre, &got, (uint64_t[]){17}, 1, 1, NULL, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    ca_ec_joint_pair_clear(&pre);
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
    ca_tau_pair_complete_precomp mixed_pre;
    CHECK(ca_ec_tau_pair_complete_prepare(&g, &point, &mixed_pre, NULL, NULL, NULL, NULL));
    ca_tau3_fused_precomp tau3 = {0};
    CHECK(ca_ec_tau3_fused_prepare(&g, &point, &tau3, NULL, NULL, NULL, NULL, NULL, NULL));
    CHECK(ca_ec_tau3_fused_prepare_verify(&tau3));
    for (uint64_t k = 0; k < 3 * g.order; k++) {
        ca_elem got, want;
        CHECK(ca_ec_tau3_fused_mul_profile(&g, &tau3, &got, k, NULL, NULL, NULL));
        ca_group_mul(&g, &want, &point, k % g.order, NULL);
        CHECK(ca_group_equal(&g, &got, &want));
        CHECK(ca_ec_tau3_fused_recode_verify_scalar(&tau3, k));
        CHECK(ca_ec_tau3_atlas_mul_profile(&g, &tau3, &got, k, NULL, NULL, NULL));
        CHECK(ca_group_equal(&g, &got, &want));
        CHECK(ca_ec_tau3_atlas_recode_verify_scalar(&tau3, k));
        CHECK(ca_ec_tau_pair_mixed_mul_profile(&g, &mixed_pre, &got, k, NULL, NULL, NULL,
                                               NULL, NULL, NULL));
        ca_group_mul(&g, &want, &point, k % g.order, NULL);
        CHECK(ca_group_equal(&g, &got, &want));
        CHECK(ca_ec_tau_pair_mixed_recode_verify_scalar(&mixed_pre, k));
        CHECK(ca_ec_tau_pair_mixed_full_mul_profile(&g, &mixed_pre, &got, k, NULL, NULL, NULL,
                                                    NULL, NULL, NULL));
        CHECK(ca_group_equal(&g, &got, &want));
        CHECK(ca_ec_tau_pair_mixed_full_recode_verify_scalar(&mixed_pre, k));
    }
    ca_ec_tau3_fused_clear(&tau3);
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

static void tau3_sparse_action_maps(void)
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
        ca_elem point;
        CHECK(ca_group_find_generator(&g, &point, 1) == CA_OK);
        ca_tau3_sparse_precomp pre = {0};
        CHECK(ca_ec_tau3_sparse_prepare(&g, &point, &pre, NULL, NULL, NULL, NULL, NULL, NULL));
        CHECK_EQ_U64(pre.point_entries, curve_index ? 756 : 396);
        CHECK_EQ_U64(pre.hot_entries, curve_index ? 630 : 324);
        CHECK(ca_ec_tau3_sparse_prepare_verify(&pre));
        CHECK(ca_ec_tau3_sparse_verify_actions(&pre));
        uint64_t state = UINT64_C(0xb47e2d19ca8f435b);
        for (unsigned i = 0; i < 128; i++) {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            uint64_t scalar = 1 + state % (order - 1);
            ca_elem expected, got;
            ca_group_mul(&g, &expected, &point, scalar, NULL);
            uint64_t sparse_adds = 0, optimal_adds = 0, fallback = 0, dp_states = 0;
            CHECK(ca_ec_tau3_sparse_mul_profile(&g, &pre, &got, scalar, &sparse_adds, NULL, NULL,
                                                NULL));
            CHECK(ca_group_equal(&g, &got, &expected));
            CHECK(ca_ec_tau3_radix27_mul_profile(&g, &pre, &got, scalar, &optimal_adds, NULL, NULL,
                                                 &fallback, &dp_states, NULL));
            CHECK(ca_group_equal(&g, &got, &expected));
            CHECK_EQ_U64(fallback, 0);
            CHECK(optimal_adds <= sparse_adds);
            CHECK(dp_states > 0);
        }
        ca_ec_tau3_sparse_clear(&pre);
    }
}

static void tau_mixed_kernel(void)
{
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, 97, 0, 1, 3, &info) == CA_OK);
    ca_elem point;
    const uint64_t coordinates[4] = {0, 1, 0, 0};
    CHECK(ca_group_encode(&g, &point, coordinates));
    ca_elem triple;
    ca_group_mul(&g, &triple, &point, 3, NULL);
    CHECK(ca_group_is_identity(&g, &triple));
    CHECK(ca_ec_tau_pair_mixed_verify_tau_kernel(&g, &point));
}

static void paired_rho_startup_checks(void)
{
    ca_group group;
    ca_curve_info info;
    CHECK(ca_curve_group(&group, UINT64_C(4294967377), 0, 15,
                         UINT64_C(23729779), &info) == CA_OK);
    CHECK(info.endo == CA_CURVE_ENDO_J0);
    const uint64_t words[4] = {UINT64_C(481899190), UINT64_C(1998487369), 0, 0};
    ca_elem base;
    CHECK(ca_group_encode(&group, &base, words));
    const uint64_t scalars[] = {7, 123456, UINT64_C(23729776)};
    const uint64_t seeds[] = {17, 29};
    for (size_t i = 0; i < sizeof(scalars) / sizeof(scalars[0]); i++) {
        ca_elem target;
        ca_group_mul(&group, &target, &base, scalars[i], NULL);
        for (size_t j = 0; j < sizeof(seeds) / sizeof(seeds[0]); j++) {
            uint64_t reference = UINT64_MAX, candidate = UINT64_MAX, batched = UINT64_MAX;
            uint64_t plane_result = UINT64_MAX;
            ca_stats ref_stats = {0}, cand_stats = {0}, batch_stats = {0};
            ca_stats plane_stats = {0};
            ca_curve_startup_stats ref_startup = {0}, cand_startup = {0};
            ca_curve_startup_stats batch_startup = {0}, plane_startup = {0};
            CHECK(ca_curve_solve_startup(&group, &base, &target, seeds[j], &reference,
                  CA_CURVE_STARTUP_GENERIC, &ref_startup, NULL, &ref_stats) == CA_OK);
            CHECK(ca_curve_solve_startup(&group, &base, &target, seeds[j], &candidate,
                  CA_CURVE_STARTUP_TAU_PAIRED2, &cand_startup, NULL, &cand_stats) == CA_OK);
            CHECK(ca_curve_solve_startup(&group, &base, &target, seeds[j], &batched,
                  CA_CURVE_STARTUP_TAU_PAIRED2_BATCH, &batch_startup,
                  NULL, &batch_stats) == CA_OK);
            CHECK(ca_curve_solve_startup(&group, &base, &target, seeds[j], &plane_result,
                  CA_CURVE_STARTUP_TAU_PAIRED2_PLANE_BATCH, &plane_startup,
                  NULL, &plane_stats) == CA_OK);
            CHECK_EQ_U64(reference, scalars[i]);
            CHECK_EQ_U64(candidate, reference);
            CHECK_EQ_U64(batched, reference);
            CHECK_EQ_U64(plane_result, reference);
            CHECK_EQ_U64(cand_stats.group_ops, ref_stats.group_ops);
            CHECK_EQ_U64(cand_stats.table_entries, ref_stats.table_entries);
            CHECK_EQ_U64(cand_startup.budget_equivalent_group_ops,
                         ref_startup.budget_equivalent_group_ops);
            CHECK_EQ_U64(cand_startup.table_evaluations, ref_startup.table_evaluations);
            CHECK_EQ_U64(cand_startup.restart_evaluations, ref_startup.restart_evaluations);
            CHECK(cand_startup.prepare_inversions == 1);
            CHECK(cand_startup.eval_recode_attempts > 0);
            CHECK(cand_startup.eval_tau > 0);
            CHECK(cand_startup.eval_mixed_adds > 0);
            CHECK_EQ_U64(batch_stats.group_ops, ref_stats.group_ops);
            CHECK_EQ_U64(batch_stats.table_entries, ref_stats.table_entries);
            CHECK_EQ_U64(batch_startup.budget_equivalent_group_ops,
                         cand_startup.budget_equivalent_group_ops);
            CHECK_EQ_U64(batch_startup.table_evaluations, cand_startup.table_evaluations);
            CHECK_EQ_U64(batch_startup.restart_evaluations, cand_startup.restart_evaluations);
            CHECK_EQ_U64(batch_startup.eval_tau, cand_startup.eval_tau);
            CHECK_EQ_U64(batch_startup.eval_mixed_adds, cand_startup.eval_mixed_adds);
            CHECK_EQ_U64(batch_startup.eval_rotations, cand_startup.eval_rotations);
            CHECK_EQ_U64(batch_startup.eval_recode_attempts,
                         cand_startup.eval_recode_attempts);
            CHECK_EQ_U64(batch_startup.eval_pair_scores, cand_startup.eval_pair_scores);
            CHECK_EQ_U64(batch_startup.table_batch_size, batch_startup.table_evaluations);
            CHECK_EQ_U64(batch_startup.table_output_inversions, 1);
            CHECK_EQ_U64(batch_startup.restart_output_inversions,
                         cand_startup.restart_output_inversions);
            CHECK_EQ_U64(batch_startup.eval_inversions,
                         batch_startup.table_output_inversions +
                         batch_startup.restart_output_inversions);
            CHECK_EQ_U64(plane_stats.group_ops, batch_stats.group_ops);
            CHECK_EQ_U64(plane_stats.table_entries, batch_stats.table_entries);
            CHECK_EQ_U64(plane_startup.budget_equivalent_group_ops,
                         batch_startup.budget_equivalent_group_ops);
            CHECK_EQ_U64(plane_startup.table_evaluations, batch_startup.table_evaluations);
            CHECK_EQ_U64(plane_startup.restart_evaluations, batch_startup.restart_evaluations);
            CHECK_EQ_U64(plane_startup.prepare_bytes, sizeof(ca_tau4_joint_plane_precomp));
            CHECK_EQ_U64(batch_startup.prepare_bytes, sizeof(ca_tau4_joint_precomp));
            CHECK_EQ_U64(plane_startup.prepare_rotations, 18);
            CHECK_EQ_U64(batch_startup.prepare_rotations, 0);
            CHECK_EQ_U64(plane_startup.eval_rotations, 0);
            CHECK_EQ_U64(plane_startup.eval_tau, batch_startup.eval_tau);
            CHECK_EQ_U64(plane_startup.eval_mixed_adds, batch_startup.eval_mixed_adds);
            CHECK_EQ_U64(plane_startup.eval_recode_attempts,
                         batch_startup.eval_recode_attempts);
            CHECK_EQ_U64(plane_startup.eval_pair_scores, batch_startup.eval_pair_scores);
            CHECK_EQ_U64(plane_startup.eval_inversions, batch_startup.eval_inversions);
        }
    }
    ca_group generic;
    CHECK(ca_group_ec_init(&generic, 97, 2, 3, 0) == CA_OK);
    ca_elem id;
    ca_group_identity(&generic, &id);
    uint64_t output = UINT64_MAX;
    CHECK(ca_curve_solve_startup(&generic, &id, &id, 17, &output,
          CA_CURVE_STARTUP_TAU_PAIRED2, NULL, NULL, NULL) == CA_ERR_UNSUPPORTED);
    CHECK_EQ_U64(output, UINT64_MAX);
    CHECK(ca_curve_solve_startup(&generic, &id, &id, 17, &output,
          CA_CURVE_STARTUP_TAU_PAIRED2_BATCH, NULL, NULL, NULL) == CA_ERR_UNSUPPORTED);
    CHECK(ca_curve_solve_startup(&generic, &id, &id, 17, &output,
          CA_CURVE_STARTUP_TAU_PAIRED2_PLANE_BATCH,
          NULL, NULL, NULL) == CA_ERR_UNSUPPORTED);
}

int main(void)
{
    paired_rho_startup_checks();
    j0_orbit_checks();
    tau_atlas_recode_checks();
    tau3_scatter_graph_checks();
    CHECK(ca_ec_tau3_fused_verify_map());
    CHECK(ca_ec_tau3_atlas_verify_map());
    CHECK(ca_ec_tau3_sparse_verify_map());
    CHECK(ca_ec_tau3_radix27_verify_map());
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
    CHECK(ca_ec_tau_pair_mixed_verify_map());
    CHECK(ca_ec_tau_pair_mixed_full_verify_map());
    tau_cost_named("glv-j0-32");
    joint_plane_named(UINT64_C(4294967377), 15, UINT64_C(23729779));
    joint_plane_named(UINT64_C(2305843009213693951), 7, UINT64_C(53624256071278747));
    joint_zero_named(UINT64_C(4294967377), 15, UINT64_C(23729779), UINT64_C(5233680));
    joint_zero_named(UINT64_C(2305843009213693951), 7, UINT64_C(53624256071278747),
                     UINT64_C(3880360191224661));
    joint_pair_hex_named(UINT64_C(4294967377), 15, UINT64_C(23729779), 2, 0);
    joint_pair_hex_named(UINT64_C(2305843009213693951), 7, UINT64_C(53624256071278747), 4, 0);
    joint_pair_hex_named(UINT64_C(4294967377), 15, UINT64_C(23729779), 2, 1);
    joint_pair_hex_named(UINT64_C(2305843009213693951), 7, UINT64_C(53624256071278747), 4, 1);
    joint_pair_width_named(UINT64_C(4294967377), 15, UINT64_C(23729779), 2, 3);
    joint_pair_width_named(UINT64_C(4294967377), 15, UINT64_C(23729779), 2, 2);
    joint_pair_width_named(UINT64_C(2305843009213693951), 7, UINT64_C(53624256071278747), 4, 3);
    joint_pair_width_named(UINT64_C(2305843009213693951), 7, UINT64_C(53624256071278747), 4, 2);
    tau_cost_boundary_curves();
    tau_fused_named("glv-j0-32", 4);
    tau_fused_named("j0-56", 6);
    tau_wavefront_tables();
    tau_fused_small_order();
    tau3_sparse_action_maps();
    tau_mixed_kernel();
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
