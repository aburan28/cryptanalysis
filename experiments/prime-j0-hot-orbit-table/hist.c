/* Train only on the old scalar pairs; output all 486 slot frequencies. */
#include "cryptanalysis/ca_curve.h"
#include "ec_tau_internal.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static uint64_t read_u64(const unsigned char bytes[8])
{
    uint64_t value = 0;
    for (unsigned i = 0; i < 8; i++) value |= (uint64_t)bytes[i] << (8 * i);
    return value;
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fputs("usage: ca_joint_tau_hist glv-j0-32|j0-56 pairs.bin\n", stderr);
        return 2;
    }
    int large = strcmp(argv[1], "j0-56") == 0;
    if (!large && strcmp(argv[1], "glv-j0-32") != 0) return 2;
    FILE *input = fopen(argv[2], "rb");
    if (!input) return 2;
    uint64_t scalars[1024][2];
    for (size_t i = 0; i < 1024; i++) {
        unsigned char bytes[16];
        if (fread(bytes, 1, 16, input) != 16) { fclose(input); return 2; }
        scalars[i][0] = read_u64(bytes);
        scalars[i][1] = read_u64(bytes + 8);
    }
    int eof = fgetc(input) == EOF;
    if (fclose(input) != 0 || !eof) return 2;

    uint64_t p = large ? UINT64_C(2305843009213693951) : UINT64_C(4294967377);
    uint64_t b = large ? 7 : 15;
    uint64_t order = large ? UINT64_C(53624256071278747) : UINT64_C(23729779);
    uint64_t words[4] = {large ? UINT64_C(1839617427631136375) : UINT64_C(481899190),
                         large ? UINT64_C(725584580046817702) : UINT64_C(1998487369), 0, 0};
    ca_group group;
    ca_curve_info info;
    if (ca_curve_group(&group, p, 0, b, order, &info) != CA_OK ||
        info.endo != CA_CURVE_ENDO_J0) return 2;
    ca_elem base, partner;
    if (!ca_group_encode(&group, &base, words)) return 2;
    ca_group_mul(&group, &partner, &base, 37, NULL);
    ca_tau4_joint_precomp pre;
    if (!ca_ec_tau4_joint_prepare(&group, &base, &partner, &pre, NULL)) return 2;
    uint64_t histogram[486] = {0};
    for (size_t i = 0; i < 1024; i++)
        if (!ca_ec_tau4_pair_histogram(&pre, scalars[i][0], scalars[i][1], histogram)) return 2;
    for (unsigned i = 0; i < 486; i++) printf("%u,%" PRIu64 "\n", i, histogram[i]);
    return 0;
}
