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
 * ~ n^{2/3}, per-target online ~ n^{1/3}.
 *
 * Optimisations (see docs/ALGORITHMS.md):
 *   - walk starts use a fixed-base table G[b] = 2^b * base, so a * base is a
 *     sum over the set bits of a rather than a generic double-and-add;
 *   - the precomputation walks W chains in lockstep through one batched field
 *     inversion (ca_group_batch_op), across `threads` workers;
 *   - an optional Bloom filter over covered points aborts a chain as soon as
 *     it re-enters covered ground (a win when the table over-covers the
 *     group, e.g. a large coverage factor);
 *   - the table is a sorted (fingerprint, exponent) array, binary-searched.
 */
#include "cryptanalysis/ca_precomp.h"
#include "dlog_internal.h"

#include <math.h>
#include <pthread.h>
#include <stdatomic.h>

#define PRECOMP_DEFAULT_R      20
#define PRECOMP_MAX_WALKS      1024
#define PRECOMP_BLOOM_MAX_BITS (1ULL << 33) /* 1 GiB filter ceiling */

/* One stored chain endpoint: the 64-bit hash of e*base and the exponent e. */
typedef struct pc_entry {
    uint64_t fp;
    uint64_t exp;
} pc_entry;

/* Approximate-membership filter over covered points (build only). */
typedef struct pc_bloom {
    _Atomic uint64_t *w;
    size_t nwords; /* power of two */
    uint64_t mask; /* nwords - 1 */
    int k;
} pc_bloom;

struct ca_precomp_table {
    const ca_group *g;
    ca_elem base;
    uint64_t n;
    uint32_t r;
    uint32_t walks; /* batch width used to build */
    int32_t dp_bits;
    uint64_t dp_mask;
    uint64_t chain_limit;
    uint64_t max_online_ops;
    uint64_t seed;

    ca_elem *S;  /* r step points, S[i] = s[i] * base */
    uint64_t *s; /* r step scalars in [1, n) */

    int bitlen;    /* number of bits in n */
    ca_elem *Gpow; /* fixed-base table, Gpow[b] = 2^b * base */

    pc_entry *ent; /* sorted by fp, deduplicated */
    size_t nent;

    uint64_t chains; /* distinct endpoints stored (== nent) */
    uint64_t merges; /* endpoints dropped as duplicates + early aborts */
    uint64_t precomp_ops;
};

void ca_precomp_params_default(ca_precomp_params *p)
{
    memset(p, 0, sizeof(*p));
    p->dp_bits = -1;
    p->early_abort = -1;
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

/* ---- fixed-base scalar multiplication --------------------------------- */

/* r = k * base as the sum of Gpow[b] over the set bits b of k.  Counts each
 * addition into *ops. */
static void pc_base_mul(const ca_precomp_table *t, ca_elem *r, uint64_t k, uint64_t *ops)
{
    const ca_group *g = t->g;
    ca_elem acc;
    int started = 0;
    for (int b = 0; b < t->bitlen; b++) {
        if (!((k >> b) & 1)) continue;
        if (!started) {
            acc = t->Gpow[b];
            started = 1;
        } else {
            ca_group_op(g, &acc, &acc, &t->Gpow[b]);
            if (ops) (*ops)++;
        }
    }
    if (!started) ca_group_identity(g, &acc);
    *r = acc;
}

/* ---- Bloom filter ----------------------------------------------------- */

static int pc_bloom_init(pc_bloom *b, uint64_t bits)
{
    size_t words = 1;
    while ((uint64_t)words * 64 < bits) words <<= 1;
    b->w = calloc(words, sizeof(_Atomic uint64_t));
    if (!b->w) return -1;
    b->nwords = words;
    b->mask = (uint64_t)words - 1;
    b->k = 4;
    return 0;
}

static void pc_bloom_free(pc_bloom *b)
{
    free(b->w);
    b->w = NULL;
}

/* Test membership of key; when add != 0 also set its bits.  Returns 1 if all
 * bits were already present (a probable hit). */
static int pc_bloom_test_and_add(pc_bloom *b, uint64_t key, int add)
{
    int all = 1;
    for (int j = 0; j < b->k; j++) {
        uint64_t h = ca_mix64(key + 0x9E3779B97F4A7C15ULL * (uint64_t)(j + 1));
        size_t wi = (size_t)((h >> 6) & b->mask);
        uint64_t bit = 1ULL << (h & 63);
        uint64_t cur = atomic_load_explicit(&b->w[wi], memory_order_relaxed);
        if (!(cur & bit)) {
            all = 0;
            if (add) atomic_fetch_or_explicit(&b->w[wi], bit, memory_order_relaxed);
        }
    }
    return all;
}

/* ---- table lookup ----------------------------------------------------- */

static int pc_entry_cmp(const void *A, const void *B)
{
    const pc_entry *a = A;
    const pc_entry *b = B;
    return (a->fp > b->fp) - (a->fp < b->fp);
}

static int pc_lookup(const ca_precomp_table *t, uint64_t fp, uint64_t *exp)
{
    size_t lo = 0, hi = t->nent;
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        if (t->ent[mid].fp < fp)
            lo = mid + 1;
        else
            hi = mid;
    }
    if (lo < t->nent && t->ent[lo].fp == fp) {
        *exp = t->ent[lo].exp;
        return 1;
    }
    return 0;
}

