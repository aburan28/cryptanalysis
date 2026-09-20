/*
 * coord.c - the job, the derived context, the walk, the CRDT and the
 * wire format for distributed rho.  The sockets are in coord_net.c.
 *
 * The division of labour here is the one the header describes: this
 * file holds everything that is pure C11 and testable without a
 * network, and it is the file that decides what is true.  A hub and an
 * agent differ only in who dialled; both merge with ca_coord_apply and
 * both refuse the same records.
 */
#include "cryptanalysis/ca_coord.h"
#include "coord_internal.h"
#include "dlog_internal.h"

#include <inttypes.h>
#include <stdio.h>

/* ---- derivation -------------------------------------------------------- */

/*
 * The PRF behind every derived quantity.  splitmix64 over (id, tag,
 * index, lane) -- not a cryptographic PRF and not asked to be one: its
 * job is to make the branch table and the start points look random and,
 * far more importantly, to make them *identical* on every machine that
 * agrees on the job id.  An adversary who biases their own start points
 * only wastes their own time, because the coefficients travel with the
 * point and are checked.
 */
static uint64_t coord_prf(uint64_t id, uint64_t tag, uint64_t index, uint64_t lane)
{
    uint64_t x = id ^ ca_mix64(tag + 0x9E3779B97F4A7C15ULL * (index + 1));
    x = ca_mix64(x ^ (lane * 0xD1B54A32D192ED03ULL));
    return ca_splitmix64(&x);
}

/* A scalar in [0, n) derived from (tag, index, lane). */
static uint64_t coord_scalar(uint64_t id, uint64_t tag, uint64_t index, uint64_t lane, uint64_t n)
{
    uint64_t v = coord_prf(id, tag, index, lane);
    return n ? v % n : v;
}

#define COORD_TAG_BRANCH 1u
#define COORD_TAG_WALKER 2u

/* ---- the job ----------------------------------------------------------- */

static int32_t coord_default_dp_bits(uint64_t n)
{
    int bits = 0;
    while ((n >> bits) > 1) bits++;
    int32_t dp = (int32_t)(bits / 4);
    if (dp < 1) dp = 1;
    if (dp > 40) dp = 40;
    return dp;
}

/* The canonical encoding, and therefore the id's preimage.  Every field
 * that changes the walk appears exactly once, in this order, in a fixed
 * spelling: two agents agree on the id exactly when they agree on all of
 * it. */
static size_t coord_job_body(const ca_coord_job *job, char *buf, size_t cap)
{
    int n = snprintf(
        buf, cap,
        "ca-rho-job v1 kind=%d p=%" PRIu64 " a=%" PRIu64 " b=%" PRIu64 " n=%" PRIu64 " g=%" PRIu64
        ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 " h=%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64
        " dp=%" PRId32 " r=%" PRIu32 " neg=%" PRId32 " unit=%" PRIu64 " seed=%" PRIu64,
        (int)job->kind, job->p, job->a, job->b, job->order, job->base[0], job->base[1],
        job->base[2], job->base[3], job->target[0], job->target[1], job->target[2], job->target[3],
        job->dp_bits, job->r, job->negation_map, job->unit_size, job->seed);
    if (n < 0 || (size_t)n >= cap) return 0;
    return (size_t)n;
}

static uint64_t coord_job_hash(const char *body, size_t len)
{
    /* FNV-1a, then a strong 64-bit mix.  An agreement check, per the
     * header: not a commitment, and nothing rests on preimage
     * resistance. */
    uint64_t h = 1469598103934665603ULL;
    for (size_t i = 0; i < len; i++) {
        h ^= (unsigned char)body[i];
        h *= 1099511628211ULL;
    }
    return ca_mix64(h);
}

ca_status ca_coord_job_init(ca_coord_job *job, const ca_group *g, const ca_elem *base,
                            const ca_elem *target, int32_t dp_bits, uint32_t r, int negation_map,
                            uint64_t unit_size, uint64_t seed)
{
    if (!job || !g || !base || !target) {
        ca_set_error("null argument");
        return CA_ERR_INVALID;
    }
    if (g->order < 2) {
        ca_set_error("group order unknown or trivial");
        return CA_ERR_INVALID;
    }
    if (!ca_group_is_valid(g, base) || !ca_group_is_valid(g, target)) {
        ca_set_error("base or target is not a group element");
        return CA_ERR_INVALID;
    }
    if (negation_map && !ca_group_has_negation_map(g)) {
        ca_set_error("this group has no cheap negation");
        return CA_ERR_UNSUPPORTED;
    }
    memset(job, 0, sizeof(*job));
    job->kind = g->kind;
    job->p = g->p;
    job->a = g->a;
    job->b = g->b;
    job->order = g->order;
    ca_group_decode(g, job->base, base);
    ca_group_decode(g, job->target, target);
    job->dp_bits = dp_bits >= 0 ? dp_bits : coord_default_dp_bits(g->order);
    if (job->dp_bits > 58) job->dp_bits = 58;
    job->r = r ? r : 32;
    job->negation_map = negation_map ? 1 : 0;
    job->unit_size = unit_size ? unit_size : 256;
    job->seed = seed;
    if (job->r < 4 || job->r > 4096) {
        ca_set_error("r must be in [4, 4096]");
        return CA_ERR_INVALID;
    }

    char body[CA_COORD_LINE_MAX];
    size_t len = coord_job_body(job, body, sizeof(body));
    if (!len) {
        ca_set_error("job does not fit one line");
        return CA_ERR_INVALID;
    }
    job->id = coord_job_hash(body, len);
    return CA_OK;
}

size_t ca_coord_job_encode(const ca_coord_job *job, char *buf, size_t cap)
{
    if (!job || !buf) return 0;
    char body[CA_COORD_LINE_MAX];
    size_t len = coord_job_body(job, body, sizeof(body));
    if (!len) return 0;
    int n = snprintf(buf, cap, "%s id=%016" PRIx64, body, coord_job_hash(body, len));
    if (n < 0 || (size_t)n >= cap) return 0;
    return (size_t)n;
}

/* Scan "key=" and return the pointer just past it, or NULL.  Keys are
 * matched at a token boundary so that "h=" never matches inside "kh=". */
static const char *coord_field(const char *line, const char *key)
{
    size_t klen = strlen(key);
    for (const char *p = line; (p = strstr(p, key)) != NULL; p += klen) {
        if (p != line && p[-1] != ' ') continue;
        if (p[klen] != '=') continue;
        return p + klen + 1;
    }
    return NULL;
}

