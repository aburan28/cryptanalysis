/* Paired prepared-scalar workload for the isolated benchmark service.
 * All loading, preparation, and independent replay are outside online_ms. */
#include "ca_internal.h"
#include "cryptanalysis/ca_curve.h"
#include "ec_tau_internal.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef SCALARS
#define SCALARS    4096
#endif
#define FNV_OFFSET UINT64_C(14695981039346656037)
#define FNV_PRIME  UINT64_C(1099511628211)

static uint64_t digest_word(uint64_t digest, uint64_t value)
{
    for (int i = 0; i < 8; i++) {
        digest ^= (uint8_t)(value >> (8 * i));
        digest *= FNV_PRIME;
    }
    return digest;
}

static int read_scalars(const char *path, uint64_t order, uint64_t scalars[SCALARS],
                        uint64_t *digest)
{
    FILE *file = fopen(path, "rb");
    if (!file) return 0;
    *digest = FNV_OFFSET;
    for (size_t i = 0; i < SCALARS; i++) {
        unsigned char bytes[8];
        if (fread(bytes, 1, sizeof(bytes), file) != sizeof(bytes)) {
            fclose(file);
            return 0;
        }
        uint64_t value = 0;
        for (int j = 0; j < 8; j++) value |= (uint64_t)bytes[j] << (8 * j);
        if (value >= order) {
            fclose(file);
            return 0;
        }
        scalars[i] = value;
        *digest = digest_word(*digest, scalars[i]);
    }
    int extra = fgetc(file);
    fclose(file);
    return extra == EOF;
}

static int select_curve(const char *name, uint64_t *p, uint64_t *b, uint64_t *order)
{
    if (strcmp(name, "glv-j0-32") == 0) {
        *p = UINT64_C(4294967377);
        *b = 15;
        *order = UINT64_C(23729779);
        return 1;
    }
    if (strcmp(name, "j0-56") == 0) {
        *p = UINT64_C(2305843009213693951);
        *b = 7;
        *order = UINT64_C(53624256071278747);
        return 1;
    }
    return 0;
}

static int select_mode(const char *name)
{
    static const char *names[] = {"reference",
                                  "baseline",
                                  "cost",
                                  "pos",
                                  "pos-global",
                                  "pos-prep",
                                  "pos-global-prep",
                                  "pos-batch32",
                                  "pos-batch128",
                                  "pos-batch512",
                                  "pos-batch4096",
                                  "atlas",
                                  "fused-batch128",
                                  "fused-orbit-batch128",
                                  "fused-hot-batch128",
                                  "fused-hot-adapt2-batch128",
                                  "fused-hot-gated-batch128",
                                  "fused-hot-steer-batch128",
                                  "fused-hot-steer-gated2-batch128",
                                  "tapered-residue-orbit-batch128",
                                  "tapered-residue-graph-batch128",
                                  "tapered-residue-packed-batch128",
                                  "tapered-residue-wavefront-batch128",
                                  "tail-oracle",
                                  "tail-oracle-gated",
                                  "tail-double",
                                  "tail-double-fold",
                                  "tail-double-residue",
                                  "tail-pair-fused",
                                  "tail-pair-complete",
                                  "tail-pair-periodic-canonical",
                                  "tail-pair-periodic-gated27",
                                  "tail-pair-periodic-firstword27",
                                  "tail-pair-mixed-radix",
                                  "tail-pair-mixed-full-digits",
                                  "fixed-comb9",
                                  "pos-compact",
                                  "tau3-fused-pos",
                                  "tau3-atlas-pos",
                                  "tau3-sparse-pos",
                                  "tau3-radix27-pos",
                                  "tau3-scatter-pos",
                                  "tau3-scatter-direct-pos",
                                  "tau3-scatter-atlas-pos",
                                  "endo-radix8-pos",
                                  "joint-window4-pos",
                                  "joint-window4-hot-pos",
                                  "joint-window4-xplane-pos",
                                  "joint-window4-zero-pos",
                                  "joint-pair-hex-pos",
                                  "joint-pair-top-pos",
                                  "joint-pair-top-triple-pos",
                                  "joint-pair-top-double-pos",
                                  "joint-pair-top-triple-wave128",
                                  "joint-pair-top-double-wave128",
                                  "joint-pair-top-triple-five-pos",
                                  "joint-pair-top-double-five-pos",
                                  "joint-pair-top-triple-five-wave128",
                                  "joint-pair-top-double-five-wave128",
                                  "joint-pair-top-triple-guard-pos",
                                  "joint-pair-top-double-guard-pos",
                                  "joint-pair-top-triple-guard-wave128",
                                  "joint-pair-top-double-guard-wave128",
                                  "joint-pair-top-triple-qcorr-pos",
                                  "joint-pair-top-double-qcorr-pos",
                                  "joint-pair-top-triple-qcorr-wave128",
                                  "joint-pair-top-double-qcorr-wave128"};
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); i++)
        if (strcmp(name, names[i]) == 0) return (int)i;
    return -1;
}

