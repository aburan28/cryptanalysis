/*
 * dist.c - the distributed (van Oorschot-Wiener) rho protocol.
 *
 * Walk definition.  Identical in shape to rho.c's r-adding walk, and
 * deliberately without its negation map: multipliers M_i = alpha_i*G +
 * beta_i*H for i < r, state (Y, a, b) with Y = a*G + b*H, one step is
 * i = (hash(Y) >> 32) mod r; Y <- Y + M_i; (a, b) <- (a + alpha_i, b +
 * beta_i).  A point is distinguished when the low dp_bits of hash(Y) are
 * zero.
 *
 * Everything in the walk is a pure function of the campaign and the unit
 * id: the multipliers come from the campaign seed, the starting points
 * from (campaign seed, unit id, walk index), and a walk that is abandoned
 * restarts from the next deterministic start rather than from the RNG.
 * That is what makes a unit replayable, which is what makes a scheduler's
 * at-least-once delivery safe.
 *
 * The merger is the other half: it verifies each point, stores it by its
 * canonical coordinates, and solves (b1 - b2) x == a2 - a1 (mod n) on the
 * first collision with different exponents.  It verifies the candidate
 * against the target before reporting it, so a hash collision, a buggy
 * agent or a hostile one costs a rejected point and never a wrong answer.
 */
#include "cryptanalysis/ca_dist.h"
#include "dlog_internal.h"

#include <stdio.h>

/* The corpus a campaign aims for when dp_bits is resolved rather than
 * given: about a million points for a full search.  Large enough that the
 * per-point overheads (a network round trip, a database row) are amortised
 * over 2^dp_bits walk steps, small enough that the server holds the corpus
 * in tens of megabytes. */
#define CA_DIST_TARGET_POINTS 1048576.0

/* A walk that has gone this many multiples of the mean inter-point distance
 * without a point is assumed to be in a cycle and is restarted.  Same rule
 * and same constant as rho.c. */
#define CA_DIST_ABANDON 24

#define CA_DIST_MAX_WALKS 4096

typedef struct dist_walk {
    ca_elem Y;
    uint64_t a, b;
    uint64_t since_point;
    uint64_t restart;   /* which deterministic start this walk is on */
} dist_walk;

static int dist_ilog2(uint64_t v)
{
    int l = -1;
    while (v) { v >>= 1; l++; }
    return l;
}

void ca_dist_campaign_default(ca_dist_campaign *c)
{
    memset(c, 0, sizeof(*c));
    c->dp_bits = -1;
}

/* sqrt(n), rounded up; n is at most 2^64-1 so this stays in 64 bits. */
static uint64_t dist_sqrt(uint64_t n)
{
    if (n == 0) return 0;
    uint64_t x = (uint64_t)1 << ((dist_ilog2(n) / 2) + 1);
    for (int i = 0; i < 64 && x; i++) {
        uint64_t y = (x + n / x) / 2;
        if (y >= x) break;
        x = y;
    }
    return x;
}

ca_status ca_dist_resolve(const ca_group *g, ca_dist_campaign *c)
{
    if (g->order == 0) {
        ca_set_error("distributed rho needs a known group order");
        return CA_ERR_INVALID;
    }
    if (c->seed == 0) {
        /* A campaign seed of zero would make every campaign on every host
         * the same walk.  Resolving it here rather than at walk time means
         * the control plane sees the value it has to ship to the fleet. */
        c->seed = ca_seed_or_random(0);
    }
    if (c->r == 0) c->r = 32;
    if (c->r < 4) c->r = 4;
    if (c->r > 1024) c->r = 1024;
    if (c->dp_bits < 0) {
        double expected = 1.25 * (double)dist_sqrt(g->order);
        double per_point = expected / CA_DIST_TARGET_POINTS;
        int dp = per_point >= 2.0 ? dist_ilog2((uint64_t)per_point) : 0;
        if (dp > 48) dp = 48;
        c->dp_bits = dp;
    }
    if (c->dp_bits > 58) c->dp_bits = 58;
    return CA_OK;
}