/* ---- precomputation (threaded, batched) ------------------------------- */

typedef struct pc_build {
    ca_precomp_table *t;
    pc_bloom *bloom; /* may be NULL */
    uint64_t target_chains;
    uint64_t max_starts;
    uint64_t max_ops;
    atomic_uint_fast64_t stored;
    atomic_uint_fast64_t starts;
    atomic_uint_fast64_t total_ops;
    atomic_int done;
} pc_build;

typedef struct pc_worker {
    pc_build *bd;
    uint32_t id;
    pc_entry *buf;
    size_t n, cap;
    uint64_t merges;
    int err;
} pc_worker;

static int pc_worker_push(pc_worker *wk, uint64_t fp, uint64_t exp)
{
    if (wk->n == wk->cap) {
        size_t nc = wk->cap ? wk->cap * 2 : 1024;
        pc_entry *nb = realloc(wk->buf, nc * sizeof(pc_entry));
        if (!nb) return -1;
        wk->buf = nb;
        wk->cap = nc;
    }
    wk->buf[wk->n].fp = fp;
    wk->buf[wk->n].exp = exp;
    wk->n++;
    return 0;
}

/* Atomically charge nops against the shared build budget. Returns 0 if over max_ops. */
static int pc_charge_ops(pc_build *bd, uint64_t nops)
{
    if (!nops) return 1;
    if (!bd->max_ops) {
        atomic_fetch_add_explicit(&bd->total_ops, nops, memory_order_relaxed);
        return 1;
    }
    for (;;) {
        uint64_t cur = atomic_load_explicit(&bd->total_ops, memory_order_relaxed);
        if (cur + nops > bd->max_ops) {
            atomic_store(&bd->done, 1);
            return 0;
        }
        if (atomic_compare_exchange_weak_explicit(&bd->total_ops, &cur, cur + nops,
                                                  memory_order_relaxed, memory_order_relaxed))
            return 1;
    }
}

/* Restart one lane at a fresh random multiple of base. */
static int pc_lane_restart(const ca_precomp_table *t, ca_rng *rng, ca_elem *Y, uint64_t *a,
                           uint64_t *stepc, uint8_t *stall, pc_build *bd)
{
    *a = ca_rng_below(rng, t->n);
    uint64_t nops = 0;
    pc_base_mul(t, Y, *a, &nops);
    *stepc = 0;
    *stall = 1;
    atomic_fetch_add_explicit(&bd->starts, 1, memory_order_relaxed);
    return pc_charge_ops(bd, nops);
}

