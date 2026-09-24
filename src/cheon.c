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
        /* d divides p-1 exactly here, so the division loses nothing. */
        uint64_t cofactor = (p - 1) / d;
        double cost = 2.0 * (sqrt((double)cofactor) + sqrt((double)d));
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
    if (ord == 0) return CA_ERR_INVALID; /* callers pass a divisor of p-1 */
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
    uint64_t steps = m ? (ord - 1) / m + 1 : 1;
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


/* -------------------------------------------------------------------------
 * Cheon p+1: DLP with auxiliary inputs P_i=[alpha^i]P, i=0..2d.
 *
 * Let theta^2=u be a quadratic non-residue modulo p and
 *
 *      gamma = (alpha-theta)/(alpha+theta) in F_{p^2}^*.
 *
 * gamma has norm one, hence order dividing p+1.  From P_0..P_2d we can
 * encode gamma^d projectively without knowing alpha:
 *
 *   gamma^d = (alpha-theta)^(2d) / (alpha^2-u)^d
 *           = (A(alpha)+B(alpha)theta) / C(alpha).
 *
 * BSGS then runs in the norm-one torus using only group operations on
 * ([A]P,[B]P,[C]P).  A second, small BSGS resolves the remaining coset.
 * ------------------------------------------------------------------------- */

typedef struct cheon_f2 {
    uint64_t a, b; /* a + b theta, theta^2 = u */
} cheon_f2;

static uint64_t cheon_mulmod(uint64_t a, uint64_t b, uint64_t p)
{
    return (uint64_t)(((ca_u128)a * b) % p);
}

static uint64_t cheon_addmod(uint64_t a, uint64_t b, uint64_t p)
{
    return (uint64_t)(((ca_u128)a + b) % p);
}

static uint64_t cheon_submod(uint64_t a, uint64_t b, uint64_t p)
{
    return a >= b ? a - b : p - (b - a);
}

static cheon_f2 cheon_f2_mul(cheon_f2 x, cheon_f2 y, uint64_t u, uint64_t p)
{
    cheon_f2 z;
    z.a = cheon_addmod(cheon_mulmod(x.a, y.a, p),
                       cheon_mulmod(u, cheon_mulmod(x.b, y.b, p), p), p);
    z.b = cheon_addmod(cheon_mulmod(x.a, y.b, p),
                       cheon_mulmod(x.b, y.a, p), p);
    return z;
}

static ca_status cheon_f2_inv(cheon_f2 x, uint64_t u, uint64_t p, cheon_f2 *out)
{
    uint64_t den = cheon_submod(cheon_mulmod(x.a, x.a, p),
                                cheon_mulmod(u, cheon_mulmod(x.b, x.b, p), p), p);
    if (den == 0) return CA_ERR_INVALID;
    uint64_t di = ca_invmod(den, p);
    if (di == 0) return CA_ERR_INVALID;
    out->a = cheon_mulmod(x.a, di, p);
    out->b = cheon_mulmod(x.b ? p - x.b : 0, di, p);
    return CA_OK;
}

static cheon_f2 cheon_f2_pow(cheon_f2 x, uint64_t e, uint64_t u, uint64_t p)
{
    cheon_f2 z = {1, 0};
    while (e) {
        if (e & 1) z = cheon_f2_mul(z, x, u, p);
        x = cheon_f2_mul(x, x, u, p);
        e >>= 1;
    }
    return z;
}

static int cheon_f2_equal(cheon_f2 x, cheon_f2 y)
{
    return x.a == y.a && x.b == y.b;
}

