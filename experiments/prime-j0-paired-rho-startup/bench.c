/* One invocation solves one public target with an empty rho table. The
 * target is supplied as a point; its fixture scalar is never an argument. */
#include "cryptanalysis/ca_curve.h"
#include "ca_internal.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int parse_u64(const char *input, uint64_t *value)
{
    char *end = NULL;
    errno = 0;
    unsigned long long parsed = strtoull(input, &end, 10);
    if (errno || end == input || *end) return 0;
    *value = (uint64_t)parsed;
    return (unsigned long long)*value == parsed;
}

int main(int argc, char **argv)
{
    if (argc != 5 || (strcmp(argv[1], "reference") && strcmp(argv[1], "paired2") &&
                      strcmp(argv[1], "paired2-batch") &&
                      strcmp(argv[1], "paired2-plane-batch") &&
                      strcmp(argv[1], "paired2-free-gauge-batch") &&
                      strcmp(argv[1], "taupair-steered-batch"))) {
        fputs("usage: ca_paired_rho_bench reference|paired2|paired2-batch|paired2-plane-batch|paired2-free-gauge-batch|taupair-steered-batch target_x target_y seed\n", stderr);
        return 2;
    }
    uint64_t target_x, target_y, seed;
    if (!parse_u64(argv[2], &target_x) || !parse_u64(argv[3], &target_y) ||
        !parse_u64(argv[4], &seed) || !seed) {
        fputs("invalid target or seed\n", stderr);
        return 2;
    }
    ca_group group;
    ca_curve_info info;
    if (ca_curve_group(&group, UINT64_C(4294967377), 0, 15,
                       UINT64_C(23729779), &info) != CA_OK ||
        info.endo != CA_CURVE_ENDO_J0) return 2;
    uint64_t base_words[4] = {UINT64_C(481899190), UINT64_C(1998487369), 0, 0};
    uint64_t target_words[4] = {target_x, target_y, 0, 0};
    ca_elem base, target;
    if (!ca_group_encode(&group, &base, base_words) ||
        !ca_group_encode(&group, &target, target_words)) {
        fputs("invalid public point\n", stderr);
        return 2;
    }
    ca_curve_startup_mode mode = strcmp(argv[1], "paired2") == 0
        ? CA_CURVE_STARTUP_TAU_PAIRED2
        : strcmp(argv[1], "paired2-batch") == 0
            ? CA_CURVE_STARTUP_TAU_PAIRED2_BATCH
            : strcmp(argv[1], "paired2-plane-batch") == 0
                ? CA_CURVE_STARTUP_TAU_PAIRED2_PLANE_BATCH
                : strcmp(argv[1], "paired2-free-gauge-batch") == 0
                    ? CA_CURVE_STARTUP_TAU_PAIRED2_FREE_GAUGE_BATCH
                : strcmp(argv[1], "taupair-steered-batch") == 0
                    ? CA_CURVE_STARTUP_TAU_PAIRED2_TAUPAIR_STEER_BATCH
                : CA_CURVE_STARTUP_GENERIC;
    ca_stats stats = {0};
    ca_curve_startup_stats startup = {0};
    uint64_t scalar = UINT64_MAX;
    ca_status status = ca_curve_solve_startup(&group, &base, &target, seed, &scalar,
                                              mode, &startup, NULL, &stats);
    if (status != CA_OK) {
        fprintf(stderr, "rho failed: status=%d\n", (int)status);
        return 1;
    }
    double replay_start = ca_now();
    ca_elem replay;
    ca_group_mul(&group, &replay, &base, scalar, NULL);
    int verified = scalar < group.order && ca_group_equal(&group, &replay, &target);
    double replay_ms = 1000.0 * (ca_now() - replay_start);
    if (!verified) {
        fputs("scalar replay failed\n", stderr);
        return 1;
    }
    printf("curve=glv-j0-32 target_x=%" PRIu64 " target_y=%" PRIu64
           " seed=%" PRIu64 " mode=%s scalar=%" PRIu64
           " online_ms=%.6f replay_ms=%.6f"
           " group_ops=%" PRIu64 " table_entries=%" PRIu64
           " table_evaluations=%" PRIu64 " restart_evaluations=%" PRIu64
           " startup_budget_ops=%" PRIu64
           " prepare_tau=%" PRIu64 " prepare_doubles=%" PRIu64
           " prepare_mixed_adds=%" PRIu64 " prepare_inversions=%" PRIu64
           " prepare_rotations=%" PRIu64 " precomp_bytes=%" PRIu64
           " eval_tau=%" PRIu64 " eval_mixed_adds=%" PRIu64
           " eval_rotations=%" PRIu64 " eval_inversions=%" PRIu64
           " table_output_inversions=%" PRIu64
           " restart_output_inversions=%" PRIu64 " table_batch_size=%" PRIu64
           " eval_recode_attempts=%" PRIu64 " eval_pair_scores=%" PRIu64
           " eval_lattice_points_checked=%" PRIu64
           " eval_free_gauge_transitions=%" PRIu64
           " eval_tau_pairs=%" PRIu64
           " eval_tau_pair_cheap_z=%" PRIu64
           " eval_gauge_table_lookups=%" PRIu64
           " prepare_ms=%.6f startup_eval_ms=%.6f verified=1\n",
           target_x, target_y, seed, argv[1], scalar,
           1000.0 * stats.seconds, replay_ms, stats.group_ops, stats.table_entries,
           startup.table_evaluations, startup.restart_evaluations,
           startup.budget_equivalent_group_ops,
           startup.prepare_tau, startup.prepare_doubles, startup.prepare_mixed_adds,
           startup.prepare_inversions, startup.prepare_rotations,
           startup.prepare_bytes, startup.eval_tau, startup.eval_mixed_adds,
           startup.eval_rotations, startup.eval_inversions,
           startup.table_output_inversions, startup.restart_output_inversions,
           startup.table_batch_size,
           startup.eval_recode_attempts, startup.eval_pair_scores,
           startup.eval_lattice_points_checked,
           startup.eval_free_gauge_transitions,
           startup.eval_tau_pairs, startup.eval_tau_pair_cheap_z,
           startup.eval_gauge_table_lookups,
           1000.0 * startup.prepare_seconds, 1000.0 * startup.evaluation_seconds);
    return 0;
}