uint64_t ca_dist_campaign_id(const ca_group *g, const ca_elem *base, const ca_elem *target,
                             const ca_dist_campaign *c)
{
    uint64_t h = 0x243F6A8885A308D3ULL;
    const uint64_t mix[] = {
        (uint64_t)g->kind, g->p, g->a, g->b, g->order, g->cofactor,
        ca_group_hash(g, base), ca_group_hash(g, target),
        c->seed, (uint64_t)c->r, (uint64_t)(int64_t)c->dp_bits,
    };
    for (size_t i = 0; i < sizeof(mix) / sizeof(mix[0]); i++)
        h = ca_mix64(h ^ (mix[i] + 0x9E3779B97F4A7C15ULL + (h << 6) + (h >> 2)));
    return h ? h : 1;
}

double ca_dist_expected_points(const ca_group *g, const ca_dist_campaign *c)
{
    if (g->order == 0) return 0.0;
    int dp = c->dp_bits < 0 ? 0 : c->dp_bits;
    return 1.25 * (double)dist_sqrt(g->order) / (double)((uint64_t)1 << dp);
}

void ca_dist_point_encode(unsigned char out[CA_DIST_POINT_BYTES], const ca_dist_point *p)
{
    const uint64_t words[4] = {p->w0, p->w1, p->a, p->b};
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 8; j++)
            out[i * 8 + j] = (unsigned char)(words[i] >> (8 * j));
}

void ca_dist_point_decode(ca_dist_point *p, const unsigned char in[CA_DIST_POINT_BYTES])
{
    uint64_t words[4] = {0, 0, 0, 0};
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 8; j++)
            words[i] |= (uint64_t)in[i * 8 + j] << (8 * j);
    p->w0 = words[0];
    p->w1 = words[1];
    p->a = words[2];
    p->b = words[3];
}

/* ---- the walk ---------------------------------------------------------- */

typedef struct dist_ctx {
    const ca_group *g;
    ca_elem base, target;
    uint64_t n;
    uint32_t r;
    ca_elem *M;
    uint64_t *alpha, *beta;
    uint64_t dp_mask;
} dist_ctx;

static void dist_free_ctx(dist_ctx *d)
{
    free(d->M);
    free(d->alpha);
    free(d->beta);
    d->M = NULL;
    d->alpha = NULL;
    d->beta = NULL;
}

/* Multipliers from the campaign seed alone: this is the fleet's walk
 * function, and nothing about the unit, the agent or the machine may enter
 * it.  A change here changes every campaign's point corpus. */
static ca_status dist_multipliers(dist_ctx *d, const ca_dist_campaign *c, uint64_t *ops)
{
    d->M = calloc(d->r, sizeof(ca_elem));
    d->alpha = calloc(d->r, sizeof(uint64_t));
    d->beta = calloc(d->r, sizeof(uint64_t));
    if (!d->M || !d->alpha || !d->beta) {
        dist_free_ctx(d);
        return CA_ERR_NOMEM;
    }
    ca_rng rng;
    ca_rng_seed(&rng, c->seed);
    for (uint32_t i = 0; i < d->r; i++) {
        d->alpha[i] = ca_rng_below(&rng, d->n);
        d->beta[i] = ca_rng_below(&rng, d->n);
        ca_elem t1, t2;
        ca_group_mul(d->g, &t1, &d->base, d->alpha[i], ops);
        ca_group_mul(d->g, &t2, &d->target, d->beta[i], ops);
        ca_group_op(d->g, &d->M[i], &t1, &t2);
        (*ops)++;
    }
    return CA_OK;
}

/* The k-th deterministic start of walk `w` in unit `id`.
 *
 * Every input is a campaign-level constant or a unit-level one, so two
 * agents handed the same unit walk the same trails.  `restart` is in the
 * mix because an abandoned walk has to go somewhere reproducible: taking a
 * fresh value from a PRNG would make the second run of a unit differ from
 * the first, and the scheduler's whole retry story rests on it not doing
 * that. */