static ca_status cheon_find_torus(uint64_t p, uint64_t *u_out, cheon_f2 *zeta_out)
{
    if (p == UINT64_MAX) return CA_ERR_UNSUPPORTED;
    uint64_t p1 = p + 1;
    uint64_t u = 2;
    while (u < p && ca_powmod(u, (p - 1) / 2, p) != p - 1) u++;
    if (u == p) return CA_ERR_INTERNAL;

    ca_factorization fac;
    ca_status rc = ca_factorize(p1, &fac);
    if (rc != CA_OK) return rc;

    for (uint64_t c = 1; c < p; c++) {
        cheon_f2 x = {c, 1};
        /* x^(p-1) lies in the norm-one subgroup of order p+1. */
        cheon_f2 z = cheon_f2_pow(x, p - 1, u, p);
        if (cheon_f2_equal(z, (cheon_f2){1, 0})) continue;
        int full = 1;
        for (unsigned i = 0; i < fac.count; i++) {
            if (cheon_f2_equal(cheon_f2_pow(z, p1 / fac.f[i].p, u, p),
                               (cheon_f2){1, 0})) {
                full = 0;
                break;
            }
        }
        if (full) {
            *u_out = u;
            *zeta_out = z;
            return CA_OK;
        }
    }
    return CA_ERR_NOT_FOUND;
}

static uint64_t cheon_binom_next(uint64_t cur, uint64_t n, uint64_t i, uint64_t p)
{
    /* C(n,i+1) = C(n,i) * (n-i)/(i+1), with n < p by the caller guard. */
    cur = cheon_mulmod(cur, (n - i) % p, p);
    return cheon_mulmod(cur, ca_invmod((i + 1) % p, p), p);
}

static ca_status cheon_accum(const ca_group *g, ca_elem *acc, const ca_elem *point,
                             uint64_t coeff, uint64_t max_exps,
                             uint64_t *ops, uint64_t *exps)
{
    if (coeff == 0) return CA_OK;
    ca_elem term, sum;
    ca_group_mul(g, &term, point, coeff, ops);
    (*exps)++;
    if (max_exps && *exps > max_exps) return CA_ERR_LIMIT;
    ca_group_op(g, &sum, acc, &term);
    (*ops)++;
    *acc = sum;
    return CA_OK;
}

static ca_status cheon_project_pplus(const ca_group *g, const ca_elem *powers,
                                     uint64_t d, uint64_t u, uint64_t max_exps,
                                     ca_elem *ga, ca_elem *gb, ca_elem *gc,
                                     uint64_t *ops, uint64_t *exps)
{
    uint64_t p = g->order;
    uint64_t two_d = 2 * d;
    ca_group_identity(g, ga);
    ca_group_identity(g, gb);
    ca_group_identity(g, gc);

    /* (x-theta)^(2d) = A(x)+B(x)theta. */
    uint64_t bin = 1; /* C(2d,0) */
    for (uint64_t i = 0; i <= two_d; i++) {
        uint64_t e = two_d - i;
        uint64_t coeff = cheon_mulmod(bin, ca_powmod(u, e / 2, p), p);
        if (e & 1) coeff = coeff ? p - coeff : 0;
        ca_status rc = cheon_accum(g, (e & 1) ? gb : ga, &powers[i],
                                   coeff, max_exps, ops, exps);
        if (rc != CA_OK) return rc;
        if (i < two_d) bin = cheon_binom_next(bin, two_d, i, p);
    }

    /* (x^2-u)^d = C(x). */
    bin = 1; /* C(d,0) */
    uint64_t neg_u = u ? p - u : 0;
    for (uint64_t j = 0; j <= d; j++) {
        uint64_t coeff = cheon_mulmod(bin, ca_powmod(neg_u, d - j, p), p);
        ca_status rc = cheon_accum(g, gc, &powers[2 * j], coeff,
                                   max_exps, ops, exps);
        if (rc != CA_OK) return rc;
        if (j < d) bin = cheon_binom_next(bin, d, j, p);
    }
    return CA_OK;
}

typedef struct cheon_pair_slot {
    uint64_t hash;
    uint64_t index;
    ca_elem x, y;
    int used;
} cheon_pair_slot;

typedef struct cheon_pair_table {
    cheon_pair_slot *slots;
    size_t cap;
    size_t count;
} cheon_pair_table;

static uint64_t cheon_pair_hash(const ca_group *g, const ca_elem *x, const ca_elem *y)
{
    uint64_t a = ca_group_hash(g, x);
    uint64_t b = ca_group_hash(g, y);
    return ca_mix64(a ^ (b + UINT64_C(0x9e3779b97f4a7c15) + (a << 6) + (a >> 2)));
}

