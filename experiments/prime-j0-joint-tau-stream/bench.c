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
                       strcmp(argv[1], "hot64"))) {
        fputs("usage: ca_joint_tau_bench generic|split|joint|orbit|hot64 glv-j0-32|j0-56 pairs.bin\n", stderr);
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
               strcmp(argv[1], "orbit") == 0 ? 3 : 4;
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
            int ok = mode == 4
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
            total.doubles += one.doubles;
            total.mixed_adds += one.mixed_adds;
            total.full_adds += one.full_adds;
            total.rotations += one.rotations;
            total.inversions += one.inversions;
            total.overlaps += one.overlaps;
            total.fused_hits += one.fused_hits;
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
           " tau_steps=%" PRIu64 " doubles=%" PRIu64
           " mixed_adds=%" PRIu64 " full_adds=%" PRIu64
           " rotations=%" PRIu64 " output_inversions=%" PRIu64
           " overlaps=%" PRIu64 " fused_hits=%" PRIu64
           " verified=1\n",
           argv[1], argv[2], PAIRS, words[0], words[1],
           partner_words[0], partner_words[1], input_digest, output_digest,
           mode == 4 ? sizeof(hot) : mode == 3 ? sizeof(orbit) : sizeof(pre),
           prep_ms, online_ms, verify_ms, prep.tau_steps, prep.doubles,
           prep.mixed_adds, prep.rotations, prep.inversions,
           total.tau_steps, total.doubles, total.mixed_adds, total.full_adds,
           total.rotations, total.inversions, total.overlaps, total.fused_hits);
    return 0;
}