static void dist_start(dist_ctx *d, dist_walk *w, uint64_t seed, uint64_t id, uint32_t index,
                       uint64_t restart, uint64_t *ops)
{
    uint64_t s = seed;
    s = ca_mix64(s ^ (id + 0x9E3779B97F4A7C15ULL));
    s = ca_mix64(s ^ ((uint64_t)index + 0xBF58476D1CE4E5B9ULL));
    s = ca_mix64(s ^ (restart + 0x94D049BB133111EBULL));
    ca_rng rng;
    ca_rng_seed(&rng, s);
    w->a = ca_rng_below(&rng, d->n);
    w->b = ca_rng_below(&rng, d->n);
    ca_elem t1, t2;
    ca_group_mul(d->g, &t1, &d->base, w->a, ops);
    ca_group_mul(d->g, &t2, &d->target, w->b, ops);
    ca_group_op(d->g, &w->Y, &t1, &t2);
    (*ops)++;
    w->since_point = 0;
    w->restart = restart;
}

static void dist_point_of(const ca_group *g, ca_dist_point *pt, const ca_elem *Y, uint64_t a,
                          uint64_t b)
{
    uint64_t words[4];
    ca_group_decode(g, words, Y);
    pt->w0 = words[0];
    pt->w1 = words[1];
    pt->a = a;
    pt->b = b;
}