static ca_status cheon_pair_init(cheon_pair_table *tab, uint64_t expected)
{
    size_t cap = 8;
    while (cap < (size_t)expected * 2) {
        if (cap > SIZE_MAX / 2) return CA_ERR_NOMEM;
        cap <<= 1;
    }
    tab->slots = (cheon_pair_slot *)calloc(cap, sizeof(*tab->slots));
    if (!tab->slots) return CA_ERR_NOMEM;
    tab->cap = cap;
    tab->count = 0;
    return CA_OK;
}

static void cheon_pair_free(cheon_pair_table *tab)
{
    free(tab->slots);
    tab->slots = NULL;
    tab->cap = 0;
    tab->count = 0;
}

static ca_status cheon_pair_insert(cheon_pair_table *tab, const ca_group *g,
                                   const ca_elem *x, const ca_elem *y, uint64_t index)
{
    uint64_t hash = cheon_pair_hash(g, x, y);
    size_t pos = (size_t)hash & (tab->cap - 1);
    for (;;) {
        cheon_pair_slot *slot = &tab->slots[pos];
        if (!slot->used) {
            slot->used = 1;
            slot->hash = hash;
            slot->index = index;
            slot->x = *x;
            slot->y = *y;
            tab->count++;
            return CA_OK;
        }
        if (slot->hash == hash && ca_group_equal(g, &slot->x, x) &&
            ca_group_equal(g, &slot->y, y))
            return CA_OK;
        pos = (pos + 1) & (tab->cap - 1);
    }
}

static int cheon_pair_find(const cheon_pair_table *tab, const ca_group *g,
                           const ca_elem *x, const ca_elem *y, uint64_t *index)
{
    uint64_t hash = cheon_pair_hash(g, x, y);
    size_t pos = (size_t)hash & (tab->cap - 1);
    for (;;) {
        const cheon_pair_slot *slot = &tab->slots[pos];
        if (!slot->used) return 0;
        if (slot->hash == hash && ca_group_equal(g, &slot->x, x) &&
            ca_group_equal(g, &slot->y, y)) {
            *index = slot->index;
            return 1;
        }
        pos = (pos + 1) & (tab->cap - 1);
    }
}

static ca_status cheon_pair_bsgs(const ca_group *g, cheon_f2 zeta_hat, uint64_t order,
                                 uint64_t u, const ca_elem *ga, const ca_elem *gb,
                                 const ca_elem *gc, uint64_t max_exps,
                                 uint64_t *answer, uint64_t *ops, uint64_t *exps,
                                 uint64_t *table_entries, uint64_t *bytes_peak)
{
    if (order == 0) return CA_ERR_INVALID;
    uint64_t p = g->order;
    uint64_t m = ca_isqrt(order - 1) + 1;
    if (m > order) m = order;

    cheon_pair_table tab = {0};
    ca_status rc = cheon_pair_init(&tab, m);
    if (rc != CA_OK) return rc;

    cheon_f2 z = {1, 0};
    for (uint64_t j = 0; j < m; j++) {
        ca_elem x, y;
        ca_group_mul(g, &x, gc, z.a, ops);
        ca_group_mul(g, &y, gc, z.b, ops);
        *exps += 2;
        if (max_exps && *exps > max_exps) {
            rc = CA_ERR_LIMIT;
            goto out;
        }
        rc = cheon_pair_insert(&tab, g, &x, &y, j);
        if (rc != CA_OK) goto out;
        z = cheon_f2_mul(z, zeta_hat, u, p);
    }

    cheon_f2 inv;
    rc = cheon_f2_inv(zeta_hat, u, p, &inv);
    if (rc != CA_OK) goto out;
    cheon_f2 step = cheon_f2_pow(inv, m, u, p);
    z = (cheon_f2){1, 0};

    rc = CA_ERR_NOT_FOUND;
    for (uint64_t v = 0; v <= m; v++) {
        uint64_t s0 = z.a;
        uint64_t s1 = z.b;
        ca_elem as, ubt, at, bs, l0, l1;

        ca_group_mul(g, &as, ga, s0, ops);
        ca_group_mul(g, &ubt, gb, cheon_mulmod(u, s1, p), ops);
        ca_group_mul(g, &at, ga, s1, ops);
        ca_group_mul(g, &bs, gb, s0, ops);
        *exps += 4;
        if (max_exps && *exps > max_exps) {
            rc = CA_ERR_LIMIT;
            goto out;
        }

        ca_group_op(g, &l0, &as, &ubt);
        ca_group_op(g, &l1, &at, &bs);
        *ops += 2;

        uint64_t j;
        if (cheon_pair_find(&tab, g, &l0, &l1, &j)) {
            *answer = (uint64_t)(((ca_u128)j + (ca_u128)m * v) % order);
            rc = CA_OK;
            goto out;
        }
        z = cheon_f2_mul(z, step, u, p);
    }

out:
    if (table_entries) *table_entries = ca_max_u64(*table_entries, tab.count);
    if (bytes_peak) *bytes_peak = ca_max_u64(*bytes_peak, tab.cap * sizeof(*tab.slots));
    cheon_pair_free(&tab);
    return rc;
}

