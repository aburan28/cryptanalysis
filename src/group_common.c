/*
 * group_common.c - generic operations on top of the vtable.
 */
#include "cryptanalysis/ca_group.h"
#include "ca_internal.h"

#include <stdio.h>

void ca_group_mul(const ca_group *g, ca_elem *r, const ca_elem *a, uint64_t k, uint64_t *ops)
{
    ca_elem acc, base = *a;
    ca_group_identity(g, &acc);
    uint64_t n = 0;
    /* right-to-left double-and-add: safe when r aliases a */
    while (k) {
        if (k & 1) { ca_group_op(g, &acc, &acc, &base); n++; }
        k >>= 1;
        if (k) { ca_group_dbl(g, &base, &base); n++; }
    }
    *r = acc;
    if (ops) *ops += n;
}

void ca_group_div(const ca_group *g, ca_elem *r, const ca_elem *a, const ca_elem *b)
{
    ca_elem bi;
    ca_group_inv(g, &bi, b);
    ca_group_op(g, r, a, &bi);
}

uint64_t ca_group_elem_order(const ca_group *g, const ca_elem *a)
{
    if (g->order == 0) return 0;
    ca_elem t;
    ca_group_mul(g, &t, a, g->order, NULL);
    if (!ca_group_is_identity(g, &t)) return 0;
    ca_factorization f;
    ca_factorize(g->order, &f);
    uint64_t ord = g->order;
    for (unsigned i = 0; i < f.count; i++) {
        for (unsigned e = 0; e < f.f[i].e; e++) {
            uint64_t cand = ord / f.f[i].p;
            ca_group_mul(g, &t, a, cand, NULL);
            if (ca_group_is_identity(g, &t)) ord = cand; else break;
        }
    }
    return ord;
}

void ca_group_random_power(const ca_group *g, ca_elem *r, const ca_elem *gen, uint64_t seed,
                           uint64_t *k_out)
{
    ca_rng rng;
    ca_rng_seed(&rng, ca_seed_or_random(seed));
    uint64_t n = g->order ? g->order : g->p;
    uint64_t k = 1 + ca_rng_below(&rng, n - 1);
    ca_group_mul(g, r, gen, k, NULL);
    if (k_out) *k_out = k;
}

ca_status ca_group_find_generator(const ca_group *g, ca_elem *gen, uint64_t seed)
{
    if (g->order == 0) return CA_ERR_INVALID;
    ca_rng rng;
    ca_rng_seed(&rng, ca_seed_or_random(seed));
    ca_factorization f;
    ca_factorize(g->order, &f);
    for (int tries = 0; tries < 10000; tries++) {
        ca_elem cand;
        if (g->kind == CA_GROUP_ZP) {
            uint64_t x = 2 + ca_rng_below(&rng, g->p - 3);
            uint64_t words[4] = {x, 0, 0, 0};
            ca_group_encode(g, &cand, words);
            if (g->cofactor > 1) ca_group_mul(g, &cand, &cand, g->cofactor, NULL);
        } else {
            ca_ec_random_point(g, &cand, ca_rng_next(&rng));
            if (g->cofactor > 1) ca_group_mul(g, &cand, &cand, g->cofactor, NULL);
        }
        if (ca_group_is_identity(g, &cand)) continue;
        int ok = 1;
        ca_elem t;
        for (unsigned i = 0; i < f.count; i++) {
            ca_group_mul(g, &t, &cand, g->order / f.f[i].p, NULL);
            if (ca_group_is_identity(g, &t)) { ok = 0; break; }
        }
        if (ok) {
            /* also make sure it really has order n */
            ca_group_mul(g, &t, &cand, g->order, NULL);
            if (!ca_group_is_identity(g, &t)) continue;
            *gen = cand;
            return CA_OK;
        }
    }
    return CA_ERR_NOT_FOUND;
}

void ca_group_format(const ca_group *g, const ca_elem *a, char *buf, size_t len)
{
    uint64_t w[4];
    ca_group_decode(g, w, a);
    if (g->kind == CA_GROUP_ZP) {
        snprintf(buf, len, "%llu", (unsigned long long)w[0]);
    } else if (w[2]) {
        snprintf(buf, len, "O");
    } else {
        snprintf(buf, len, "(%llu, %llu)", (unsigned long long)w[0], (unsigned long long)w[1]);
    }
}
