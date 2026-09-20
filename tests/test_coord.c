#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <poll.h>
#include <stdatomic.h>
#include <signal.h>
#include <sys/socket.h>
/*
 * test_coord.c - distributed rho: the job, the CRDT, the wire, and the
 * property the whole module exists for -- agents that never listen on
 * anything converging through a hub they dialled out to.
 */
#include "test_fixtures.h"

#include "cryptanalysis/ca_coord.h"
#include "coord_internal.h"

#include <pthread.h>
#include <unistd.h>

/*
 * A small instance with a planted secret, so every run is checkable.
 * The negation map needs a group with a cheap negation, which here means
 * a curve: ca_coord_job_init refuses it for Z_p^*, and that refusal is
 * checked below.
 */
static ca_coord_ctx *make_ctx_in(ca_group *g, ca_elem *gen, uint64_t secret, int negation,
                                 uint64_t *out_secret)
{
    if (negation)
        fx_ec(g, gen, 1000003ULL, 1, 7);
    else
        fx_zp_safe(g, gen, 2000303ULL); /* p = 2q+1, q = 1000151 */
    uint64_t x = secret % g->order;
    if (!x) x = 1;
    ca_elem h;
    fx_instance(g, gen, x, &h);
    ca_coord_job job;
    CHECK(ca_coord_job_init(&job, g, gen, &h, 5, 16, negation, 32, 7) == CA_OK);
    ca_coord_ctx *ctx = NULL;
    CHECK(ca_coord_ctx_open(&ctx, &job) == CA_OK);
    if (out_secret) *out_secret = x;
    return ctx;
}

static ca_coord_ctx *make_ctx(ca_group *g, ca_elem *gen, uint64_t secret, int negation,
                              uint64_t *out_secret)
{
    ca_coord_ctx *ctx = make_ctx_in(g, gen, secret, negation, out_secret);
    if (!ctx) {
        fprintf(stderr, "fixture failed; the remaining checks cannot run\n");
        exit(1);
    }
    return ctx;
}

/* The negation map is refused where the group has no cheap negation,
 * rather than silently walked without it. */
static void test_negation_needs_a_curve(void)
{
    ca_group g;
    ca_elem gen;
    fx_zp_safe(&g, &gen, 2000303ULL);
    ca_elem h;
    fx_instance(&g, &gen, 5, &h);
    ca_coord_job job;
    CHECK(ca_coord_job_init(&job, &g, &gen, &h, 5, 16, 1, 32, 7) == CA_ERR_UNSUPPORTED);
}

/* ---- the job ------------------------------------------------------------ */

/* A job document is not a credential.  Its id is a hash of its own body,
 * so it proves only that the line was not altered in transit -- anybody
 * can mint a consistent one.  So the bounds the constructor enforces have
 * to be enforced again on the way in, or a crafted line decides whether
 * the agent lives: r=0 divides by zero when picking a branch, and a
 * negative dp shifts by a negative amount. */
static void test_job_decode_bounds(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 4242, 0, NULL);
    char line[CA_COORD_LINE_MAX];
    CHECK(ca_coord_job_encode(ca_coord_ctx_job(ctx), line, sizeof(line)) > 0);

    /* These are refused before the id is even recomputed, so the error
     * says which bound was broken rather than "document was altered" --
     * which is what tells us the check is the one doing the work. */
    struct {
        const char *field;
        const char *value;
        const char *want;
    } cases[] = {
        {" r=", " r=0 ", "r must be"},       {" r=", " r=99999 ", "r must be"},
        {" dp=", " dp=-1 ", "dp must be"},   {" dp=", " dp=63 ", "dp must be"},
        {" unit=", " unit=0 ", "unit must"}, {" n=", " n=0 ", "n must be"},
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        char bad[CA_COORD_LINE_MAX];
        snprintf(bad, sizeof(bad), "%s", line);
        const char *at = strstr(bad, cases[i].field);
        CHECK(at != NULL);
        if (!at) continue;
        char tail[CA_COORD_LINE_MAX];
        const char *sp = strchr(at + 1, ' ');
        snprintf(tail, sizeof(tail), "%s", sp ? sp : "");
        size_t head = (size_t)(at - bad);
        snprintf(bad + head, sizeof(bad) - head, "%s%s", cases[i].value, sp ? tail + 1 : "");

        ca_coord_job job;
        CHECK(ca_coord_job_decode(&job, bad) == CA_ERR_INVALID);
        CHECK(strstr(ca_last_error(), cases[i].want) != NULL);
    }
    ca_coord_ctx_close(ctx);
}

static void test_job_roundtrip(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 123456, 0, NULL);
    const ca_coord_job *job = ca_coord_ctx_job(ctx);

    char line[CA_COORD_LINE_MAX];
    CHECK(ca_coord_job_encode(job, line, sizeof(line)) > 0);
    ca_coord_job back;
    CHECK(ca_coord_job_decode(&back, line) == CA_OK);
    CHECK_EQ_U64(back.id, job->id);
    CHECK_EQ_U64(back.p, job->p);
    CHECK_EQ_U64(back.order, job->order);
    CHECK_EQ_U64((uint64_t)back.dp_bits, (uint64_t)job->dp_bits);

    /* A document altered in transit is refused, not walked: two agents
     * on different branch tables would silently stop colliding. */
    char *dp = strstr(line, " dp=");
    CHECK(dp != NULL);
    if (dp) {
        dp[4] = dp[4] == '5' ? '6' : '5';
        ca_coord_job tampered;
        CHECK(ca_coord_job_decode(&tampered, line) == CA_ERR_INVALID);
    }

    /* And every field that changes the walk changes the id, so two
     * agents cannot agree on an id while disagreeing on the walk. */
    ca_group g2;
    ca_elem gen2;
    fx_zp_safe(&g2, &gen2, 2000303ULL);
    ca_elem h2;
    fx_instance(&g2, &gen2, 999, &h2);
    ca_coord_job base_job, variant;
    CHECK(ca_coord_job_init(&base_job, &g2, &gen2, &h2, 5, 16, 0, 32, 7) == CA_OK);
    CHECK(ca_coord_job_init(&variant, &g2, &gen2, &h2, 5, 16, 0, 32, 8) == CA_OK);
    CHECK(base_job.id != variant.id); /* seed */
    CHECK(ca_coord_job_init(&variant, &g2, &gen2, &h2, 6, 16, 0, 32, 7) == CA_OK);
    CHECK(base_job.id != variant.id); /* dp_bits */
    CHECK(ca_coord_job_init(&variant, &g2, &gen2, &h2, 5, 20, 0, 32, 7) == CA_OK);
    CHECK(base_job.id != variant.id); /* branches */
    CHECK(ca_coord_job_init(&variant, &g2, &gen2, &h2, 5, 16, 0, 64, 7) == CA_OK);
    CHECK(base_job.id != variant.id); /* unit size */
    ca_coord_ctx_close(ctx);
}