static int coord_u64(const char *line, const char *key, uint64_t *out)
{
    const char *p = coord_field(line, key);
    if (!p) return 0;
    char *end = NULL;
    unsigned long long v = strtoull(p, &end, 10);
    if (end == p) return 0;
    *out = (uint64_t)v;
    return 1;
}

static int coord_i32(const char *line, const char *key, int32_t *out)
{
    const char *p = coord_field(line, key);
    if (!p) return 0;
    char *end = NULL;
    long v = strtol(p, &end, 10);
    if (end == p || v < INT32_MIN || v > INT32_MAX) return 0;
    *out = (int32_t)v;
    return 1;
}

static int coord_words(const char *line, const char *key, uint64_t out[4])
{
    const char *p = coord_field(line, key);
    if (!p) return 0;
    for (int i = 0; i < 4; i++) {
        char *end = NULL;
        unsigned long long v = strtoull(p, &end, 10);
        if (end == p) return 0;
        out[i] = (uint64_t)v;
        p = end;
        if (i < 3) {
            if (*p != ',') return 0;
            p++;
        }
    }
    return 1;
}

ca_status ca_coord_job_decode(ca_coord_job *job, const char *line)
{
    if (!job || !line) return CA_ERR_INVALID;
    if (strncmp(line, "ca-rho-job v1 ", 14) != 0) {
        ca_set_error("not a v1 job document");
        return CA_ERR_INVALID;
    }
    memset(job, 0, sizeof(*job));
    int32_t kind = 0;
    uint64_t r = 0, id = 0;
    const char *idp = coord_field(line, "id");
    if (!coord_i32(line, "kind", &kind) || !coord_u64(line, "p", &job->p) ||
        !coord_u64(line, "a", &job->a) || !coord_u64(line, "b", &job->b) ||
        !coord_u64(line, "n", &job->order) || !coord_words(line, "g", job->base) ||
        !coord_words(line, "h", job->target) || !coord_i32(line, "dp", &job->dp_bits) ||
        !coord_u64(line, "r", &r) || !coord_i32(line, "neg", &job->negation_map) ||
        !coord_u64(line, "unit", &job->unit_size) || !coord_u64(line, "seed", &job->seed) || !idp) {
        ca_set_error("job document is missing a field");
        return CA_ERR_INVALID;
    }
    if (kind != CA_GROUP_ZP && kind != CA_GROUP_EC) {
        ca_set_error("unknown group kind %d", kind);
        return CA_ERR_INVALID;
    }
    if (r > UINT32_MAX) {
        ca_set_error("r out of range");
        return CA_ERR_INVALID;
    }
    job->kind = (ca_group_kind)kind;
    job->r = (uint32_t)r;
    {
        char *end = NULL;
        id = strtoull(idp, &end, 16);
        if (end == idp) {
            ca_set_error("bad job id");
            return CA_ERR_INVALID;
        }
    }

    /* Recompute rather than trust: a document that was truncated or
     * edited in transit must not be walked, because two agents walking
     * different branch tables silently stop colliding. */
    char body[CA_COORD_LINE_MAX];
    size_t len = coord_job_body(job, body, sizeof(body));
    if (!len) {
        ca_set_error("job does not fit one line");
        return CA_ERR_INVALID;
    }
    uint64_t want = coord_job_hash(body, len);
    if (want != id) {
        ca_set_error("job id mismatch (document was altered)");
        return CA_ERR_INVALID;
    }
    job->id = id;
    return CA_OK;
}

ca_status ca_coord_job_group(const ca_coord_job *job, ca_group *g)
{
    if (!job || !g) return CA_ERR_INVALID;
    if (job->kind == CA_GROUP_ZP) return ca_group_zp_init(g, job->p, job->order);
    if (job->kind == CA_GROUP_EC) return ca_group_ec_init(g, job->p, job->a, job->b, job->order);
    ca_set_error("unknown group kind");
    return CA_ERR_INVALID;
}

/* ---- the context ------------------------------------------------------- */

ca_status ca_coord_ctx_open(ca_coord_ctx **out, const ca_coord_job *job)
{
    if (!out || !job) return CA_ERR_INVALID;
    *out = NULL;
    ca_coord_ctx *ctx = calloc(1, sizeof(*ctx));
    if (!ctx) return CA_ERR_NOMEM;
    ctx->job = *job;
    ca_status rc = ca_coord_job_group(&ctx->job, &ctx->g);
    if (rc != CA_OK) {
        free(ctx);
        return rc;
    }
    if (ctx->job.negation_map && !ca_group_has_negation_map(&ctx->g)) {
        ca_set_error("job asks for the negation map in a group without one");
        free(ctx);
        return CA_ERR_UNSUPPORTED;
    }
    if (ca_group_encode(&ctx->g, &ctx->base, ctx->job.base) != 1 ||
        ca_group_encode(&ctx->g, &ctx->target, ctx->job.target) != 1 ||
        !ca_group_is_valid(&ctx->g, &ctx->base) || !ca_group_is_valid(&ctx->g, &ctx->target)) {
        ca_set_error("job's base or target is not a group element");
        free(ctx);
        return CA_ERR_INVALID;
    }
    ctx->n = ctx->job.order;
    ctx->r = ctx->job.r;
    ctx->dp_mask = ctx->job.dp_bits >= 64 ? UINT64_MAX : ((uint64_t)1 << ctx->job.dp_bits) - 1;
    ctx->M = calloc(ctx->r, sizeof(ca_elem));
    ctx->alpha = calloc(ctx->r, sizeof(uint64_t));
    ctx->beta = calloc(ctx->r, sizeof(uint64_t));
    if (!ctx->M || !ctx->alpha || !ctx->beta) {
        ca_coord_ctx_close(ctx);
        return CA_ERR_NOMEM;
    }
    /* The branch table: M_i = alpha_i*G + beta_i*H, derived, never sent. */
    for (uint32_t i = 0; i < ctx->r; i++) {
        ctx->alpha[i] = coord_scalar(ctx->job.id, COORD_TAG_BRANCH, i, 0, ctx->n);
        ctx->beta[i] = coord_scalar(ctx->job.id, COORD_TAG_BRANCH, i, 1, ctx->n);
        ca_elem t1, t2;
        ca_group_mul(&ctx->g, &t1, &ctx->base, ctx->alpha[i], NULL);
        ca_group_mul(&ctx->g, &t2, &ctx->target, ctx->beta[i], NULL);
        ca_group_op(&ctx->g, &ctx->M[i], &t1, &t2);
        /* An identity multiplier would make a branch a no-op and stall
         * every walk that lands on it, so nudge it off. */
        if (ca_group_is_identity(&ctx->g, &ctx->M[i])) {
            ctx->alpha[i] = ca_addmod(ctx->alpha[i], 1, ctx->n);
            ca_group_op(&ctx->g, &ctx->M[i], &ctx->M[i], &ctx->base);
        }
    }
    *out = ctx;
    return CA_OK;
}

