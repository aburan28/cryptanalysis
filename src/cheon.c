/*
 * cheon.c - Cheon's strong-DH attack, d | p-1 case.
 *
 * Phase 1.  Let zeta generate (Z/pZ)^*, alpha = zeta^k, and
 *   eta = zeta^d      (order (p-1)/d in the exponent group).
 * Then g^(alpha^d) = g^(eta^k), so k mod (p-1)/d is the "discrete log" of
 * gd with respect to the map u -> g^(eta^u).  BSGS: baby steps
 *   g^(eta^j),  j < m1,
 * giant steps  gd^(eta^(-m1 i)) -- a match  g^(eta^j) = gd^(eta^(-m1 i))
 * means  eta^j = eta^(k - m1 i)  i.e.  k == j + m1 i  (mod (p-1)/d).
 *
 * Phase 2.  Write k = k1 + ((p-1)/d) k2 with k2 < d.  Let
 *   theta = zeta^((p-1)/d)   (order d),  base = g^(zeta^k1).
 * Then g^alpha = base^(theta^k2): the same BSGS with m2 = ceil(sqrt(d)).
 */
#include "cryptanalysis/ca_cheon.h"
#include "dlog_internal.h"

#include <math.h>

void ca_cheon_params_default(ca_cheon_params *p) { memset(p, 0, sizeof(*p)); }

ca_status ca_cheon_make_instance(const ca_group *g, const ca_elem *gen, uint64_t alpha, uint64_t d,
                                 ca_elem *g_alpha, ca_elem *g_alpha_d)
{
    uint64_t p = g->order;
    if (p == 0 || !ca_is_prime(p)) {
        ca_set_error("Cheon's attack needs a prime group order");
        return CA_ERR_INVALID;
    }
    if (d == 0 || (p - 1) % d != 0) {
        ca_set_error("d must divide p-1");
        return CA_ERR_INVALID;
    }
    if (alpha % p == 0) {
        ca_set_error("alpha must be nonzero modulo p");
        return CA_ERR_INVALID;
    }
    ca_group_mul(g, g_alpha, gen, alpha % p, NULL);
    ca_group_mul(g, g_alpha_d, gen, ca_powmod(alpha, d, p), NULL);
    return CA_OK;
}

uint64_t ca_cheon_best_divisor(uint64_t p, double *cost_exps)
{
    ca_factorization f;
    if (ca_factorize(p - 1, &f) != CA_OK) return 0;
    /* enumerate divisors */
    uint64_t best = 1;
    double best_cost = 1e300;
    unsigned idx[CA_MAX_FACTORS] = {0};
    for (;;) {
        uint64_t d = 1;
        for (unsigned i = 0; i < f.count; i++)
            for (unsigned e = 0; e < idx[i]; e++) d *= f.f[i].p;
        double cost = 2.0 * (sqrt((double)((p - 1) / d)) + sqrt((double)d));
        if (cost < best_cost) { best_cost = cost; best = d; }
        unsigned i = 0;
        while (i < f.count) {
            if (++idx[i] <= f.f[i].e) break;
            idx[i] = 0;
            i++;
        }
        if (i == f.count) break;
    }
    if (cost_exps) *cost_exps = best_cost;
    return best;
}

/*
 * Generic "exponent-orbit BSGS": find u in [0, ord) with
 *   base^(eta^u) == target,   eta of multiplicative order ord mod p.
 * Costs about 2 sqrt(ord) exponentiations.
 */