ca_status ca_dist_walk(const ca_group *g, const ca_elem *base, const ca_elem *target,
                       const ca_dist_campaign *c, const ca_dist_unit *u, ca_dist_sink sink,
                       void *ctx, ca_stats *st)
{
    if (!g || !base || !target || !c || !u || !sink) return CA_ERR_INVALID;
    ca_dist_campaign cc = *c;
    ca_status rc = ca_dist_resolve(g, &cc);
    if (rc != CA_OK) return rc;
    if (cc.seed != c->seed && c->seed != 0) return CA_ERR_INVALID;

    dist_ctx d;
    memset(&d, 0, sizeof(d));
    d.g = g;
    d.base = *base;
    d.target = *target;
    d.n = g->order;
    d.r = cc.r;
    d.dp_mask = cc.dp_bits ? (((uint64_t)1 << cc.dp_bits) - 1) : 0;

    uint64_t ops = 0;
    double start_time = ca_now();
    rc = dist_multipliers(&d, &cc, &ops);
    if (rc != CA_OK) return rc;

    uint32_t W = u->walks;
    if (W == 0) {
        /* One walk is a scalar multiplication to start and then one group
         * operation per step; many walks amortise the field inversion over
         * the batch.  256 is what rho.c uses on curves for the same reason,
         * and a unit whose budget is too small to pay for that many starts
         * uses fewer. */
        W = (g->kind == CA_GROUP_EC) ? 256 : 16;
        if (u->max_steps) {
            int lg = dist_ilog2(d.n) + 1;
            uint64_t cap = u->max_steps / (24u * (uint64_t)lg);
            if (cap < 1) cap = 1;
            if ((uint64_t)W > cap) W = (uint32_t)cap;
        }
    }
    if (W > CA_DIST_MAX_WALKS) W = CA_DIST_MAX_WALKS;

    dist_walk *walks = calloc(W, sizeof(dist_walk));
    ca_elem *Yn = calloc(W, sizeof(ca_elem));
    ca_elem *B = calloc(W, sizeof(ca_elem));
    uint64_t *scratch = calloc(2 * (size_t)W, sizeof(uint64_t));
    uint32_t *idxs = calloc(W, sizeof(uint32_t));
    if (!walks || !Yn || !B || !scratch || !idxs) {
        free(walks); free(Yn); free(B); free(scratch); free(idxs);
        dist_free_ctx(&d);
        return CA_ERR_NOMEM;
    }
    for (uint32_t w = 0; w < W; w++) dist_start(&d, &walks[w], cc.seed, u->id, w, 0, &ops);

    const uint64_t abandon = (uint64_t)CA_DIST_ABANDON << cc.dp_bits;
    uint64_t steps = 0, points = 0;
    ca_status out = CA_OK;
    int stop = 0;

    while (!stop) {
        for (uint32_t w = 0; w < W; w++) {
            /* The multiplier index is kept rather than recomputed after the
             * step: the exponent update must use the multiplier that was
             * actually added, and after the batched op the old Y is gone. */
            idxs[w] = (uint32_t)((ca_group_hash(g, &walks[w].Y) >> 32) % d.r);
            B[w] = d.M[idxs[w]];
            walks[w].since_point++;
            Yn[w] = walks[w].Y;
        }
        ca_group_batch_op(g, Yn, Yn, B, W, scratch);
        steps += W;
        ops += W;

        for (uint32_t w = 0; w < W; w++) {
            dist_walk *wk = &walks[w];
            uint32_t i = idxs[w];
            wk->Y = Yn[w];
            wk->a = ca_addmod(wk->a, d.alpha[i], d.n);
            wk->b = ca_addmod(wk->b, d.beta[i], d.n);

            if (ca_group_is_identity(g, &wk->Y)) {
                /* Y = 0 is a relation that would solve the instance, and it
                 * is also the one point whose coordinates carry nothing: the
                 * wire record has no way to say "infinity" and the walk
                 * cannot continue from it, since every further step adds a
                 * fixed multiplier to a fixed point.  It happens with
                 * probability about 1/n per step -- never, at these sizes --
                 * so the relation is dropped and the walk restarts rather
                 * than the format growing a case for it. */
                dist_start(&d, wk, cc.seed, u->id, w, wk->restart + 1, &ops);
                continue;
            }

            uint64_t h = ca_group_hash(g, &wk->Y);
            if ((h & d.dp_mask) == 0) {
                ca_dist_point pt;
                dist_point_of(g, &pt, &wk->Y, wk->a, wk->b);
                points++;
                wk->since_point = 0;
                ca_status src = sink(ctx, &pt);
                if (src != CA_OK) { out = src; stop = 1; break; }
                if (u->max_points && points >= u->max_points) { stop = 1; break; }
            } else if (wk->since_point > abandon) {
                /* Almost certainly a cycle: a walk that has gone 24 mean
                 * inter-point distances without a point is not going to
                 * produce one.  Restarting deterministically keeps the unit
                 * replayable. */
                dist_start(&d, wk, cc.seed, u->id, w, wk->restart + 1, &ops);
            }
        }
        if (stop) break;
        if (u->max_steps && steps >= u->max_steps) break;
    }

    if (st) {
        st->group_ops += ops;
        st->iterations += points;
        st->seconds += ca_now() - start_time;
        st->bytes_peak = ca_max_u64(st->bytes_peak,
                                    (uint64_t)W * (uint64_t)(sizeof(dist_walk) + 2 * sizeof(ca_elem))
                                        + (uint64_t)d.r * sizeof(ca_elem));
    }
    free(walks); free(Yn); free(B); free(scratch); free(idxs);
    dist_free_ctx(&d);
    return out;
}

/* ---- the merger -------------------------------------------------------- */

typedef struct dist_entry {
    uint64_t w0, w1;
    uint64_t a, b;
    int used;
} dist_entry;

struct ca_dist_merger {
    const ca_group *g;
    ca_elem base, target;
    ca_dist_campaign c;
    uint64_t n;
    uint64_t dp_mask;
    int verify;

    dist_entry *e;
    size_t cap;      /* power of two */
    size_t count;
    size_t limit;    /* resize threshold */

    int solved;
    uint64_t result;
    size_t added, duplicates, rejected, collisions;
};