/* ---- derivation and the walk -------------------------------------------- */

static void test_derivation_is_deterministic(void)
{
    ca_group g;
    ca_elem gen;
    uint64_t secret = 0;
    ca_coord_ctx *a = make_ctx(&g, &gen, 4242, 0, &secret);
    ca_coord_ctx *b = NULL;
    CHECK(ca_coord_ctx_open(&b, ca_coord_ctx_job(a)) == CA_OK);

    /* Two processes that agree on the job derive the same start points
     * without exchanging any of them -- the whole basis for dividing
     * work by index. */
    for (uint64_t i = 0; i < 32; i++) {
        ca_elem ya, yb;
        uint64_t aa, ab, ba, bb;
        ca_coord_walker_start(a, i, &ya, &aa, &ab);
        ca_coord_walker_start(b, i, &yb, &ba, &bb);
        CHECK(ca_group_equal(&a->g, &ya, &yb));
        CHECK_EQ_U64(aa, ba);
        CHECK_EQ_U64(ab, bb);
        /* and the invariant every step preserves */
        ca_elem t1, t2, z;
        ca_group_mul(&a->g, &t1, &a->base, aa, NULL);
        ca_group_mul(&a->g, &t2, &a->target, ab, NULL);
        ca_group_op(&a->g, &z, &t1, &t2);
        CHECK(ca_group_equal(&a->g, &z, &ya));
    }
    ca_coord_ctx_close(a);
    ca_coord_ctx_close(b);
}

static void test_walk_produces_verifiable_points(void)
{
    for (int neg = 0; neg < 2; neg++) {
        ca_group g;
        ca_elem gen;
        ca_coord_ctx *ctx = make_ctx(&g, &gen, 999, neg, NULL);
        int got = 0;
        for (uint64_t i = 0; i < 64 && got < 8; i++) {
            ca_coord_dp dp;
            uint64_t steps = 0;
            if (!ca_coord_walk_one(ctx, i, 20u << 5, &dp, &steps)) continue;
            got++;
            /* A receiver's whole check, for work worth 2^dp_bits steps. */
            CHECK(ca_coord_dp_verify(ctx, &dp, NULL) == 1);
            /* Tampering with any field is caught. */
            ca_coord_dp bad = dp;
            bad.a = (bad.a + 1) % ctx->n;
            CHECK(ca_coord_dp_verify(ctx, &bad, NULL) == 0);
            bad = dp;
            bad.point[0] ^= 1;
            CHECK(ca_coord_dp_verify(ctx, &bad, NULL) == 0);
        }
        CHECK(got > 0);
        ca_coord_ctx_close(ctx);
    }
}

/* Walking the same walker twice gives the same trail -- the reason a
 * duplicated unit is waste and not corruption. */
static void test_trails_are_reproducible(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 31337, 1, NULL);
    for (uint64_t i = 0; i < 16; i++) {
        ca_coord_dp d1, d2;
        uint64_t s1 = 0, s2 = 0;
        int r1 = ca_coord_walk_one(ctx, i, 20u << 5, &d1, &s1);
        int r2 = ca_coord_walk_one(ctx, i, 20u << 5, &d2, &s2);
        CHECK(r1 == r2);
        CHECK_EQ_U64(s1, s2);
        if (r1) {
            CHECK_EQ_U64(d1.a, d2.a);
            CHECK_EQ_U64(d1.b, d2.b);
            CHECK(memcmp(d1.point, d2.point, sizeof(d1.point)) == 0);
        }
    }
    ca_coord_ctx_close(ctx);
}

/* ---- the wire ----------------------------------------------------------- */

static void test_checkin_wire(void)
{
    ca_coord_checkin ci;
    memset(&ci, 0, sizeof(ci));
    ci.job_id = 0xdeadbeefcafef00dULL;
    snprintf(ci.peer, sizeof(ci.peer), "alice.3");
    ci.seq = 17;
    ci.time = 1757520000;
    ci.num_units = 2;
    ci.units[0] = (ca_coord_unit){42, 128, 131072, 127, 1, 0};
    ci.units[1] = (ca_coord_unit){43, 32, 4096, 4, 0, 1};
    ci.num_dps = 2;
    ci.dps[0] = (ca_coord_dp){10879, 1031, {7, 8, 9, 10}, 11, 12};
    ci.dps[1] = (ca_coord_dp){10880, 999, {1, 2, 3, 4}, 5, 6};
    ci.has_solution = 1;
    ci.solution = 123456789;

    char line[CA_COORD_LINE_MAX];
    CHECK(ca_coord_checkin_encode(&ci, line, sizeof(line)) > 0);
    ca_coord_checkin back;
    CHECK(ca_coord_checkin_decode(&back, line) == CA_OK);
    CHECK_EQ_U64(back.job_id, ci.job_id);
    CHECK(strcmp(back.peer, ci.peer) == 0);
    CHECK_EQ_U64(back.seq, ci.seq);
    CHECK_EQ_U64(back.num_units, ci.num_units);
    CHECK_EQ_U64(back.num_dps, ci.num_dps);
    CHECK_EQ_U64(back.units[1].unit, 43);
    CHECK(back.units[1].completed == 1);
    CHECK_EQ_U64(back.dps[0].walker, 10879);
    CHECK_EQ_U64(back.dps[1].b, 6);
    CHECK(back.has_solution == 1);
    CHECK_EQ_U64(back.solution, 123456789);

    /* A check-in with no work at all still round-trips. */
    ca_coord_checkin empty;
    memset(&empty, 0, sizeof(empty));
    snprintf(empty.peer, sizeof(empty.peer), "bob.0");
    empty.seq = 1;
    CHECK(ca_coord_checkin_encode(&empty, line, sizeof(line)) > 0);
    CHECK(ca_coord_checkin_decode(&back, line) == CA_OK);
    CHECK_EQ_U64(back.num_units, 0);
    CHECK(back.has_solution == 0);

    /* Garbage is refused, never half-parsed. */
    static const char *bad[] = {
        "",
        "ci",
        "ci x alice 1 2 U: D: S:-",
        "ci 1 alice 1 2 U:1,2,3;",
        "ci 1 alice 1 2 U:1,2,3,4,5,6; D:1,2,3,4,5,6,7;  S:-",
        "ci 1 al ice 1 2 U: D: S:-",
        "ci 1 alice 1 2 U:1,2,3,4,5,6 D: S:-",
        "ci 1 alice; 1 2 U: D: S:-",
        "ci 1 alice 1 2 U: D: S:x",
        "ci 1 alice 1 2 U:-1,2,3,4,5,6; D: S:-",
    };
    for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++)
        CHECK(ca_coord_checkin_decode(&back, bad[i]) == CA_ERR_INVALID);

    /* A peer name carrying a separator cannot be encoded, so it can
     * never inject a field. */
    ca_coord_checkin evil;
    memset(&evil, 0, sizeof(evil));
    snprintf(evil.peer, sizeof(evil.peer), "a b;c");
    CHECK(ca_coord_checkin_encode(&evil, line, sizeof(line)) == 0);
}

