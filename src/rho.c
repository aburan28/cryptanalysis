/*
 * rho.c - parallel Pollard rho with distinguished points.
 *
 * Walk definition (Teske r-adding walk).  Multipliers M_i = alpha_i*G +
 * beta_i*H for i < r.  A walk state is (Y, a, b) with Y = a*G + b*H.  One
 * step: i = idx(Y); Y <- Y + M_i; (a, b) <- (a + alpha_i, b + beta_i).
 *
 * With the negation map every point is replaced by the canonical member of
 * {Y, -Y} after each step (negating (a, b) when needed), and idx() is
 * evaluated on the canonical form.  Fruitless 2-cycles are suppressed by
 * the look-ahead rule "if idx(Y + M_i) == i use M_{i+1} instead" and
 * longer cycles are caught by a sliding-window self-comparison; a walk
 * caught in a cycle escapes deterministically from the minimum element of
 * the cycle by doubling, so two walks that merged inside the cycle stay
 * merged.
 *
 * Distinguished points (hash with dp_bits trailing zeros) are stored in a
 * shared table with their (a, b).  A second arrival at the same point with
 * a different (a, b) yields (b - b') x == a' - a (mod n).
 */
#include "cryptanalysis/ca_rho.h"
#include "dlog_internal.h"

#include <pthread.h>
#include <stdatomic.h>

#define RHO_WINDOW 64
#define RHO_MAX_WALKS 4096

typedef struct rho_shared {
    const ca_group *g;
    ca_elem base, target;
    uint64_t n;
    uint32_t r;
    ca_elem *M;
    uint64_t *alpha, *beta;
    int negmap;
    int dp_bits;
    uint64_t dp_mask;
    uint32_t walks;
    uint64_t seed;
    uint64_t max_ops, max_table;

    pthread_mutex_t lock;
    ca_htab tab;
    atomic_int done;
    atomic_uint_fast64_t total_ops;
    atomic_uint_fast64_t total_dps;
    atomic_uint_fast64_t restarts;
    uint64_t result;
    ca_status status;
} rho_shared;

typedef struct rho_walk {
    ca_elem Y;
    uint64_t a, b;
    uint32_t idx;
    uint8_t retry;
    uint64_t since_dp;
    ca_elem saved;
    uint32_t win;
} rho_walk;

typedef struct rho_thread {
    rho_shared *sh;
    uint32_t id;
    uint64_t ops;
} rho_thread;

void ca_rho_params_default(ca_rho_params *p)
{
    memset(p, 0, sizeof(*p));
    p->threads = 1;
    p->dp_bits = -1;
    p->negation_map = 1;
}

static inline uint32_t rho_index(const rho_shared *sh, uint64_t h)
{
    return (uint32_t)((h >> 32) % sh->r);
}

static inline void exp_add(uint64_t n, uint64_t *a, uint64_t d)
{
    *a = ca_addmod(*a, d, n);
}

static void walk_restart(rho_shared *sh, rho_walk *w, ca_rng *rng, uint64_t *ops)
{
    const ca_group *g = sh->g;
    w->a = ca_rng_below(rng, sh->n);
    w->b = ca_rng_below(rng, sh->n);
    ca_elem t1, t2;
    ca_group_mul(g, &t1, &sh->base, w->a, ops);
    ca_group_mul(g, &t2, &sh->target, w->b, ops);
    ca_group_op(g, &w->Y, &t1, &t2);
    (*ops)++;
    if (sh->negmap && ca_group_canonicalize(g, &w->Y)) {
        w->a = w->a ? sh->n - w->a : 0;
        w->b = w->b ? sh->n - w->b : 0;
    }
    w->retry = 0;
    w->since_dp = 0;
    w->win = 0;
}

/* Apply the exponent update for a step with multiplier i and sign flag. */
static inline void walk_apply(const rho_shared *sh, rho_walk *w, uint32_t i, int negated)
{
    exp_add(sh->n, &w->a, sh->alpha[i]);
    exp_add(sh->n, &w->b, sh->beta[i]);
    if (negated) {
        w->a = w->a ? sh->n - w->a : 0;
        w->b = w->b ? sh->n - w->b : 0;
    }
}