static void *pc_build_worker(void *arg)
{
    pc_worker *wk = arg;
    pc_build *bd = wk->bd;
    ca_precomp_table *t = bd->t;
    const ca_group *g = t->g;
    uint32_t W = t->walks;

    ca_elem *Y = calloc(W, sizeof(ca_elem));
    ca_elem *Yn = calloc(W, sizeof(ca_elem));
    ca_elem *B = calloc(W, sizeof(ca_elem));
    uint64_t *a = calloc(W, sizeof(uint64_t));
    uint64_t *pend = calloc(W, sizeof(uint64_t));
    uint64_t *stepc = calloc(W, sizeof(uint64_t));
    uint8_t *stall = calloc(W, 1);
    uint64_t *scratch = calloc(2 * (size_t)W, sizeof(uint64_t));
    if (!Y || !Yn || !B || !a || !pend || !stepc || !stall || !scratch) {
        wk->err = 1;
        atomic_store(&bd->done, 1);
        goto cleanup;
    }
    ca_elem idelem;
    ca_group_identity(g, &idelem);
    ca_rng rng;
    ca_rng_seed(&rng, t->seed ^ (0x9E3779B97F4A7C15ULL * (wk->id + 1)));
    for (uint32_t i = 0; i < W; i++) {
        a[i] = ca_rng_below(&rng, t->n);
        uint64_t nops = 0;
        pc_base_mul(t, &Y[i], a[i], &nops);
        if (!pc_charge_ops(bd, nops)) goto cleanup;
        stepc[i] = 0;
        stall[i] = 0;
        atomic_fetch_add_explicit(&bd->starts, 1, memory_order_relaxed);
    }

    while (!atomic_load_explicit(&bd->done, memory_order_relaxed)) {
        if (atomic_load_explicit(&bd->stored, memory_order_relaxed) >= bd->target_chains) break;
        if (atomic_load_explicit(&bd->starts, memory_order_relaxed) >= bd->max_starts) break;

        for (uint32_t i = 0; i < W; i++) {
            uint64_t h = ca_group_hash(g, &Y[i]);
            int terminal = ((h & t->dp_mask) == 0);
            if (!terminal && bd->bloom && pc_bloom_test_and_add(bd->bloom, h, 0)) {
                wk->merges++;
                if (!pc_lane_restart(t, &rng, &Y[i], &a[i], &stepc[i], &stall[i], bd)) break;
                continue;
            }
            if (terminal) {
                if (pc_worker_push(wk, h, a[i]) != 0) {
                    wk->err = 1;
                    atomic_store(&bd->done, 1);
                    break;
                }
                atomic_fetch_add_explicit(&bd->stored, 1, memory_order_relaxed);
                if (bd->bloom) pc_bloom_test_and_add(bd->bloom, h, 1);
                if (!pc_lane_restart(t, &rng, &Y[i], &a[i], &stepc[i], &stall[i], bd)) break;
                continue;
            }
            if (stepc[i] >= t->chain_limit) {
                if (!pc_lane_restart(t, &rng, &Y[i], &a[i], &stepc[i], &stall[i], bd)) break;
                continue;
            }
            if (bd->bloom) pc_bloom_test_and_add(bd->bloom, h, 1);
            uint32_t idx = (uint32_t)(ca_mix64(h) % t->r);
            B[i] = t->S[idx];
            pend[i] = t->s[idx];
            stall[i] = 0;
        }
        if (wk->err) break;

        uint32_t active = 0;
        for (uint32_t i = 0; i < W; i++) {
            if (stall[i])
                B[i] = idelem;
            else
                active++;
        }
        if (!pc_charge_ops(bd, active)) break;
        ca_group_batch_op(g, Yn, Y, B, W, scratch);
        for (uint32_t i = 0; i < W; i++) {
            Y[i] = Yn[i];
            if (stall[i]) {
                stall[i] = 0;
            } else {
                a[i] = ca_addmod(a[i], pend[i], t->n);
                stepc[i]++;
            }
        }
    }

cleanup:
    free(Y);
    free(Yn);
    free(B);
    free(a);
    free(pend);
    free(stepc);
    free(stall);
    free(scratch);
    return NULL;
}

/* Build Gpow and the r-step table; returns setup ops or -1 on failure. */
static int64_t pc_build_tables(ca_precomp_table *t, const ca_elem *base, ca_rng *rng)
{
    const ca_group *g = t->g;
    t->Gpow = calloc((size_t)t->bitlen, sizeof(ca_elem));
    t->S = calloc(t->r, sizeof(ca_elem));
    t->s = calloc(t->r, sizeof(uint64_t));
    if (!t->Gpow || !t->S || !t->s) return -1;
    t->Gpow[0] = *base;
    for (int b = 1; b < t->bitlen; b++) ca_group_dbl(g, &t->Gpow[b], &t->Gpow[b - 1]);
    uint64_t ops = 0;
    for (uint32_t i = 0; i < t->r; i++) {
        t->s[i] = ca_rng_below(rng, t->n - 1) + 1; /* nonzero: the walk advances */
        pc_base_mul(t, &t->S[i], t->s[i], &ops);
    }
    return (int64_t)((uint64_t)(t->bitlen - 1) + ops); /* doublings + step-table adds */
}