/* ---- the CRDT ----------------------------------------------------------- */

/* Collect check-ins produced by a lane. */
typedef struct collector {
    ca_coord_checkin *ci;
    size_t count, cap;
} collector;

static void collect(void *user, const ca_coord_checkin *ci)
{
    collector *c = user;
    if (c->count == c->cap) {
        size_t cap = c->cap ? c->cap * 2 : 64;
        ca_coord_checkin *grown = realloc(c->ci, cap * sizeof(*c->ci));
        CHECK(grown != NULL);
        if (!grown) return;
        c->ci = grown;
        c->cap = cap;
    }
    c->ci[c->count++] = *ci;
}

static void test_merge_is_order_independent_and_idempotent(void)
{
    ca_group g;
    ca_elem gen;
    uint64_t secret = 0;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 55555, 0, &secret);

    collector c;
    memset(&c, 0, sizeof(c));
    ca_coord_state *src = NULL;
    CHECK(ca_coord_state_init(&src, ctx) == CA_OK);
    ca_coord_lane_params p;
    ca_coord_lane_params_default(&p, "a.0");
    p.max_walkers = 24;
    p.checkin_every = 4;
    ca_coord_lane_result res;
    CHECK(ca_coord_lane_run(ctx, src, &p, collect, &c, NULL, NULL, &res) == CA_OK);
    CHECK(c.count > 2);

    /* Forwards, backwards, and twice over: same DP table, same answer. */
    ca_coord_state *fwd = NULL, *rev = NULL;
    CHECK(ca_coord_state_init(&fwd, ctx) == CA_OK);
    CHECK(ca_coord_state_init(&rev, ctx) == CA_OK);
    for (size_t i = 0; i < c.count; i++)
        CHECK(ca_coord_apply(fwd, ctx, &c.ci[i], 100, 1, NULL) == CA_OK);
    for (size_t i = 0; i < c.count; i++)
        CHECK(ca_coord_apply(fwd, ctx, &c.ci[i], 100, 1, NULL) == CA_OK); /* again */
    for (size_t i = c.count; i-- > 0;)
        CHECK(ca_coord_apply(rev, ctx, &c.ci[i], 100, 1, NULL) == CA_OK);

    ca_coord_progress pf, pr;
    ca_coord_progress_get(fwd, ctx, 100, 120, &pf);
    ca_coord_progress_get(rev, ctx, 100, 120, &pr);
    CHECK_EQ_U64(pf.dps_stored, pr.dps_stored);
    CHECK_EQ_U64(pf.steps, pr.steps);
    CHECK_EQ_U64(pf.checkins, pr.checkins);
    CHECK_EQ_U64(pf.rejected_dps, 0);
    CHECK(pf.have_solution == pr.have_solution);

    ca_coord_state_free(src);
    ca_coord_state_free(fwd);
    ca_coord_state_free(rev);
    free(c.ci);
    ca_coord_ctx_close(ctx);
}

static void test_foreign_and_forged_are_refused(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 777, 0, NULL);
    ca_coord_state *st = NULL;
    CHECK(ca_coord_state_init(&st, ctx) == CA_OK);

    /* Another job's check-in. */
    ca_coord_checkin ci;
    memset(&ci, 0, sizeof(ci));
    snprintf(ci.peer, sizeof(ci.peer), "mallory.0");
    ci.seq = 1;
    ci.job_id = ca_coord_ctx_job(ctx)->id ^ 1;
    CHECK(ca_coord_apply(st, ctx, &ci, 10, 1, NULL) == CA_ERR_INVALID);

    /* A forged point: right shape, wrong coefficients. */
    ci.job_id = ca_coord_ctx_job(ctx)->id;
    ci.num_dps = 1;
    for (uint64_t i = 0; i < 64; i++) {
        uint64_t steps = 0;
        if (ca_coord_walk_one(ctx, i, 20u << 5, &ci.dps[0], &steps)) break;
    }
    ci.dps[0].a = (ci.dps[0].a + 1) % ctx->n;
    ca_coord_outcome oc;
    CHECK(ca_coord_apply(st, ctx, &ci, 10, 1, &oc) == CA_OK);
    CHECK_EQ_U64(oc.rejected_dps, 1);
    CHECK_EQ_U64(oc.accepted_dps, 0);

    /* A lie about the answer is checked against the target. */
    ci.seq = 2;
    ci.num_dps = 0;
    ci.has_solution = 1;
    ci.solution = 12345;
    CHECK(ca_coord_apply(st, ctx, &ci, 10, 1, NULL) == CA_OK);
    CHECK(ca_coord_solution(st, NULL) == 0);

    ca_coord_state_free(st);
    ca_coord_ctx_close(ctx);
}