void ca_coord_ctx_close(ca_coord_ctx *ctx)
{
    if (!ctx) return;
    free(ctx->M);
    free(ctx->alpha);
    free(ctx->beta);
    free(ctx);
}

const ca_coord_job *ca_coord_ctx_job(const ca_coord_ctx *ctx) { return &ctx->job; }
const ca_group *ca_coord_ctx_group(const ca_coord_ctx *ctx) { return &ctx->g; }

void ca_coord_walker_start(const ca_coord_ctx *ctx, uint64_t walker, ca_elem *out, uint64_t *a,
                           uint64_t *b)
{
    uint64_t av = coord_scalar(ctx->job.id, COORD_TAG_WALKER, walker, 0, ctx->n);
    uint64_t bv = coord_scalar(ctx->job.id, COORD_TAG_WALKER, walker, 1, ctx->n);
    ca_elem t1, t2, y;
    ca_group_mul(&ctx->g, &t1, &ctx->base, av, NULL);
    ca_group_mul(&ctx->g, &t2, &ctx->target, bv, NULL);
    ca_group_op(&ctx->g, &y, &t1, &t2);
    if (ctx->job.negation_map && ca_group_canonicalize(&ctx->g, &y)) {
        av = av ? ctx->n - av : 0;
        bv = bv ? ctx->n - bv : 0;
    }
    if (out) *out = y;
    if (a) *a = av;
    if (b) *b = bv;
}

double ca_coord_expected_steps(const ca_coord_ctx *ctx)
{
    double n = (double)ctx->n;
    double e = sqrt(3.14159265358979323846 * n / 2.0);
    if (ctx->job.negation_map) e /= sqrt(2.0);
    return e;
}

double ca_coord_expected_dps(const ca_coord_ctx *ctx)
{
    double trail = (double)((uint64_t)1 << (ctx->job.dp_bits > 62 ? 62 : ctx->job.dp_bits));
    return ca_coord_expected_steps(ctx) / trail;
}

/* ---- the walk ---------------------------------------------------------- */

static uint32_t coord_index(const ca_coord_ctx *ctx, uint64_t h)
{
    return (uint32_t)((h >> 32) % ctx->r);
}

int ca_coord_is_dp(const ca_coord_ctx *ctx, const ca_elem *y)
{
    return (ca_group_hash(&ctx->g, y) & ctx->dp_mask) == 0;
}

/*
 * One step of the agreed walk function.  This has to match, bit for
 * bit, on every machine: the whole scheme rests on two agents' trails
 * merging when they meet, and they only merge if the step they take
 * from a shared point is the same step.  So it follows rho.c's rules
 * exactly -- the 2-cycle look-ahead under the negation map included --
 * and takes no randomness of its own.
 */
static void coord_step(const ca_coord_ctx *ctx, coord_walk *w, uint64_t *ops)
{
    const ca_group *g = &ctx->g;
    uint32_t i = coord_index(ctx, ca_group_hash(g, &w->y));
    for (uint32_t guard = 0; guard <= ctx->r; guard++) {
        ca_elem yn;
        ca_group_op(g, &yn, &w->y, &ctx->M[i]);
        if (ops) (*ops)++;
        int neg = ctx->job.negation_map ? ca_group_canonicalize(g, &yn) : 0;
        if (ctx->job.negation_map && coord_index(ctx, ca_group_hash(g, &yn)) == i) {
            i = (i + 1) % ctx->r;
            continue;
        }
        w->y = yn;
        w->a = ca_addmod(w->a, ctx->alpha[i], ctx->n);
        w->b = ca_addmod(w->b, ctx->beta[i], ctx->n);
        if (neg) {
            w->a = w->a ? ctx->n - w->a : 0;
            w->b = w->b ? ctx->n - w->b : 0;
        }
        return;
    }
    /* Every branch looked like a 2-cycle: take the first one anyway
     * rather than spin.  Deterministic, so trails still merge. */
    ca_group_op(g, &w->y, &w->y, &ctx->M[0]);
    if (ops) (*ops)++;
    if (ctx->job.negation_map) ca_group_canonicalize(g, &w->y);
    w->a = ca_addmod(w->a, ctx->alpha[0], ctx->n);
    w->b = ca_addmod(w->b, ctx->beta[0], ctx->n);
}

/*
 * Walk walker `index` until it reaches a distinguished point or the step
 * cap.  The cap is what keeps a fruitless cycle under the negation map
 * from eating a lane: a capped trail is reported as dead and costs only
 * its steps.  Returns 1 on a DP, 0 on a dead trail.
 */
int ca_coord_walk_one(const ca_coord_ctx *ctx, uint64_t index, uint64_t cap, ca_coord_dp *out,
                      uint64_t *steps_out)
{
    coord_walk w;
    ca_coord_walker_start(ctx, index, &w.y, &w.a, &w.b);
    uint64_t steps = 0;
    /* A start that is already distinguished is reported as it is. */
    while (!ca_coord_is_dp(ctx, &w.y)) {
        if (steps >= cap) {
            if (steps_out) *steps_out = steps;
            return 0;
        }
        coord_step(ctx, &w, NULL);
        steps++;
    }
    if (out) {
        memset(out, 0, sizeof(*out));
        out->walker = index;
        out->steps = steps;
        out->a = w.a;
        out->b = w.b;
        ca_group_decode(&ctx->g, out->point, &w.y);
    }
    if (steps_out) *steps_out = steps;
    return 1;
}

/*
 * Verify a record the way a receiver must: the point is a real element,
 * it really is distinguished, and its coefficients really produce it.
 * Two scalar multiplications to check work worth 2^dp_bits steps.
 */
int ca_coord_dp_verify(const ca_coord_ctx *ctx, const ca_coord_dp *dp, ca_elem *out)
{
    ca_elem y;
    if (ca_group_encode(&ctx->g, &y, dp->point) != 1) return 0;
    if (!ca_group_is_valid(&ctx->g, &y)) return 0;
    if (dp->a >= ctx->n || dp->b >= ctx->n) return 0;
    if (!ca_coord_is_dp(ctx, &y)) return 0;
    ca_elem t1, t2, z;
    ca_group_mul(&ctx->g, &t1, &ctx->base, dp->a, NULL);
    ca_group_mul(&ctx->g, &t2, &ctx->target, dp->b, NULL);
    ca_group_op(&ctx->g, &z, &t1, &t2);
    if (ctx->job.negation_map) {
        ca_group_canonicalize(&ctx->g, &z);
        ca_group_canonicalize(&ctx->g, &y);
    }
    if (!ca_group_equal(&ctx->g, &z, &y)) return 0;
    if (out) *out = y;
    return 1;
}