/* Merge the workers' endpoint buffers into one sorted, deduplicated array. */
static ca_status pc_collect(ca_precomp_table *t, pc_worker *wks, uint32_t nthreads)
{
    size_t total = 0;
    for (uint32_t w = 0; w < nthreads; w++) total += wks[w].n;
    if (total == 0) {
        t->ent = NULL;
        t->nent = 0;
        t->chains = 0;
        return CA_OK;
    }
    pc_entry *all = malloc(total * sizeof(pc_entry));
    if (!all) return CA_ERR_NOMEM;
    size_t off = 0;
    for (uint32_t w = 0; w < nthreads; w++) {
        if (wks[w].n) memcpy(all + off, wks[w].buf, wks[w].n * sizeof(pc_entry));
        off += wks[w].n;
        t->merges += wks[w].merges;
    }
    qsort(all, total, sizeof(pc_entry), pc_entry_cmp);
    size_t u = 0;
    for (size_t i = 0; i < total; i++) {
        if (u == 0 || all[i].fp != all[u - 1].fp)
            all[u++] = all[i];
        else
            t->merges++;
    }
    t->ent = all;
    t->nent = u;
    t->chains = u;
    return CA_OK;
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
    t->bitlen = precomp_ilog2(n) + 1;

    int32_t dp = params->dp_bits;
    if (dp < 0) dp = (int32_t)((t->bitlen) / 3);
    if (dp < 0) dp = 0;
    if (dp > 40) dp = 40;
    t->dp_bits = dp;
    t->dp_mask = dp ? ((1ULL << dp) - 1) : 0;

    t->r = params->r ? params->r : PRECOMP_DEFAULT_R;
    if (t->r < 2) t->r = 2;

    double two_t = ldexp(1.0, dp);
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

    uint32_t W = params->walks;
    if (W == 0) W = (g->kind == CA_GROUP_EC) ? 256u : 1u;
    if ((uint64_t)W > chains) W = (uint32_t)chains;
    if (W < 1) W = 1;
    if (W > PRECOMP_MAX_WALKS) W = PRECOMP_MAX_WALKS;
    t->walks = W;

    ca_rng rng;
    ca_rng_seed(&rng, t->seed);
    int64_t setup = pc_build_tables(t, base, &rng);
    if (setup < 0) {
        ca_precomp_table_free(t);
        return CA_ERR_NOMEM;
    }

    /* Optional early-abort filter.  Auto-enable only when the table is built
     * to cover a non-trivial fraction of the group (large coverage factor),
     * where chains actually merge; otherwise merges are negligible and the
     * filter would only add per-step overhead. */
    pc_bloom bloom;
    memset(&bloom, 0, sizeof(bloom));
    int use_bloom = 0;
    double covered_est = (double)chains * two_t;
    int auto_on = covered_est * 8.0 >= (double)n;
    if (params->early_abort == 1 || (params->early_abort < 0 && auto_on)) {
        double bits = covered_est * 8.0 + 1024.0;
        if (bits > (double)PRECOMP_BLOOM_MAX_BITS) bits = (double)PRECOMP_BLOOM_MAX_BITS;
        if (pc_bloom_init(&bloom, (uint64_t)bits) == 0) use_bloom = 1;
    }

    pc_build bd;
    memset(&bd, 0, sizeof(bd));
    bd.t = t;
    bd.bloom = use_bloom ? &bloom : NULL;
    bd.target_chains = chains;
    bd.max_starts = chains * 4 + (uint64_t)W * 4 + 64;
    bd.max_ops = params->max_precomp_ops;
    atomic_store(&bd.stored, 0);
    atomic_store(&bd.starts, 0);
    atomic_store(&bd.total_ops, 0);
    atomic_store(&bd.done, 0);

    uint32_t threads = params->threads ? params->threads : 1;
    pthread_t *tids = calloc(threads, sizeof(pthread_t));
    pc_worker *wks = calloc(threads, sizeof(pc_worker));
    uint8_t *created = calloc(threads, 1);
    if (!tids || !wks || !created) {
        free(tids);
        free(wks);
        free(created);
        if (use_bloom) pc_bloom_free(&bloom);
        ca_precomp_table_free(t);
        return CA_ERR_NOMEM;
    }
    for (uint32_t i = 0; i < threads; i++) {
        wks[i].bd = &bd;
        wks[i].id = i;
    }
    uint32_t started = 0;
    for (uint32_t i = 0; i < threads; i++) {
        if (threads == 1) {
            pc_build_worker(&wks[i]);
        } else if (pthread_create(&tids[i], NULL, pc_build_worker, &wks[i]) == 0) {
            created[i] = 1;
            started++;
        }
    }
    if (threads > 1 && started == 0) pc_build_worker(&wks[0]);
    for (uint32_t i = 0; i < threads; i++)
        if (created[i]) pthread_join(tids[i], NULL);

    ca_status rc = CA_OK;
    for (uint32_t i = 0; i < threads; i++)
        if (wks[i].err) rc = CA_ERR_NOMEM;
    if (rc == CA_OK) rc = pc_collect(t, wks, threads);

    t->precomp_ops = (uint64_t)setup + atomic_load(&bd.total_ops);

    for (uint32_t i = 0; i < threads; i++) free(wks[i].buf);
    free(tids);
    free(wks);
    free(created);
    if (use_bloom) pc_bloom_free(&bloom);

    if (rc != CA_OK) {
        ca_precomp_table_free(t);
        return rc;
    }

    if (st) {
        st->group_ops += t->precomp_ops;
        st->iterations += t->chains + t->merges;
        st->collisions += t->merges;
        st->table_entries = ca_max_u64(st->table_entries, t->nent);
        st->bytes_peak = ca_max_u64(st->bytes_peak, t->nent * sizeof(pc_entry) +
                                                        (uint64_t)t->r * sizeof(ca_elem) +
                                                        (uint64_t)t->bitlen * sizeof(ca_elem));
        st->threads = threads;
        st->seconds += ca_now() - t0;
    }
    *out = t;
    return CA_OK;
}

