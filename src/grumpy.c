/*
 * grumpy.c - two grumpy giants and a baby.
 *
 * After shifting the problem so that x' = x - lo lies in [0, N):
 *   baby   B_j = j*G                       (j = 0, 1, 2, ...)
 *   giant1 U_i = H' + i*m*G                (i = 0, 1, 2, ...)
 *   giant2 V_i = 2H' - i*(m+1)*G
 * Collisions:
 *   B_j = U_i   =>  x' = j - i m
 *   B_j = V_i   =>  2x' = j + i (m+1)
 *   U_i = V_k   =>  x' = i m + k (m+1)
 * All congruences are taken modulo the group order n when known, and
 * every candidate is verified before being returned.
 */
#include "cryptanalysis/ca_grumpy.h"
#include "dlog_internal.h"

enum { W_BABY = 0, W_G1 = 1, W_G2 = 2 };

void ca_grumpy_params_default(ca_grumpy_params *p)
{
    memset(p, 0, sizeof(*p));
    p->alpha = 0.7;
}

typedef struct grumpy_ctx {
    const ca_group *g;
    const ca_elem *base, *target;
    uint64_t lo, hi, n, m;
    uint64_t inv2;
} grumpy_ctx;

static int grumpy_candidate(grumpy_ctx *c, ca_i128 xprime_times, int doubled, uint64_t *x)
{
    /* xprime_times is x' (doubled == 0) or 2x' (doubled == 1) as a possibly
     * negative integer; reduce and verify. */
    uint64_t n = c->n;
    ca_i128 v = xprime_times;
    uint64_t cands[2];
    int nc = 0;
    if (n) {
        ca_i128 nn = (ca_i128)n;
        v %= nn;
        if (v < 0) v += nn;
        uint64_t u = (uint64_t)v;
        if (!doubled) cands[nc++] = u;
        else if (n & 1) cands[nc++] = ca_mulmod(u, c->inv2, n);
        else {
            if ((u & 1) == 0) { cands[nc++] = u / 2; cands[nc++] = (u / 2 + n / 2) % n; }
        }
    } else {
        if (v < 0) return 0;
        if (doubled) {
            if (v & 1) return 0;
            v /= 2;
        }
        if (v > (ca_i128)UINT64_MAX) return 0;
        cands[nc++] = (uint64_t)v;
    }
    for (int i = 0; i < nc; i++) {
        ca_u128 full = (ca_u128)c->lo + cands[i];
        uint64_t xx;
        if (n) xx = (uint64_t)(full % n);
        else {
            if (full > UINT64_MAX) continue;
            xx = (uint64_t)full;
        }
        if (ca_verify_log(c->g, c->base, c->target, xx)) {
            /* The header promises x in [lo, hi].  A verified logarithm that
             * cannot be shifted into the interval is not the answer that was
             * asked for, so keep looking rather than return it. */
            if (!ca_fit_interval_base(c->g, c->base, &xx, c->lo, c->hi)) continue;
            *x = xx;
            return 1;
        }
    }
    return 0;
}

static int grumpy_collide(grumpy_ctx *c, int t1, uint64_t i1, int t2, uint64_t i2, uint64_t *x)
{
    if (t1 == t2) return 0;
    /* order so that t1 < t2 */
    if (t1 > t2) { int tt = t1; t1 = t2; t2 = tt; uint64_t ti = i1; i1 = i2; i2 = ti; }
    ca_i128 m = (ca_i128)c->m;
    if (t1 == W_BABY && t2 == W_G1) {
        /* j = i1, i = i2: x' = j - i m */
        return grumpy_candidate(c, (ca_i128)i1 - (ca_i128)i2 * m, 0, x);
    }
    if (t1 == W_BABY && t2 == W_G2) {
        /* 2x' = j + i (m+1) */
        return grumpy_candidate(c, (ca_i128)i1 + (ca_i128)i2 * (m + 1), 1, x);
    }
    /* G1 (i1) vs G2 (i2): x' = i1 m + i2 (m+1) */
    return grumpy_candidate(c, (ca_i128)i1 * m + (ca_i128)i2 * (m + 1), 0, x);
}