int main(int argc, char **argv)
{
    int mode = argc > 1 ? select_mode(argv[1]) : -1;
    if (argc != 5 || mode < 0 ||
        (strcmp(argv[3], "0") != 0 && strcmp(argv[3], "1") != 0 && strcmp(argv[3], "2") != 0 &&
         strcmp(argv[3], "3") != 0)) {
        fprintf(stderr,
                "usage: %s "
                "reference|baseline|cost|pos|pos-global|pos-prep|pos-global-prep|"
                "pos-batch32|pos-batch128|pos-batch512|pos-batch4096|atlas|"
                "fused-batch128|fused-orbit-batch128|fused-hot-batch128|"
                "fused-hot-adapt2-batch128|fused-hot-gated-batch128|"
                "fused-hot-steer-batch128|fused-hot-steer-gated2-batch128|"
                "tapered-residue-orbit-batch128|tapered-residue-graph-batch128|"
                "tapered-residue-packed-batch128|tapered-residue-wavefront-batch128|"
                "tail-oracle|tail-oracle-gated|tail-double|tail-double-fold|"
                "tail-double-residue|tail-pair-fused|tail-pair-complete|"
                "tail-pair-periodic-canonical|tail-pair-periodic-gated27|"
                "tail-pair-periodic-firstword27|tail-pair-mixed-radix|"
                "tail-pair-mixed-full-digits|fixed-comb9|pos-compact|tau3-fused-pos|"
                "tau3-atlas-pos|tau3-sparse-pos|tau3-radix27-pos|tau3-scatter-pos|"
                "tau3-scatter-direct-pos|tau3-scatter-atlas-pos|endo-radix8-pos|"
                "joint-window4-pos|joint-window4-hot-pos|joint-window4-xplane-pos|"
                "joint-window4-zero-pos|joint-pair-hex-pos|joint-pair-top-pos|"
                "joint-pair-top-triple-pos|joint-pair-top-double-pos|"
                "joint-pair-top-triple-wave128|joint-pair-top-double-wave128|"
                "joint-pair-top-triple-five-pos|joint-pair-top-double-five-pos|"
                "joint-pair-top-triple-five-wave128|joint-pair-top-double-five-wave128|"
                "joint-pair-top-triple-guard-pos|joint-pair-top-double-guard-pos|"
                "joint-pair-top-triple-guard-wave128|joint-pair-top-double-guard-wave128|"
                "joint-pair-top-triple-qcorr-pos|joint-pair-top-double-qcorr-pos|"
                "joint-pair-top-triple-qcorr-wave128|joint-pair-top-double-qcorr-wave128 "
                "glv-j0-32|j0-56 0|1|2|3 INPUT\n",
                argv[0]);
        return 2;
    }
    uint64_t p, b, order;
    if (!select_curve(argv[2], &p, &b, &order)) return 2;
    int global_builder = mode == 4 || mode == 6 || (mode >= 7 && mode <= 10);
    int positional = mode >= 3 && mode <= 10;
    int fused = mode >= 12 && mode <= 18;
    int orbit = mode == 13;
    int hot = mode >= 14 && mode <= 18;
    int adapt2 = mode == 15;
    int gated = mode == 16;
    int steer = mode == 17;
    int gated2_steer = mode == 18;
    int tapered = mode >= 19 && mode <= 22;
    int graph = mode == 20;
    int packed = mode == 21;
    int wavefront = mode == 22;
    int pair_fused = mode == 28;
    int pair_periodic = mode >= 30 && mode <= 32;
    int pair_full = mode == 34;
    int pair_mixed = mode == 33 || pair_full;
    int comb = mode == 35;
    int compact = mode == 36;
    int tau3 = mode == 37 || mode == 38;
    int tau3_atlas = mode == 38;
    int sparse = mode == 39 || mode == 40;
    int radix27 = mode == 40;
    int scatter_direct = mode == 42;
    int scatter_atlas = mode == 43;
    int scatter = mode == 41 || scatter_direct || scatter_atlas;
    int endo_radix8 = mode == 44;
    int joint_window4 = mode >= 45 && mode <= 48;
    int joint_window4_hot = mode >= 46 && mode <= 48;
    int joint_window4_plane = mode == 47 || mode == 48;
    int joint_window4_zero = mode == 48;
    int joint_pair_any = mode >= 49 && mode <= 66;
    int joint_pair_top = mode >= 50 && mode <= 66;
    int joint_pair_width = mode >= 51 && mode <= 66;
    int joint_pair_wave = mode == 53 || mode == 54 || mode == 57 || mode == 58 || mode == 61 ||
                          mode == 62 || mode == 65 || mode == 66;
    int joint_pair_five = mode >= 55 && mode <= 58;
    int joint_pair_guard = mode >= 59 && mode <= 62;
    int joint_pair_qcorr = mode >= 63 && mode <= 66;
    unsigned joint_pair_words = mode == 51 || mode == 53 || mode == 55 || mode == 57 ||
                                        mode == 59 || mode == 61 || mode == 63 || mode == 65
                                    ? 3u
                                : joint_pair_width ? 2u
                                                   : 4u;
    int periodic_policy = mode == 32 ? 2 : (mode == 31 ? 1 : 0);
    int pair_complete = mode == 29 || pair_periodic || pair_mixed;
    int prep_repeats = mode == 5 || mode == 6 ? 256 : 1;
    size_t block_size = mode >= 7 && mode <= 10 ? (size_t[]){32, 128, 512, 4096}[mode - 7] : 1;
    uint64_t scalars[SCALARS], input_digest;
    if (!read_scalars(argv[4], order, scalars, &input_digest)) {
        fprintf(stderr,
                "invalid scalar input: expected exactly %d little-endian u64 "
                "values < r\n",
                SCALARS);
        return 2;
    }
    ca_group group;
    ca_curve_info info;
    if (ca_curve_group(&group, p, 0, b, order, &info) != CA_OK || info.endo != CA_CURVE_ENDO_J0)
        return 2;
    ca_elem point;
    if (ca_group_find_generator(&group, &point, 1) != CA_OK) return 2;
    if (strcmp(argv[3], "0") != 0) {
        ca_elem second;
        uint64_t multiple = strcmp(argv[3], "1") == 0 ? 37 : strcmp(argv[3], "2") == 0 ? 101 : 103;
        ca_group_mul(&group, &second, &point, multiple, NULL);
        point = second;
    }
    uint64_t point_words[4];
    ca_group_decode(&group, point_words, &point);
    ca_elem *outputs = calloc(SCALARS, sizeof(*outputs));
    if (!outputs) return 2;
    ca_tau4_precomp pre;
    ca_tau_pair_fused_precomp pair_pre;
    ca_tau_pair_complete_precomp complete_pre;
    ca_fixed_comb_precomp comb_pre;
    ca_endo_radix8_precomp endo_radix8_pre = {0};
    ca_joint_window4_precomp joint_window4_pre = {0};
    ca_joint_pair_precomp joint_pair_pre = {0};
    ca_tau4_pos_compact_precomp compact_pre = {0};
    ca_tau3_fused_precomp tau3_pre = {0};
    ca_tau3_scatter_precomp scatter_pre = {0};
    ca_tau3_sparse_precomp sparse_pre = {0};
    ca_tau4_pos_precomp positional_pre;
    ca_tau8_fused_precomp fused_pre = {0};
    ca_tau_wide_precomp wide_pre = {0};
    int wide_schedule = strcmp(argv[2], "j0-56") == 0 ? 1 : 0;
    size_t fused_blocks = strcmp(argv[2], "j0-56") == 0 ? 6 : 4;
    double prep_ms = 0;
    uint64_t prep_triples = 0;
    uint64_t prep_doubles = 0;
    uint64_t prep_tau_steps = 0;
    uint64_t prep_layer_inversions = 0;
    uint64_t prep_adds = 0, prep_rotations = 0, prep_plane_muls = 0;
    uint64_t prep_seed_ops = 0;
    uint64_t prep_slot_lookups = 0;
    ca_tau_wide_wavefront_stats wavefront_stats = {0};
    size_t prep_temp_heap_bytes =
        global_builder ? CA_TAU_POS_Q * 2 * 9 * (3 * sizeof(uint64_t) + sizeof(uint64_t)) : 0;
    size_t prep_temp_stack_bytes =
        joint_pair_any  ? 2 * 171 * 3 * sizeof(uint64_t)
        : joint_window4 ? (7 * 71 * 4 + 25 * 3) * sizeof(uint64_t)
        : endo_radix8   ? 4 * CA_ENDO_RADIX8_MAGNITUDES * 4 * sizeof(uint64_t)
        : comb          ? (CA_FIXED_COMB_ENTRIES * 4 + CA_FIXED_COMB_WIDTH * 3) * sizeof(uint64_t)
                        : 0;
    size_t fused_entries = hot ? 2048 : orbit ? 4933 : 29593;
    size_t point_entries = joint_pair_top   ? ca_ec_joint_pair_top_point_entries(&group)
                           : joint_pair_any ? ca_ec_joint_pair_point_entries(&group)
                           : joint_window4  ? ca_ec_joint_window4_point_entries(&group)
                           : endo_radix8    ? ca_ec_endo_radix8_point_entries(&group)
                           : scatter        ? ca_ec_tau3_scatter_point_entries(&group)
                           : sparse         ? ca_ec_tau3_sparse_point_entries(&group)
                           : tau3           ? ca_ec_tau3_fused_blocks(&group) * 343
                           : compact        ? ca_ec_tau4_pos_compact_layers(&group) * 18
                           : comb           ? CA_FIXED_COMB_ENTRIES
                           : pair_complete  ? CA_TAU_PAIR_COMPLETE_COUNT
                           : pair_fused     ? CA_TAU_PAIR_FUSED_REP_COUNT
                           : tapered        ? ca_ec_tau_wide_entries(wide_schedule)
                           : fused          ? fused_blocks * fused_entries
                                            : 0;
    size_t point_table_bytes =
        point_entries * (joint_pair_width ? joint_pair_words * sizeof(uint64_t) : sizeof(ca_elem));
    size_t prep_bytes = joint_pair_any  ? sizeof(joint_pair_pre) + point_table_bytes
                        : joint_window4 ? sizeof(joint_window4_pre) + point_table_bytes
                        : endo_radix8   ? sizeof(endo_radix8_pre) + point_table_bytes
                        : scatter       ? sizeof(scatter_pre) + point_table_bytes
                        : sparse        ? sizeof(sparse_pre) + point_table_bytes
                        : tau3          ? sizeof(tau3_pre) + point_table_bytes
                        : compact       ? sizeof(compact_pre) + point_table_bytes
                        : comb          ? sizeof(comb_pre)
                        : pair_complete ? sizeof(complete_pre)
                        : pair_fused    ? sizeof(pair_pre)
                        : tapered       ? sizeof(wide_pre) + point_table_bytes
                        : fused         ? sizeof(fused_pre) + point_table_bytes
                        : positional    ? sizeof(positional_pre)
                        : mode == 0     ? 0
                                        : sizeof(pre);
    if (fused) prep_temp_heap_bytes = fused_entries * (3 * sizeof(uint64_t) + sizeof(uint64_t));
    if (compact) prep_temp_heap_bytes = point_entries * (3 * sizeof(uint64_t) + sizeof(uint64_t));
    if (tau3) prep_temp_heap_bytes = point_entries * (3 * sizeof(uint64_t) + sizeof(uint64_t));
    if (joint_window4_plane) prep_temp_heap_bytes = point_table_bytes;
    if (joint_pair_any)
        prep_temp_heap_bytes = ca_ec_joint_pair_point_entries(&group) /
                               (strcmp(argv[2], "j0-56") == 0 ? 4 : 2) *
                               (sizeof(ca_elem) + 3 * sizeof(uint64_t) + sizeof(uint64_t));
    if (sparse) prep_temp_heap_bytes = point_entries * (3 * sizeof(uint64_t) + sizeof(uint64_t));
    if (scatter)
        prep_temp_heap_bytes =
            ca_ec_tau3_fused_blocks(&group) * 343 * (3 * sizeof(uint64_t) + sizeof(uint64_t));
    if (tapered) prep_temp_heap_bytes = ca_ec_tau_wide_temp_bytes(wide_schedule);
    if (wavefront) prep_temp_heap_bytes = ca_ec_tau_wide_wavefront_temp_bytes(wide_schedule);
    if (mode != 0) {
        double t0 = ca_now();
        if (scatter) {
            if (!ca_ec_tau3_scatter_prepare(&group, &point, &scatter_pre, &prep_seed_ops,
                                            &prep_triples, &prep_tau_steps, &prep_adds,
                                            &prep_rotations, &prep_layer_inversions)) {
                free(outputs);
                return 2;
            }
        } else if (sparse) {
            if (!ca_ec_tau3_sparse_prepare(&group, &point, &sparse_pre, &prep_seed_ops,
                                           &prep_triples, &prep_tau_steps, &prep_adds,
                                           &prep_rotations, &prep_layer_inversions)) {
                free(outputs);
                return 2;
            }
        } else if (tau3) {
            if (!ca_ec_tau3_fused_prepare(&group, &point, &tau3_pre, &prep_seed_ops, &prep_triples,
                                          &prep_tau_steps, &prep_adds, &prep_rotations,
                                          &prep_layer_inversions)) {
                free(outputs);
                return 2;
            }
        } else if (compact) {
            if (!ca_ec_tau4_pos_compact_prepare(&group, &point, &compact_pre, &prep_triples,
                                                 &prep_layer_inversions)) {
                free(outputs);
                return 2;
            }
        } else if (joint_pair_any) {
            int prepared =
                joint_pair_width
                    ? ca_ec_joint_pair_width_prepare(&group, &point, &joint_pair_pre,
                                                     joint_pair_words, &prep_doubles, &prep_adds,
                                                     &prep_layer_inversions, &prep_plane_muls)
                : joint_pair_top
                    ? ca_ec_joint_pair_top_prepare(&group, &point, &joint_pair_pre, &prep_doubles,
                                                   &prep_adds, &prep_layer_inversions,
                                                   &prep_plane_muls)
                    : ca_ec_joint_pair_prepare(&group, &point, &joint_pair_pre, &prep_doubles,
                                               &prep_adds, &prep_layer_inversions,
                                               &prep_plane_muls);
            if (!prepared) {
                free(outputs);
                return 2;
            }
        } else if (joint_window4) {
            int prepared =
                joint_window4_zero
                    ? ca_ec_joint_window4_zero_prepare(&group, &point, &joint_window4_pre,
                                                       &prep_doubles, &prep_adds, &prep_rotations,
                                                       &prep_layer_inversions, &prep_plane_muls)
                : joint_window4_plane
                    ? ca_ec_joint_window4_xplane_prepare(&group, &point, &joint_window4_pre,
                                                         &prep_doubles, &prep_adds, &prep_rotations,
                                                         &prep_layer_inversions, &prep_plane_muls)
                : joint_window4_hot
                    ? ca_ec_joint_window4_hot_prepare(&group, &point, &joint_window4_pre,
                                                      &prep_doubles, &prep_adds, &prep_rotations,
                                                      &prep_layer_inversions)
                    : ca_ec_joint_window4_prepare(&group, &point, &joint_window4_pre, &prep_doubles,
                                                  &prep_adds, &prep_rotations,
                                                  &prep_layer_inversions);
            if (!prepared) {
                free(outputs);
                return 2;
            }
        } else if (endo_radix8) {
            if (!ca_ec_endo_radix8_prepare(&group, &point, &endo_radix8_pre, &prep_doubles,
                                           &prep_adds, &prep_layer_inversions)) {
                free(outputs);
                return 2;
            }
        } else if (comb) {
            if (!ca_ec_fixed_comb_prepare(&group, &point, &comb_pre, &prep_doubles,
                                           &prep_adds, &prep_layer_inversions)) {
                free(outputs);
                return 2;
            }
        } else if (pair_complete) {
            if (!ca_ec_tau_pair_complete_prepare(&group, &point, &complete_pre, &prep_seed_ops,
                                                 &prep_adds, &prep_rotations,
                                                 &prep_layer_inversions)) {
                free(outputs);
                return 2;
            }
        } else if (pair_fused) {
            if (!ca_ec_tau_pair_fused_prepare(&group, &point, &pair_pre, &prep_seed_ops, &prep_adds,
                                              &prep_rotations, &prep_layer_inversions)) {
                free(outputs);
                return 2;
            }
        } else if (tapered) {
            int prepared =
                wavefront
                    ? ca_ec_tau_wide_prepare_wavefront(&group, &point, wide_schedule, &wide_pre,
                                                       &prep_triples, &prep_adds, &prep_rotations,
                                                       &prep_layer_inversions, &wavefront_stats)
                : packed ? ca_ec_tau_wide_prepare_packed(&group, &point, wide_schedule, &wide_pre,
                                                         &prep_triples, &prep_adds, &prep_rotations,
                                                         &prep_layer_inversions, &prep_slot_lookups)
                : graph  ? ca_ec_tau_wide_prepare_graph(&group, &point, wide_schedule, &wide_pre,
                                                        &prep_triples, &prep_adds, &prep_rotations,
                                                        &prep_layer_inversions)
                         : ca_ec_tau_wide_prepare(&group, &point, wide_schedule, &wide_pre,
                                                  &prep_triples, &prep_adds, &prep_rotations,
                                                  &prep_layer_inversions);
            if (!prepared) {
                free(outputs);
                return 2;
            }
            if (wavefront) prep_slot_lookups = wavefront_stats.slot_lookups;
        } else if (fused) {
            int prepared =
                gated2_steer
                    ? ca_ec_tau8_hot_gated2_steer_prepare(&group, &point, fused_blocks, &fused_pre,
                                                          &prep_triples, &prep_adds,
                                                          &prep_rotations, &prep_layer_inversions)
                : steer  ? ca_ec_tau8_hot_steer_prepare(&group, &point, fused_blocks, &fused_pre,
                                                        &prep_triples, &prep_adds, &prep_rotations,
                                                        &prep_layer_inversions)
                : gated  ? ca_ec_tau8_hot_gated_prepare(&group, &point, fused_blocks, &fused_pre,
                                                        &prep_triples, &prep_adds, &prep_rotations,
                                                        &prep_layer_inversions)
                : adapt2 ? ca_ec_tau8_hot_adapt2_prepare(&group, &point, fused_blocks, &fused_pre,
                                                         &prep_triples, &prep_adds, &prep_rotations,
                                                         &prep_layer_inversions)
                : hot    ? ca_ec_tau8_hot_prepare(&group, &point, fused_blocks, &fused_pre,
                                                  &prep_triples, &prep_adds, &prep_rotations,
                                                  &prep_layer_inversions)
                : orbit  ? ca_ec_tau8_orbit_prepare(&group, &point, fused_blocks, &fused_pre,
                                                    &prep_triples, &prep_adds, &prep_rotations,
                                                    &prep_layer_inversions)
                         : ca_ec_tau8_fused_prepare(&group, &point, fused_blocks, &fused_pre,
                                                    &prep_triples, &prep_adds, &prep_rotations,
                                                    &prep_layer_inversions);
            if (!prepared) {
                free(outputs);
                return 2;
            }
        } else
            for (int repeat = 0; repeat < prep_repeats; repeat++) {
                uint64_t current_triples = 0;
                int prepared =
                    global_builder ? ca_ec_tau4_pos_global_prepare(&group, &point, &positional_pre,
                                                                   &current_triples)
                    : positional
                        ? ca_ec_tau4_pos_prepare(&group, &point, &positional_pre, &current_triples)
                        : ca_ec_tau4_prepare(&group, &point, &pre, NULL);
                if (!prepared) {
                    free(outputs);
                    return 2;
                }
                prep_triples += current_triples;
                if (positional && !positional_pre.base.identity)
                    prep_layer_inversions += global_builder ? 1 : CA_TAU_POS_Q - 1;
            }
        prep_ms = 1000 * (ca_now() - t0);
    }
    uint64_t triples = 0, tau_steps = 0, doubles = 0, adds = 0, rotations = 0, unit_adds = 0;
    uint64_t output_inversions = 0;
    uint64_t periodic_lookups = 0, periodic_accepted = 0, periodic_fallbacks = 0;
    uint64_t mixed_lookups = 0, mixed_fallbacks = 0;
    uint64_t fallbacks = 0, second_recodes = 0, steered_blocks = 0, guard_hits = 0;
    uint64_t quotient_corrections = 0;
    int quotient_float_enabled = joint_pair_qcorr && ca_ec_joint_pair_qcorr_available();
    uint64_t sparse_cold_pairs = 0, radix27_dp_states = 0, radix27_dp_options = 0;
    uint64_t scatter_pairs = 0;
    uint64_t zero_attempts = 0, zero_feasible = 0, zero_selected = 0;
    size_t static_map_bytes = joint_pair_top          ? ca_ec_joint_pair_top_static_bytes()
                              : joint_pair_any        ? ca_ec_joint_pair_static_bytes()
                              : joint_window4_hot     ? ca_ec_joint_window4_hot_static_bytes()
                              : joint_window4         ? ca_ec_joint_window4_static_bytes()
                              : scatter_atlas         ? ca_ec_tau3_scatter_atlas_static_bytes()
                              : scatter               ? ca_ec_tau3_scatter_static_bytes()
                              : radix27               ? ca_ec_tau3_radix27_static_bytes()
                              : sparse                ? ca_ec_tau3_sparse_static_bytes()
                              : tau3_atlas            ? ca_ec_tau3_atlas_static_bytes()
                              : tau3                  ? ca_ec_tau3_fused_static_bytes()
                              : pair_full             ? ca_ec_tau_pair_mixed_full_static_bytes()
                              : pair_mixed            ? ca_ec_tau_pair_mixed_static_bytes()
                              : mode == 32            ? ca_ec_tau_pair_firstword_static_bytes()
                              : pair_periodic         ? ca_ec_tau_pair_periodic_static_bytes()
                              : pair_complete         ? ca_ec_tau_pair_complete_static_bytes()
                              : pair_fused            ? ca_ec_tau_pair_fused_static_bytes()
                              : mode == 27            ? ca_ec_tau4_residue_static_bytes()
                              : mode == 26            ? ca_ec_tau4_fold_static_bytes()
                              : mode == 25            ? 2 * 3 * 129 * 129 + (3 * 129 * 129 + 7) / 8
                              : mode == 24            ? 3 * 129 * 129 + (3 * 129 * 129 + 7) / 8
                              : mode == 23            ? 3 * 129 * 129
                              : tapered               ? ca_ec_tau_wide_static_bytes(wide_schedule)
                              : steer || gated2_steer ? ca_ec_tau8_steer_static_bytes()
                                                      : 0;
    size_t recipe_bytes = packed || wavefront ? ca_ec_tau_wide_packed_recipe_bytes(wide_schedule)
                          : graph             ? ca_ec_tau_wide_graph_recipe_bytes(wide_schedule)
                                              : 0;
    size_t online_scratch_bytes = joint_pair_wave ? 128 * (4 * sizeof(uint32_t) + sizeof(ca_elem) +
                                                           2 * sizeof(uint64_t) + sizeof(uint8_t))
                                  : scatter       ? 0
                                  : radix27       ? ca_ec_tau3_radix27_online_scratch_bytes()
                                  : sparse        ? 160
                                  : tau3          ? 160
                                  : pair_periodic ? 1024
                                  : pair_mixed    ? 384
                                  : pair_complete || pair_fused ? 512
                                  : fused || tapered            ? 128 * 32
                                  : mode >= 7 && mode <= 10     ? block_size * 32
                                                                : 0;
    double start = ca_now();
    if (joint_pair_wave) {
        int solved = joint_pair_qcorr ? ca_ec_joint_pair_width_qcorr_mul_wave_batch_profile(
                                            &group, &joint_pair_pre, outputs, scalars, SCALARS, 128,
                                            &adds, &rotations, &unit_adds, &output_inversions,
                                            &fallbacks, &guard_hits, &quotient_corrections)
                     : joint_pair_guard
                         ? ca_ec_joint_pair_width_guard_mul_wave_batch_profile(
                               &group, &joint_pair_pre, outputs, scalars, SCALARS, 128, &adds,
                               &rotations, &unit_adds, &output_inversions, &fallbacks, &guard_hits)
                     : joint_pair_five
                         ? ca_ec_joint_pair_width_five_mul_wave_batch_profile(
                               &group, &joint_pair_pre, outputs, scalars, SCALARS, 128, &adds,
                               &rotations, &unit_adds, &output_inversions, &fallbacks)
                         : ca_ec_joint_pair_width_mul_wave_batch_profile(
                               &group, &joint_pair_pre, outputs, scalars, SCALARS, 128, &adds,
                               &rotations, &unit_adds, &output_inversions, &fallbacks);
        if (!solved) {
            fprintf(stderr, "joint-pair wavefront evaluation failed\n");
            ca_ec_joint_pair_clear(&joint_pair_pre);
            free(outputs);
            return 1;
        }
    } else if (tapered) {
        if (!ca_ec_tau_wide_mul_batch_profile(&group, &wide_pre, outputs, scalars, SCALARS, 128,
                                              &adds, &rotations, &output_inversions, &fallbacks)) {
            fprintf(stderr, "tapered batched evaluation failed\n");
            ca_ec_tau_wide_clear(&wide_pre);
            free(outputs);
            return 1;
        }
    } else if (fused) {
        if (!ca_ec_tau8_fused_mul_batch_profile(&group, &fused_pre, outputs, scalars, SCALARS, 128,
                                                &adds, &rotations, &output_inversions, &fallbacks,
                                                &second_recodes, &steered_blocks)) {
            fprintf(stderr, "fused batched evaluation failed\n");
            ca_ec_tau8_fused_clear(&fused_pre);
            free(outputs);
            return 1;
        }
    } else if (mode >= 7 && mode <= 10) {
        if (!ca_ec_tau4_pos_mul_batch(&group, &positional_pre, outputs, scalars, SCALARS,
                                      block_size, &adds, &rotations, &output_inversions)) {
            fprintf(stderr, "batched positional evaluation failed\n");
            free(outputs);
            return 1;
        }
    } else {
        for (size_t i = 0; i < SCALARS; i++) {
            if (mode == 0) {
                ca_group_mul(&group, &outputs[i], &point, scalars[i], NULL);
            } else if (positional) {
                uint64_t a = 0, r = 0;
                if (!ca_ec_tau4_pos_mul(&group, &positional_pre, &outputs[i], scalars[i], &a, &r)) {
                    fprintf(stderr, "positional evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                adds += a;
                rotations += r;
                output_inversions += !outputs[i].w[2];
            } else if (scatter) {
                uint64_t a = 0, r = 0, fallback = 0, pairs = 0;
                size_t scratch = 0;
                int success =
                    scatter_atlas
                        ? ca_ec_tau3_scatter_atlas_mul_profile(&group, &scatter_pre, &outputs[i],
                                                               scalars[i], &a, &r, &fallback,
                                                               &pairs, &scratch)
                    : scatter_direct
                        ? ca_ec_tau3_scatter_direct_mul_profile(&group, &scatter_pre, &outputs[i],
                                                                scalars[i], &a, &r, &fallback,
                                                                &pairs, &scratch)
                        : ca_ec_tau3_scatter_mul_profile(&group, &scatter_pre, &outputs[i],
                                                         scalars[i], &a, &r, &fallback, &pairs,
                                                         &scratch);
                if (!success) {
                    fprintf(stderr, "tau3 scatter evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                adds += a;
                rotations += r;
                fallbacks += fallback;
                scatter_pairs += pairs;
                if (scratch > online_scratch_bytes) online_scratch_bytes = scratch;
            } else if (sparse) {
                uint64_t a = 0, r = 0, cold = 0, fallback = 0;
                uint64_t states = 0, options = 0;
                int success =
                    radix27 ? ca_ec_tau3_radix27_mul_profile(&group, &sparse_pre, &outputs[i],
                                                             scalars[i], &a, &r, &cold, &fallback,
                                                             &states, &options)
                            : ca_ec_tau3_sparse_mul_profile(&group, &sparse_pre, &outputs[i],
                                                            scalars[i], &a, &r, &cold, &fallback);
                if (!success) {
                    fprintf(stderr, "tau3 sparse evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                adds += a;
                rotations += r;
                sparse_cold_pairs += cold;
                fallbacks += fallback;
                radix27_dp_states += states;
                radix27_dp_options += options;
            } else if (tau3) {
                uint64_t a = 0, r = 0, fallback = 0;
                int success = tau3_atlas
                                  ? ca_ec_tau3_atlas_mul_profile(&group, &tau3_pre, &outputs[i],
                                                                 scalars[i], &a, &r, &fallback)
                                  : ca_ec_tau3_fused_mul_profile(&group, &tau3_pre, &outputs[i],
                                                                 scalars[i], &a, &r, &fallback);
                if (!success) {
                    fprintf(stderr, "tau3 fused evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                adds += a;
                rotations += r;
                fallbacks += fallback;
            } else if (compact) {
                uint64_t a = 0, r = 0, fallback = 0;
                if (!ca_ec_tau4_pos_compact_mul_profile(&group, &compact_pre, &outputs[i],
                                                         scalars[i], &a, &r, &fallback)) {
                    fprintf(stderr, "compact positional evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                adds += a;
                rotations += r;
                fallbacks += fallback;
            } else if (joint_pair_any) {
                uint64_t a = 0, r = 0, u = 0, fallback = 0;
                uint64_t hit = 0, corrected = 0;
                int solved =
                    joint_pair_qcorr
                        ? ca_ec_joint_pair_width_qcorr_mul_profile(&group, &joint_pair_pre,
                                                                   &outputs[i], scalars[i], &a, &r,
                                                                   &u, &fallback, &hit, &corrected)
                    : joint_pair_guard
                        ? ca_ec_joint_pair_width_guard_mul_profile(&group, &joint_pair_pre,
                                                                   &outputs[i], scalars[i], &a, &r,
                                                                   &u, &fallback, &hit)
                    : joint_pair_five
                        ? ca_ec_joint_pair_width_five_mul_profile(&group, &joint_pair_pre,
                                                                  &outputs[i], scalars[i], &a, &r,
                                                                  &u, &fallback)
                    : joint_pair_width
                        ? ca_ec_joint_pair_width_mul_profile(&group, &joint_pair_pre, &outputs[i],
                                                             scalars[i], &a, &r, &u, &fallback)
                        : ca_ec_joint_pair_mul_profile(&group, &joint_pair_pre, &outputs[i],
                                                       scalars[i], &a, &u, &fallback);
                if (!solved) {
                    fprintf(stderr, "joint-pair evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                adds += a;
                rotations += r;
                unit_adds += u;
                fallbacks += fallback;
                guard_hits += hit;
                quotient_corrections += corrected;
            } else if (joint_window4) {
                uint64_t a = 0, r = 0, u = 0, fallback = 0;
                uint64_t attempt = 0, feasible = 0, selected = 0;
                int solved =
                    joint_window4_zero ? ca_ec_joint_window4_zero_mul_profile(
                                             &group, &joint_window4_pre, &outputs[i], scalars[i],
                                             &a, &u, &fallback, &attempt, &feasible, &selected)
                    : joint_window4_plane
                        ? ca_ec_joint_window4_xplane_mul_profile(&group, &joint_window4_pre,
                                                                 &outputs[i], scalars[i], &a, &r,
                                                                 &u, &fallback)
                        : ca_ec_joint_window4_mul_profile(&group, &joint_window4_pre, &outputs[i],
                                                          scalars[i], &a, &r, &fallback);
                if (!solved) {
                    fprintf(stderr, "joint-window evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                adds += a;
                rotations += r;
                unit_adds += u;
                fallbacks += fallback;
                zero_attempts += attempt;
                zero_feasible += feasible;
                zero_selected += selected;
            } else if (endo_radix8) {
                uint64_t a = 0, r = 0, fallback = 0;
                if (!ca_ec_endo_radix8_mul_profile(&group, &endo_radix8_pre, &outputs[i],
                                                   scalars[i], &a, &r, &fallback)) {
                    fprintf(stderr, "endomorphism radix evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                adds += a;
                rotations += r;
                fallbacks += fallback;
            } else if (comb) {
                uint64_t d = 0, a = 0;
                if (!ca_ec_fixed_comb_mul_profile(&group, &comb_pre, &outputs[i], scalars[i],
                                                   &d, &a)) {
                    fprintf(stderr, "fixed-base comb evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                doubles += d;
                adds += a;
            } else if (pair_mixed) {
                uint64_t t3 = 0, tt = 0, td = 0, a = 0, lookups = 0, fallback = 0;
                int success = pair_full
                                  ? ca_ec_tau_pair_mixed_full_mul_profile(
                                        &group, &complete_pre, &outputs[i], scalars[i],
                                        &t3, &tt, &td, &a, &lookups, &fallback)
                                  : ca_ec_tau_pair_mixed_mul_profile(
                                        &group, &complete_pre, &outputs[i], scalars[i],
                                        &t3, &tt, &td, &a, &lookups, &fallback);
                if (!success) {
                    fprintf(stderr, "mixed-radix pair evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                triples += t3;
                tau_steps += tt;
                doubles += td;
                adds += a;
                mixed_lookups += lookups;
                mixed_fallbacks += fallback;
            } else if (pair_periodic) {
                uint64_t t = 0, a = 0, lookups = 0, accepted = 0, fallbacks_local = 0;
                if (!ca_ec_tau_pair_periodic_mul_profile(&group, &complete_pre, &outputs[i],
                                                         scalars[i], periodic_policy, &t, &a,
                                                         &lookups, &accepted, &fallbacks_local)) {
                    fprintf(stderr, "periodic pair evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                triples += t;
                adds += a;
                periodic_lookups += lookups;
                periodic_accepted += accepted;
                periodic_fallbacks += fallbacks_local;
            } else if (pair_complete) {
                uint64_t t = 0, a = 0, r = 0;
                if (!ca_ec_tau_pair_complete_mul_profile(&group, &complete_pre, &outputs[i],
                                                         scalars[i], &t, &a, &r)) {
                    fprintf(stderr, "phase-complete pair evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                triples += t;
                adds += a;
                rotations += r;
            } else if (pair_fused) {
                uint64_t t = 0, a = 0, r = 0;
                if (!ca_ec_tau_pair_fused_mul_profile(&group, &pair_pre, &outputs[i], scalars[i],
                                                      &t, &a, &r)) {
                    fprintf(stderr, "orbit-pair evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                triples += t;
                adds += a;
                rotations += r;
            } else {
                uint64_t t = 0, a = 0, r = 0;
                if (!ca_ec_tau4_mul_prepared_profile(&group, &pre, &outputs[i], scalars[i],
                                                     mode == 27   ? 7
                                                     : mode == 26 ? 6
                                                     : mode == 25 ? 5
                                                     : mode == 24 ? 4
                                                     : mode == 23 ? 3
                                                     : mode == 11 ? 2
                                                                  : mode == 2,
                                                     &t, &a, &r)) {
                    fprintf(stderr, "scalar evaluation failed at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                triples += t;
                adds += a;
                rotations += r;
            }
            if (mode != 0 && !positional) output_inversions += !outputs[i].w[2];
        }
    }
    double online_ms = 1000 * (ca_now() - start);
    double verify_start = ca_now();
    uint64_t tail_pair_preparation_checks = 0;
    uint64_t tail_complete_preparation_checks = 0;
    uint64_t tau3_preparation_checks = 0;
    uint64_t sparse_preparation_checks = 0;
    uint64_t scatter_preparation_checks = 0;
    if (joint_window4 && !ca_ec_joint_window4_prepare_verify(&joint_window4_pre)) {
        fprintf(stderr, "joint-window map or point table verification failed\n");
        free(outputs);
        return 1;
    }
    if (joint_pair_any && !ca_ec_joint_pair_prepare_verify(&joint_pair_pre)) {
        fprintf(stderr, "joint-pair map or point table verification failed\n");
        free(outputs);
        return 1;
    }
    if (endo_radix8 && !ca_ec_endo_radix8_prepare_verify(&endo_radix8_pre)) {
        fprintf(stderr, "endomorphism radix point table verification failed\n");
        free(outputs);
        return 1;
    }
    if (scatter) {
        if (!ca_ec_tau3_scatter_verify_map() ||
            (scatter_atlas && !ca_ec_tau3_scatter_atlas_verify_map()) ||
            !ca_ec_tau3_scatter_prepare_verify(&scatter_pre)) {
            fprintf(stderr, "tau3 scatter map or point table verification failed\n");
            free(outputs);
            return 1;
        }
        scatter_preparation_checks = point_entries;
    }
    if (sparse) {
        if (!ca_ec_tau3_sparse_verify_map() || (radix27 && !ca_ec_tau3_radix27_verify_map()) ||
            !ca_ec_tau3_sparse_prepare_verify(&sparse_pre)) {
            fprintf(stderr, "tau3 sparse map or point table verification failed\n");
            free(outputs);
            return 1;
        }
        sparse_preparation_checks = point_entries;
    }
    if (tau3) {
        if (!ca_ec_tau3_fused_verify_map() || (tau3_atlas && !ca_ec_tau3_atlas_verify_map()) ||
            !ca_ec_tau3_fused_prepare_verify(&tau3_pre)) {
            fprintf(stderr, "tau3 map, atlas, or point table verification failed\n");
            free(outputs);
            return 1;
        }
        tau3_preparation_checks = point_entries;
    }
    if (pair_fused) {
        if (!ca_ec_tau_pair_fused_prepare_verify(&pair_pre)) {
            fprintf(stderr, "orbit-pair point table verification failed\n");
            free(outputs);
            return 1;
        }
        tail_pair_preparation_checks = CA_TAU_PAIR_FUSED_REP_COUNT;
    }
    if (pair_complete) {
        if (!ca_ec_tau_pair_complete_prepare_verify(&complete_pre)) {
            fprintf(stderr, "phase-complete pair point table verification failed\n");
            free(outputs);
            return 1;
        }
        tail_complete_preparation_checks = CA_TAU_PAIR_COMPLETE_COUNT;
    }
    uint64_t output_digest = FNV_OFFSET;
    uint64_t tail_stream_checks = 0;
    uint64_t tail_double_checks = 0;
    uint64_t tail_pair_checks = 0;
    uint64_t tail_complete_checks = 0;
    uint64_t periodic_checks = 0, periodic_word_digest = FNV_OFFSET;
    uint64_t mixed_checks = 0, mixed_action_digest = FNV_OFFSET;
    uint64_t tau3_checks = 0, tau3_action_fallbacks = 0, tau3_atlas_checks = 0;
    uint64_t tau3_action_digest = FNV_OFFSET;
    uint64_t sparse_checks = 0, sparse_action_fallbacks = 0;
    uint64_t sparse_action_digest = FNV_OFFSET;
    uint64_t radix27_checks = 0, radix27_action_fallbacks = 0;
    uint64_t radix27_action_digest = FNV_OFFSET;
    ca_tau3_fused_precomp sparse_reference = {0};
    if (sparse) {
        sparse_reference.base = sparse_pre.base;
        sparse_reference.blocks = sparse_pre.blocks;
    }
    for (size_t i = 0; i < SCALARS; i++) {
        if (mode != 0) {
            if (sparse && !radix27) {
                uint16_t actions[16], reference_actions[16];
                size_t action_count = 0, reference_count = 0;
                int recoded = ca_ec_tau3_sparse_recode_actions(&sparse_pre, scalars[i], actions,
                                                               &action_count);
                int reference_recoded = ca_ec_tau3_atlas_recode_actions(
                    &sparse_reference, scalars[i], reference_actions, &reference_count);
                if (recoded != reference_recoded ||
                    (recoded &&
                     (action_count != reference_count ||
                      memcmp(actions, reference_actions, action_count * sizeof(uint16_t)) != 0))) {
                    fprintf(stderr, "tau3 sparse action mismatch at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                if (!recoded) {
                    sparse_action_fallbacks++;
                } else {
                    sparse_action_digest = digest_word(sparse_action_digest, action_count);
                    for (size_t j = 0; j < action_count; j++)
                        sparse_action_digest = digest_word(sparse_action_digest, actions[j]);
                    sparse_checks++;
                }
            }
            if (radix27) {
                uint16_t actions[16];
                size_t action_count = 0;
                int recoded = ca_ec_tau3_radix27_recode_actions(&sparse_pre, scalars[i], actions,
                                                                &action_count, NULL, NULL);
                if (!recoded) {
                    radix27_action_fallbacks++;
                } else {
                    radix27_action_digest = digest_word(radix27_action_digest, action_count);
                    for (size_t j = 0; j < action_count; j++)
                        radix27_action_digest = digest_word(radix27_action_digest, actions[j]);
                    radix27_checks++;
                }
            }
            if (tau3) {
                uint16_t actions[16];
                size_t action_count = 0;
                int recoded = tau3_atlas ? ca_ec_tau3_atlas_recode_actions(&tau3_pre, scalars[i],
                                                                           actions, &action_count)
                                         : ca_ec_tau3_fused_recode_actions(&tau3_pre, scalars[i],
                                                                           actions, &action_count);
                if (!recoded) {
                    tau3_action_fallbacks++;
                } else {
                    if (!ca_ec_tau3_fused_recode_verify_scalar(&tau3_pre, scalars[i]) ||
                        (tau3_atlas &&
                         !ca_ec_tau3_atlas_recode_verify_scalar(&tau3_pre, scalars[i]))) {
                        fprintf(stderr, "tau3 action reconstruction failed at index %zu\n", i);
                        free(outputs);
                        return 1;
                    }
                    tau3_action_digest = digest_word(tau3_action_digest, action_count);
                    for (size_t j = 0; j < action_count; j++)
                        tau3_action_digest = digest_word(tau3_action_digest, actions[j]);
                    if (getenv("CA_TAU3_TRACE_ACTIONS")) {
                        fprintf(stderr, "tau3_actions=%zu:%zu", i, action_count);
                        for (size_t j = 0; j < action_count; j++)
                            fprintf(stderr, ":%u", (unsigned)actions[j]);
                        fputc('\n', stderr);
                    }
                    tau3_checks++;
                    tau3_atlas_checks += tau3_atlas;
                }
            }
            if (mode == 11 && !ca_ec_tau4_recode_compare_scalar(&pre, scalars[i])) {
                fprintf(stderr, "digit stream mismatch at index %zu\n", i);
                free(outputs);
                return 1;
            }
            if (mode == 24 && !ca_ec_tau4_tail_recode_compare_scalar(&pre, scalars[i])) {
                fprintf(stderr, "tail oracle digit stream mismatch at index %zu\n", i);
                free(outputs);
                return 1;
            }
            tail_stream_checks += mode == 24;
            if (mode == 25 && !ca_ec_tau4_double_recode_verify_scalar(&pre, scalars[i])) {
                fprintf(stderr, "double-pair digit reconstruction mismatch at index %zu\n", i);
                free(outputs);
                return 1;
            }
            tail_double_checks += mode == 25;
            if (mode == 26 && !ca_ec_tau4_fold_recode_verify_scalar(&pre, scalars[i])) {
                fprintf(stderr, "folded double-pair digit reconstruction mismatch at index %zu\n", i);
                free(outputs);
                return 1;
            }
            tail_double_checks += mode == 26;
            if (mode == 27 && !ca_ec_tau4_residue_recode_verify_scalar(&pre, scalars[i])) {
                fprintf(stderr, "residue-local double-pair reconstruction mismatch at index %zu\n", i);
                free(outputs);
                return 1;
            }
            tail_double_checks += mode == 27;
            if (pair_fused && !ca_ec_tau_pair_fused_recode_verify_scalar(&pair_pre, scalars[i])) {
                fprintf(stderr, "orbit-pair recode reconstruction mismatch at index %zu\n", i);
                free(outputs);
                return 1;
            }
            tail_pair_checks += pair_fused;
            if (pair_mixed) {
                uint16_t actions[128];
                size_t action_count = 0;
                int valid = pair_full
                                ? ca_ec_tau_pair_mixed_full_recode_verify_scalar(
                                      &complete_pre, scalars[i]) &&
                                      ca_ec_tau_pair_mixed_full_recode_actions(
                                          &complete_pre, scalars[i], actions, &action_count,
                                          NULL, NULL)
                                : ca_ec_tau_pair_mixed_recode_verify_scalar(
                                      &complete_pre, scalars[i]) &&
                                      ca_ec_tau_pair_mixed_recode_actions(
                                          &complete_pre, scalars[i], actions, &action_count,
                                          NULL, NULL);
                if (!valid) {
                    fprintf(stderr, "mixed-radix reconstruction mismatch at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                mixed_action_digest = digest_word(mixed_action_digest, action_count);
                for (size_t j = 0; j < action_count; j++)
                    mixed_action_digest = digest_word(mixed_action_digest, actions[j]);
                if (SCALARS == 64 && getenv("CA_MIXED_TRACE_ACTIONS")) {
                    fprintf(stderr, "trace_actions=%zu:%zu", i, action_count);
                    for (size_t j = 0; j < action_count; j++)
                        fprintf(stderr, ":%u", (unsigned)actions[j]);
                    fputc('\n', stderr);
                }
                mixed_checks++;
            }
            if (pair_periodic) {
                uint16_t pair_words[128];
                size_t pair_count = 0;
                if (!ca_ec_tau_pair_periodic_recode_verify_scalar(&complete_pre, scalars[i],
                                                                  periodic_policy) ||
                    !ca_ec_tau_pair_periodic_recode_words(&complete_pre, scalars[i],
                                                          periodic_policy, pair_words, &pair_count,
                                                          NULL, NULL, NULL)) {
                    fprintf(stderr, "periodic pair recode mismatch at index %zu\n", i);
                    free(outputs);
                    return 1;
                }
                periodic_word_digest = digest_word(periodic_word_digest, pair_count);
                for (size_t j = 0; j < pair_count; j++)
                    periodic_word_digest = digest_word(periodic_word_digest, pair_words[j]);
                if (SCALARS == 64 && getenv("CA_PAIR_TRACE_WORDS")) {
                    fprintf(stderr, "trace_words=%zu:%zu", i, pair_count);
                    for (size_t j = 0; j < pair_count; j++)
                        fprintf(stderr, ":%u", (unsigned)pair_words[j]);
                    fputc('\n', stderr);
                }
                periodic_checks++;
            }
            if (pair_complete && !pair_periodic && !pair_mixed &&
                !ca_ec_tau_pair_complete_recode_verify_scalar(&complete_pre, scalars[i])) {
                fprintf(stderr, "phase-complete pair recode mismatch at index %zu\n", i);
                free(outputs);
                return 1;
            }
            tail_complete_checks += pair_complete && !pair_periodic && !pair_mixed;
            ca_elem expected;
            ca_group_mul(&group, &expected, &point, scalars[i], NULL);
            if (!ca_group_equal(&group, &outputs[i], &expected)) {
                fprintf(stderr, "independent replay mismatch at index %zu\n", i);
                ca_ec_tau8_fused_clear(&fused_pre);
                ca_ec_tau_wide_clear(&wide_pre);
                free(outputs);
                return 1;
            }
        }
        uint64_t words[4];
        ca_group_decode(&group, words, &outputs[i]);
        for (size_t j = 0; j < 3; j++) output_digest = digest_word(output_digest, words[j]);
    }
    double verify_ms = 1000 * (ca_now() - verify_start);
    ca_ec_tau8_fused_clear(&fused_pre);
    ca_ec_tau_wide_clear(&wide_pre);
    ca_ec_tau4_pos_compact_clear(&compact_pre);
    ca_ec_tau3_fused_clear(&tau3_pre);
    ca_ec_tau3_scatter_clear(&scatter_pre);
    ca_ec_tau3_sparse_clear(&sparse_pre);
    ca_ec_endo_radix8_clear(&endo_radix8_pre);
    ca_ec_joint_window4_clear(&joint_window4_pre);
    ca_ec_joint_pair_clear(&joint_pair_pre);
    free(outputs);
    printf(
        "curve=%s point_index=%s count=%d base_x=%" PRIu64 " base_y=%" PRIu64
        " endo_lambda=%" PRIu64 " input_digest=%016" PRIx64 " output_digest=%016" PRIx64
        " online_ms=%.6f prep_ms=%.6f verify_ms=%.6f"
        " prep_triples=%" PRIu64 " prep_doubles=%" PRIu64 " prep_tau_steps=%" PRIu64
        " prep_adds=%" PRIu64 " prep_rotations=%" PRIu64 " prep_seed_ops=%" PRIu64
        " prep_plane_muls=%" PRIu64 " prep_layer_inversions=%" PRIu64
        " prep_bytes=%zu prep_temp_heap_bytes=%zu prep_temp_stack_bytes=%zu prep_repeats=%d"
        " point_entries=%zu point_table_bytes=%zu"
        " plane_entries=%zu"
        " triples=%" PRIu64 " tau_steps=%" PRIu64 " doubles=%" PRIu64 " adds=%" PRIu64
        " rotations=%" PRIu64 " unit_adds=%" PRIu64 " output_inversions=%" PRIu64
        " fallbacks=%" PRIu64 " guard_hits=%" PRIu64
        " quotient_float_enabled=%d quotient_corrections=%" PRIu64 " second_recodes=%" PRIu64
        " steered_blocks=%" PRIu64 " zero_attempts=%" PRIu64 " zero_feasible=%" PRIu64
        " zero_selected=%" PRIu64
        " static_map_bytes=%zu recipe_bytes=%zu prep_slot_lookups=%" PRIu64
        " prep_batch_denominators=%" PRIu64 " prep_affine_exceptions=%" PRIu64
        " prep_affine_doublings=%" PRIu64 " prep_affine_edge_mults_model=%" PRIu64
        " prep_affine_edge_squarings_model=%" PRIu64 " online_scratch_bytes=%zu"
        " tail_stream_checks=%" PRIu64 " tail_double_checks=%" PRIu64 " tail_pair_checks=%" PRIu64
        " tail_pair_preparation_checks=%" PRIu64 " tail_complete_checks=%" PRIu64
        " tail_complete_preparation_checks=%" PRIu64 " periodic_lookups=%" PRIu64
        " periodic_accepted=%" PRIu64 " periodic_fallbacks=%" PRIu64 " periodic_checks=%" PRIu64
        " periodic_word_digest=%016" PRIx64 " mixed_lookups=%" PRIu64 " mixed_fallbacks=%" PRIu64
        " mixed_checks=%" PRIu64 " mixed_action_digest=%016" PRIx64
        " tau3_preparation_checks=%" PRIu64 " tau3_checks=%" PRIu64
        " tau3_action_fallbacks=%" PRIu64 " tau3_action_digest=%016" PRIx64
        " tau3_atlas_checks=%" PRIu64 " sparse_preparation_checks=%" PRIu64
        " sparse_checks=%" PRIu64 " sparse_action_fallbacks=%" PRIu64
        " sparse_action_digest=%016" PRIx64 " sparse_cold_pairs=%" PRIu64 " radix27_checks=%" PRIu64
        " radix27_action_fallbacks=%" PRIu64 " radix27_action_digest=%016" PRIx64
        " radix27_dp_states=%" PRIu64 " radix27_dp_options=%" PRIu64 " scatter_pairs=%" PRIu64
        " scatter_preparation_checks=%" PRIu64 " verified=1\n",
        argv[2], argv[3], SCALARS, point_words[0], point_words[1], group.endo_lambda, input_digest,
        output_digest, online_ms, prep_ms, verify_ms, prep_triples, prep_doubles, prep_tau_steps,
        prep_adds, prep_rotations, prep_seed_ops, prep_plane_muls, prep_layer_inversions,
        prep_bytes, prep_temp_heap_bytes, prep_temp_stack_bytes, prep_repeats, point_entries,
        point_table_bytes, joint_window4_plane || joint_pair_any ? point_entries : 0, triples,
        tau_steps, doubles, adds, rotations, unit_adds, output_inversions, fallbacks, guard_hits,
        quotient_float_enabled, quotient_corrections, second_recodes, steered_blocks, zero_attempts,
        zero_feasible, zero_selected, static_map_bytes, recipe_bytes, prep_slot_lookups,
        wavefront_stats.denominators, wavefront_stats.exceptional_edges,
        wavefront_stats.doubling_edges, 5 * wavefront_stats.denominators,
        wavefront_stats.denominators + wavefront_stats.doubling_edges, online_scratch_bytes,
        tail_stream_checks, tail_double_checks, tail_pair_checks, tail_pair_preparation_checks,
        tail_complete_checks, tail_complete_preparation_checks, periodic_lookups, periodic_accepted,
        periodic_fallbacks, periodic_checks, periodic_word_digest, mixed_lookups, mixed_fallbacks,
        mixed_checks, mixed_action_digest, tau3_preparation_checks, tau3_checks,
        tau3_action_fallbacks, tau3_action_digest, tau3_atlas_checks, sparse_preparation_checks,
        sparse_checks, sparse_action_fallbacks, sparse_action_digest, sparse_cold_pairs,
        radix27_checks, radix27_action_fallbacks, radix27_action_digest, radix27_dp_states,
        radix27_dp_options, scatter_pairs, scatter_preparation_checks);
    return 0;
}
