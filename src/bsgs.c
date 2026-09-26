/*
 * bsgs.c - baby-step giant-step.
 *
 * Baby steps j*base for 0 <= j < m go into a hash table keyed by the
 * element fingerprint.  Giant steps walk target - (lo + i m) base for
 * i = 0, 1, ... and look up the table.  Matches are verified by a scalar
 * multiplication so 64-bit fingerprint collisions cannot produce a wrong
 * answer.
 */
#include "cryptanalysis/ca_bsgs.h"
#include "dlog_internal.h"

/* Baby and giant steps advance BSGS_LANES elements at once through the
 * group's batched op, which on a curve shares one field inversion among
 * them (a single affine add pays one each).  Which elements are hashed,
 * inserted, looked up and verified, in which order, and every count are
 * those of the one-at-a-time loops; a block may compute up to
 * BSGS_LANES - 1 elements past the last one used, which are not counted. */
#define BSGS_LANES 64

struct ca_bsgs_table {
    const ca_group *g;
    ca_elem base;
    ca_elem neg_m_base; /* -m * base */
    ca_elem giant[BSGS_LANES]; /* k * (-m * base) for k < BSGS_LANES */
    ca_elem giant_block;       /* BSGS_LANES * (-m * base) */
    uint64_t m;
    ca_htab1 tab;
};

void ca_bsgs_params_default(ca_bsgs_params *p)
{
    p->table_size = 0;
    p->max_ops = 0;
}

ca_status ca_bsgs_table_new(const ca_group *g, const ca_elem *base, uint64_t m, ca_bsgs_table **out)
{
    if (m == 0) return CA_ERR_INVALID;
    ca_bsgs_table *t = calloc(1, sizeof(*t));
    if (!t) return CA_ERR_NOMEM;
    t->g = g;
    t->base = *base;
    t->m = m;
    if (ca_htab1_init(&t->tab, (size_t)m) != CA_OK) { free(t); return CA_ERR_NOMEM; }
    /* lane c holds (j0 + c) * base for the block starting at j0 */
    ca_elem lane[BSGS_LANES], stride[BSGS_LANES];
    uint64_t scratch[2 * BSGS_LANES];
    const uint64_t first = m < BSGS_LANES ? m : BSGS_LANES;
    ca_group_identity(g, &lane[0]);
    for (uint64_t c = 1; c < first; c++) ca_group_op(g, &lane[c], &lane[c - 1], base);
    ca_group_mul(g, &stride[0], base, BSGS_LANES, NULL);
    for (int c = 1; c < BSGS_LANES; c++) stride[c] = stride[0];
    for (uint64_t j0 = 0; j0 < m; j0 += BSGS_LANES) {
        const uint64_t n = m - j0 < BSGS_LANES ? m - j0 : BSGS_LANES;
        for (uint64_t c = 0; c < n; c++) {
            int rc = ca_htab1_insert(&t->tab, ca_group_hash(g, &lane[c]), j0 + c, NULL);
            if (rc < 0) { ca_bsgs_table_free(t); return CA_ERR_NOMEM; }
            if (rc == 1) {
                /* base has order <= j: the table already spans the whole group */
                t->m = j0 + c;
                goto baby_done;
            }
        }
        if (j0 + BSGS_LANES < m) {
            const uint64_t next = m - j0 - BSGS_LANES;
            ca_group_batch_op(g, lane, lane, stride, next < BSGS_LANES ? next : BSGS_LANES, scratch);
        }
    }
baby_done:
    if (t->m == 0) { ca_bsgs_table_free(t); return CA_ERR_INVALID; }
    ca_elem mb;
    ca_group_mul(g, &mb, base, t->m, NULL);
    ca_group_inv(g, &t->neg_m_base, &mb);
    ca_group_identity(g, &t->giant[0]);
    for (int k = 1; k < BSGS_LANES; k++) ca_group_op(g, &t->giant[k], &t->giant[k - 1], &t->neg_m_base);
    ca_group_op(g, &t->giant_block, &t->giant[BSGS_LANES - 1], &t->neg_m_base);
    *out = t;
    return CA_OK;
}

void ca_bsgs_table_free(ca_bsgs_table *t)
{
    if (!t) return;
    ca_htab1_free(&t->tab);
    free(t);
}

