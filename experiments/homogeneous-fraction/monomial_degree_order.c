#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static uint32_t *rank_by_mask;
static uint32_t *mask_by_rank;
static uint32_t nvars_current;
static uint32_t nmonomials_current;

int degree_order_init(int nvars)
{
    if (nvars < 1 || nvars > 24) return 1;
    free(rank_by_mask);
    free(mask_by_rank);
    rank_by_mask = NULL;
    mask_by_rank = NULL;
    nvars_current = (uint32_t)nvars;
    nmonomials_current = 1u << nvars;

    rank_by_mask = (uint32_t *)malloc((size_t)nmonomials_current * sizeof(uint32_t));
    mask_by_rank = (uint32_t *)malloc((size_t)nmonomials_current * sizeof(uint32_t));
    uint32_t *colex = (uint32_t *)calloc((size_t)nmonomials_current, sizeof(uint32_t));
    if (!rank_by_mask || !mask_by_rank || !colex) return 2;

    uint32_t choose[25][25] = {{0}};
    choose[0][0] = 1;
    for (uint32_t n = 1; n <= nvars_current; n++) {
        choose[n][0] = choose[n][n] = 1;
        for (uint32_t k = 1; k < n; k++) choose[n][k] = choose[n - 1][k - 1] + choose[n - 1][k];
    }

    for (uint32_t mask = 1; mask < nmonomials_current; mask++) {
        uint32_t highest = 31u - (uint32_t)__builtin_clz(mask);
        uint32_t weight = (uint32_t)__builtin_popcount(mask);
        uint32_t lower = mask ^ (1u << highest);
        colex[mask] = colex[lower] + choose[highest][weight];
    }

    uint32_t offsets[25] = {0};
    for (uint32_t weight = 1; weight <= nvars_current; weight++)
        offsets[weight] = offsets[weight - 1] + choose[nvars_current][weight - 1];

    for (uint32_t mask = 0; mask < nmonomials_current; mask++) {
        uint32_t weight = (uint32_t)__builtin_popcount(mask);
        uint32_t rank = offsets[weight] + colex[mask];
        rank_by_mask[mask] = rank;
        mask_by_rank[rank] = mask;
    }
    free(colex);
    return 0;
}

const uint32_t *degree_order_rank_map(void) { return rank_by_mask; }
const uint32_t *degree_order_inverse_map(void) { return mask_by_rank; }

int degree_order_reorder_bits(const uint8_t *input, uint8_t *output)
{
    if (!input || !output || !rank_by_mask) return 1;
    size_t nbytes = (size_t)nmonomials_current / 8;
    memset(output, 0, nbytes);
    for (size_t byte_index = 0; byte_index < nbytes; byte_index++) {
        uint8_t byte = input[byte_index];
        while (byte) {
            uint32_t bit = (uint32_t)__builtin_ctz((unsigned int)byte);
            uint32_t monomial = (uint32_t)(byte_index * 8 + bit);
            uint32_t rank = rank_by_mask[monomial];
            output[rank >> 3] |= (uint8_t)(1u << (rank & 7));
            byte &= (uint8_t)(byte - 1);
        }
    }
    return 0;
}