/*
 * Solve from a collision: two coefficient pairs at the same point give
 * (b1 - b2) x == a2 - a1 (mod n).  Under the negation map the two
 * points may be negatives of each other, which gives the second form.
 * Both are tried and the candidate is verified against the target, so a
 * sterile collision (identical coefficients, e.g. a re-run unit) is
 * simply not a solution.
 */
int ca_coord_solve_collision(const ca_coord_ctx *ctx, uint64_t a1, uint64_t b1, uint64_t a2,
                             uint64_t b2, uint64_t *x)
{
    uint64_t n = ctx->n;
    for (int sign = 0; sign < (ctx->job.negation_map ? 2 : 1); sign++) {
        uint64_t c, d;
        if (sign == 0) {
            c = ca_submod(b1, b2, n);
            d = ca_submod(a2, a1, n);
        } else {
            c = ca_addmod(b1, b2, n);
            d = n - ca_addmod(a1, a2, n);
            if (d == n) d = 0;
        }
        if (c == 0) continue;
        uint64_t gg = ca_gcd(c, n);
        if (d % gg) continue;
        uint64_t nn = n / gg;
        uint64_t x0 = ca_mulmod((d / gg) % nn, ca_invmod((c / gg) % nn, nn), nn);
        uint64_t lim = gg > 65536 ? 65536 : gg;
        for (uint64_t k = 0; k < lim; k++) {
            uint64_t cand = x0 + k * nn;
            if (cand >= n) break;
            if (ca_verify_log(&ctx->g, &ctx->base, &ctx->target, cand)) {
                *x = cand;
                return 1;
            }
        }
    }
    return 0;
}

/* ---- the wire format --------------------------------------------------- */

/*
 * One check-in, one line:
 *
 *   ci <job-id-hex> <peer> <seq> <time> U:u,w,s,d,x,c;… D:w,s,p0,p1,p2,p3,a,b;… S:<x|->
 *
 * Deliberately not JSON.  A flat, fixed, separator-delimited grammar is
 * small enough to read in one sitting and to fuzz exhaustively
 * (fuzz/fuzz_coord.c), and the decoder below never trusts a count or an
 * index from the input: it fills fixed arrays and stops at their bounds.
 * Peer names are restricted to printable ASCII without the separators,
 * checked on both encode and decode, so a name can never inject a field.
 */

static int coord_peer_name_ok(const char *s)
{
    if (!s || !*s) return 0;
    size_t n = strlen(s);
    if (n >= CA_COORD_PEER_MAX) return 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)s[i];
        if (c <= 0x20 || c >= 0x7f) return 0;
        if (c == ';' || c == ',' || c == '|' || c == ':' || c == '=') return 0;
    }
    return 1;
}

size_t ca_coord_checkin_encode(const ca_coord_checkin *ci, char *buf, size_t cap)
{
    if (!ci || !buf || !coord_peer_name_ok(ci->peer)) return 0;
    if (ci->num_units > CA_COORD_UNITS_MAX || ci->num_dps > CA_COORD_DPS_MAX) return 0;
    size_t off = 0;
    int n = snprintf(buf, cap, "ci %" PRIu64 " %s %" PRIu64 " %" PRIu64 " U:", ci->job_id, ci->peer,
                     ci->seq, ci->time);
    if (n < 0 || (size_t)n >= cap) return 0;
    off = (size_t)n;
    for (uint32_t i = 0; i < ci->num_units; i++) {
        const ca_coord_unit *u = &ci->units[i];
        n = snprintf(buf + off, cap - off,
                     "%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%d;", u->unit,
                     u->walkers_done, u->steps, u->dps, u->dead_trails, u->completed ? 1 : 0);
        if (n < 0 || (size_t)n >= cap - off) return 0;
        off += (size_t)n;
    }
    n = snprintf(buf + off, cap - off, " D:");
    if (n < 0 || (size_t)n >= cap - off) return 0;
    off += (size_t)n;
    for (uint32_t i = 0; i < ci->num_dps; i++) {
        const ca_coord_dp *d = &ci->dps[i];
        n = snprintf(buf + off, cap - off,
                     "%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64
                     ",%" PRIu64 ",%" PRIu64 ";",
                     d->walker, d->steps, d->point[0], d->point[1], d->point[2], d->point[3], d->a,
                     d->b);
        if (n < 0 || (size_t)n >= cap - off) return 0;
        off += (size_t)n;
    }
    if (ci->has_solution)
        n = snprintf(buf + off, cap - off, " S:%" PRIu64, ci->solution);
    else
        n = snprintf(buf + off, cap - off, " S:-");
    if (n < 0 || (size_t)n >= cap - off) return 0;
    return off + (size_t)n;
}

/* Read `count` comma-separated u64s; *p is advanced past the group's
 * terminating ';'.  Returns 0 on any malformed input. */
static int coord_read_group(const char **p, uint64_t *out, int count)
{
    const char *s = *p;
    for (int i = 0; i < count; i++) {
        if (*s < '0' || *s > '9') return 0; /* no signs, no spaces, no empties */
        char *end = NULL;
        unsigned long long v = strtoull(s, &end, 10);
        if (end == s) return 0;
        out[i] = (uint64_t)v;
        s = end;
        if (i < count - 1) {
            if (*s != ',') return 0;
            s++;
        }
    }
    if (*s != ';') return 0;
    *p = s + 1;
    return 1;
}

