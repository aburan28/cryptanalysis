/*
 * precomp.c - discrete logarithms with precomputation (Bernstein-Lange
 * "free precomputation").
 *
 * A pseudorandom walk is defined as a function of the current point only:
 * i = mix(hash(Y)) mod r, Y <- Y + S_i with S_i = s_i * base.  Because the
 * step depends on nothing but the point, two walks that ever meet stay
 * merged, and both end at the same distinguished point (a point whose hash
 * has its low dp_bits zero).
 *
 * Precomputation builds a table of chains: each starts at a_0 * base for a
 * random a_0, walks to a distinguished point D = e * base, and stores
 * (hash(D) -> e).  A single online walk for target Q = x * base starts at
 * a * base + Q = (a + x) * base for a random a; the steps only add multiples
 * of base, so it ends at (a' + x) * base.  If that endpoint is a stored
 * e * base then e == a' + x (mod ord base) and x = e - a' follows.  Every
 * candidate is verified, so a 64-bit hash collision costs only a retry.
 *
 * With dp_bits t = round(log2 n / 3): table ~ n^{1/3} chains, precomputation
 * ~ n^{2/3}, per-target online ~ n^{1/3}.  See docs/ALGORITHMS.md.
 */
#include "cryptanalysis/ca_precomp.h"
#include "dlog_internal.h"

#include <math.h>

#define PRECOMP_DEFAULT_R 20

struct ca_precomp_table {
    const ca_group *g;
    ca_elem base;
    uint64_t n;
    uint32_t r;
    int32_t dp_bits;
    uint64_t dp_mask;
    uint64_t chain_limit;
    uint64_t max_online_ops;
    uint64_t seed;
    ca_elem *S;  /* r step points, S[i] = s[i] * base */
    uint64_t *s; /* r step scalars in [1, n) */
    ca_htab tab; /* hash(endpoint) -> exponent e in v0 */
    uint64_t chains;
    uint64_t merges;
    uint64_t precomp_ops;
};

void ca_precomp_params_default(ca_precomp_params *p)
{
    memset(p, 0, sizeof(*p));
    p->dp_bits = -1;
}

static int precomp_ilog2(uint64_t v)
{
    int l = -1;
    while (v) {
        v >>= 1;
        l++;
    }
    return l;
}

/* Walk from *Y (with base-exponent *a) to the first distinguished point.
 * Returns 1 on a distinguished point (Y, a updated), 0 if abandoned after
 * chain_limit steps.  Counts each step into *ops. */
static int precomp_walk(const ca_precomp_table *t, ca_elem *Y, uint64_t *a, uint64_t *ops)
{
    const ca_group *g = t->g;
    for (uint64_t steps = 0;; steps++) {
        uint64_t h = ca_group_hash(g, Y);
        if ((h & t->dp_mask) == 0) return 1;
        if (steps >= t->chain_limit) return 0;
        uint32_t i = (uint32_t)(ca_mix64(h) % t->r);
        ca_group_op(g, Y, Y, &t->S[i]);
        *a = ca_addmod(*a, t->s[i], t->n);
        (*ops)++;
    }
}

ca_status ca_precomp_table_new(const ca_group *g, const ca_elem *base,
                               const ca_precomp_params *params, ca_precomp_table **out,
                               ca_stats *st)
{
    ca_precomp_params def;
    if (!params) {
        ca_precomp_params_default(&def);
        params = &def;
    }
    if (g->order == 0) {
        ca_set_error("precomputation requires a known group order");
        return CA_ERR_INVALID;
    }
    double t0 = ca_now();
    uint64_t n = g->order;

    ca_precomp_table *t = calloc(1, sizeof(*t));
    if (!t) return CA_ERR_NOMEM;
    t->g = g;
    t->base = *base;
    t->n = n;
    t->seed = ca_seed_or_random(params->seed);
    t->max_online_ops = params->max_online_ops;

    int lg = precomp_ilog2(n); /* floor(log2 n) */
    int32_t dp = params->dp_bits;
    if (dp < 0) dp = (int32_t)((lg + 1) / 3);
    if (dp < 0) dp = 0;
    if (dp > 40) dp = 40;
    t->dp_bits = dp;
    t->dp_mask = dp ? ((1ULL << dp) - 1) : 0;

    t->r = params->r ? params->r : PRECOMP_DEFAULT_R;
    if (t->r < 2) t->r = 2;

    double two_t = ldexp(1.0, dp); /* 2^t */
    double cf = params->coverage > 0 ? params->coverage : 1.0;
    uint64_t chains = params->table_size;
    if (chains == 0) {
        double target_c = cf * (double)n / (two_t * two_t);
        if (target_c < 1.0) target_c = 1.0;
        if (target_c > 1e8) target_c = 1e8;
        chains = (uint64_t)(target_c + 0.5);
    }
    if (chains < 1) chains = 1;

    t->chain_limit = params->chain_limit ? params->chain_limit : (uint64_t)(20.0 * two_t) + 64;

    t->S = calloc(t->r, sizeof(ca_elem));
    t->s = calloc(t->r, sizeof(uint64_t));
    if (!t->S || !t->s) {
        ca_precomp_table_free(t);
        return CA_ERR_NOMEM;
    }
    ca_rng rng;
    ca_rng_seed(&rng, t->seed);
    uint64_t ops = 0;
    for (uint32_t i = 0; i < t->r; i++) {
        t->s[i] = ca_rng_below(&rng, n - 1) + 1; /* nonzero: the walk advances */
        ca_group_mul(g, &t->S[i], base, t->s[i], &ops);
    }

    size_t hint = (size_t)ca_min_u64(chains, (uint64_t)1 << 26);
    if (ca_htab_init(&t->tab, hint) != CA_OK) {
        ca_precomp_table_free(t);
        return CA_ERR_NOMEM;
    }

    for (uint64_t c = 0; c < chains; c++) {
        if (params->max_precomp_ops && ops > params->max_precomp_ops) break;
        uint64_t a = ca_rng_below(&rng, n);
        ca_elem Y;
        ca_group_mul(g, &Y, base, a, &ops);
        if (!precomp_walk(t, &Y, &a, &ops)) continue; /* cycle without a DP */
        int ins = ca_htab_insert(&t->tab, ca_group_hash(g, &Y), a, 0, NULL, NULL);
        if (ins < 0) {
            ca_precomp_table_free(t);
            return CA_ERR_NOMEM;
        }
        if (ins == 1)
            t->merges++;
        else
            t->chains++;
    }
    t->precomp_ops = ops;

    if (st) {
        st->group_ops += ops;
        st->iterations += t->chains + t->merges;
        st->collisions += t->merges;
        st->table_entries = ca_max_u64(st->table_entries, t->tab.count);
        st->bytes_peak =
            ca_max_u64(st->bytes_peak, ca_htab_bytes(&t->tab) + (uint64_t)t->r * sizeof(ca_elem));
        st->seconds += ca_now() - t0;
    }
    *out = t;
    return CA_OK;
}

