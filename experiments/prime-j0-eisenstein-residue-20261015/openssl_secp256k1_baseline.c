/* Fixed-base secp256k1 scalar multiplication on the frozen Eisenstein fixture.
 * Input lines: 64 lowercase scalar hex digits, a space, and x:y point hex.
 * Fixture parsing, curve setup and one warm multiplication are outside timing.
 * The interval includes EC_POINT_mul and affine x:y serialization for each case.
 */
#define _POSIX_C_SOURCE 200809L
#include <openssl/bn.h>
#include <openssl/ec.h>
#include <openssl/obj_mac.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define MAX_CASES 12288
#define HEX_BYTES 32
#define POINT_HEX_LEN 129

typedef struct {
    BIGNUM *scalar;
    char expected[POINT_HEX_LEN + 1];
    char actual[POINT_HEX_LEN + 1];
} test_case;

static double elapsed_ms(struct timespec start, struct timespec end) {
    return (double)(end.tv_sec - start.tv_sec) * 1000.0
        + (double)(end.tv_nsec - start.tv_nsec) / 1000000.0;
}

static void hex32(char out[65], const unsigned char in[HEX_BYTES]) {
    static const char digits[] = "0123456789abcdef";
    for (size_t i = 0; i < HEX_BYTES; ++i) {
        out[2 * i] = digits[in[i] >> 4];
        out[2 * i + 1] = digits[in[i] & 15];
    }
    out[64] = '\0';
}

static int point_hex(const EC_GROUP *group, const EC_POINT *point,
                     BN_CTX *ctx, BIGNUM *x, BIGNUM *y,
                     char out[POINT_HEX_LEN + 1]) {
    unsigned char xb[HEX_BYTES], yb[HEX_BYTES];
    char xh[65], yh[65];
    if (!EC_POINT_get_affine_coordinates(group, point, x, y, ctx)
        || BN_bn2binpad(x, xb, HEX_BYTES) != HEX_BYTES
        || BN_bn2binpad(y, yb, HEX_BYTES) != HEX_BYTES) return 0;
    hex32(xh, xb);
    hex32(yh, yb);
    memcpy(out, xh, 64);
    out[64] = ':';
    memcpy(out + 65, yh, 65);
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s fixture.txt count\n", argv[0]);
        return 2;
    }
    char *endptr = NULL;
    unsigned long parsed = strtoul(argv[2], &endptr, 10);
    if (!endptr || *endptr || parsed == 0 || parsed > MAX_CASES) return 2;
    size_t count = (size_t)parsed;
    FILE *input = fopen(argv[1], "r");
    if (!input) return 2;
    test_case *cases = calloc(count, sizeof(*cases));
    EC_GROUP *group = EC_GROUP_new_by_curve_name(NID_secp256k1);
    EC_POINT *point = group ? EC_POINT_new(group) : NULL;
    BN_CTX *ctx = BN_CTX_new();
    BIGNUM *x = BN_new(), *y = BN_new();
    if (!cases || !group || !point || !ctx || !x || !y) return 2;
    char line[256], scalar_hex[65], expected[POINT_HEX_LEN + 1];
    for (size_t i = 0; i < count; ++i) {
        if (!fgets(line, sizeof(line), input)
            || sscanf(line, "%64s %129s", scalar_hex, expected) != 2
            || strlen(scalar_hex) != 64 || strlen(expected) != POINT_HEX_LEN
            || BN_hex2bn(&cases[i].scalar, scalar_hex) != 64) return 2;
        memcpy(cases[i].expected, expected, POINT_HEX_LEN + 1);
    }
    fclose(input);
    struct timespec prep_start, prep_end, start, end;
    clock_gettime(CLOCK_MONOTONIC_RAW, &prep_start);
    if (!EC_POINT_mul(group, point, cases[0].scalar, NULL, NULL, ctx)
        || !point_hex(group, point, ctx, x, y, cases[0].actual)) return 3;
    clock_gettime(CLOCK_MONOTONIC_RAW, &prep_end);
    clock_gettime(CLOCK_MONOTONIC_RAW, &start);
    for (size_t i = 0; i < count; ++i) {
        if (!EC_POINT_mul(group, point, cases[i].scalar, NULL, NULL, ctx)
            || !point_hex(group, point, ctx, x, y, cases[i].actual)) return 3;
    }
    clock_gettime(CLOCK_MONOTONIC_RAW, &end);
    for (size_t i = 0; i < count; ++i) {
        if (strcmp(cases[i].actual, cases[i].expected)) {
            fprintf(stderr, "mismatch at case %zu\n", i);
            return 4;
        }
    }
    printf("verified=1 count=%zu online_ms=%.6f preparation_ms=%.6f "
           "max_selected=0 point=%s\n", count, elapsed_ms(start, end),
           elapsed_ms(prep_start, prep_end), cases[count - 1].actual);
    for (size_t i = 0; i < count; ++i) BN_free(cases[i].scalar);
    BN_free(y);
    BN_free(x);
    BN_CTX_free(ctx);
    EC_POINT_free(point);
    EC_GROUP_free(group);
    free(cases);
    return 0;
}