static void test_leases_expire_and_units_resume(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 4711, 0, NULL);
    ca_coord_state *st = NULL;
    CHECK(ca_coord_state_init(&st, ctx) == CA_OK);

    /* alice claims unit 0 and gets 10 walkers in, then goes quiet. */
    ca_coord_checkin ci;
    memset(&ci, 0, sizeof(ci));
    ci.job_id = ca_coord_ctx_job(ctx)->id;
    snprintf(ci.peer, sizeof(ci.peer), "alice.0");
    ci.seq = 1;
    ci.num_units = 1;
    ci.units[0].unit = 0;
    ci.units[0].walkers_done = 10;
    CHECK(ca_coord_apply(st, ctx, &ci, 1000, 1, NULL) == CA_OK);

    /* While the lease is live bob takes a different unit ... */
    uint64_t resume = 0;
    uint64_t u = ca_coord_claim_unit(st, ctx, "bob.0", 1010, 120, 1, &resume);
    CHECK(u != 0);
    /* ... and once it has expired, unit 0 is his, from alice's cursor. */
    u = ca_coord_claim_unit(st, ctx, "bob.0", 1000 + 121, 120, 1, &resume);
    CHECK_EQ_U64(u, 0);
    CHECK_EQ_U64(resume, 10);

    /* A completed unit is never handed out again. */
    ci.seq = 2;
    ci.units[0].completed = 1;
    ci.units[0].walkers_done = ca_coord_ctx_job(ctx)->unit_size;
    CHECK(ca_coord_apply(st, ctx, &ci, 1000, 1, NULL) == CA_OK);
    u = ca_coord_claim_unit(st, ctx, "bob.0", 1000 + 121, 120, 1, &resume);
    CHECK(u != 0);

    ca_coord_state_free(st);
    ca_coord_ctx_close(ctx);
}

static void test_sequence_numbers_and_deltas(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 8080, 0, NULL);
    ca_coord_state *a = NULL, *b = NULL;
    CHECK(ca_coord_state_init(&a, ctx) == CA_OK);
    CHECK(ca_coord_state_init(&b, ctx) == CA_OK);

    collector c;
    memset(&c, 0, sizeof(c));
    ca_coord_lane_params p;
    ca_coord_lane_params_default(&p, "a.0");
    p.max_walkers = 16;
    p.checkin_every = 4;
    ca_coord_lane_result res;
    CHECK(ca_coord_lane_run(ctx, a, &p, collect, &c, NULL, NULL, &res) == CA_OK);

    /* b knows nothing, so the delta for its (empty) vector is the whole
     * log; after applying it the two vectors agree. */
    ca_coord_vv *empty = NULL;
    CHECK(ca_coord_vv_new(&empty) == CA_OK);
    for (size_t i = 0; i < c.count; i++)
        CHECK(ca_coord_apply(b, ctx, &c.ci[i], 200, 1, NULL) == CA_OK);
    ca_coord_vv *va = NULL, *vb = NULL;
    CHECK(ca_coord_vv_new(&va) == CA_OK);
    CHECK(ca_coord_vv_new(&vb) == CA_OK);
    ca_coord_state_vv(a, va);
    ca_coord_state_vv(b, vb);
    CHECK_EQ_U64(ca_coord_vv_get(va, "a.0"), ca_coord_vv_get(vb, "a.0"));
    CHECK(ca_coord_vv_get(va, "a.0") > 0);
    /* Nothing is owed once the vectors match. */
    CHECK(ca_coord_delta_for(a, va, NULL, NULL) == 0);

    /* Sequence numbers continue above what is already logged, so a
     * restarted lane never reuses one. */
    CHECK(ca_coord_next_seq(a, "a.0") == ca_coord_vv_get(va, "a.0") + 1);

    ca_coord_vv_free(empty);
    ca_coord_vv_free(va);
    ca_coord_vv_free(vb);
    ca_coord_state_free(a);
    ca_coord_state_free(b);
    free(c.ci);
    ca_coord_ctx_close(ctx);
}

/* Merging two lanes' independent work solves the instance: the point of
 * distributing it at all. */
static void test_two_lanes_merge_to_a_solution(void)
{
    ca_group g;
    ca_elem gen;
    uint64_t secret = 0;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 133337, 0, &secret);
    ca_coord_state *merged = NULL;
    CHECK(ca_coord_state_init(&merged, ctx) == CA_OK);

    int solved = 0;
    for (int round = 0; round < 200 && !solved; round++) {
        for (int lane = 0; lane < 2; lane++) {
            char name[CA_COORD_PEER_MAX];
            snprintf(name, sizeof(name), "n%d.0", lane);
            ca_coord_state *own = NULL;
            CHECK(ca_coord_state_init(&own, ctx) == CA_OK);
            /* Each lane sees only the merged view it starts from. */
            collector c;
            memset(&c, 0, sizeof(c));
            ca_coord_lane_params p;
            ca_coord_lane_params_default(&p, name);
            p.max_walkers = 8;
            p.checkin_every = 4;
            p.claim_window = 1;
            ca_coord_lane_result res;
            CHECK(ca_coord_lane_run(ctx, merged, &p, collect, &c, NULL, NULL, &res) == CA_OK);
            free(c.ci);
            ca_coord_state_free(own);
        }
        solved = ca_coord_solution(merged, NULL);
    }
    uint64_t x = 0;
    CHECK(ca_coord_solution(merged, &x) == 1);
    CHECK_EQ_U64(x, secret);
    ca_coord_progress pr;
    ca_coord_progress_get(merged, ctx, 0, 120, &pr);
    CHECK_EQ_U64(pr.rejected_dps, 0);

    ca_coord_state_free(merged);
    ca_coord_ctx_close(ctx);
}

/* ---- the network -------------------------------------------------------- */

static void test_url_parsing(void)
{
    char hp[256], pfx[128];
    CHECK(ca_coord_parse_url("http://10.0.1.7:8080", hp, sizeof(hp), pfx, sizeof(pfx)) == CA_OK);
    CHECK(strcmp(hp, "10.0.1.7:8080") == 0);
    CHECK(strcmp(pfx, "") == 0);
    CHECK(ca_coord_parse_url("hub.internal:8080", hp, sizeof(hp), pfx, sizeof(pfx)) == CA_OK);
    CHECK(strcmp(hp, "hub.internal:8080") == 0);
    /* A hostname with no port is port 80 -- what a proxy publishes on. */
    CHECK(ca_coord_parse_url("http://hub.example.com", hp, sizeof(hp), pfx, sizeof(pfx)) == CA_OK);
    CHECK(strcmp(hp, "hub.example.com:80") == 0);
    /* A hub published under a subpath keeps the prefix. */
    CHECK(ca_coord_parse_url("http://hub:8080/rho/", hp, sizeof(hp), pfx, sizeof(pfx)) == CA_OK);
    CHECK(strcmp(pfx, "/rho") == 0);
    /* https is refused loudly rather than downgraded silently. */
    CHECK(ca_coord_parse_url("https://hub.example.com", hp, sizeof(hp), pfx, sizeof(pfx)) ==
          CA_ERR_UNSUPPORTED);
}

/* ---- the agent's side of the wire --------------------------------------- */

