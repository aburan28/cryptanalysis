/*
 * pohlig.c - Pohlig-Hellman and solver dispatch.
 */
#include "cryptanalysis/ca_pohlig.h"
#include "dlog_internal.h"

void ca_dlog_params_default(ca_dlog_params *p)
{
    memset(p, 0, sizeof(*p));
    p->solver = CA_SOLVER_AUTO;
    p->bsgs_max_prime = 1ULL << 36;
    ca_bsgs_params_default(&p->bsgs);
    ca_rho_params_default(&p->rho);
    ca_kangaroo_params_default(&p->kangaroo);
    ca_grumpy_params_default(&p->grumpy);
}

const char *ca_solver_name(ca_solver s)
{
    switch (s) {
    case CA_SOLVER_AUTO: return "auto";
    case CA_SOLVER_BSGS: return "bsgs";
    case CA_SOLVER_RHO: return "rho";
    case CA_SOLVER_KANGAROO: return "kangaroo";
    case CA_SOLVER_GRUMPY: return "grumpy";
    case CA_SOLVER_BRUTE: return "brute";
    }
    return "?";
}

static ca_status brute_force(const ca_group *g, const ca_elem *base, const ca_elem *target,
                             uint64_t lo, uint64_t hi, uint64_t *x, ca_stats *st)
{
    ca_elem cur;
    ca_group_mul(g, &cur, base, lo, st ? &st->group_ops : NULL);
    for (uint64_t k = lo;; k++) {
        if (ca_group_equal(g, &cur, target)) { *x = k; return CA_OK; }
        if (k == hi) break;
        ca_group_op(g, &cur, &cur, base);
        if (st) st->group_ops++;
    }
    return CA_ERR_NOT_FOUND;
}

ca_status ca_dlog_prime_order(const ca_group *g, const ca_elem *base, const ca_elem *target,
                              uint64_t lo, uint64_t hi, const ca_dlog_params *params,
                              uint64_t *x, ca_stats *st)
{
    ca_dlog_params def;
    if (!params) { ca_dlog_params_default(&def); params = &def; }
    ca_status rc = ca_resolve_interval(g, &lo, &hi);
    if (rc != CA_OK) return rc;
    uint64_t width = hi - lo;
    ca_solver s = params->solver;
    if (s == CA_SOLVER_AUTO) {
        uint64_t limit = params->bsgs_max_prime ? params->bsgs_max_prime : (1ULL << 36);
        if (width < 4096) s = CA_SOLVER_BRUTE;
        else if (width <= limit) s = CA_SOLVER_BSGS;
        else if (lo == 0 && g->order && hi == g->order - 1) s = CA_SOLVER_RHO;
        else s = CA_SOLVER_KANGAROO;
    }
    switch (s) {
    case CA_SOLVER_BRUTE:
        return brute_force(g, base, target, lo, hi, x, st);
    case CA_SOLVER_BSGS:
        return ca_bsgs_solve(g, base, target, lo, hi, &params->bsgs, x, st);
    case CA_SOLVER_KANGAROO:
        return ca_kangaroo_solve(g, base, target, lo, hi, &params->kangaroo, x, st);
    case CA_SOLVER_GRUMPY:
        return ca_grumpy_solve(g, base, target, lo, hi, &params->grumpy, x, st);
    case CA_SOLVER_RHO: {
        if (lo == 0 && g->order && hi == g->order - 1)
            return ca_rho_solve(g, base, target, &params->rho, x, st);
        /* rho on a sub-interval: solve in the full group and reduce */
        if (g->order == 0) return CA_ERR_INVALID;
        rc = ca_rho_solve(g, base, target, &params->rho, x, st);
        if (rc != CA_OK) return rc;
        /* modulo ord(base), not just modulo the group order: see the comment
         * on ca_fit_interval_base */
        if (!ca_fit_interval_base(g, base, x, lo, hi)) return CA_ERR_NOT_FOUND;
        return CA_OK;
    }
    default:
        return CA_ERR_INVALID;
    }
}

ca_status ca_pohlig_hellman(const ca_group *g, const ca_elem *base, const ca_elem *target,
                            const ca_dlog_params *params, uint64_t *x, ca_stats *st)
{
    ca_dlog_params def;
    if (!params) { ca_dlog_params_default(&def); params = &def; }
    if (g->order == 0) {
        ca_set_error("Pohlig-Hellman requires the group order");
        return CA_ERR_INVALID;
    }
    double t0 = ca_now();
    /* Decompose by ord(base), not by the group order: when base generates a
     * proper subgroup (a non-cyclic curve group, or a base of smaller order)
     * some q^(e-1) * base_e is the identity and the digit solve below has no
     * answer.  The logarithm is only defined modulo ord(base) anyway. */
    uint64_t n = ca_group_elem_order(g, base);
    if (n == 0) n = g->order;
    /* ord(target) must divide ord(base); otherwise a rho digit solve in some
     * large prime subgroup would walk forever. */
    if (!ca_check_members(g, base, target, n, "Pohlig-Hellman")) return CA_ERR_NOT_FOUND;
    ca_factorization f;
    ca_factorize(n, &f);
    uint64_t result = 0, modulus = 1;
    for (unsigned fi = 0; fi < f.count; fi++) {
        uint64_t q = f.f[fi].p;
        unsigned e = f.f[fi].e;
        uint64_t qe = 1;
        for (unsigned k = 0; k < e; k++) qe *= q;
        /* work in the order-q^e subgroup: base_e = (n/q^e) base */
        ca_elem base_e, target_e, gq;
        ca_group_mul(g, &base_e, base, n / qe, st ? &st->group_ops : NULL);
        ca_group_mul(g, &target_e, target, n / qe, st ? &st->group_ops : NULL);
        /* gq = q^(e-1) * base_e has order q */
        ca_group_mul(g, &gq, &base_e, qe / q, st ? &st->group_ops : NULL);
        ca_group sub = *g;
        sub.order = q;
        uint64_t xk = 0, qk = 1;
        for (unsigned k = 0; k < e; k++) {
            /* h_k = (target_e - xk * base_e) * q^(e-1-k) */
            ca_elem t, hk;
            ca_group_mul(g, &t, &base_e, xk, st ? &st->group_ops : NULL);
            ca_group_inv(g, &t, &t);
            ca_group_op(g, &hk, &target_e, &t);
            ca_group_mul(g, &hk, &hk, qe / (qk * q), st ? &st->group_ops : NULL);
            uint64_t d;
            ca_status rc = ca_dlog_prime_order(&sub, &gq, &hk, 0, q - 1, params, &d, st);
            if (rc != CA_OK) return rc;
            xk += d * qk;
            qk *= q;
        }
        result = ca_crt2(result, modulus, xk, qe);
        modulus *= qe;
    }
    if (!ca_verify_log(g, base, target, result)) {
        ca_set_error("Pohlig-Hellman result failed verification (target not in <base>?)");
        return CA_ERR_NOT_FOUND;
    }
    *x = result;
    if (st) st->seconds = ca_now() - t0;
    return CA_OK;
}

ca_status ca_dlog(const ca_group *g, const ca_elem *base, const ca_elem *target, uint64_t *x,
                  ca_stats *st)
{
    return ca_pohlig_hellman(g, base, target, NULL, x, st);
}