/* One full (unbatched) step of the walk function.  Used only for cycle
 * escapes; must match the batched path exactly. */
static void walk_step_single(rho_shared *sh, rho_walk *w, uint64_t *ops)
{
    const ca_group *g = sh->g;
    uint32_t i = w->retry ? w->idx : rho_index(sh, ca_group_hash(g, &w->Y));
    for (;;) {
        ca_elem Yn;
        ca_group_op(g, &Yn, &w->Y, &sh->M[i]);
        (*ops)++;
        int neg = sh->negmap ? ca_group_canonicalize(g, &Yn) : 0;
        if (sh->negmap && rho_index(sh, ca_group_hash(g, &Yn)) == i) {
            i = (i + 1) % sh->r;
            continue;
        }
        w->Y = Yn;
        walk_apply(sh, w, i, neg);
        w->retry = 0;
        return;
    }
}

/* Escape from a fruitless cycle containing w->Y: find the cycle's minimum
 * (by hash), then jump to 2*min. */
static void walk_escape_cycle(rho_shared *sh, rho_walk *w, uint64_t *ops)
{
    const ca_group *g = sh->g;
    rho_walk cur = *w;
    cur.retry = 0;
    rho_walk best = cur;
    uint64_t best_h = ca_group_hash(g, &cur.Y);
    for (uint32_t k = 0; k < 4 * RHO_WINDOW; k++) {
        walk_step_single(sh, &cur, ops);
        uint64_t h = ca_group_hash(g, &cur.Y);
        if (ca_group_equal(g, &cur.Y, &w->Y)) break;
        if (h < best_h) { best_h = h; best = cur; }
    }
    ca_group_dbl(g, &w->Y, &best.Y);
    (*ops)++;
    w->a = ca_addmod(best.a, best.a, sh->n);
    w->b = ca_addmod(best.b, best.b, sh->n);
    if (sh->negmap && ca_group_canonicalize(g, &w->Y)) {
        w->a = w->a ? sh->n - w->a : 0;
        w->b = w->b ? sh->n - w->b : 0;
    }
    w->retry = 0;
    w->win = 0;
}

/* Try to solve from a collision between stored (a1,b1) and new (a2,b2) at
 * the same canonical point.  Returns 1 on success and sets sh->result. */
static int rho_try_solve(rho_shared *sh, uint64_t a1, uint64_t b1, uint64_t a2, uint64_t b2)
{
    const ca_group *g = sh->g;
    uint64_t n = sh->n;
    for (int sign = 0; sign < (sh->negmap ? 2 : 1); sign++) {
        uint64_t c, d;
        if (sign == 0) {
            /* a1 + b1 x == a2 + b2 x  =>  (b1 - b2) x == a2 - a1 */
            c = ca_submod(b1, b2, n);
            d = ca_submod(a2, a1, n);
        } else {
            /* a1 + b1 x == -(a2 + b2 x) => (b1 + b2) x == -(a1 + a2) */
            c = ca_addmod(b1, b2, n);
            d = n - ca_addmod(a1, a2, n);
            if (d == n) d = 0;
        }
        if (c == 0) continue;
        uint64_t gg = ca_gcd(c, n);
        if (d % gg) continue;
        uint64_t nn = n / gg;
        uint64_t x0 = ca_mulmod((d / gg) % nn, ca_invmod((c / gg) % nn, nn), nn);
        if (gg > 65536) gg = 65536;
        for (uint64_t k = 0; k < gg; k++) {
            uint64_t x = x0 + k * nn;
            if (x >= n) break;
            if (ca_verify_log(g, &sh->base, &sh->target, x)) {
                sh->result = x;
                return 1;
            }
        }
    }
    return 0;
}