/*
 * A scripted server: it speaks just enough HTTP to answer the client
 * calls in coord_net.c, and replays canned lines.  It is a test double,
 * not a second coordinator -- the real one is in Go, and the end-to-end
 * against it lives there.  What is tested here is the *client*: that it
 * frames requests correctly, refuses what it should, merges what comes
 * back, and reconnects when the socket goes away, all of which a
 * scripted peer pins down far more precisely than a live one.
 */

typedef enum server_script {
    SCRIPT_JOB,             /* GET /v1/job -> 200 with the job document */
    SCRIPT_JOB_401,         /* GET /v1/job -> 401 */
    SCRIPT_JOB_GARBAGE,     /* GET /v1/job -> 200 with something that is not a job */
    SCRIPT_SYNC,            /* POST /v1/sync -> our vector and our lines */
    SCRIPT_SYNC_CHUNKED,    /* the same, sent with Transfer-Encoding: chunked */
    SCRIPT_CHANNEL,         /* GET /v1/channel -> 101, then push lines */
    SCRIPT_CHANNEL_REFUSED, /* GET /v1/channel -> 426 */
    SCRIPT_HANGUP,          /* accept and close, to exercise the redial path */
    SCRIPT_CHANNEL_RESET    /* upgrade, then reset the first connection */
} server_script;

typedef struct test_server {
    int fd;
    int port;
    server_script script;
    pthread_t thread;
    /* Crosses threads, so it is an atomic and not merely volatile --
     * which is what ThreadSanitizer says if you try the latter. */
    atomic_int stop;
    /* What the server should say, and what it heard. */
    char push[4][CA_COORD_LINE_MAX];
    int push_count;
    pthread_mutex_t lock;
    char heard[32][CA_COORD_LINE_MAX];
    int heard_count;
    int connections;
} test_server;

static void server_note(test_server *s, const char *line)
{
    pthread_mutex_lock(&s->lock);
    if (s->heard_count < (int)(sizeof(s->heard) / sizeof(s->heard[0]))) {
        snprintf(s->heard[s->heard_count], CA_COORD_LINE_MAX, "%s", line);
        s->heard_count++;
    }
    pthread_mutex_unlock(&s->lock);
}

/* Queue a line for the server to replay, bounded explicitly: gcc cannot
 * see the row length of a decayed `char [N][LINE_MAX]` argument, and at
 * -O2 it says so. */
static void server_push_line(test_server *s, const char *line)
{
    int cap = (int)(sizeof(s->push) / sizeof(s->push[0]));
    if (s->push_count >= cap) return;
    size_t n = strnlen(line, CA_COORD_LINE_MAX - 1);
    memcpy(s->push[s->push_count], line, n);
    s->push[s->push_count][n] = 0;
    s->push_count++;
}

static int server_heard(test_server *s, const char *prefix)
{
    int n = 0;
    pthread_mutex_lock(&s->lock);
    for (int i = 0; i < s->heard_count; i++)
        if (strncmp(s->heard[i], prefix, strlen(prefix)) == 0) n++;
    pthread_mutex_unlock(&s->lock);
    return n;
}

/* Read one \n-terminated line; returns 0 at EOF or on error. */
static int server_read_line(int fd, char *out, size_t cap)
{
    size_t n = 0;
    while (n + 1 < cap) {
        char c;
        ssize_t r = recv(fd, &c, 1, 0);
        if (r <= 0) return 0;
        if (c == '\n') break;
        if (c != '\r') out[n++] = c;
    }
    out[n] = 0;
    return 1;
}

static void server_write(int fd, const char *s) { (void)!send(fd, s, strlen(s), MSG_NOSIGNAL); }

/* The same answer, framed the way Go frames a streamed body once it
 * outgrows its write buffer -- and the way a proxy may re-frame it
 * whatever the hub did.  Deliberately split small, so the client has to
 * reassemble across chunk boundaries rather than get one lucky read. */
static void server_respond_chunked(int fd, int status, const char *body)
{
    char head[256];
    snprintf(head, sizeof(head),
             "HTTP/1.1 %d X\r\nContent-Type: text/plain\r\n"
             "Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n",
             status);
    server_write(fd, head);
    size_t len = strlen(body), off = 0;
    while (off < len) {
        size_t n = len - off < 17 ? len - off : 17;
        char sz[32];
        snprintf(sz, sizeof(sz), "%zx\r\n", n);
        server_write(fd, sz);
        (void)!send(fd, body + off, n, MSG_NOSIGNAL);
        server_write(fd, "\r\n");
        off += n;
    }
    server_write(fd, "0\r\n\r\n");
}

static void server_respond(int fd, int status, const char *body)
{
    char head[256];
    snprintf(head, sizeof(head),
             "HTTP/1.1 %d X\r\nContent-Type: text/plain\r\nContent-Length: %zu\r\n"
             "Connection: close\r\n\r\n",
             status, strlen(body));
    server_write(fd, head);
    server_write(fd, body);
}