static ca_status bsgs_table_solve_impl(const ca_bsgs_table *t, const ca_elem *target, uint64_t lo,
                                       uint64_t hi, uint64_t *x, ca_stats *st, int add_time)
{
    const ca_group *g = t->g;
    ca_status rc = ca_resolve_interval(g, &lo, &hi);
    if (rc != CA_OK) return rc;
    double t0 = ca_now();
    uint64_t width_m1 = hi - lo; /* number of candidates minus one */
    uint64_t m = t->m;
    /* R = target - lo*base */
    ca_elem R, tmp;
    ca_group_mul(g, &tmp, &t->base, lo, st ? &st->group_ops : NULL);
    ca_group_inv(g, &tmp, &tmp);
    ca_group_op(g, &R, target, &tmp);
    uint64_t steps = width_m1 / m + 1;
    /* Step i + k of a block is R_i + k * (-m base), BSGS_LANES of them per
     * batched op; they are looked up in order and each one that does not
     * return is charged one op, as the one-step loop charges it. */
    ca_elem Rs[BSGS_LANES], Rrep[BSGS_LANES];
    uint64_t scratch[2 * BSGS_LANES];
    for (uint64_t i0 = 0; i0 < steps; i0 += BSGS_LANES) {
        const uint64_t n = steps - i0 < BSGS_LANES ? steps - i0 : BSGS_LANES;
        for (uint64_t k = 0; k < n; k++) Rrep[k] = R;
        ca_group_batch_op(g, Rs, Rrep, t->giant, n, scratch);
        for (uint64_t k = 0; k < n; k++) {
            const uint64_t i = i0 + k;
            uint64_t j;
            if (ca_htab1_find(&t->tab, ca_group_hash(g, &Rs[k]), &j)) {
                ca_u128 cand = (ca_u128)lo + (ca_u128)i * m + j;
                if (cand <= hi) {
                    uint64_t cx = (uint64_t)cand;
                    if (ca_verify_log(g, &t->base, target, cx)) {
                        *x = cx;
                        if (st) {
                            st->iterations += i + 1;
                            st->table_entries = ca_max_u64(st->table_entries, t->tab.count);
                            st->bytes_peak = ca_max_u64(st->bytes_peak, ca_htab1_bytes(&t->tab));
                            if (add_time) st->seconds += ca_now() - t0;
                        }
                        return CA_OK;
                    }
                }
            }
            if (st) st->group_ops++;
        }
        if (n == BSGS_LANES) ca_group_op(g, &R, &R, &t->giant_block);
    }
    if (st) {
        st->iterations += steps;
        st->table_entries = ca_max_u64(st->table_entries, t->tab.count);
        st->bytes_peak = ca_max_u64(st->bytes_peak, ca_htab1_bytes(&t->tab));
        if (add_time) st->seconds += ca_now() - t0;
    }
    return CA_ERR_NOT_FOUND;
}

ca_status ca_bsgs_table_solve(const ca_bsgs_table *t, const ca_elem *target, uint64_t lo,
                              uint64_t hi, uint64_t *x, ca_stats *st)
{
    return bsgs_table_solve_impl(t, target, lo, hi, x, st, 1);
}

ca_status ca_bsgs_solve(const ca_group *g, const ca_elem *base, const ca_elem *target, uint64_t lo,
                        uint64_t hi, const ca_bsgs_params *params, uint64_t *x, ca_stats *st)
{
    ca_bsgs_params def;
    if (!params) { ca_bsgs_params_default(&def); params = &def; }
    ca_status rc = ca_resolve_interval(g, &lo, &hi);
    if (rc != CA_OK) return rc;
    double t0 = ca_now();
    uint64_t width_m1 = hi - lo;
    uint64_t m = params->table_size;
    if (m == 0) { m = ca_isqrt(width_m1) + 1; /* >= 1 for every width, including 0 */ }
    if (params->max_ops && m + width_m1 / m > params->max_ops) return CA_ERR_LIMIT;
    ca_bsgs_table *t;
    rc = ca_bsgs_table_new(g, base, m, &t);
    if (rc != CA_OK) return rc;
    if (st) st->group_ops += t->m;
    rc = bsgs_table_solve_impl(t, target, lo, hi, x, st, 0);
    ca_bsgs_table_free(t);
    if (st) st->seconds += ca_now() - t0;
    return rc;
}