static uint64_t dist_key(uint64_t w0, uint64_t w1)
{
    return ca_mix64(w0 ^ ca_mix64(w1 + 0x9E3779B97F4A7C15ULL));
}

static ca_status dist_table_init(ca_dist_merger *m, size_t expect)
{
    size_t cap = 1024;
    while (cap < expect * 2 && cap < ((size_t)1 << 40)) cap <<= 1;
    m->e = calloc(cap, sizeof(dist_entry));
    if (!m->e) return CA_ERR_NOMEM;
    m->cap = cap;
    m->count = 0;
    m->limit = cap - cap / 4;   /* 75% load */
    return CA_OK;
}

static ca_status dist_table_grow(ca_dist_merger *m)
{
    size_t cap = m->cap * 2;
    dist_entry *e = calloc(cap, sizeof(dist_entry));
    if (!e) return CA_ERR_NOMEM;
    for (size_t i = 0; i < m->cap; i++) {
        if (!m->e[i].used) continue;
        size_t j = (size_t)dist_key(m->e[i].w0, m->e[i].w1) & (cap - 1);
        while (e[j].used) j = (j + 1) & (cap - 1);
        e[j] = m->e[i];
    }
    free(m->e);
    m->e = e;
    m->cap = cap;
    m->limit = cap - cap / 4;
    return CA_OK;
}

ca_status ca_dist_merger_new(ca_dist_merger **out, const ca_group *g, const ca_elem *base,
                             const ca_elem *target, const ca_dist_campaign *c, size_t expect)
{
    if (!out || !g || !base || !target || !c) return CA_ERR_INVALID;
    ca_dist_campaign cc = *c;
    ca_status rc = ca_dist_resolve(g, &cc);
    if (rc != CA_OK) return rc;
    ca_dist_merger *m = calloc(1, sizeof(*m));
    if (!m) return CA_ERR_NOMEM;
    m->g = g;
    m->base = *base;
    m->target = *target;
    m->c = cc;
    m->n = g->order;
    m->dp_mask = cc.dp_bits ? (((uint64_t)1 << cc.dp_bits) - 1) : 0;
    m->verify = 1;
    if (expect == 0) {
        double e = ca_dist_expected_points(g, &cc);
        expect = e > 1e8 ? (size_t)1e8 : (size_t)e;
    }
    rc = dist_table_init(m, expect);
    if (rc != CA_OK) {
        free(m);
        return rc;
    }
    *out = m;
    return CA_OK;
}

void ca_dist_merger_set_verify(ca_dist_merger *m, int on)
{
    if (m) m->verify = on ? 1 : 0;
}

/* (b1 - b2) x == a2 - a1 (mod n), with the same gcd handling as rho.c and
 * the same final verification: a candidate that does not satisfy
 * x*base == target is discarded, so nothing a bad agent submits can be
 * reported as a solution. */
static int dist_try_solve(ca_dist_merger *m, uint64_t a1, uint64_t b1, uint64_t a2, uint64_t b2)
{
    uint64_t n = m->n;
    uint64_t c = ca_submod(b1, b2, n);
    uint64_t dd = ca_submod(a2, a1, n);
    if (c == 0) return 0;
    uint64_t gg = ca_gcd(c, n);
    if (dd % gg) return 0;
    uint64_t nn = n / gg;
    uint64_t x0 = ca_mulmod((dd / gg) % nn, ca_invmod((c / gg) % nn, nn), nn);
    uint64_t tries = gg > 65536 ? 65536 : gg;
    for (uint64_t k = 0; k < tries; k++) {
        uint64_t x = x0 + k * nn;
        if (x >= n) break;
        if (ca_verify_log(m->g, &m->base, &m->target, x)) {
            m->result = x;
            m->solved = 1;
            return 1;
        }
    }
    return 0;
}