void ca_precomp_table_free(ca_precomp_table *t)
{
    if (!t) return;
    free(t->ent);
    free(t->S);
    free(t->s);
    free(t->Gpow);
    free(t);
}

ca_status ca_precomp_table_solve(const ca_precomp_table *t, const ca_elem *target, uint64_t *x,
                                 ca_stats *st)
{
    const ca_group *g = t->g;
    double t0 = ca_now();
    uint64_t n = t->n;
    ca_elem nt;
    ca_group_mul(g, &nt, target, n, NULL);
    if (!ca_group_is_identity(g, &nt)) {
        ca_set_error("precomp: the target is not in the subgroup of order %llu",
                     (unsigned long long)n);
        return CA_ERR_NOT_FOUND;
    }

    if (ca_group_is_identity(g, target)) {
        *x = 0;
        return CA_OK;
    }

    ca_rng rng;
    ca_rng_seed(&rng, t->seed ^ ca_group_hash(g, target) ^ 0x9E3779B97F4A7C15ULL);

    const uint64_t max_attempts = 512;
    uint64_t ops = 0, attempts = 0;
    ca_status rc = CA_ERR_NOT_FOUND;

    while (attempts < max_attempts) {
        if (t->max_online_ops && ops > t->max_online_ops) {
            rc = CA_ERR_LIMIT;
            break;
        }
        attempts++;
        uint64_t a = ca_rng_below(&rng, n);
        ca_elem Y;
        pc_base_mul(t, &Y, a, &ops);
        ca_group_op(g, &Y, &Y, target);
        ops++;
        uint64_t steps = 0;
        for (;;) {
            uint64_t h = ca_group_hash(g, &Y);
            if ((h & t->dp_mask) == 0) {
                uint64_t e;
                if (pc_lookup(t, h, &e)) {
                    uint64_t cand = ca_submod(e % n, a % n, n); /* x = e - a' (mod n) */
                    if (ca_verify_log(g, &t->base, target, cand)) {
                        *x = cand;
                        rc = CA_OK;
                    }
                }
                break;
            }
            if (steps >= t->chain_limit) break;
            uint32_t idx = (uint32_t)(ca_mix64(h) % t->r);
            ca_group_op(g, &Y, &Y, &t->S[idx]);
            a = ca_addmod(a, t->s[idx], n);
            ops++;
            steps++;
        }
        if (rc == CA_OK) break;
    }

    if (st) {
        st->group_ops += ops;
        st->iterations += attempts;
        st->table_entries = ca_max_u64(st->table_entries, t->nent);
        st->bytes_peak = ca_max_u64(st->bytes_peak, t->nent * sizeof(pc_entry));
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
