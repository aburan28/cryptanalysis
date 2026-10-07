/* Prepared public double-scalar workload. Point/fixture loading and common
 * preparation precede online_ms. Generic replay and output digest follow it. */
#include "cryptanalysis/ca_curve.h"
#include "ec_tau_internal.h"
#include "ca_internal.h"
#include "../prime-j0-hot-orbit-table/hot64_selected.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#define PAIRS 1024

typedef struct scalar_pair { uint64_t a, b; } scalar_pair;

static uint64_t load_u64_le(const unsigned char bytes[8])
{
    uint64_t value = 0;
    for (unsigned i = 0; i < 8; i++) value |= (uint64_t)bytes[i] << (8 * i);
    return value;
}

static int load_pairs(const char *path, scalar_pair pairs[PAIRS])
{
    FILE *file = fopen(path, "rb");
    if (!file) return 0;
    int ok = 1;
    for (size_t i = 0; i < PAIRS; i++) {
        unsigned char bytes[16];
        if (fread(bytes, 1, sizeof(bytes), file) != sizeof(bytes)) { ok = 0; break; }
        pairs[i] = (scalar_pair){load_u64_le(bytes), load_u64_le(bytes + 8)};
    }
    if (ok && fgetc(file) != EOF) ok = 0;
    if (fclose(file) != 0) ok = 0;
    return ok;
}