void ca_precomp_table_free(ca_precomp_table *t)
{
    if (!t) return;
    ca_htab_free(&t->tab);
    free(t->S);
    free(t->s);
    free(t);
}

ca_status ca_precomp_table_solve(const ca_precomp_table *t, const ca_elem *target, uint64_t *x,
                                 ca_stats *st)
{
    const ca_group *g = t->g;
    double t0 = ca_now();
    uint64_t n = t->n;

    if (ca_group_is_identity(g, target)) {
        *x = 0;
        return CA_OK;
    }

    ca_rng rng;
    ca_rng_seed(&rng, t->seed ^ ca_group_hash(g, target) ^ 0x9E3779B97F4A7C15ULL);

    /* Each attempt walks ~2^t steps and, with the intended coverage,
     * succeeds with constant probability; independent restarts make a few
     * hundred attempts astronomically safe and also bound the work when the
     * table is too small or the target is not in <base>. */
    const uint64_t max_attempts = 512;
    uint64_t ops = 0, attempts = 0;
    ca_status rc = CA_ERR_NOT_FOUND;

    while (attempts < max_attempts) {
        if (t->max_online_ops && ops > t->max_online_ops) {
            rc = CA_ERR_LIMIT;
            break;
        }
        attempts++;
        /* Start at a random group element a*base + target = (a + x)*base and
         * walk to a distinguished point (a' + x)*base. */
        uint64_t a = ca_rng_below(&rng, n);
        ca_elem Y;
        ca_group_mul(g, &Y, &t->base, a, &ops);
        ca_group_op(g, &Y, &Y, target);
        ops++;
        if (!precomp_walk(t, &Y, &a, &ops)) continue;
        uint64_t e;
        if (ca_htab_find(&t->tab, ca_group_hash(g, &Y), &e, NULL)) {
            uint64_t cand = ca_submod(e % n, a % n, n); /* x = e - a' (mod n) */
            if (ca_verify_log(g, &t->base, target, cand)) {
                *x = cand;
                rc = CA_OK;
                break;
            }
        }
    }

    if (st) {
        st->group_ops += ops;
        st->iterations += attempts;
        st->table_entries = ca_max_u64(st->table_entries, t->tab.count);
        st->bytes_peak =
            ca_max_u64(st->bytes_peak, ca_htab_bytes(&t->tab) + (uint64_t)t->r * sizeof(ca_elem));
        st->seconds += ca_now() - t0;
    }
    if (rc == CA_ERR_NOT_FOUND)
        ca_set_error("precomputation solve: no stored distinguished point matched");
    return rc;
}

void ca_precomp_table_info(const ca_precomp_table *t, int32_t *dp_bits, uint64_t *chains,
                           uint32_t *r, uint64_t *precomp_ops)
{
    if (dp_bits) *dp_bits = t->dp_bits;
    if (chains) *chains = t->chains;
    if (r) *r = t->r;
    if (precomp_ops) *precomp_ops = t->precomp_ops;
}

ca_status ca_precomp_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                           const ca_precomp_params *params, uint64_t *x, ca_stats *st)
{
    ca_precomp_table *t = NULL;
    ca_status rc = ca_precomp_table_new(g, base, params, &t, st);
    if (rc != CA_OK) return rc;
    rc = ca_precomp_table_solve(t, target, x, st);
    ca_precomp_table_free(t);
    return rc;
}