static void server_handle(test_server *s, int fd)
{
    char line[CA_COORD_LINE_MAX];
    if (!server_read_line(fd, line, sizeof(line))) return;
    server_note(s, line);
    size_t content_length = 0;
    for (;;) {
        char h[CA_COORD_LINE_MAX];
        if (!server_read_line(fd, h, sizeof(h))) return;
        if (!h[0]) break;
        if (!strncasecmp(h, "content-length:", 15)) content_length = strtoul(h + 15, NULL, 10);
        if (!strncasecmp(h, "authorization:", 14)) server_note(s, h);
    }

    switch (s->script) {
    case SCRIPT_JOB: server_respond(fd, 200, s->push_count ? s->push[0] : ""); break;
    case SCRIPT_JOB_401: server_respond(fd, 401, "no\n"); break;
    case SCRIPT_JOB_GARBAGE: server_respond(fd, 200, "not a job document at all\n"); break;
    case SCRIPT_SYNC_CHUNKED:
    case SCRIPT_SYNC: {
        /* Read the body the client pushed, then answer with ours. */
        char *body = calloc(content_length + 1, 1);
        if (body && content_length) {
            size_t got = 0;
            while (got < content_length) {
                ssize_t r = recv(fd, body + got, content_length - got, 0);
                if (r <= 0) break;
                got += (size_t)r;
            }
            for (char *save = NULL, *tok = strtok_r(body, "\n", &save); tok;
                 tok = strtok_r(NULL, "\n", &save))
                server_note(s, tok);
        }
        free(body);
        char reply[8 * CA_COORD_LINE_MAX];
        size_t off = (size_t)snprintf(reply, sizeof(reply), "vv\n");
        for (int i = 0; i < s->push_count && off < sizeof(reply); i++)
            off += (size_t)snprintf(reply + off, sizeof(reply) - off, "%s\n", s->push[i]);
        if (s->script == SCRIPT_SYNC_CHUNKED)
            server_respond_chunked(fd, 200, reply);
        else
            server_respond(fd, 200, reply);
        break;
    }
    case SCRIPT_CHANNEL_REFUSED: server_respond(fd, 426, "upgrade\n"); break;
    case SCRIPT_CHANNEL: {
        server_write(fd, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: " CA_COORD_PROTOCOL
                         "\r\nConnection: Upgrade\r\n\r\n");
        for (int i = 0; i < s->push_count; i++) {
            server_write(fd, s->push[i]);
            server_write(fd, "\n");
        }
        /* Then listen until the client goes away or the test stops. */
        struct timeval tv = {0, (suseconds_t)200 * 1000};
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        while (!atomic_load(&s->stop)) {
            char in[CA_COORD_LINE_MAX];
            if (!server_read_line(fd, in, sizeof(in))) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) continue;
                break;
            }
            if (in[0]) server_note(s, in);
            /* The hub acks every check-in; the agent keeps it until then. */
            if (!strncmp(in, "ci ", 3)) server_write(fd, "ack 0 0\n");
        }
        break;
    }
    case SCRIPT_HANGUP: break;
    case SCRIPT_CHANNEL_RESET: {
        /* Upgrade, take one check-in off the wire without acking it, then
         * abort the first connection with an RST.  The agent's write of
         * that line succeeded, so only keeping it until the ack can bring
         * it back.  Later connections behave like SCRIPT_CHANNEL, so
         * whatever the agent kept goes up when it redials. */
        server_write(fd, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: " CA_COORD_PROTOCOL
                         "\r\nConnection: Upgrade\r\n\r\n");
        pthread_mutex_lock(&s->lock);
        int first = (s->connections == 1);
        pthread_mutex_unlock(&s->lock);
        if (first) {
            struct timeval tv = {2, 0};
            setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
            char in[CA_COORD_LINE_MAX];
            while (server_read_line(fd, in, sizeof(in)) && strncmp(in, "ci ", 3) != 0) {}
            struct linger lg = {1, 0};
            setsockopt(fd, SOL_SOCKET, SO_LINGER, &lg, sizeof(lg));
            break;
        }
        struct timeval tv = {0, (suseconds_t)200 * 1000};
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        while (!atomic_load(&s->stop)) {
            char in[CA_COORD_LINE_MAX];
            if (!server_read_line(fd, in, sizeof(in))) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) continue;
                break;
            }
            if (in[0]) server_note(s, in);
            if (!strncmp(in, "ci ", 3)) server_write(fd, "ack 0 0\n");
        }
        break;
    }
    }
}

static void *server_main(void *arg)
{
    test_server *s = arg;
    while (!atomic_load(&s->stop)) {
        struct pollfd pf = {.fd = s->fd, .events = POLLIN};
        if (poll(&pf, 1, 100) <= 0) continue;
        int fd = accept(s->fd, NULL, NULL);
        if (fd < 0) continue;
        pthread_mutex_lock(&s->lock);
        s->connections++;
        pthread_mutex_unlock(&s->lock);
        server_handle(s, fd);
        close(fd);
    }
    return NULL;
}

static test_server *server_start(server_script script)
{
    test_server *s = calloc(1, sizeof(*s));
    CHECK(s != NULL);
    if (!s) return NULL;
    s->script = script;
    pthread_mutex_init(&s->lock, NULL);
    s->fd = socket(AF_INET, SOCK_STREAM, 0);
    CHECK(s->fd >= 0);
    int one = 1;
    setsockopt(s->fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    struct sockaddr_in sin;
    memset(&sin, 0, sizeof(sin));
    sin.sin_family = AF_INET;
    sin.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    sin.sin_port = 0;
    CHECK(bind(s->fd, (struct sockaddr *)&sin, sizeof(sin)) == 0);
    CHECK(listen(s->fd, 8) == 0);
    socklen_t slen = sizeof(sin);
    CHECK(getsockname(s->fd, (struct sockaddr *)&sin, &slen) == 0);
    s->port = ntohs(sin.sin_port);
    CHECK(pthread_create(&s->thread, NULL, server_main, s) == 0);
    return s;
}

static void server_stop(test_server *s)
{
    if (!s) return;
    atomic_store(&s->stop, 1);
    shutdown(s->fd, SHUT_RDWR);
    pthread_join(s->thread, NULL);
    close(s->fd);
    pthread_mutex_destroy(&s->lock);
    free(s);
}

static void server_url(const test_server *s, char *out, size_t cap)
{
    snprintf(out, cap, "http://127.0.0.1:%d", s->port);
}

/* Produce real check-in lines for the server to replay. */
static int lane_lines(const ca_coord_ctx *ctx, const char *peer, char out[][CA_COORD_LINE_MAX],
                      int cap)
{
    ca_coord_state *st = NULL;
    CHECK(ca_coord_state_init(&st, ctx) == CA_OK);
    if (!st) return 0;
    ca_coord_lane_params p;
    ca_coord_lane_params_default(&p, peer);
    p.max_walkers = 8;
    p.checkin_every = 4;
    ca_coord_lane_result res;
    CHECK(ca_coord_lane_run(ctx, st, &p, NULL, NULL, NULL, NULL, &res) == CA_OK);
    int n = 0;
    size_t count = ca_coord_log_count(st);
    for (size_t i = 0; i < count && n < cap; i++) {
        uint64_t seq = 0;
        char who[CA_COORD_PEER_MAX];
        if (ca_coord_log_get(st, i, out[n], CA_COORD_LINE_MAX, who, sizeof(who), &seq)) n++;
    }
    ca_coord_state_free(st);
    return n;
}

/* An agent needs only a URL: the job comes down it. */
static void test_fetch_job_over_http(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 4242, 0, NULL);
    char url[64];

    test_server *s = server_start(SCRIPT_JOB);
    if (s) {
        char doc[CA_COORD_LINE_MAX];
        CHECK(ca_coord_job_encode(ca_coord_ctx_job(ctx), doc, sizeof(doc)) > 0);
        server_push_line(s, doc);
        server_url(s, url, sizeof(url));
        ca_coord_job got;
        CHECK(ca_coord_fetch_job(url, "tok", &got) == CA_OK);
        CHECK_EQ_U64(got.id, ca_coord_ctx_job(ctx)->id);
        /* The token really went out as a bearer header. */
        CHECK(server_heard(s, "Authorization: Bearer tok") == 1);
        CHECK(server_heard(s, "GET /v1/job") == 1);
        server_stop(s);
    }

    /* A refusal is an error, not a silent empty job. */
    s = server_start(SCRIPT_JOB_401);
    if (s) {
        server_url(s, url, sizeof(url));
        ca_coord_job got;
        CHECK(ca_coord_fetch_job(url, NULL, &got) == CA_ERR_INVALID);
        server_stop(s);
    }
    /* So is a 200 that does not carry a job document. */
    s = server_start(SCRIPT_JOB_GARBAGE);
    if (s) {
        server_url(s, url, sizeof(url));
        ca_coord_job got;
        CHECK(ca_coord_fetch_job(url, NULL, &got) == CA_ERR_INVALID);
        server_stop(s);
    }
    /* And a coordinator that is not there at all. */
    ca_coord_job got;
    CHECK(ca_coord_fetch_job("http://127.0.0.1:1", NULL, &got) != CA_OK);
    CHECK(ca_coord_fetch_job("https://example.com", NULL, &got) == CA_ERR_UNSUPPORTED);
    ca_coord_ctx_close(ctx);
}