static ca_status orbit_bsgs(const ca_group *g, const ca_elem *base, const ca_elem *target,
                            uint64_t eta, uint64_t ord, uint64_t p, uint64_t max_exps,
                            uint64_t *u, ca_stats *st)
{
    uint64_t m = ca_isqrt(ord - 1) + 1;
    if (m > ord) m = ord;
    ca_htab tab;
    if (ca_htab_init(&tab, (size_t)m) != CA_OK) return CA_ERR_NOMEM;
    uint64_t exps = 0, ops = 0;
    /* baby steps: cur = base^(eta^j) ; next = cur^eta */
    ca_elem cur = *base;
    for (uint64_t j = 0; j < m; j++) {
        if (ca_htab_insert(&tab, ca_group_hash(g, &cur), j, 0, NULL, NULL) < 0) {
            ca_htab_free(&tab);
            return CA_ERR_NOMEM;
        }
        ca_group_mul(g, &cur, &cur, eta, &ops);
        exps++;
    }
    /* giant steps: gt = target^(eta^(-m i)) */
    uint64_t eta_inv_m = ca_powmod(ca_invmod(eta, p), m, p);
    ca_elem gt = *target;
    uint64_t steps = (ord - 1) / m + 1;
    ca_status rc = CA_ERR_NOT_FOUND;
    for (uint64_t i = 0; i < steps; i++) {
        uint64_t j;
        if (ca_htab_find(&tab, ca_group_hash(g, &gt), &j, NULL)) {
            ca_u128 cand = (ca_u128)j + (ca_u128)m * i;
            uint64_t c = (uint64_t)(cand % ord);
            /* verify: base^(eta^c) == target */
            ca_elem chk;
            ca_group_mul(g, &chk, base, ca_powmod(eta, c, p), &ops);
            exps++;
            if (ca_group_equal(g, &chk, target)) { *u = c; rc = CA_OK; break; }
        }
        ca_group_mul(g, &gt, &gt, eta_inv_m, &ops);
        exps++;
        if (max_exps && exps > max_exps) { rc = CA_ERR_LIMIT; break; }
    }
    if (st) {
        st->group_ops += ops;
        st->iterations += exps;
        st->table_entries = ca_max_u64(st->table_entries, tab.count);
        st->bytes_peak = ca_max_u64(st->bytes_peak, ca_htab_bytes(&tab));
    }
    ca_htab_free(&tab);
    return rc;
}

ca_status ca_cheon_solve(const ca_group *g, const ca_elem *gen, const ca_elem *g_alpha,
                         const ca_elem *g_alpha_d, uint64_t d, const ca_cheon_params *params,
                         uint64_t *alpha, ca_stats *st)
{
    ca_cheon_params def;
    if (!params) { ca_cheon_params_default(&def); params = &def; }
    uint64_t p = g->order;
    if (p == 0 || !ca_is_prime(p)) {
        ca_set_error("Cheon's attack needs a prime group order");
        return CA_ERR_INVALID;
    }
    if (d == 0 || (p - 1) % d != 0) {
        ca_set_error("d must divide p-1");
        return CA_ERR_INVALID;
    }
    double t0 = ca_now();
    uint64_t zeta = ca_primitive_root(p);
    uint64_t ord1 = (p - 1) / d;
    uint64_t eta = ca_powmod(zeta, d, p);            /* order ord1 */
    uint64_t theta = ca_powmod(zeta, ord1, p);       /* order d */
    uint64_t k1 = 0, k2 = 0;
    ca_status rc;
    /* Phase 1: gd = gen^(eta^k1) */
    rc = orbit_bsgs(g, gen, g_alpha_d, eta, ord1, p, params->max_exps, &k1, st);
    if (rc != CA_OK) return rc;
    /* Phase 2: g_alpha = base2^(theta^k2) with base2 = gen^(zeta^k1) */
    ca_elem base2;
    ca_group_mul(g, &base2, gen, ca_powmod(zeta, k1, p), st ? &st->group_ops : NULL);
    rc = orbit_bsgs(g, &base2, g_alpha, theta, d, p, params->max_exps, &k2, st);
    if (rc != CA_OK) return rc;
    /* alpha = zeta^(k1 + ord1 * k2) */
    uint64_t k = (uint64_t)(((ca_u128)k1 + (ca_u128)ord1 * k2) % (p - 1));
    uint64_t a = ca_powmod(zeta, k, p);
    ca_elem chk;
    ca_group_mul(g, &chk, gen, a, NULL);
    if (!ca_group_equal(g, &chk, g_alpha)) {
        ca_set_error("Cheon: recovered alpha failed verification");
        return CA_ERR_INTERNAL;
    }
    *alpha = a;
    if (st) st->seconds += ca_now() - t0;
    return rc;
}