static void *rho_thread_main(void *arg)
{
    rho_thread *th = arg;
    rho_shared *sh = th->sh;
    const ca_group *g = sh->g;
    uint32_t W = sh->walks;
    rho_walk *walks = calloc(W, sizeof(rho_walk));
    ca_elem *Yn = calloc(W, sizeof(ca_elem));
    ca_elem *B = calloc(W, sizeof(ca_elem));
    uint64_t *scratch = calloc(2 * (size_t)W, sizeof(uint64_t));
    if (!walks || !Yn || !B || !scratch) {
        free(walks); free(Yn); free(B); free(scratch);
        pthread_mutex_lock(&sh->lock);
        sh->status = CA_ERR_NOMEM;
        atomic_store(&sh->done, 1);
        pthread_mutex_unlock(&sh->lock);
        return NULL;
    }
    ca_rng rng;
    ca_rng_seed(&rng, sh->seed ^ (0x9E3779B97F4A7C15ULL * (th->id + 1)));
    uint64_t ops = 0;
    for (uint32_t w = 0; w < W; w++) walk_restart(sh, &walks[w], &rng, &ops);
    const uint64_t abandon = (uint64_t)24 << sh->dp_bits;
    uint64_t local_dps = 0, local_restarts = 0;

    while (!atomic_load_explicit(&sh->done, memory_order_relaxed)) {
        for (uint32_t w = 0; w < W; w++) {
            rho_walk *wk = &walks[w];
            if (!wk->retry) wk->idx = rho_index(sh, ca_group_hash(g, &wk->Y));
            B[w] = sh->M[wk->idx];
        }
        for (uint32_t w = 0; w < W; w++) Yn[w] = walks[w].Y;
        ca_group_batch_op(g, Yn, Yn, B, W, scratch);
        ops += W;
        for (uint32_t w = 0; w < W; w++) {
            rho_walk *wk = &walks[w];
            int neg = sh->negmap ? ca_group_canonicalize(g, &Yn[w]) : 0;
            uint64_t h = ca_group_hash(g, &Yn[w]);
            if (sh->negmap && rho_index(sh, h) == wk->idx) {
                wk->idx = (wk->idx + 1) % sh->r;
                wk->retry = 1;
                continue;
            }
            wk->retry = 0;
            wk->Y = Yn[w];
            walk_apply(sh, wk, wk->idx, neg);
            wk->since_dp++;

            if (sh->negmap) {
                if (wk->win == 0) {
                    wk->saved = wk->Y;
                    wk->win = RHO_WINDOW;
                } else {
                    wk->win--;
                    if (wk->Y.w[0] == wk->saved.w[0] && ca_group_equal(g, &wk->Y, &wk->saved)) {
                        walk_escape_cycle(sh, wk, &ops);
                        h = ca_group_hash(g, &wk->Y);
                    }
                }
            }

            if ((h & sh->dp_mask) == 0) {
                uint64_t oa, ob;
                int rc;
                pthread_mutex_lock(&sh->lock);
                rc = ca_htab_insert(&sh->tab, h, wk->a, wk->b, &oa, &ob);
                size_t entries = sh->tab.count;
                pthread_mutex_unlock(&sh->lock);
                local_dps++;
                if (rc < 0) {
                    pthread_mutex_lock(&sh->lock);
                    sh->status = CA_ERR_NOMEM;
                    atomic_store(&sh->done, 1);
                    pthread_mutex_unlock(&sh->lock);
                    break;
                }
                if (rc == 1) {
                    if (oa == wk->a && ob == wk->b) {
                        /* the walk merged with its own earlier trail (or an
                         * identical trail): restart */
                        walk_restart(sh, wk, &rng, &ops);
                        local_restarts++;
                    } else {
                        pthread_mutex_lock(&sh->lock);
                        if (!atomic_load(&sh->done) && rho_try_solve(sh, oa, ob, wk->a, wk->b)) {
                            sh->status = CA_OK;
                            atomic_store(&sh->done, 1);
                        }
                        pthread_mutex_unlock(&sh->lock);
                        if (atomic_load(&sh->done)) break;
                        /* useless collision (e.g. same point, unsolvable congruence): restart */
                        walk_restart(sh, wk, &rng, &ops);
                        local_restarts++;
                    }
                }
                wk->since_dp = 0;
                if (sh->max_table && entries > sh->max_table) {
                    pthread_mutex_lock(&sh->lock);
                    if (!atomic_load(&sh->done)) sh->status = CA_ERR_LIMIT;
                    atomic_store(&sh->done, 1);
                    pthread_mutex_unlock(&sh->lock);
                    break;
                }
            } else if (wk->since_dp > abandon) {
                walk_restart(sh, wk, &rng, &ops);
                local_restarts++;
            }
        }
        if (sh->max_ops) {
            uint64_t tot = atomic_load_explicit(&sh->total_ops, memory_order_relaxed) + ops;
            if (tot > sh->max_ops) {
                pthread_mutex_lock(&sh->lock);
                if (!atomic_load(&sh->done)) sh->status = CA_ERR_LIMIT;
                atomic_store(&sh->done, 1);
                pthread_mutex_unlock(&sh->lock);
            }
        }
        if (ops >= 65536) {
            /* publish progress occasionally so max_ops is global */
            atomic_fetch_add(&sh->total_ops, ops);
            ops = 0;
        }
    }
    atomic_fetch_add(&sh->total_ops, ops);
    atomic_fetch_add(&sh->total_dps, local_dps);
    atomic_fetch_add(&sh->restarts, local_restarts);
    th->ops = ops;
    free(walks); free(Yn); free(B); free(scratch);
    return NULL;
}

