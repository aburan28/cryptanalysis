#include "ec_tau_internal.h"
#include "generated/tau4_residue_atlas.h"
#include "generated/tau8_pair_map.h"
#include "test_fixtures.h"

static int tau_cost_cases;

/* Solve `reps` random logs on the group with ca_curve_solve and return the
 * mean group operations / sqrt(n). */
static double run(const ca_group *g, const ca_elem *gen, int reps) {
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
    ca_status rc =
        ca_curve_solve(g, gen, &h, 7 + (uint64_t)k, &got, &info, &st);
    CHECK(rc == CA_OK);
    CHECK_EQ_U64(got, x);
    tot += (double)st.group_ops;
  }
  return tot / reps / sqrt((double)n);
}

/* Build a group by name, solve on its subgroup generator, and confirm the
 * detected endomorphism and that logs come out right. */
static void by_name(const char *name, ca_curve_endo want_endo, uint32_t want_m,
                    double max_s) {
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
    for (uint32_t k = 0; k < want_m; k++)
      lp = ca_mulmod(lp, info.lambda, order);
    CHECK_EQ_U64(lp, 1 % order);
  }
  ca_elem gen;
  CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);
  double s = run(&g, &gen, 6);
  printf("%-14s endo=%d m=%u  S=ops/sqrt(n)=%.3f\n", name, (int)info.endo,
         info.aut_order, s);
  /* Sanity bound only (6 instances scatter ~+-30%); the endomorphism
   * speedup is measured properly in ca_bench glv. */
  CHECK(s < max_s);
}

/* Compare complete point outputs for the baseline and schedule-selected
 * representatives.  These are correctness controls, not timing claims. */
static void tau_cost_checks(const ca_group *g, const ca_elem *point,
                            int samples) {
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
        for (size_t word = 0; word < 4; word++)
          CHECK_EQ_U64(old->w[word], fresh->w[word]);
      }
  const uint64_t batch_scalars[] = {0,        1,         2, 3, g->order - 1,
                                    g->order, UINT64_MAX};
  const size_t batch_count = sizeof(batch_scalars) / sizeof(batch_scalars[0]);
  ca_elem batch_outputs[7], batch_expected[7];
  for (size_t i = 0; i < batch_count; i++)
    ca_group_mul(g, &batch_expected[i], point, batch_scalars[i] % g->order,
                 NULL);
  const size_t blocks[] = {1, 2, 4, 7};
  for (size_t b = 0; b < sizeof(blocks) / sizeof(blocks[0]); b++) {
    uint64_t inversions = UINT64_MAX;
    CHECK(ca_ec_tau4_pos_mul_batch(g, &global_pre, batch_outputs, batch_scalars,
                                   batch_count, blocks[b], NULL, NULL,
                                   &inversions));
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
    uint64_t k = i < 8 ? (uint64_t[]){0,
                                      1,
                                      2,
                                      3,
                                      g->order - 2,
                                      g->order - 1,
                                      g->order,
                                      UINT64_MAX}[i]
                       : ca_rng_next(&rng);
    ca_elem expected, baseline = *point, selected = *point, atlas = *point;
    ca_elem positional = *point, global = *point;
    uint64_t base_triples = UINT64_MAX, base_adds = UINT64_MAX;
    uint64_t cost_triples = UINT64_MAX, cost_adds = UINT64_MAX;
    uint64_t atlas_triples = UINT64_MAX, atlas_adds = UINT64_MAX;
    uint64_t base_rotations = UINT64_MAX, atlas_rotations = UINT64_MAX;
    ca_group_mul(g, &expected, point, k % g->order, NULL);
    CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &baseline, k, 0, &base_triples, &base_adds,
                                          &base_rotations));
    CHECK(ca_ec_tau4_mul_prepared_cost(g, &pre, &selected, k, &cost_triples,
                                       &cost_adds));
    CHECK(ca_ec_tau4_mul_prepared_profile(g, &pre, &atlas, k, 2, &atlas_triples, &atlas_adds,
                                          &atlas_rotations));
    uint64_t positional_adds = UINT64_MAX, positional_rotations = UINT64_MAX;
    CHECK(ca_ec_tau4_pos_mul(g, &positional_pre, &positional, k,
                             &positional_adds, &positional_rotations));
    CHECK(ca_ec_tau4_pos_mul(g, &global_pre, &global, k, NULL, NULL));
    CHECK(ca_group_equal(g, &baseline, &expected));
    CHECK(ca_group_equal(g, &selected, &expected));
    CHECK(ca_group_equal(g, &atlas, &expected));
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

static void tau_cost_named(const char *name) {
  uint64_t p, a, b, order;
  CHECK(ca_curve_by_name(name, &p, &a, &b, &order) == CA_OK);
  ca_group g;
  ca_curve_info info;
  CHECK(ca_curve_group(&g, p, a, b, order, &info) == CA_OK);
  CHECK(info.endo == CA_CURVE_ENDO_J0);
  ca_elem generator;
  CHECK(ca_group_find_generator(&g, &generator, 1) == CA_OK);
  tau_cost_checks(&g, &generator, 256);
  ca_elem second_point;
  ca_group_mul(&g, &second_point, &generator, 37, NULL);
  tau_cost_checks(&g, &second_point, 128);
}

static void tau_cost_boundary_curves(void) {
  const struct {
    uint64_t p, b, order;
    int samples;
  } cases[] = {
      {97, 2, 13, 13},
      {97, 10, 103, 103},
      {UINT64_C(2305843009213693951), 7, UINT64_C(53624256071278747), 128}};
  for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
    ca_group g;
    ca_curve_info info;
    CHECK(ca_curve_group(&g, cases[i].p, 0, cases[i].b, cases[i].order,
                         &info) == CA_OK);
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
    CHECK(ca_ec_tau4_pos_global_prepare(&g, &identity, &global_identity_pre,
                                        &triples));
    CHECK_EQ_U64(triples, 0);
    CHECK(ca_ec_tau4_pos_mul(&g, &identity_pre, &got, 123, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    CHECK(ca_ec_tau4_pos_mul(&g, &global_identity_pre, &got, 123, NULL, NULL));
    CHECK(ca_group_is_identity(&g, &got));
    const uint64_t identity_scalars[] = {0, 1, 123};
    ca_elem identity_outputs[3];
    uint64_t output_inversions = UINT64_MAX;
    CHECK(ca_ec_tau4_pos_mul_batch(&g, &global_identity_pre, identity_outputs,
                                   identity_scalars, 3, 2, NULL, NULL,
                                   &output_inversions));
    CHECK_EQ_U64(output_inversions, 0);
    for (size_t j = 0; j < 3; j++)
      CHECK(ca_group_is_identity(&g, &identity_outputs[j]));
    CHECK(ca_ec_tau4_pos_mul_batch(NULL, NULL, NULL, NULL, 0, 0, NULL, NULL,
                                   NULL));
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
            }
        }
        factor = ca_mulmod(factor, tau8, g.order);
    }
    uint64_t scalars[27];
    ca_elem outputs[27], expected;
    for (size_t i = 0; i < 26; i++) scalars[i] = i;
    scalars[26] = UINT64_MAX;
    CHECK(ca_ec_tau8_fused_mul_batch(&g, &pre, outputs, scalars, 27, 7, NULL, NULL, NULL, NULL));
    for (size_t i = 0; i < 27; i++) {
        ca_group_mul(&g, &expected, &point, scalars[i] % 13, NULL);
        CHECK(ca_group_equal(&g, &outputs[i], &expected));
    }
    ca_ec_tau8_fused_clear(&pre);
}

int main(void) {
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
