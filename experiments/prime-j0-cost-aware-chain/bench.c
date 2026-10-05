/* Paired prepared-scalar workload for the isolated benchmark service.
 * All loading, preparation, and independent replay are outside online_ms. */
#include "ca_internal.h"
#include "cryptanalysis/ca_curve.h"
#include "ec_tau_internal.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SCALARS    4096
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

int main(int argc, char **argv)
{
    if (argc != 5 ||
        (strcmp(argv[1], "reference") != 0 && strcmp(argv[1], "baseline") != 0 &&
         strcmp(argv[1], "cost") != 0 && strcmp(argv[1], "atlas") != 0) ||
        (strcmp(argv[3], "0") != 0 && strcmp(argv[3], "1") != 0)) {
        fprintf(stderr, "usage: %s reference|baseline|cost|atlas glv-j0-32|j0-56 0|1 INPUT\n",
                argv[0]);
        return 2;
    }
    uint64_t p, b, order;
    if (!select_curve(argv[2], &p, &b, &order)) return 2;
    int mode = strcmp(argv[1], "reference") == 0  ? 0
               : strcmp(argv[1], "baseline") == 0 ? 1
               : strcmp(argv[1], "cost") == 0     ? 2
                                                  : 3;
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
    if (strcmp(argv[3], "1") == 0) {
        ca_elem second;
        ca_group_mul(&group, &second, &point, 37, NULL);
        point = second;
    }
    uint64_t point_words[4];
    ca_group_decode(&group, point_words, &point);
    ca_elem *outputs = calloc(SCALARS, sizeof(*outputs));
    if (!outputs) return 2;
    ca_tau4_precomp pre;
    double prep_ms = 0;
    if (mode != 0) {
        double t0 = ca_now();
        if (!ca_ec_tau4_prepare(&group, &point, &pre, NULL)) {
            free(outputs);
            return 2;
        }
        prep_ms = 1000 * (ca_now() - t0);
    }
    uint64_t triples = 0, adds = 0, rotations = 0;
    double start = ca_now();
    for (size_t i = 0; i < SCALARS; i++) {
        if (mode == 0) {
            ca_group_mul(&group, &outputs[i], &point, scalars[i], NULL);
        } else {
            uint64_t t = 0, a = 0, r = 0;
            if (!ca_ec_tau4_mul_prepared_profile(&group, &pre, &outputs[i], scalars[i], mode - 1,
                                                 &t, &a, &r)) {
                fprintf(stderr, "scalar evaluation failed at index %zu\n", i);
                free(outputs);
                return 1;
            }
            triples += t;
            adds += a;
            rotations += r;
        }
    }
    double online_ms = 1000 * (ca_now() - start);
    double verify_start = ca_now();
    uint64_t output_digest = FNV_OFFSET;
    for (size_t i = 0; i < SCALARS; i++) {
        if (mode != 0) {
            if (mode == 3 && !ca_ec_tau4_recode_compare_scalar(&pre, scalars[i])) {
                fprintf(stderr, "digit stream mismatch at index %zu\n", i);
                free(outputs);
                return 1;
            }
            ca_elem expected;
            ca_group_mul(&group, &expected, &point, scalars[i], NULL);
            if (!ca_group_equal(&group, &outputs[i], &expected)) {
                fprintf(stderr, "independent replay mismatch at index %zu\n", i);
                free(outputs);
                return 1;
            }
        }
        uint64_t words[4];
        ca_group_decode(&group, words, &outputs[i]);
        for (size_t j = 0; j < 3; j++) output_digest = digest_word(output_digest, words[j]);
    }
    double verify_ms = 1000 * (ca_now() - verify_start);
    free(outputs);
    printf("curve=%s point_index=%s count=%d base_x=%" PRIu64 " base_y=%" PRIu64
           " input_digest=%016" PRIx64 " output_digest=%016" PRIx64
           " online_ms=%.6f prep_ms=%.6f verify_ms=%.6f"
           " triples=%" PRIu64 " adds=%" PRIu64 " rotations=%" PRIu64 " verified=1\n",
           argv[2], argv[3], SCALARS, point_words[0], point_words[1], input_digest, output_digest,
           online_ms, prep_ms, verify_ms, triples, adds, rotations);
    return 0;
}
