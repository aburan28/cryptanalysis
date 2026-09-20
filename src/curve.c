/*
 * curve.c - curve-aware dispatch and the GLV endomorphism-accelerated rho.
 *
 * ca_curve_detect / ca_curve_group recognise the two prime-field families
 * with an efficiently computable endomorphism psi(P) = lambda * P:
 *
 *   j = 0     (a = 0, p = 1 mod 3):  psi(x, y) = (beta x, -y), <psi> order 6
 *   j = 1728  (b = 0, p = 1 mod 4):  psi(x, y) = (-x, i y),    <psi> order 4
 *
 * beta is a cube root of unity mod p, i a square root of -1 mod p; lambda is
 * the matching root of unity mod the subgroup order (picked by testing
 * psi(P) == lambda * P on a subgroup point, so the sign branch cannot be
 * wrong).  glv_rho_solve then folds the Pollard rho walk by <psi>: it walks
 * canonical representatives of the automorphism classes, which shrinks the
 * search space by the class size m and the operation count by sqrt(m).
 */
#include "cryptanalysis/ca_curve.h"
#include "cryptanalysis/ca_rho.h"
#include "dlog_internal.h"

#include <math.h>

#define GLV_MAX_WALKS 4096

static int glv_ilog2(uint64_t v)
{
    int l = -1;
    while (v) {
        v >>= 1;
        l++;
    }
    return l;
}

/* nontrivial cube root of unity mod p (p = 1 mod 3) */
static uint64_t cube_root_unity(uint64_t p)
{
    uint64_t e = (p - 1) / 3;
    for (uint64_t base = 2; base < p; base++) {
        uint64_t w = ca_powmod(base, e, p);
        if (w != 1) return w;
    }
    return 1;
}

/* Enable the endomorphism on an already-initialised EC group `g` (order set)
 * and fill *info.  Falls back to the negation-only structure when the curve
 * is generic or the subgroup order is incompatible. */
static void curve_enable(ca_group *g, ca_curve_info *info)
{
    memset(info, 0, sizeof(*info));
    g->endo_kind = 0;
    g->aut_order = 0;
    g->endo_lambda = 0;
    g->endo_c_mont = 0;
    info->endo = CA_CURVE_ENDO_NONE;
    info->aut_order = 2; /* the negation map is always available on a curve */
    info->rho_speedup = sqrt(2.0);

    uint64_t p = g->p;
    int kind = 0;
    if (g->a == 0 && g->b != 0 && p % 3 == 1)
        kind = CA_CURVE_ENDO_J0;
    else if (g->b == 0 && g->a != 0 && p % 4 == 1)
        kind = CA_CURVE_ENDO_J1728;
    if (kind == 0) return;

    uint64_t c;
    if (kind == CA_CURVE_ENDO_J0)
        c = cube_root_unity(p);
    else if (!ca_sqrtmod_prime(p - 1, p, &c))
        return;
    info->beta = c;
    uint32_t m = (kind == CA_CURVE_ENDO_J0) ? 6u : 4u;
    info->endo = (ca_curve_endo)kind;
    info->aut_order = m;
    info->rho_speedup = sqrt((double)m);

    uint64_t n = g->order;
    if (n == 0) return; /* structure only; no lambda without an order */
    if ((kind == CA_CURVE_ENDO_J0 && n % 3 != 1) || (kind == CA_CURVE_ENDO_J1728 && n % 4 != 1)) {
        info->endo = CA_CURVE_ENDO_NONE;
        info->aut_order = 2;
        info->rho_speedup = sqrt(2.0);
        return;
    }

    /* Point the group's endomorphism at psi so ca_ec_endo can apply it. */
    g->endo_kind = (uint32_t)kind;
    g->aut_order = m;
    g->endo_c_mont = ca_mont_to(&g->mont, c);

    /* A subgroup point to fix the eigenvalue on: cofactor * random point. */
    if (g->cofactor == 0) {
        uint64_t full;
        if (ca_ec_count_points(p, g->a, g->b, &full, NULL) != CA_OK || full % n != 0) {
            g->endo_kind = 0;
            g->aut_order = 0;
            info->endo = CA_CURVE_ENDO_NONE;
            info->aut_order = 2;
            info->rho_speedup = sqrt(2.0);
            return;
        }
        g->cofactor = full / n;
    }
    ca_elem P;
    if (ca_group_find_generator(g, &P, 1) != CA_OK) {
        g->endo_kind = 0;
        g->aut_order = 0;
        info->endo = CA_CURVE_ENDO_NONE;
        info->aut_order = 2;
        info->rho_speedup = sqrt(2.0);
        return;
    }
    ca_elem psiP;
    ca_ec_endo(g, &psiP, &P);

    /* Candidate eigenvalues: roots of x^2 - x + 1 (j0) or x^2 + 1 (j1728). */
    uint64_t cand[2];
    int nc = 0;
    if (kind == CA_CURVE_ENDO_J0) {
        uint64_t s;
        if (ca_sqrtmod_prime(n - 3, n, &s)) {
            uint64_t inv2 = ca_invmod(2, n);
            cand[nc++] = ca_mulmod(ca_addmod(1 % n, s, n), inv2, n);
            cand[nc++] = ca_mulmod(ca_submod(1 % n, s, n), inv2, n);
        }
    } else {
        uint64_t s;
        if (ca_sqrtmod_prime(n - 1, n, &s)) {
            cand[nc++] = s;
            cand[nc++] = n - s;
        }
    }
    for (int k = 0; k < nc; k++) {
        if (cand[k] <= 1) continue;
        ca_elem Q;
        ca_group_mul(g, &Q, &P, cand[k], NULL);
        if (ca_group_equal(g, &Q, &psiP)) {
            g->endo_lambda = cand[k];
            break;
        }
    }
    if (g->endo_lambda == 0) {
        g->endo_kind = 0;
        g->aut_order = 0;
        info->endo = CA_CURVE_ENDO_NONE;
        info->aut_order = 2;
        info->rho_speedup = sqrt(2.0);
        return;
    }
    info->lambda = g->endo_lambda;
}