ca_status ca_cheon_make_instance_p_plus_1(const ca_group *g, const ca_elem *gen,
                                          uint64_t alpha, uint64_t d,
                                          ca_elem *out, size_t out_len)
{
    if (!g || !gen || !out || g->order == 0 || !ca_is_prime(g->order))
        return CA_ERR_INVALID;
    uint64_t p = g->order;
    if (p == UINT64_MAX || d == 0 || (p + 1) % d != 0 ||
        d > (SIZE_MAX - 1) / 2 || out_len < (size_t)(2 * d + 1)) {
        ca_set_error("Cheon p+1 needs d | p+1 and room for P_0..P_2d");
        return CA_ERR_INVALID;
    }
    if (alpha % p == 0) {
        ca_set_error("alpha must be nonzero modulo p");
        return CA_ERR_INVALID;
    }

    uint64_t scalar = 1;
    for (uint64_t i = 0; i <= 2 * d; i++) {
        ca_group_mul(g, &out[i], gen, scalar, NULL);
        scalar = cheon_mulmod(scalar, alpha % p, p);
    }
    return CA_OK;
}

ca_status ca_cheon_solve_p_plus_1(const ca_group *g, const ca_elem *powers,
                                  size_t powers_len, uint64_t d,
                                  const ca_cheon_params *params,
                                  uint64_t *alpha, ca_stats *st)
{
    ca_cheon_params def;
    if (!params) {
        ca_cheon_params_default(&def);
        params = &def;
    }
    if (!g || !powers || !alpha || g->order == 0 || !ca_is_prime(g->order))
        return CA_ERR_INVALID;

    uint64_t p = g->order;
    if (p == UINT64_MAX || d == 0 || (p + 1) % d != 0 ||
        d > (SIZE_MAX - 1) / 2 || powers_len < (size_t)(2 * d + 1)) {
        ca_set_error("Cheon p+1 needs d | p+1 and auxiliary points P_0..P_2d");
        return CA_ERR_INVALID;
    }
    if (d > (p - 1) / 2) {
        ca_set_error("Cheon p+1 currently requires 2d < p");
        return CA_ERR_UNSUPPORTED;
    }

    double t0 = ca_now();
    uint64_t ops = 0, exps = 0, table_entries = 0, bytes_peak = 0;
    uint64_t u;
    cheon_f2 zeta;
    ca_status rc = cheon_find_torus(p, &u, &zeta);
    if (rc != CA_OK) return rc;

    ca_elem ga, gb, gc;
    rc = cheon_project_pplus(g, powers, d, u, params->max_exps,
                             &ga, &gb, &gc, &ops, &exps);
    if (rc != CA_OK) goto done;

    uint64_t n = (p + 1) / d;
    uint64_t k0 = 0;
    rc = cheon_pair_bsgs(g, cheon_f2_pow(zeta, d, u, p), n, u,
                         &ga, &gb, &gc, params->max_exps, &k0,
                         &ops, &exps, &table_entries, &bytes_peak);
    if (rc != CA_OK) goto done;

    /* gamma=(alpha-theta)/(alpha+theta)
     *       = (alpha^2+u - 2 alpha theta)/(alpha^2-u). */
    ca_elem ga1, gb1, gc1, t0p, t1p;
    ca_group_mul(g, &t0p, &powers[0], u, &ops);
    ca_group_op(g, &ga1, &t0p, &powers[2]);
    ops++;
    ca_group_mul(g, &gb1, &powers[1], p - 2, &ops);
    ca_group_mul(g, &t0p, &powers[0], p - u, &ops);
    ca_group_op(g, &gc1, &t0p, &powers[2]);
    ops++;
    exps += 3;
    if (params->max_exps && exps > params->max_exps) {
        rc = CA_ERR_LIMIT;
        goto done;
    }

    /* Multiply numerator by zeta^(-k0). */
    cheon_f2 zeta_inv;
    rc = cheon_f2_inv(zeta, u, p, &zeta_inv);
    if (rc != CA_OK) goto done;
    cheon_f2 shift = cheon_f2_pow(zeta_inv, k0, u, p);

    ca_elem ga2, gb2, x0, x1;
    ca_group_mul(g, &x0, &ga1, shift.a, &ops);
    ca_group_mul(g, &x1, &gb1, cheon_mulmod(u, shift.b, p), &ops);
    ca_group_op(g, &ga2, &x0, &x1);
    ops++;
    ca_group_mul(g, &x0, &ga1, shift.b, &ops);
    ca_group_mul(g, &x1, &gb1, shift.a, &ops);
    ca_group_op(g, &gb2, &x0, &x1);
    ops++;
    exps += 4;
    if (params->max_exps && exps > params->max_exps) {
        rc = CA_ERR_LIMIT;
        goto done;
    }

    uint64_t k1 = 0;
    rc = cheon_pair_bsgs(g, cheon_f2_pow(zeta, n, u, p), d, u,
                         &ga2, &gb2, &gc1, params->max_exps, &k1,
                         &ops, &exps, &table_entries, &bytes_peak);
    if (rc != CA_OK) goto done;

    uint64_t k = (uint64_t)(((ca_u128)k0 + (ca_u128)k1 * n) % (p + 1));
    cheon_f2 gamma = cheon_f2_pow(zeta, k, u, p);

    /* alpha = theta(1+gamma)/(1-gamma), which must lie in F_p. */
    cheon_f2 num = {cheon_mulmod(u, gamma.b, p),
                    cheon_addmod(1, gamma.a, p)};
    cheon_f2 den = {cheon_submod(1, gamma.a, p),
                    gamma.b ? p - gamma.b : 0};
    cheon_f2 den_inv;
    rc = cheon_f2_inv(den, u, p, &den_inv);
    if (rc != CA_OK) {
        rc = CA_ERR_NOT_FOUND;
        goto done;
    }
    cheon_f2 candidate = cheon_f2_mul(num, den_inv, u, p);
    if (candidate.b != 0 || candidate.a == 0) {
        rc = CA_ERR_NOT_FOUND;
        goto done;
    }

    ca_group_mul(g, &t1p, &powers[0], candidate.a, &ops);
    exps++;
    if (!ca_group_equal(g, &t1p, &powers[1])) {
        ca_set_error("Cheon p+1: recovered alpha failed verification");
        rc = CA_ERR_INTERNAL;
        goto done;
    }
    *alpha = candidate.a;
    rc = CA_OK;

done:
    if (st) {
        st->group_ops += ops;
        st->iterations += exps;
        st->table_entries = ca_max_u64(st->table_entries, table_entries);
        st->bytes_peak = ca_max_u64(st->bytes_peak, bytes_peak);
        st->seconds += ca_now() - t0;
    }
    return rc;
}