ca_status ca_coord_checkin_decode(ca_coord_checkin *ci, const char *line)
{
    if (!ci || !line) return CA_ERR_INVALID;
    if (strlen(line) >= CA_COORD_LINE_MAX) {
        ca_set_error("check-in line too long");
        return CA_ERR_INVALID;
    }
    memset(ci, 0, sizeof(*ci));
    if (strncmp(line, "ci ", 3) != 0) {
        ca_set_error("not a check-in line");
        return CA_ERR_INVALID;
    }
    const char *p = line + 3;
    char *end = NULL;

    ci->job_id = (uint64_t)strtoull(p, &end, 10);
    if (end == p || *end != ' ') goto bad;
    p = end + 1;

    const char *sp = strchr(p, ' ');
    if (!sp || (size_t)(sp - p) >= CA_COORD_PEER_MAX) goto bad;
    memcpy(ci->peer, p, (size_t)(sp - p));
    ci->peer[sp - p] = 0;
    if (!coord_peer_name_ok(ci->peer)) goto bad;
    p = sp + 1;

    ci->seq = (uint64_t)strtoull(p, &end, 10);
    if (end == p || *end != ' ') goto bad;
    p = end + 1;
    ci->time = (uint64_t)strtoull(p, &end, 10);
    if (end == p || *end != ' ') goto bad;
    p = end + 1;

    if (strncmp(p, "U:", 2) != 0) goto bad;
    p += 2;
    while (*p && *p != ' ') {
        uint64_t f[6];
        if (!coord_read_group(&p, f, 6)) goto bad;
        if (ci->num_units >= CA_COORD_UNITS_MAX) {
            /* A peer that reports more units than one check-in carries
             * is refused rather than truncated: silently dropping a
             * report would make its unit look unclaimed. */
            ca_set_error("too many unit reports in one check-in");
            return CA_ERR_INVALID;
        }
        ca_coord_unit *u = &ci->units[ci->num_units++];
        u->unit = f[0];
        u->walkers_done = f[1];
        u->steps = f[2];
        u->dps = f[3];
        u->dead_trails = f[4];
        u->completed = f[5] ? 1 : 0;
    }
    if (*p != ' ') goto bad;
    p++;

    if (strncmp(p, "D:", 2) != 0) goto bad;
    p += 2;
    while (*p && *p != ' ') {
        uint64_t f[8];
        if (!coord_read_group(&p, f, 8)) goto bad;
        if (ci->num_dps >= CA_COORD_DPS_MAX) {
            ca_set_error("too many points in one check-in");
            return CA_ERR_INVALID;
        }
        ca_coord_dp *d = &ci->dps[ci->num_dps++];
        d->walker = f[0];
        d->steps = f[1];
        d->point[0] = f[2];
        d->point[1] = f[3];
        d->point[2] = f[4];
        d->point[3] = f[5];
        d->a = f[6];
        d->b = f[7];
    }
    if (*p != ' ') goto bad;
    p++;

    if (strncmp(p, "S:", 2) != 0) goto bad;
    p += 2;
    if (*p == '-' && p[1] == 0) {
        ci->has_solution = 0;
    } else {
        ci->solution = (uint64_t)strtoull(p, &end, 10);
        if (end == p || *end != 0) goto bad;
        ci->has_solution = 1;
    }
    return CA_OK;
bad:
    ca_set_error("malformed check-in line");
    return CA_ERR_INVALID;
}

/* ---- the state --------------------------------------------------------- */

ca_status ca_coord_state_init(ca_coord_state **out, const ca_coord_ctx *ctx)
{
    if (!out || !ctx) return CA_ERR_INVALID;
    ca_coord_state *st = calloc(1, sizeof(*st));
    if (!st) return CA_ERR_NOMEM;
    if (pthread_mutex_init(&st->lock, NULL) != 0) {
        free(st);
        return CA_ERR_INTERNAL;
    }
    st->job_id = ctx->job.id;
    st->dp_cap = 1024;
    st->dp = calloc(st->dp_cap, sizeof(*st->dp));
    if (!st->dp) {
        pthread_mutex_destroy(&st->lock);
        free(st);
        return CA_ERR_NOMEM;
    }
    *out = st;
    return CA_OK;
}

void ca_coord_state_free(ca_coord_state *st)
{
    if (!st) return;
    for (size_t i = 0; i < st->log_count; i++) free(st->log[i].line);
    free(st->log);
    free(st->dp);
    free(st->peers);
    free(st->units);
    pthread_mutex_destroy(&st->lock);
    free(st);
}

/* peer table -------------------------------------------------------------- */

static int coord_peer_index(ca_coord_state *st, const char *name, uint32_t *out, int create)
{
    for (size_t i = 0; i < st->peer_count; i++) {
        if (strcmp(st->peers[i].name, name) == 0) {
            *out = (uint32_t)i;
            return 1;
        }
    }
    if (!create) return 0;
    if (st->peer_count == st->peer_cap) {
        size_t cap = st->peer_cap ? st->peer_cap * 2 : 8;
        coord_peer *p = realloc(st->peers, cap * sizeof(*p));
        if (!p) return 0;
        st->peers = p;
        st->peer_cap = cap;
    }
    coord_peer *p = &st->peers[st->peer_count];
    memset(p, 0, sizeof(*p));
    snprintf(p->name, sizeof(p->name), "%s", name);
    *out = (uint32_t)st->peer_count++;
    return 1;
}

/* the DP table: grow-only, keyed by the canonical point's hash ------------ */

static int coord_dp_grow(ca_coord_state *st)
{
    size_t cap = st->dp_cap * 2;
    coord_dp_entry *e = calloc(cap, sizeof(*e));
    if (!e) return 0;
    for (size_t i = 0; i < st->dp_cap; i++) {
        if (!st->dp[i].used) continue;
        size_t j = st->dp[i].key & (cap - 1);
        while (e[j].used) j = (j + 1) & (cap - 1);
        e[j] = st->dp[i];
    }
    free(st->dp);
    st->dp = e;
    st->dp_cap = cap;
    return 1;
}

/*
 * Insert one verified point.  A key already present with *different*
 * coefficients is the collision the whole search is for; identical
 * coefficients are the same trail arriving twice (a re-run unit, a
 * duplicated message) and merge as a no-op.  Returns 1 if the instance
 * was solved by this insertion.
 */
static int coord_dp_insert(ca_coord_state *st, const ca_coord_ctx *ctx, const ca_elem *y,
                           const ca_coord_dp *dp, uint32_t peer)
{
    if (st->dp_count * 4 >= st->dp_cap * 3 && !coord_dp_grow(st)) return 0;
    uint64_t key = ca_group_hash(&ctx->g, y);
    size_t j = key & (st->dp_cap - 1);
    while (st->dp[j].used) {
        coord_dp_entry *e = &st->dp[j];
        if (e->key == key) {
            ca_elem stored;
            if (ca_group_encode(&ctx->g, &stored, e->point) == 1 &&
                ca_group_equal(&ctx->g, &stored, y)) {
                if (e->a == dp->a && e->b == dp->b) return 0; /* same trail */
                uint64_t x;
                if (ca_coord_solve_collision(ctx, e->a, e->b, dp->a, dp->b, &x)) {
                    if (!st->have_solution) {
                        st->have_solution = 1;
                        st->solution = x;
                        return 1;
                    }
                    return 0;
                }
                /* Same point, different coefficients, no solution: the
                 * sterile case (b1 == b2), worth counting and no more. */
                st->sterile_collisions++;
                return 0;
            }
        }
        j = (j + 1) & (st->dp_cap - 1);
    }
    coord_dp_entry *e = &st->dp[j];
    e->used = 1;
    e->key = key;
    memcpy(e->point, dp->point, sizeof(e->point));
    e->a = dp->a;
    e->b = dp->b;
    e->walker = dp->walker;
    e->peer = peer;
    st->dp_count++;
    return 0;
}

