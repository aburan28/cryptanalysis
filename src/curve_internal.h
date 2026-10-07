/* Coordinate representative for the order-six j=0 rho quotient.
 * Internal to the curve solver and its correctness tests. */
#ifndef CA_CURVE_INTERNAL_H
#define CA_CURVE_INTERNAL_H

#include "cryptanalysis/ca_group.h"
#include "ca_internal.h"

/* Precondition: g carries psi(x,y)=(beta*x,-y), with beta of order three.
 * Return k such that the replacement point is psi^k of the input. */
static inline uint32_t ca_j0_coordinate_class_reduce(const ca_group *g, ca_elem *Y)
{
    if (Y->w[2]) return 0;

    uint64_t x0 = Y->w[0];
    uint64_t x1 = ca_mont_mul(&g->mont, g->endo_c_mont, x0);
    uint64_t x2 = ca_mont_mul(&g->mont, g->endo_c_mont, x1);
    uint64_t best = x0;
    uint32_t j = 0;
    if (x1 < best) { best = x1; j = 1; }
    if (x2 < best) { best = x2; j = 2; }

    uint64_t y = Y->w[1];
    uint64_t minus_y = y ? g->p - y : 0;
    uint32_t neg = minus_y < y;
    Y->w[0] = best;
    if (neg) Y->w[1] = minus_y;
    Y->w[2] = 0;
    Y->w[3] = 0;

    /* psi^j has sign (-1)^j; psi^(j+3) has the opposite sign. */
    return j + 3u * ((j & 1u) ^ neg);
}

/* Same hash-minimum representative and strict k-order tie break as the
 * legacy loop. Factor the six hashes into three x words and two y words. */
static inline uint32_t ca_j0_factored_hash_class_reduce(const ca_group *g, ca_elem *Y)
{
    if (Y->w[2]) return 0;
    uint64_t x[3];
    x[0] = Y->w[0];
    x[1] = ca_mont_mul(&g->mont, g->endo_c_mont, x[0]);
    x[2] = ca_mont_mul(&g->mont, g->endo_c_mont, x[1]);
    const uint64_t y[2] = {Y->w[1], Y->w[1] ? g->p - Y->w[1] : 0};
    const uint64_t yh[2] = {ca_mix64(y[0]), ca_mix64(y[1])};
    uint64_t best_hash = ca_mix64(x[0] * UINT64_C(0x9E3779B97F4A7C15) ^ yh[0]);
    uint32_t best_k = 0;
    for (uint32_t k = 1; k < 6; k++) {
        uint64_t h = ca_mix64(x[k % 3] * UINT64_C(0x9E3779B97F4A7C15) ^ yh[k & 1]);
        if (h < best_hash) { best_hash = h; best_k = k; }
    }
    Y->w[0] = x[best_k % 3];
    Y->w[1] = y[best_k & 1];
    if (best_k) {
        Y->w[2] = 0;
        Y->w[3] = 0;
    }
    return best_k;
}

#endif