/* The one-shot path: push what we hold, merge what comes back. */
static void test_sync_once_client(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 31337, 0, NULL);
    static char lines[8][CA_COORD_LINE_MAX];
    int n = lane_lines(ctx, "peer.0", lines, 8);
    CHECK(n > 0);

    test_server *s = server_start(SCRIPT_SYNC);
    if (s) {
        for (int i = 0; i < n && i < 4; i++) server_push_line(s, lines[i]);
        char url[64];
        server_url(s, url, sizeof(url));

        ca_coord_state *mine = NULL;
        CHECK(ca_coord_state_init(&mine, ctx) == CA_OK);
        uint64_t received = 0, rejected = 0;
        CHECK(ca_coord_sync_once(url, "tok", ctx, mine, &received, &rejected) == CA_OK);
        CHECK_EQ_U64(received, (uint64_t)s->push_count);
        CHECK_EQ_U64(rejected, 0);
        /* We sent our vector, and the request was a POST. */
        CHECK(server_heard(s, "POST /v1/sync") == 1);
        CHECK(server_heard(s, "vv") >= 1);

        /* Now that we hold those lines, a second sync pushes them. */
        received = 0;
        CHECK(ca_coord_sync_once(url, "tok", ctx, mine, &received, &rejected) == CA_OK);
        CHECK_EQ_U64(received, 0); /* nothing new: the merge is idempotent */
        CHECK(server_heard(s, "ci ") >= 1);
        ca_coord_state_free(mine);
        server_stop(s);
    }
    ca_coord_ctx_close(ctx);
}

/* Nothing published around a reset is lost: the agent redials and every
 * check-in still arrives.  The first connection reads a check-in and then
 * resets without acking it, which is the case a failed write does not
 * cover -- the bytes left this process, and the hub never merged them --
 * so an agent that lets go of a line on the write, rather than on the
 * ack, fails this. */
static void test_agent_requeues_unsent(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 8080, 0, NULL);
    static char lines[8][CA_COORD_LINE_MAX];
    int n = lane_lines(ctx, "other.0", lines, 8);
    CHECK(n > 0);

    test_server *s = server_start(SCRIPT_CHANNEL_RESET);
    if (!s) return;
    char url[64];
    server_url(s, url, sizeof(url));

    ca_coord_state *st = NULL;
    CHECK(ca_coord_state_init(&st, ctx) == CA_OK);
    ca_coord_agent *ag = NULL;
    CHECK(ca_coord_agent_start(&ag, url, "tok", "me.0", ctx, st) == CA_OK);

    /* Wait for the first connection, which is the one that gets reset. */
    for (int i = 0; i < 100; i++) {
        pthread_mutex_lock(&s->lock);
        int c = s->connections;
        pthread_mutex_unlock(&s->lock);
        if (c >= 1) break;
        struct timespec ts = {0, 20 * 1000000L};
        nanosleep(&ts, NULL);
    }

    /* Publish while that connection is dying.  Whichever of these the
     * agent fails to write, it must still deliver after the redial. */
    const int published = 4;
    for (int i = 0; i < published; i++) {
        ca_coord_checkin ci;
        CHECK(ca_coord_checkin_decode(&ci, lines[0]) == CA_OK);
        snprintf(ci.peer, sizeof(ci.peer), "me.0");
        ci.seq = 100 + (uint64_t)i;
        ca_coord_agent_publish(ag, &ci);
    }

    /* The agent redials and the queue drains, in order and in full. */
    int heard = 0;
    for (int i = 0; i < 300 && heard < published; i++) {
        struct timespec ts = {0, 20 * 1000000L};
        nanosleep(&ts, NULL);
        heard = server_heard(s, "ci ");
    }
    CHECK_EQ_U64((uint64_t)heard, (uint64_t)published);

    ca_coord_agent_stop(ag);
    ca_coord_state_free(st);
    server_stop(s);
    ca_coord_ctx_close(ctx);
}

/* A chunked answer carries exactly the same facts.  The hub sets a
 * Content-Length now, but it is not the only thing on the wire: Go
 * chunks any streamed body past its write buffer, and the nginx in
 * deploy/ can re-frame whatever the hub decided.  Read as payload, the
 * size lines corrupt or drop check-ins. */
static void test_sync_reads_chunked(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 31337, 0, NULL);
    static char lines[8][CA_COORD_LINE_MAX];
    int n = lane_lines(ctx, "peer.0", lines, 8);
    CHECK(n > 0);

    test_server *s = server_start(SCRIPT_SYNC_CHUNKED);
    if (s) {
        for (int i = 0; i < n && i < 4; i++) server_push_line(s, lines[i]);
        char url[64];
        server_url(s, url, sizeof(url));
        ca_coord_state *mine = NULL;
        CHECK(ca_coord_state_init(&mine, ctx) == CA_OK);
        uint64_t received = 0, rejected = 0;
        CHECK(ca_coord_sync_once(url, "tok", ctx, mine, &received, &rejected) == CA_OK);
        /* Every line, and none of them mangled into a rejection. */
        CHECK_EQ_U64(received, (uint64_t)s->push_count);
        CHECK_EQ_U64(rejected, 0);
        CHECK_EQ_U64((uint64_t)ca_coord_log_count(mine), (uint64_t)s->push_count);
        ca_coord_state_free(mine);
        server_stop(s);
    }
    ca_coord_ctx_close(ctx);
}