ca_status ca_curve_detect(uint64_t p, uint64_t a, uint64_t b, uint64_t order, ca_curve_info *out)
{
    ca_group g;
    ca_status rc = ca_group_ec_init(&g, p, a, b, order);
    if (rc != CA_OK) return rc;
    ca_curve_info info;
    curve_enable(&g, &info);
    if (out) *out = info;
    return CA_OK;
}

/* ---- named registry --------------------------------------------------- */

typedef struct curve_entry {
    const char *name;
    uint64_t p, a, b, order;
} curve_entry;

/* Example curves with a large prime-order subgroup of the right congruence,
 * one small (for tests) and one ~2^32 (for benchmarks) per family, plus a
 * generic curve that has only the negation map. */
static const curve_entry CURVES[] = {
    {"glv-j0-26", 67108933, 0, 7, 16773703},    {"glv-j1728-26", 67108933, 6, 0, 6712457},
    {"glv-j0-32", 4294967377, 0, 15, 23729779}, {"glv-j1728-32", 4294967377, 3, 0, 37025581},
    {"generic-26", 67108879, 2, 3, 3355777},
};

ca_status ca_curve_by_name(const char *name, uint64_t *p, uint64_t *a, uint64_t *b, uint64_t *order)
{
    for (size_t i = 0; i < sizeof(CURVES) / sizeof(CURVES[0]); i++) {
        if (strcmp(name, CURVES[i].name) == 0) {
            if (p) *p = CURVES[i].p;
            if (a) *a = CURVES[i].a;
            if (b) *b = CURVES[i].b;
            if (order) *order = CURVES[i].order;
            return CA_OK;
        }
    }
    ca_set_error("unknown curve name '%s'", name);
    return CA_ERR_NOT_FOUND;
}

size_t ca_curve_list(const char **names, size_t cap)
{
    size_t n = sizeof(CURVES) / sizeof(CURVES[0]);
    for (size_t i = 0; i < n && i < cap; i++) names[i] = CURVES[i].name;
    return n;
}