static int ilog2_u64(uint64_t v)
{
    int l = -1;
    while (v) { v >>= 1; l++; }
    return l;
}

ca_status ca_rho_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                       const ca_rho_params *params, uint64_t *x, ca_stats *st)
{
    ca_rho_params def;
    if (!params) { ca_rho_params_default(&def); params = &def; }
    if (g->order == 0) {
        ca_set_error("rho requires a known group order");
        return CA_ERR_INVALID;
    }
    double t0 = ca_now();
    uint64_t n = g->order;

    /* trivial cases */
    if (ca_group_is_identity(g, target)) { *x = 0; return CA_OK; }
    if (n < 64) {
        ca_elem cur;
        ca_group_identity(g, &cur);
        for (uint64_t k = 0; k < n; k++) {
            if (ca_group_equal(g, &cur, target)) { *x = k; if (st) st->group_ops += k; return CA_OK; }
            ca_group_op(g, &cur, &cur, base);
        }
        return CA_ERR_NOT_FOUND;
    }

    rho_shared sh;
    memset(&sh, 0, sizeof(sh));
    sh.g = g;
    sh.base = *base;
    sh.target = *target;
    sh.n = n;
    sh.negmap = params->negation_map && ca_group_has_negation_map(g);
    uint64_t sqrt_n = ca_isqrt(n) + 1;
    if (params->r) sh.r = params->r;
    else {
        /* Building each multiplier costs ~3 log2(n) group operations; keep
         * the whole table under sqrt(n)/16 operations so that the setup
         * never dominates, within [8, 1024] (negation map) or [8, 32]. */
        int lg = ilog2_u64(n) + 1;
        uint64_t budget = sqrt_n / (48u * (uint64_t)lg);
        uint32_t r = 8;
        uint32_t cap = sh.negmap ? 1024u : 32u;
        while ((uint64_t)r * 2 <= budget && r * 2 <= cap) r *= 2;
        sh.r = r;
    }
    if (sh.r < 4) sh.r = 4;
    sh.seed = ca_seed_or_random(params->seed);
    sh.max_ops = params->max_ops;
    sh.max_table = params->max_table_entries;
    uint32_t threads = params->threads ? params->threads : 1;
    uint32_t W = params->walks_per_thread;
    if (W == 0) {
        /* Each walk start costs ~3 log2(n) group operations (two scalar
         * multiplications).  Keep the total start-up cost under sqrt(n)/8
         * so that small groups are not dominated by it. */
        W = (g->kind == CA_GROUP_EC) ? 256 : 16;
        int lg = ilog2_u64(n) + 1;
        uint64_t total_cap = sqrt_n / (24u * (uint64_t)lg);
        uint64_t cap = total_cap / threads;
        if (cap < 1) cap = 1;
        if (W > cap) W = (uint32_t)cap;
    }
    if (W > RHO_MAX_WALKS) W = RHO_MAX_WALKS;
    sh.walks = W;
    int dp = params->dp_bits;
    /* dp is a shift count for a 64-bit mask, and `24 << dp` must not wrap. */
    if (dp > 58) dp = 58;
    if (dp < 0) {
        double expected = 1.25 * (double)sqrt_n / (sh.negmap ? 1.4142 : 1.0);
        double total_walks = (double)threads * W;
        double per_walk = expected / (32.0 * total_walks);
        dp = per_walk >= 2.0 ? ilog2_u64((uint64_t)per_walk) : 0;
        /* keep the DP table under ~2^24 entries */
        int min_dp = ilog2_u64((uint64_t)expected) - 24;
        if (dp < min_dp) dp = min_dp;
        if (dp < 0) dp = 0;
        if (dp > 48) dp = 48;
    }
    sh.dp_bits = dp;
    sh.dp_mask = dp ? ((1ULL << dp) - 1) : 0;

    /* multipliers */
    sh.M = calloc(sh.r, sizeof(ca_elem));
    sh.alpha = calloc(sh.r, sizeof(uint64_t));
    sh.beta = calloc(sh.r, sizeof(uint64_t));
    if (!sh.M || !sh.alpha || !sh.beta) {
        free(sh.M); free(sh.alpha); free(sh.beta);
        return CA_ERR_NOMEM;
    }
    ca_rng rng;
    ca_rng_seed(&rng, sh.seed);
    uint64_t setup_ops = 0;
    for (uint32_t i = 0; i < sh.r; i++) {
        sh.alpha[i] = ca_rng_below(&rng, n);
        sh.beta[i] = ca_rng_below(&rng, n);
        ca_elem t1, t2;
        ca_group_mul(g, &t1, base, sh.alpha[i], &setup_ops);
        ca_group_mul(g, &t2, target, sh.beta[i], &setup_ops);
        ca_group_op(g, &sh.M[i], &t1, &t2);
        setup_ops++;
    }
    double expected_dps = 1.25 * (double)sqrt_n / (double)(1ULL << dp) + 1024;
    if (ca_htab_init(&sh.tab, (size_t)(expected_dps < 1e8 ? expected_dps : 1e8)) != CA_OK) {
        free(sh.M); free(sh.alpha); free(sh.beta);
        return CA_ERR_NOMEM;
    }
    pthread_mutex_init(&sh.lock, NULL);
    atomic_store(&sh.done, 0);
    sh.status = CA_ERR_INTERNAL;

    pthread_t *tids = calloc(threads, sizeof(pthread_t));
    rho_thread *ths = calloc(threads, sizeof(rho_thread));
    uint8_t *created = calloc(threads, 1);
    if (!tids || !ths || !created) {
        free(tids);
        free(ths);
        free(created);
        ca_htab_free(&sh.tab);
        free(sh.M); free(sh.alpha); free(sh.beta);
        pthread_mutex_destroy(&sh.lock);
        return CA_ERR_NOMEM;
    }
    uint32_t started = 0;
    for (uint32_t t = 0; t < threads; t++) {
        ths[t].sh = &sh;
        ths[t].id = t;
        if (threads == 1) {
            rho_thread_main(&ths[t]);
        } else if (pthread_create(&tids[t], NULL, rho_thread_main, &ths[t]) == 0) {
            created[t] = 1;
            started++;
        }
    }
    if (threads > 1 && started == 0) {
        /* could not spawn: run inline */
        rho_thread_main(&ths[0]);
    }
    for (uint32_t t = 0; t < threads; t++)
        if (created[t]) pthread_join(tids[t], NULL);

    ca_status rc = sh.status;
    if (rc == CA_OK) *x = sh.result;
    if (st) {
        st->group_ops += atomic_load(&sh.total_ops) + setup_ops;
        st->iterations += atomic_load(&sh.total_dps);
        st->collisions += atomic_load(&sh.restarts);
        st->table_entries = ca_max_u64(st->table_entries, sh.tab.count);
        st->bytes_peak = ca_max_u64(st->bytes_peak, ca_htab_bytes(&sh.tab) + (uint64_t)sh.r * 48);
        st->threads = threads;
        st->seconds += ca_now() - t0;
    }
    free(tids);
    free(ths);
    free(created);
    ca_htab_free(&sh.tab);
    free(sh.M); free(sh.alpha); free(sh.beta);
    pthread_mutex_destroy(&sh.lock);
    return rc;
}