/* unit views -------------------------------------------------------------- */

static coord_unit_view *coord_unit_slot(ca_coord_state *st, uint64_t unit, uint32_t peer)
{
    for (size_t i = 0; i < st->unit_count; i++)
        if (st->units[i].unit == unit && st->units[i].peer == peer) return &st->units[i];
    if (st->unit_count == st->unit_cap) {
        size_t cap = st->unit_cap ? st->unit_cap * 2 : 16;
        coord_unit_view *u = realloc(st->units, cap * sizeof(*u));
        if (!u) return NULL;
        st->units = u;
        st->unit_cap = cap;
    }
    coord_unit_view *v = &st->units[st->unit_count++];
    memset(v, 0, sizeof(*v));
    v->unit = unit;
    v->peer = peer;
    return v;
}

/* the log ----------------------------------------------------------------- */

static int coord_log_append(ca_coord_state *st, uint32_t peer, uint64_t seq, const char *line)
{
    if (st->log_count == st->log_cap) {
        size_t cap = st->log_cap ? st->log_cap * 2 : 64;
        coord_log_entry *l = realloc(st->log, cap * sizeof(*l));
        if (!l) return 0;
        st->log = l;
        st->log_cap = cap;
    }
    char *copy = NULL;
    size_t n = strlen(line) + 1;
    copy = malloc(n);
    if (!copy) return 0;
    memcpy(copy, line, n);
    st->log[st->log_count].peer = peer;
    st->log[st->log_count].seq = seq;
    st->log[st->log_count].line = copy;
    st->log_count++;
    return 1;
}

static int coord_seen(ca_coord_state *st, uint32_t peer, uint64_t seq)
{
    for (size_t i = 0; i < st->log_count; i++)
        if (st->log[i].peer == peer && st->log[i].seq == seq) return 1;
    return 0;
}

/* merge ------------------------------------------------------------------- */

ca_status ca_coord_apply(ca_coord_state *st, const ca_coord_ctx *ctx, const ca_coord_checkin *ci,
                         uint64_t now, int verify, ca_coord_outcome *out)
{
    ca_coord_outcome dummy;
    if (!out) out = &dummy;
    memset(out, 0, sizeof(*out));
    if (!st || !ctx || !ci) return CA_ERR_INVALID;
    if (ci->job_id != ctx->job.id) {
        ca_set_error("check-in is for another job");
        pthread_mutex_lock(&st->lock);
        st->rejected_checkins++;
        pthread_mutex_unlock(&st->lock);
        return CA_ERR_INVALID;
    }
    if (!coord_peer_name_ok(ci->peer) || ci->num_units > CA_COORD_UNITS_MAX ||
        ci->num_dps > CA_COORD_DPS_MAX) {
        ca_set_error("malformed check-in");
        pthread_mutex_lock(&st->lock);
        st->rejected_checkins++;
        pthread_mutex_unlock(&st->lock);
        return CA_ERR_INVALID;
    }

    char line[CA_COORD_LINE_MAX];
    if (!ca_coord_checkin_encode(ci, line, sizeof(line))) {
        ca_set_error("check-in does not fit one line");
        return CA_ERR_INVALID;
    }

    pthread_mutex_lock(&st->lock);
    uint32_t peer;
    if (!coord_peer_index(st, ci->peer, &peer, 1)) {
        pthread_mutex_unlock(&st->lock);
        return CA_ERR_NOMEM;
    }
    /* Idempotence: the same (peer, seq) twice is a no-op, which is what
     * lets any transport resend freely. */
    if (coord_seen(st, peer, ci->seq)) {
        pthread_mutex_unlock(&st->lock);
        return CA_OK;
    }
    out->fresh = 1;
    if (!coord_log_append(st, peer, ci->seq, line)) {
        pthread_mutex_unlock(&st->lock);
        return CA_ERR_NOMEM;
    }
    if (ci->seq > st->peers[peer].max_seq) st->peers[peer].max_seq = ci->seq;

    /* Unit reports are a per-peer max-register: a later seq replaces an
     * earlier one, an out-of-order arrival is ignored. */
    for (uint32_t i = 0; i < ci->num_units; i++) {
        const ca_coord_unit *u = &ci->units[i];
        coord_unit_view *v = coord_unit_slot(st, u->unit, peer);
        if (!v) {
            pthread_mutex_unlock(&st->lock);
            return CA_ERR_NOMEM;
        }
        if (ci->seq >= v->seq) {
            if (u->steps > v->steps) st->steps += u->steps - v->steps;
            if (u->dead_trails > v->dead_trails) st->dead_trails += u->dead_trails - v->dead_trails;
            v->seq = ci->seq;
            v->walkers_done = u->walkers_done > v->walkers_done ? u->walkers_done : v->walkers_done;
            v->steps = u->steps > v->steps ? u->steps : v->steps;
            v->dps = u->dps > v->dps ? u->dps : v->dps;
            v->dead_trails = u->dead_trails > v->dead_trails ? u->dead_trails : v->dead_trails;
            if (u->completed) v->completed = 1;
        }
        /* The lease clock is local receipt, always: a peer with a wrong
         * clock must not be able to hold or lose a unit. */
        v->seen_local = now;
    }

    for (uint32_t i = 0; i < ci->num_dps; i++) {
        const ca_coord_dp *dp = &ci->dps[i];
        ca_elem y;
        if (verify) {
            if (!ca_coord_dp_verify(ctx, dp, &y)) {
                out->rejected_dps++;
                st->rejected_dps++;
                continue;
            }
        } else {
            if (ca_group_encode(&ctx->g, &y, dp->point) != 1) {
                out->rejected_dps++;
                st->rejected_dps++;
                continue;
            }
            if (ctx->job.negation_map) ca_group_canonicalize(&ctx->g, &y);
        }
        out->accepted_dps++;
        st->dps_total++;
        if (coord_dp_insert(st, ctx, &y, dp, peer)) out->solved_now = 1;
    }

    /* A claimed solution is accepted only if it is the answer. */
    if (ci->has_solution && !st->have_solution) {
        if (ca_verify_log(&ctx->g, &ctx->base, &ctx->target, ci->solution)) {
            st->have_solution = 1;
            st->solution = ci->solution;
            out->solved_now = 1;
        } else {
            st->rejected_checkins++;
        }
    }
    pthread_mutex_unlock(&st->lock);
    return CA_OK;
}