int main(int argc, char **argv)
{
    if (argc != 4 || (strcmp(argv[1], "generic") && strcmp(argv[1], "split") &&
                       strcmp(argv[1], "joint") && strcmp(argv[1], "orbit") &&
                       strcmp(argv[1], "hot64") && strcmp(argv[1], "paired") &&
                       strcmp(argv[1], "paired5") && strcmp(argv[1], "paired2") &&
                       strcmp(argv[1], "paired2-gauge") &&
                       strcmp(argv[1], "paired2-trellis") &&
                       strcmp(argv[1], "paired2-free-gauge") &&
                       strcmp(argv[1], "paired2-free-gauge-scored") &&
                       strcmp(argv[1], "paired5-free-gauge-scored") &&
                       strcmp(argv[1], "paired2-free-gauge-taupair") &&
                       strcmp(argv[1], "paired2-free-gauge-taupair-steered") &&
                       strcmp(argv[1], "paired2-free-gauge-taupair-cost-aware"))) {
        fputs("usage: ca_joint_tau_bench generic|split|joint|orbit|hot64|paired|paired5|paired2|paired2-gauge|paired2-trellis|paired2-free-gauge|paired2-free-gauge-scored|paired5-free-gauge-scored|paired2-free-gauge-taupair|paired2-free-gauge-taupair-steered|paired2-free-gauge-taupair-cost-aware glv-j0-32|j0-56 pairs.bin\n", stderr);
        return 2;
    }
    int large = strcmp(argv[2], "j0-56") == 0;
    if (!large && strcmp(argv[2], "glv-j0-32") != 0) {
        fputs("unknown curve\n", stderr);
        return 2;
    }
    scalar_pair pairs[PAIRS];
    if (!load_pairs(argv[3], pairs)) {
        fputs("expected exactly 1024 little-endian scalar pairs\n", stderr);
        return 2;
    }
    uint64_t input_digest = UINT64_C(0xf1d9ee7c70d6b80f);
    for (size_t i = 0; i < PAIRS; i++)
        input_digest = ca_mix64(input_digest ^ ca_mix64(pairs[i].a) ^
                                ca_mix64(pairs[i].b + i));

    uint64_t p = large ? UINT64_C(2305843009213693951) : UINT64_C(4294967377);
    uint64_t b = large ? 7 : 15;
    uint64_t order = large ? UINT64_C(53624256071278747) : UINT64_C(23729779);
    uint64_t words[4] = {large ? UINT64_C(1839617427631136375) : UINT64_C(481899190),
                         large ? UINT64_C(725584580046817702) : UINT64_C(1998487369), 0, 0};
    ca_group g;
    ca_curve_info info;
    if (ca_curve_group(&g, p, 0, b, order, &info) != CA_OK ||
        info.endo != CA_CURVE_ENDO_J0) {
        fputs("group setup failed\n", stderr);
        return 2;
    }
    ca_elem base, partner;
    if (!ca_group_encode(&g, &base, words)) return 2;
    ca_group_mul(&g, &partner, &base, 37, NULL);

    int mode = strcmp(argv[1], "generic") == 0 ? 0 :
               strcmp(argv[1], "split") == 0 ? 1 :
               strcmp(argv[1], "joint") == 0 ? 2 :
               strcmp(argv[1], "orbit") == 0 ? 3 :
               strcmp(argv[1], "hot64") == 0 ? 4 :
               strcmp(argv[1], "paired") == 0 ? 5 :
               strcmp(argv[1], "paired5") == 0 ? 6 :
               strcmp(argv[1], "paired2") == 0 ? 7 :
               strcmp(argv[1], "paired2-gauge") == 0 ? 8 :
               strcmp(argv[1], "paired2-trellis") == 0 ? 9 :
               strcmp(argv[1], "paired2-free-gauge") == 0 ? 10 :
               strcmp(argv[1], "paired2-free-gauge-scored") == 0 ? 11 :
               strcmp(argv[1], "paired5-free-gauge-scored") == 0 ? 12 :
               strcmp(argv[1], "paired2-free-gauge-taupair") == 0 ? 13 :
               strcmp(argv[1], "paired2-free-gauge-taupair-steered") == 0 ? 14 : 15;
    ca_tau4_joint_precomp pre;
    ca_tau4_orbit_precomp orbit;
    ca_tau4_hot_precomp hot;
    const uint16_t *selected = large ? ca_hot64_j0_56 : ca_hot64_j0_32;
    ca_tau4_joint_counts prep = {0};
    double prepare_start = ca_now();
    int prepared = mode == 4
        ? ca_ec_tau4_hot_prepare(&g, &base, &partner, selected, &hot, &prep)
        : mode == 3
            ? ca_ec_tau4_orbit_prepare(&g, &base, &partner, &orbit, &prep)
            : !mode || ca_ec_tau4_joint_prepare(&g, &base, &partner, &pre, &prep);
    if (!prepared) {
        fputs("joint preparation failed\n", stderr);
        return 2;
    }
    double prep_ms = 1000.0 * (ca_now() - prepare_start);

    ca_elem outputs[PAIRS];
    ca_tau4_joint_counts total = {0};
    double start = ca_now();
    for (size_t i = 0; i < PAIRS; i++) {
        if (mode == 0) {
            ca_elem left, right;
            ca_group_mul(&g, &left, &base, pairs[i].a % order, NULL);
            ca_group_mul(&g, &right, &partner, pairs[i].b % order, NULL);
            ca_group_op(&g, &outputs[i], &left, &right);
        } else {
            ca_tau4_joint_counts one = {0};
            int ok = mode == 15
                ? ca_ec_tau4_paired_two_free_gauge_tau_pair_cost_aware_mul_profile(
                    &g, &pre, &outputs[i], pairs[i].a, pairs[i].b, &one)
                : mode == 14
                ? ca_ec_tau4_paired_two_free_gauge_tau_pair_steered_mul_profile(
                    &g, &pre, &outputs[i], pairs[i].a, pairs[i].b, &one)
                : mode == 13
                ? ca_ec_tau4_paired_two_free_gauge_tau_pair_mul_profile(
                    &g, &pre, &outputs[i], pairs[i].a, pairs[i].b, &one)
                : mode == 12
                ? ca_ec_tau4_paired_five_free_gauge_scored_mul_profile(
                    &g, &pre, &outputs[i], pairs[i].a, pairs[i].b, &one)
                : mode == 11
                ? ca_ec_tau4_paired_two_free_gauge_scored_mul_profile(
                    &g, &pre, &outputs[i], pairs[i].a, pairs[i].b, &one)
                : mode == 10
                ? ca_ec_tau4_paired_two_free_gauge_mul_profile(&g, &pre, &outputs[i],
                                                               pairs[i].a, pairs[i].b, &one)
                : mode == 9
                ? ca_ec_tau4_paired_two_trellis_mul_profile(&g, &pre, &outputs[i],
                                                            pairs[i].a, pairs[i].b, &one)
                : mode == 8
                ? ca_ec_tau4_paired_two_gauge_mul_profile(&g, &pre, &outputs[i],
                                                          pairs[i].a, pairs[i].b, &one)
                : mode == 7
                ? ca_ec_tau4_paired_two_mul_profile(&g, &pre, &outputs[i],
                                                    pairs[i].a, pairs[i].b, &one)
                : mode == 6
                ? ca_ec_tau4_paired_five_mul_profile(&g, &pre, &outputs[i],
                                                     pairs[i].a, pairs[i].b, &one)
                : mode == 5
                ? ca_ec_tau4_paired_lattice_mul_profile(&g, &pre, &outputs[i],
                                                        pairs[i].a, pairs[i].b, &one)
                : mode == 4
                ? ca_ec_tau4_hot_mul_profile(&g, &hot, &outputs[i],
                                             pairs[i].a, pairs[i].b, &one)
                : mode == 3
                ? ca_ec_tau4_orbit_mul_profile(&g, &orbit, &outputs[i],
                                               pairs[i].a, pairs[i].b, &one)
                : ca_ec_tau4_joint_mul_profile(&g, &pre, &outputs[i], pairs[i].a,
                                                pairs[i].b, mode == 2, &one);
            if (!ok) {
                fprintf(stderr, "evaluation failed at pair %zu\n", i);
                return 1;
            }
            total.tau_steps += one.tau_steps;
            total.tau_pairs += one.tau_pairs;
            total.tau_pair_cheap_z += one.tau_pair_cheap_z;
            total.doubles += one.doubles;
            total.mixed_adds += one.mixed_adds;
            total.full_adds += one.full_adds;
            total.rotations += one.rotations;
            total.inversions += one.inversions;
            total.overlaps += one.overlaps;
            total.fused_hits += one.fused_hits;
            total.recode_attempts += one.recode_attempts;
            total.pair_scores += one.pair_scores;
            total.selected_changed += one.selected_changed;
            total.lattice_points_checked += one.lattice_points_checked;
            total.gauge_selected += one.gauge_selected;
            total.digit_rotations += one.digit_rotations;
            total.gauge_transitions += one.gauge_transitions;
            total.final_rotations += one.final_rotations;
            total.gauge_table_lookups += one.gauge_table_lookups;
            total.gauge_model_rotations += one.gauge_model_rotations;
            total.free_gauge_transitions += one.free_gauge_transitions;
            total.pair_model_positions += one.pair_model_positions;
            total.selected_model_m += one.selected_model_m;
        }
    }
    double online_ms = 1000.0 * (ca_now() - start);

    double verify_start = ca_now();
    uint64_t output_digest = UINT64_C(0x513adf887a8b4d29);
    for (size_t i = 0; i < PAIRS; i++) {
        ca_elem left, right, expected;
        ca_group_mul(&g, &left, &base, pairs[i].a % order, NULL);
        ca_group_mul(&g, &right, &partner, pairs[i].b % order, NULL);
        ca_group_op(&g, &expected, &left, &right);
        if (!ca_group_equal(&g, &outputs[i], &expected)) {
            fprintf(stderr, "independent replay failed at pair %zu\n", i);
            return 1;
        }
        uint64_t decoded[4];
        ca_group_decode(&g, decoded, &outputs[i]);
        output_digest = ca_mix64(output_digest ^ ca_mix64(decoded[0] + i) ^
                                  ca_mix64(decoded[1]) ^ decoded[2]);
    }
    double verify_ms = 1000.0 * (ca_now() - verify_start);
    uint64_t partner_words[4];
    ca_group_decode(&g, partner_words, &partner);
    printf("mode=%s curve=%s count=%u base_x=%" PRIu64 " base_y=%" PRIu64
           " partner_x=%" PRIu64 " partner_y=%" PRIu64
           " input_digest=%016" PRIx64 " output_digest=%016" PRIx64
           " precomp_bytes=%zu prep_ms=%.6f online_ms=%.6f verify_ms=%.6f"
           " prep_tau=%" PRIu64 " prep_doubles=%" PRIu64
           " prep_mixed_adds=%" PRIu64 " prep_rotations=%" PRIu64
           " prep_inversions=%" PRIu64
           " tau_steps=%" PRIu64 " tau_pairs=%" PRIu64
           " tau_pair_cheap_z=%" PRIu64 " doubles=%" PRIu64
           " mixed_adds=%" PRIu64 " full_adds=%" PRIu64
           " rotations=%" PRIu64 " output_inversions=%" PRIu64
           " overlaps=%" PRIu64 " fused_hits=%" PRIu64
           " recode_attempts=%" PRIu64 " pair_scores=%" PRIu64
           " selected_changed=%" PRIu64 " lattice_points_checked=%" PRIu64
           " gauge_selected=%" PRIu64
           " digit_rotations=%" PRIu64 " gauge_transitions=%" PRIu64
           " final_rotations=%" PRIu64 " gauge_table_lookups=%" PRIu64
           " gauge_model_rotations=%" PRIu64 " free_gauge_transitions=%" PRIu64
           " pair_model_positions=%" PRIu64 " selected_model_m=%" PRIu64
           " verified=1\n",
           argv[1], argv[2], PAIRS, words[0], words[1],
           partner_words[0], partner_words[1], input_digest, output_digest,
           mode == 4 ? sizeof(hot) : mode == 3 ? sizeof(orbit) : sizeof(pre),
           prep_ms, online_ms, verify_ms, prep.tau_steps, prep.doubles,
           prep.mixed_adds, prep.rotations, prep.inversions,
           total.tau_steps, total.tau_pairs, total.tau_pair_cheap_z,
           total.doubles, total.mixed_adds, total.full_adds,
           total.rotations, total.inversions, total.overlaps, total.fused_hits,
           total.recode_attempts, total.pair_scores, total.selected_changed,
           total.lattice_points_checked, total.gauge_selected,
           total.digit_rotations, total.gauge_transitions,
           total.final_rotations, total.gauge_table_lookups,
           total.gauge_model_rotations, total.free_gauge_transitions,
           total.pair_model_positions, total.selected_model_m);
    return 0;
}