ca_status ca_curve_group(ca_group *g, uint64_t p, uint64_t a, uint64_t b, uint64_t order,
                         ca_curve_info *info)
{
    ca_status rc = ca_group_ec_init(g, p, a, b, order);
    if (rc != CA_OK) return rc;
    /* Resolve the cofactor so find_generator (and thus every solver) works on
     * the requested subgroup, for generic and CM curves alike. */
    if (order) {
        uint64_t full;
        if (ca_ec_count_points(p, a, b, &full, NULL) == CA_OK && full % order == 0)
            g->cofactor = full / order;
    }
    ca_curve_info local;
    curve_enable(g, &local);
    if (info) *info = local;
    return CA_OK;
}

/* ---- GLV endomorphism-accelerated rho --------------------------------- */

/* Reduce Y to the canonical representative of its automorphism class {Y,
 * psi(Y), ..., psi^{m-1}(Y)} (the minimum by hash) and return the power k of
 * psi applied, so the caller can multiply the exponents by lambda^k. */
static uint32_t glv_class_reduce(const ca_group *g, ca_elem *Y, uint32_t m)
{
    ca_elem cur = *Y, best = *Y;
    uint64_t best_h = ca_group_hash(g, Y);
    uint32_t best_k = 0;
    for (uint32_t k = 1; k < m; k++) {
        ca_elem nx;
        ca_ec_endo(g, &nx, &cur);
        cur = nx;
        uint64_t h = ca_group_hash(g, &cur);
        if (h < best_h) {
            best_h = h;
            best = cur;
            best_k = k;
        }
    }
    *Y = best;
    return best_k;
}

static int glv_recover(const ca_group *g, const ca_elem *base, const ca_elem *target, uint64_t n,
                       uint64_t a1, uint64_t b1, uint64_t a2, uint64_t b2, uint64_t *x)
{
    uint64_t c = ca_submod(b1, b2, n);
    uint64_t d = ca_submod(a2, a1, n);
    if (c == 0) return 0;
    uint64_t gg = ca_gcd(c, n);
    if (d % gg) return 0;
    uint64_t nn = n / gg;
    uint64_t x0 = ca_mulmod((d / gg) % nn, ca_invmod((c / gg) % nn, nn), nn);
    uint64_t reps = gg > 65536 ? 65536 : gg;
    for (uint64_t k = 0; k < reps; k++) {
        uint64_t cand = x0 + k * nn;
        if (cand >= n) break;
        if (ca_verify_log(g, base, target, cand)) {
            *x = cand;
            return 1;
        }
    }
    return 0;
}

typedef struct glv_walk {
    ca_elem Y;
    uint64_t a, b;
    uint64_t since_dp;
    uint32_t idx;
    uint8_t retry;
} glv_walk;

/* base/target and the multiplier table travel with the walk in this context
 * rather than in each glv_walk. */
typedef struct glv_ctx {
    const ca_group *g;
    ca_elem base, target;
    uint32_t r;
    ca_elem *M;
    uint64_t *alpha, *beta;
    uint32_t m;
    uint64_t lam_pow[6];
    int dp_bits;
    uint64_t dp_mask;
    uint64_t abandon;
} glv_ctx;

static void glv_restart(const glv_ctx *c, glv_walk *w, ca_rng *rng, uint64_t *ops)
{
    const ca_group *g = c->g;
    uint64_t n = g->order;
    w->a = ca_rng_below(rng, n);
    w->b = ca_rng_below(rng, n);
    ca_elem t1, t2;
    ca_group_mul(g, &t1, &c->base, w->a, ops);
    ca_group_mul(g, &t2, &c->target, w->b, ops);
    ca_group_op(g, &w->Y, &t1, &t2);
    (*ops)++;
    uint32_t k = glv_class_reduce(g, &w->Y, c->m);
    if (k) {
        w->a = ca_mulmod(w->a, c->lam_pow[k], n);
        w->b = ca_mulmod(w->b, c->lam_pow[k], n);
    }
    w->since_dp = 0;
    w->retry = 0;
}