int ca_coord_solution(ca_coord_state *st, uint64_t *x)
{
    if (!st) return 0;
    pthread_mutex_lock(&st->lock);
    int have = st->have_solution;
    if (have && x) *x = st->solution;
    pthread_mutex_unlock(&st->lock);
    return have;
}

void ca_coord_progress_get(ca_coord_state *st, const ca_coord_ctx *ctx, uint64_t now,
                           uint64_t lease_secs, ca_coord_progress *out)
{
    memset(out, 0, sizeof(*out));
    if (!lease_secs) lease_secs = 120;
    pthread_mutex_lock(&st->lock);
    out->steps = st->steps;
    out->dps_stored = st->dp_count;
    out->dead_trails = st->dead_trails;
    out->peers = st->peer_count;
    out->checkins = st->log_count;
    out->rejected_dps = st->rejected_dps;
    out->sterile_collisions = st->sterile_collisions;
    out->have_solution = st->have_solution;
    out->solution = st->solution;
    /* Units are counted once, however many peers reported them. */
    for (size_t i = 0; i < st->unit_count; i++) {
        int seen_before = 0;
        for (size_t j = 0; j < i; j++)
            if (st->units[j].unit == st->units[i].unit) {
                seen_before = 1;
                break;
            }
        if (seen_before) continue;
        int completed = 0, active = 0;
        for (size_t j = 0; j < st->unit_count; j++) {
            if (st->units[j].unit != st->units[i].unit) continue;
            if (st->units[j].completed)
                completed = 1;
            else if (now < st->units[j].seen_local + lease_secs)
                active = 1;
        }
        if (completed)
            out->units_completed++;
        else if (active)
            out->units_active++;
    }
    pthread_mutex_unlock(&st->lock);
    out->expected_steps = ca_coord_expected_steps(ctx);
    out->fraction = out->expected_steps > 0 ? (double)out->steps / out->expected_steps : 0.0;
}

/* version vectors --------------------------------------------------------- */

ca_status ca_coord_vv_new(ca_coord_vv **out)
{
    if (!out) return CA_ERR_INVALID;
    *out = calloc(1, sizeof(**out));
    return *out ? CA_OK : CA_ERR_NOMEM;
}

void ca_coord_vv_free(ca_coord_vv *vv)
{
    if (!vv) return;
    free(vv->e);
    free(vv);
}

void ca_coord_vv_set(ca_coord_vv *vv, const char *peer, uint64_t seq)
{
    if (!vv || !coord_peer_name_ok(peer)) return;
    for (size_t i = 0; i < vv->count; i++) {
        if (strcmp(vv->e[i].name, peer) == 0) {
            if (seq > vv->e[i].max_seq) vv->e[i].max_seq = seq;
            return;
        }
    }
    if (vv->count == vv->cap) {
        size_t cap = vv->cap ? vv->cap * 2 : 8;
        coord_peer *e = realloc(vv->e, cap * sizeof(*e));
        if (!e) return;
        vv->e = e;
        vv->cap = cap;
    }
    memset(&vv->e[vv->count], 0, sizeof(vv->e[0]));
    snprintf(vv->e[vv->count].name, CA_COORD_PEER_MAX, "%s", peer);
    vv->e[vv->count].max_seq = seq;
    vv->count++;
}

uint64_t ca_coord_vv_get(const ca_coord_vv *vv, const char *peer)
{
    if (!vv || !peer) return 0;
    for (size_t i = 0; i < vv->count; i++)
        if (strcmp(vv->e[i].name, peer) == 0) return vv->e[i].max_seq;
    return 0;
}

void ca_coord_state_vv(ca_coord_state *st, ca_coord_vv *out)
{
    if (!st || !out) return;
    pthread_mutex_lock(&st->lock);
    for (size_t i = 0; i < st->peer_count; i++)
        ca_coord_vv_set(out, st->peers[i].name, st->peers[i].max_seq);
    pthread_mutex_unlock(&st->lock);
}

int ca_coord_delta_for(ca_coord_state *st, const ca_coord_vv *known,
                       int (*fn)(void *user, const ca_coord_checkin *ci), void *user)
{
    if (!st || !fn) return 0;
    int rc = 0;
    pthread_mutex_lock(&st->lock);
    for (size_t i = 0; i < st->log_count && rc == 0; i++) {
        const char *name = st->peers[st->log[i].peer].name;
        if (known && st->log[i].seq <= ca_coord_vv_get(known, name)) continue;
        ca_coord_checkin ci;
        if (ca_coord_checkin_decode(&ci, st->log[i].line) != CA_OK) continue;
        rc = fn(user, &ci);
    }
    pthread_mutex_unlock(&st->lock);
    return rc;
}

uint64_t ca_coord_next_seq(ca_coord_state *st, const char *peer)
{
    uint64_t seq = 1;
    pthread_mutex_lock(&st->lock);
    uint32_t idx;
    if (coord_peer_index(st, peer, &idx, 0)) seq = st->peers[idx].max_seq + 1;
    pthread_mutex_unlock(&st->lock);
    return seq;
}

/* ---- claiming ----------------------------------------------------------- */

/*
 * There is no assignment.  A lane picks from its own merged view: the
 * lowest-numbered units that are neither completed nor live-leased by
 * somebody else, and among the first `claim_window` of those, the one
 * its own name hashes to -- so lanes whose views lag each other tend to
 * spread out instead of piling onto the same unit.
 *
 * Two lanes working one unit is only waste, never corruption: the trails
 * are deterministic, so the duplicate points arrive with identical
 * coefficients and merge as no-ops.
 */