/* The reverse channel, from the agent's end. */
static void test_agent_channel(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 8080, 0, NULL);
    static char lines[8][CA_COORD_LINE_MAX];
    int n = lane_lines(ctx, "other.0", lines, 8);
    CHECK(n > 0);

    test_server *s = server_start(SCRIPT_CHANNEL);
    if (s) {
        for (int i = 0; i < n && i < 4; i++) server_push_line(s, lines[i]);
        char url[64];
        server_url(s, url, sizeof(url));

        ca_coord_state *st = NULL;
        CHECK(ca_coord_state_init(&st, ctx) == CA_OK);
        ca_coord_agent *ag = NULL;
        CHECK(ca_coord_agent_start(&ag, url, "tok", "me.0", ctx, st) == CA_OK);

        /* What the coordinator pushes is merged without being asked for:
         * that is the whole point of the channel. */
        int merged = 0;
        for (int i = 0; i < 100 && !merged; i++) {
            struct timespec ts = {0, 50 * 1000000L};
            nanosleep(&ts, NULL);
            ca_coord_agent_stats as;
            ca_coord_agent_stats_get(ag, &as);
            merged = as.received >= (uint64_t)s->push_count;
        }
        CHECK(merged == 1);
        CHECK_EQ_U64((uint64_t)ca_coord_log_count(st), (uint64_t)s->push_count);

        /* And what we publish goes up. */
        ca_coord_checkin ci;
        CHECK(ca_coord_checkin_decode(&ci, lines[0]) == CA_OK);
        snprintf(ci.peer, sizeof(ci.peer), "me.0");
        ci.seq = 99;
        ca_coord_agent_publish(ag, &ci);
        CHECK(ca_coord_agent_flush(ag, 5000) == 1);
        int heard = 0;
        for (int i = 0; i < 100 && !heard; i++) {
            struct timespec ts = {0, 50 * 1000000L};
            nanosleep(&ts, NULL);
            heard = server_heard(s, "ci ") >= 1;
        }
        CHECK(heard == 1);
        CHECK(server_heard(s, "hello ") == 1);

        ca_coord_agent_stats as;
        ca_coord_agent_stats_get(ag, &as);
        CHECK(as.connected == 1);
        CHECK(as.connects >= 1);
        CHECK(as.sent >= 1);
        CHECK_EQ_U64(as.rejected, 0);

        ca_coord_agent_stop(ag);
        ca_coord_state_free(st);
        server_stop(s);
    }
    ca_coord_ctx_close(ctx);
}

/*
 * A coordinator that goes away is an ordinary event -- a pod eviction, a
 * rolling restart -- so the agent redials instead of dying, and keeps
 * whatever it was told to publish meanwhile.
 */
static void test_agent_redials(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 555, 0, NULL);

    test_server *s = server_start(SCRIPT_HANGUP);
    if (s) {
        char url[64];
        server_url(s, url, sizeof(url));
        ca_coord_state *st = NULL;
        CHECK(ca_coord_state_init(&st, ctx) == CA_OK);
        ca_coord_agent *ag = NULL;
        CHECK(ca_coord_agent_start(&ag, url, NULL, "me.0", ctx, st) == CA_OK);
        int tries = 0;
        for (int i = 0; i < 60 && tries < 2; i++) {
            struct timespec ts = {0, 100 * 1000000L};
            nanosleep(&ts, NULL);
            pthread_mutex_lock(&s->lock);
            tries = s->connections;
            pthread_mutex_unlock(&s->lock);
        }
        CHECK(tries >= 2); /* it came back rather than giving up */
        ca_coord_agent_stats as;
        ca_coord_agent_stats_get(ag, &as);
        CHECK(as.connected == 0);
        CHECK(as.reconnects >= 1);
        CHECK(as.last_error[0] != 0); /* and said why */
        ca_coord_agent_stop(ag);
        ca_coord_state_free(st);
        server_stop(s);
    }

    /* A coordinator that refuses the upgrade is reported, not retried
     * into a hot loop. */
    s = server_start(SCRIPT_CHANNEL_REFUSED);
    if (s) {
        char url[64];
        server_url(s, url, sizeof(url));
        ca_coord_state *st = NULL;
        CHECK(ca_coord_state_init(&st, ctx) == CA_OK);
        ca_coord_agent *ag = NULL;
        CHECK(ca_coord_agent_start(&ag, url, NULL, "me.0", ctx, st) == CA_OK);
        int reported = 0;
        for (int i = 0; i < 60 && !reported; i++) {
            struct timespec ts = {0, 100 * 1000000L};
            nanosleep(&ts, NULL);
            ca_coord_agent_stats as;
            ca_coord_agent_stats_get(ag, &as);
            reported = as.last_error[0] != 0;
        }
        CHECK(reported == 1);
        ca_coord_agent_stop(ag);
        ca_coord_state_free(st);
        server_stop(s);
    }

    /* An https:// URL is refused at the door: there is no TLS here. */
    ca_coord_state *st = NULL;
    CHECK(ca_coord_state_init(&st, ctx) == CA_OK);
    ca_coord_agent *ag = NULL;
    CHECK(ca_coord_agent_start(&ag, "https://example.com", NULL, "me.0", ctx, st) ==
          CA_ERR_UNSUPPORTED);
    CHECK(ag == NULL);
    ca_coord_state_free(st);
    ca_coord_ctx_close(ctx);
}

/*
 * The tests that need a coordinator live with the coordinator, in
 * bindings/go/cmd/ca-coordinator: an end-to-end there starts the real
 * hub and runs real agents through this library's cgo binding, which
 * tests the pairing that actually ships rather than a C hub that does
 * not exist.  What stays here is everything that decides what is true,
 * none of which needs a socket.
 */

int main(void)
{
    signal(SIGPIPE, SIG_IGN);
    test_job_roundtrip();
    test_job_decode_bounds();
    test_negation_needs_a_curve();
    test_derivation_is_deterministic();
    test_walk_produces_verifiable_points();
    test_trails_are_reproducible();
    test_checkin_wire();
    test_merge_is_order_independent_and_idempotent();
    test_foreign_and_forged_are_refused();
    test_leases_expire_and_units_resume();
    test_sequence_numbers_and_deltas();
    test_two_lanes_merge_to_a_solution();
    test_url_parsing();
    test_fetch_job_over_http();
    test_sync_once_client();
    test_sync_reads_chunked();
    test_agent_channel();
    test_agent_requeues_unsent();
    test_agent_redials();
    TEST_MAIN_END();
}