ca_status ca_grumpy_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                          uint64_t lo, uint64_t hi, const ca_grumpy_params *params,
                          uint64_t *x, ca_stats *st)
{
    ca_grumpy_params def;
    if (!params) { ca_grumpy_params_default(&def); params = &def; }
    ca_status rc = ca_resolve_interval(g, &lo, &hi);
    if (rc != CA_OK) return rc;
    double t0 = ca_now();
    uint64_t width = hi - lo;
    uint64_t n = g->order;
    grumpy_ctx c = { g, base, target, lo, hi, n, 0, 0 };
    uint64_t sq = ca_isqrt(width) + 1;
    uint64_t m = params->m;
    if (m == 0) {
        double alpha = params->alpha > 0 ? params->alpha : 0.7;
        m = (uint64_t)(alpha * (double)sq + 0.5);
        if (m < 1) m = 1;
    }
    c.m = m;
    if (n & 1) c.inv2 = ca_invmod(2, n);

    /* shifted target H' = target - lo*base, and 2H' */
    ca_elem Hp, H2, t;
    uint64_t ops = 0;
    ca_group_mul(g, &t, base, lo, &ops);
    ca_group_inv(g, &t, &t);
    ca_group_op(g, &Hp, target, &t);
    ca_group_dbl(g, &H2, &Hp);
    ops += 2;
    ca_elem mG, m1G_neg;
    ca_group_mul(g, &mG, base, m, &ops);
    ca_group_op(g, &m1G_neg, &mG, base);
    ca_group_inv(g, &m1G_neg, &m1G_neg);
    ops += 1;

    ca_htab tab;
    if (ca_htab_init(&tab, (size_t)(3 * sq / 2 + 64)) != CA_OK) return CA_ERR_NOMEM;
    /* The three walks B (baby), U and V (giants) advance together through
     * the batched op, which on a curve shares one field inversion among
     * the three; results and counts are the three single ops'. */
    ca_elem walk[3] = {{{0}}, Hp, H2}, step[3] = {*base, mG, m1G_neg};
    ca_group_identity(g, &walk[0]);
    uint64_t scratch[6];
    uint64_t i = 0;
    /* Upper bound on iterations: the baby walk alone finds x' in at most
     * width+1 steps (it meets U_0 = H'). */
    uint64_t max_iter = width + 2;
    for (i = 0; i < max_iter; i++) {
        for (int tpe = 0; tpe < 3; tpe++) {
            uint64_t ot, oi;
            int ir = ca_htab_insert(&tab, ca_group_hash(g, &walk[tpe]), (uint64_t)tpe, i, &ot, &oi);
            if (ir < 0) { rc = CA_ERR_NOMEM; goto out; }
            if (ir == 1) {
                if (grumpy_collide(&c, (int)ot, oi, tpe, i, x)) { rc = CA_OK; goto out; }
                /* same walk type re-visiting a point: happens only when the
                 * walk period divides a small order; keep going */
            }
        }
        ca_group_batch_op(g, walk, walk, step, 3, scratch);
        ops += 3;
        if (params->max_ops && ops > params->max_ops) { rc = CA_ERR_LIMIT; goto out; }
    }
    rc = CA_ERR_NOT_FOUND;
out:
    if (st) {
        st->group_ops += ops;
        st->iterations += i;
        st->table_entries = ca_max_u64(st->table_entries, tab.count);
        st->bytes_peak = ca_max_u64(st->bytes_peak, ca_htab_bytes(&tab));
        st->threads = 1;
        st->seconds += ca_now() - t0;
    }
    ca_htab_free(&tab);
    return rc;
}