static ca_status glv_rho_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                               uint64_t seed, uint64_t *x, ca_stats *st)
{
    double t0 = ca_now();
    uint64_t n = g->order;
    if (ca_group_is_identity(g, target)) {
        *x = 0;
        return CA_OK;
    }
    if (n < 64) {
        ca_elem cur;
        ca_group_identity(g, &cur);
        for (uint64_t k = 0; k < n; k++) {
            if (ca_group_equal(g, &cur, target)) {
                *x = k;
                if (st) st->group_ops += k;
                return CA_OK;
            }
            ca_group_op(g, &cur, &cur, base);
        }
        return CA_ERR_NOT_FOUND;
    }

    glv_ctx c;
    memset(&c, 0, sizeof(c));
    c.g = g;
    c.base = *base;
    c.target = *target;
    c.m = g->aut_order;
    c.lam_pow[0] = 1 % n;
    for (uint32_t k = 1; k < c.m; k++)
        c.lam_pow[k] = ca_mulmod(c.lam_pow[k - 1], g->endo_lambda, n);

    /* The folded search space has size n/m, so all budgets scale with
     * sqrt(n/m).  Keep the r-multiplier table and the W walk start-ups (each
     * about 3 log2(n) operations) to a small fraction of it, exactly as rho
     * does, so that the setup never dominates on small groups. */
    uint64_t sqrt_nm = ca_isqrt(n / c.m) + 1;
    int lg = glv_ilog2(n) + 1;
    uint64_t rbudget = sqrt_nm / (48u * (uint64_t)lg);
    uint32_t rr = 8;
    while ((uint64_t)rr * 2 <= rbudget && rr * 2 <= 32) rr *= 2;
    c.r = rr;
    uint64_t wcap = sqrt_nm / (24u * (uint64_t)lg);
    uint32_t W = wcap < 1 ? 1 : (wcap > GLV_MAX_WALKS ? GLV_MAX_WALKS : (uint32_t)wcap);

    int dp = 0;
    double per_walk = 1.25 * (double)sqrt_nm / (32.0 * (double)W);
    if (per_walk >= 2.0) dp = glv_ilog2((uint64_t)per_walk);
    int min_dp = glv_ilog2(sqrt_nm) - 24;
    if (dp < min_dp) dp = min_dp;
    if (dp < 0) dp = 0;
    if (dp > 48) dp = 48;
    c.dp_bits = dp;
    c.dp_mask = dp ? ((1ULL << dp) - 1) : 0;
    c.abandon = (uint64_t)24 << dp;

    ca_rng rng;
    ca_rng_seed(&rng, ca_seed_or_random(seed));
    uint64_t ops = 0;
    c.M = calloc(c.r, sizeof(ca_elem));
    c.alpha = calloc(c.r, sizeof(uint64_t));
    c.beta = calloc(c.r, sizeof(uint64_t));
    uint64_t *scratch = calloc(2 * (size_t)W, sizeof(uint64_t));
    glv_walk *walks = calloc(W, sizeof(glv_walk));
    ca_elem *Yn = calloc(W, sizeof(ca_elem));
    ca_elem *B = calloc(W, sizeof(ca_elem));
    ca_htab tab;
    int have_tab = 0;
    if (!c.M || !c.alpha || !c.beta || !scratch || !walks || !Yn || !B) goto nomem;
    for (uint32_t i = 0; i < c.r; i++) {
        c.alpha[i] = ca_rng_below(&rng, n);
        c.beta[i] = ca_rng_below(&rng, n);
        ca_elem t1, t2;
        ca_group_mul(g, &t1, base, c.alpha[i], &ops);
        ca_group_mul(g, &t2, target, c.beta[i], &ops);
        ca_group_op(g, &c.M[i], &t1, &t2);
        ops++;
    }
    double exp_dps = 1.25 * (double)sqrt_nm / (double)(1ULL << dp) + 1024;
    if (ca_htab_init(&tab, (size_t)(exp_dps < 1e8 ? exp_dps : 1e8)) != CA_OK) goto nomem;
    have_tab = 1;
    for (uint32_t w = 0; w < W; w++) glv_restart(&c, &walks[w], &rng, &ops);

    ca_status rc = CA_ERR_NOT_FOUND;
    uint64_t cap = 64 * sqrt_nm * c.m + (1ULL << 20); /* runaway guard */
    while (ops < cap) {
        for (uint32_t w = 0; w < W; w++) {
            glv_walk *wk = &walks[w];
            if (!wk->retry) wk->idx = (uint32_t)(ca_mix64(ca_group_hash(g, &wk->Y)) % c.r);
            B[w] = c.M[wk->idx];
            Yn[w] = wk->Y;
        }
        ca_group_batch_op(g, Yn, Yn, B, W, scratch);
        ops += W;
        for (uint32_t w = 0; w < W; w++) {
            glv_walk *wk = &walks[w];
            uint32_t k = glv_class_reduce(g, &Yn[w], c.m);
            uint64_t h = ca_group_hash(g, &Yn[w]);
            /* Fruitless-cycle look-ahead: if the reduced point would pick the
             * same multiplier we just used, advance to the next one and redo
             * the step -- a deterministic function of the class, so walks
             * still merge (generalises the negation map's 2-cycle rule). */
            if ((uint32_t)(ca_mix64(h) % c.r) == wk->idx) {
                wk->idx = (wk->idx + 1) % c.r;
                wk->retry = 1;
                continue;
            }
            wk->retry = 0;
            wk->a = ca_addmod(wk->a, c.alpha[wk->idx], n);
            wk->b = ca_addmod(wk->b, c.beta[wk->idx], n);
            if (k) {
                wk->a = ca_mulmod(wk->a, c.lam_pow[k], n);
                wk->b = ca_mulmod(wk->b, c.lam_pow[k], n);
            }
            wk->Y = Yn[w];
            wk->since_dp++;
            if ((h & c.dp_mask) == 0) {
                uint64_t oa, ob;
                int ins = ca_htab_insert(&tab, h, wk->a, wk->b, &oa, &ob);
                if (ins < 0) goto nomem;
                wk->since_dp = 0;
                if (ins == 1) {
                    if (!(oa == wk->a && ob == wk->b) &&
                        glv_recover(g, base, target, n, oa, ob, wk->a, wk->b, x)) {
                        rc = CA_OK;
                        goto done;
                    }
                    glv_restart(&c, wk, &rng, &ops);
                }
            } else if (wk->since_dp > c.abandon) {
                glv_restart(&c, wk, &rng, &ops);
            }
        }
    }
done:
    if (st) {
        st->group_ops += ops;
        st->table_entries = ca_max_u64(st->table_entries, tab.count);
        st->bytes_peak = ca_max_u64(st->bytes_peak, ca_htab_bytes(&tab) + (uint64_t)c.r * 32);
        st->seconds += ca_now() - t0;
        st->threads = 1;
    }
    ca_htab_free(&tab);
    free(c.M);
    free(c.alpha);
    free(c.beta);
    free(scratch);
    free(walks);
    free(Yn);
    free(B);
    return rc;
nomem:
    if (have_tab) ca_htab_free(&tab);
    free(c.M);
    free(c.alpha);
    free(c.beta);
    free(scratch);
    free(walks);
    free(Yn);
    free(B);
    return CA_ERR_NOMEM;
}

ca_status ca_curve_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                         uint64_t seed, uint64_t *x, ca_curve_info *info, ca_stats *st)
{
    if (info) {
        memset(info, 0, sizeof(*info));
        info->endo = (ca_curve_endo)g->endo_kind;
        info->aut_order = g->endo_kind ? g->aut_order : 2;
        info->lambda = g->endo_lambda;
        info->rho_speedup = sqrt((double)info->aut_order);
    }
    if (g->kind == CA_GROUP_EC && g->endo_kind != 0)
        return glv_rho_solve(g, base, target, seed, x, st);
    ca_rho_params rp;
    ca_rho_params_default(&rp);
    rp.seed = seed;
    return ca_rho_solve(g, base, target, &rp, x, st);
}