/* A point is admissible if it is a real group element, really distinguished
 * under this campaign's cutoff, and really equal to a*G + b*H.
 *
 * The last check is the expensive one (two scalar multiplications, about
 * 3*log2(n) group operations) and it is the one that matters: without it an
 * agent that reports fabricated exponents poisons the corpus, and the
 * poison is not visible until the server reports a discrete log that does
 * not verify -- or, worse, silently never collides. */
static int dist_admissible(ca_dist_merger *m, const ca_dist_point *pt)
{
    const ca_group *g = m->g;
    if (pt->a >= m->n || pt->b >= m->n) return 0;
    uint64_t words[4] = {pt->w0, pt->w1, 0, 0};
    ca_elem Y;
    if (!ca_group_encode(g, &Y, words)) return 0;   /* encode: 1 = ok, 0 = not a point */
    if (!ca_group_is_valid(g, &Y)) return 0;
    if ((ca_group_hash(g, &Y) & m->dp_mask) != 0) return 0;
    ca_elem t1, t2, sum;
    ca_group_mul(g, &t1, &m->base, pt->a, NULL);
    ca_group_mul(g, &t2, &m->target, pt->b, NULL);
    ca_group_op(g, &sum, &t1, &t2);
    return ca_group_equal(g, &sum, &Y);
}

ca_status ca_dist_merger_add(ca_dist_merger *m, const ca_dist_point *pts, size_t n,
                             size_t *accepted, size_t *duplicates, size_t *rejected)
{
    if (!m || (!pts && n)) return CA_ERR_INVALID;
    size_t acc = 0, dup = 0, rej = 0;
    for (size_t i = 0; i < n; i++) {
        const ca_dist_point *pt = &pts[i];
        if (m->verify && !dist_admissible(m, pt)) {
            rej++;
            continue;
        }
        if (m->count >= m->limit) {
            ca_status rc = dist_table_grow(m);
            if (rc != CA_OK) {
                if (accepted) *accepted = acc;
                if (duplicates) *duplicates = dup;
                if (rejected) *rejected = rej;
                m->added += acc;
                m->duplicates += dup;
                m->rejected += rej;
                return rc;
            }
        }
        size_t j = (size_t)dist_key(pt->w0, pt->w1) & (m->cap - 1);
        while (m->e[j].used && !(m->e[j].w0 == pt->w0 && m->e[j].w1 == pt->w1))
            j = (j + 1) & (m->cap - 1);
        if (!m->e[j].used) {
            m->e[j].used = 1;
            m->e[j].w0 = pt->w0;
            m->e[j].w1 = pt->w1;
            m->e[j].a = pt->a;
            m->e[j].b = pt->b;
            m->count++;
            acc++;
            continue;
        }
        if (m->e[j].a == pt->a && m->e[j].b == pt->b) {
            /* The same trail reported twice: a replayed unit, a retried
             * upload, or one walk arriving at its own earlier point. */
            dup++;
            continue;
        }
        acc++;
        m->collisions++;
        if (!m->solved) dist_try_solve(m, m->e[j].a, m->e[j].b, pt->a, pt->b);
    }
    if (accepted) *accepted = acc;
    if (duplicates) *duplicates = dup;
    if (rejected) *rejected = rej;
    m->added += acc;
    m->duplicates += dup;
    m->rejected += rej;
    return CA_OK;
}

int ca_dist_merger_solved(const ca_dist_merger *m, uint64_t *x)
{
    if (!m || !m->solved) return 0;
    if (x) *x = m->result;
    return 1;
}

size_t ca_dist_merger_size(const ca_dist_merger *m)
{
    return m ? m->count : 0;
}

void ca_dist_merger_stats(const ca_dist_merger *m, ca_stats *st)
{
    if (!m || !st) return;
    st->iterations += m->added;
    st->collisions += m->collisions;
    st->bytes_peak = ca_max_u64(st->bytes_peak, (uint64_t)m->cap * sizeof(dist_entry));
}

void ca_dist_merger_free(ca_dist_merger *m)
{
    if (!m) return;
    free(m->e);
    free(m);
}