uint64_t ca_coord_claim_unit(ca_coord_state *st, const ca_coord_ctx *ctx, const char *peer,
                             uint64_t now, uint64_t lease_secs, uint32_t claim_window,
                             uint64_t *resume_from)
{
    (void)ctx;
    if (!claim_window) claim_window = 4;
    if (!lease_secs) lease_secs = 120;
    uint64_t candidates[64];
    uint64_t cursors[64];
    uint32_t found = 0;
    if (claim_window > 64) claim_window = 64;

    pthread_mutex_lock(&st->lock);
    uint32_t self;
    int have_self = coord_peer_index(st, peer, &self, 0);
    for (uint64_t u = 0; found < claim_window; u++) {
        int completed = 0, leased = 0;
        uint64_t cursor = 0;
        for (size_t i = 0; i < st->unit_count; i++) {
            if (st->units[i].unit != u) continue;
            if (st->units[i].walkers_done > cursor) cursor = st->units[i].walkers_done;
            if (st->units[i].completed) {
                completed = 1;
                break;
            }
            int mine = have_self && st->units[i].peer == self;
            if (!mine && now < st->units[i].seen_local + lease_secs) leased = 1;
        }
        if (completed || leased) continue;
        candidates[found] = u;
        cursors[found] = cursor;
        found++;
        /* Cap the scan: past the highest unit anybody has touched, every
         * further unit is equally free, so the window is already full of
         * sensible choices. */
        if (u > st->unit_count + claim_window + 8) break;
    }
    pthread_mutex_unlock(&st->lock);

    if (!found) return UINT64_MAX;
    uint64_t h = 1469598103934665603ULL;
    for (const char *s = peer; *s; s++) {
        h ^= (unsigned char)*s;
        h *= 1099511628211ULL;
    }
    uint32_t pick = (uint32_t)(ca_mix64(h) % found);
    if (resume_from) *resume_from = cursors[pick];
    return candidates[pick];
}

/* ---- the lane ----------------------------------------------------------- */

void ca_coord_lane_params_default(ca_coord_lane_params *p, const char *peer)
{
    memset(p, 0, sizeof(*p));
    if (peer) snprintf(p->peer, sizeof(p->peer), "%s", peer);
    p->checkin_every = 64;
    p->lease_secs = 120;
    p->claim_window = 4;
}

static uint64_t coord_now(void) { return (uint64_t)time(NULL); }

/* Merge our own check-in (no verification: we just made it), then hand
 * it to the transport.  Merging first is what makes the hook's argument
 * a fact and not a proposal. */
static void coord_emit(const ca_coord_ctx *ctx, ca_coord_state *st, ca_coord_checkin *ci,
                       void (*on_checkin)(void *, const ca_coord_checkin *), void *user,
                       ca_coord_lane_result *res)
{
    ci->job_id = ctx->job.id;
    ci->seq = ca_coord_next_seq(st, ci->peer);
    ci->time = coord_now();
    if (ca_coord_apply(st, ctx, ci, coord_now(), 0, NULL) != CA_OK) return;
    res->checkins++;
    if (on_checkin) on_checkin(user, ci);
    ci->num_dps = 0;
    ci->has_solution = 0;
}

ca_status ca_coord_lane_run(const ca_coord_ctx *ctx, ca_coord_state *st,
                            const ca_coord_lane_params *p,
                            void (*on_checkin)(void *user, const ca_coord_checkin *ci),
                            void *on_checkin_user, int (*should_stop)(void *user),
                            void *should_stop_user, ca_coord_lane_result *out)
{
    ca_coord_lane_result res;
    memset(&res, 0, sizeof(res));
    if (!ctx || !st || !p || !coord_peer_name_ok(p->peer)) return CA_ERR_INVALID;
    uint64_t every = p->checkin_every ? p->checkin_every : 64;
    uint64_t lease = p->lease_secs ? p->lease_secs : 120;
    /* The step cap: 20 mean trails.  A walk that has not reached a DP by
     * then is in a fruitless cycle (or very unlucky), and is worth less
     * than the next walker. */
    uint64_t cap = ctx->job.dp_bits >= 58 ? UINT64_MAX : (uint64_t)20 << ctx->job.dp_bits;
    uint64_t units_done = 0;

    for (;;) {
        if (should_stop && should_stop(should_stop_user)) break;
        if (ca_coord_solution(st, &res.solution)) {
            res.have_solution = 1;
            break;
        }
        if (p->max_units && units_done >= p->max_units) break;
        if (p->max_walkers && res.walkers >= p->max_walkers) break;

        uint64_t resume = 0;
        uint64_t unit =
            ca_coord_claim_unit(st, ctx, p->peer, coord_now(), lease, p->claim_window, &resume);
        if (unit == UINT64_MAX) break;

        uint64_t first = unit * ctx->job.unit_size;
        uint64_t count = ctx->job.unit_size;
        ca_coord_checkin ci;
        memset(&ci, 0, sizeof(ci));
        snprintf(ci.peer, sizeof(ci.peer), "%s", p->peer);
        ci.num_units = 1;
        ci.units[0].unit = unit;
        ci.units[0].walkers_done = resume;
        /* Announce the claim before walking it: a lane that dies after
         * one walker should still have told everyone which unit it took. */
        coord_emit(ctx, st, &ci, on_checkin, on_checkin_user, &res);

        uint64_t since_checkin = 0;
        for (uint64_t k = resume; k < count; k++) {
            if (should_stop && should_stop(should_stop_user)) break;
            if (p->max_walkers && res.walkers >= p->max_walkers) break;

            ca_coord_dp dp;
            uint64_t steps = 0;
            int got = ca_coord_walk_one(ctx, first + k, cap, &dp, &steps);
            res.walkers++;
            res.steps += steps;
            ci.units[0].walkers_done = k + 1;
            ci.units[0].steps += steps;
            if (got) {
                res.dps++;
                ci.units[0].dps++;
                if (ci.num_dps < CA_COORD_DPS_MAX) ci.dps[ci.num_dps++] = dp;
            } else {
                res.dead_trails++;
                ci.units[0].dead_trails++;
            }
            since_checkin++;

            if (since_checkin >= every || ci.num_dps == CA_COORD_DPS_MAX) {
                since_checkin = 0;
                coord_emit(ctx, st, &ci, on_checkin, on_checkin_user, &res);
                if (ca_coord_solution(st, &res.solution)) {
                    res.have_solution = 1;
                    break;
                }
            }
        }

        if (ci.units[0].walkers_done >= count) {
            ci.units[0].completed = 1;
            units_done++;
            res.units_completed++;
        }
        /* One last check-in for this unit, carrying the solution if this
         * lane's merge is the one that produced it. */
        if (ca_coord_solution(st, &res.solution)) {
            res.have_solution = 1;
            ci.has_solution = 1;
            ci.solution = res.solution;
        }
        coord_emit(ctx, st, &ci, on_checkin, on_checkin_user, &res);
        if (res.have_solution) break;
    }

    if (!res.have_solution && ca_coord_solution(st, &res.solution)) res.have_solution = 1;
    if (out) *out = res;
    return CA_OK;
}
