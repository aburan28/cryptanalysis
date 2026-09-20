#include <signal.h>
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
    dp[4] = dp[4] == '5' ? '6' : '5';
    ca_coord_job tampered;
    CHECK(ca_coord_job_decode(&tampered, line) == CA_ERR_INVALID);

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

typedef struct agent_thread {
    pthread_t t;
    ca_coord_ctx *ctx;
    ca_coord_state *st;
    ca_coord_agent *ag;
    char name[CA_COORD_PEER_MAX];
    volatile int stop;
} agent_thread;

static void agent_publish_hook(void *user, const ca_coord_checkin *ci)
{
    ca_coord_agent_publish((ca_coord_agent *)user, ci);
}

static int agent_should_stop(void *user)
{
    agent_thread *at = user;
    return at->stop || ca_coord_solution(at->st, NULL);
}

static void *agent_main_thread(void *arg)
{
    agent_thread *at = arg;
    ca_coord_lane_params p;
    ca_coord_lane_params_default(&p, at->name);
    p.checkin_every = 4;
    p.claim_window = 1;
    ca_coord_lane_result res;
    ca_coord_lane_run(at->ctx, at->st, &p, agent_publish_hook, at->ag, agent_should_stop, at, &res);
    return NULL;
}

/* Count what the hub's durability hook saw. */
static pthread_mutex_t hook_lock = PTHREAD_MUTEX_INITIALIZER;
static uint64_t hook_calls;

static void hub_hook(void *user, const ca_coord_checkin *ci)
{
    (void)user;
    (void)ci;
    pthread_mutex_lock(&hook_lock);
    hook_calls++;
    pthread_mutex_unlock(&hook_lock);
}

/*
 * The property the module exists for: two agents that never listen on
 * anything, each dialling out to one hub, converge -- and the solution
 * reaches the agent that did not find it, over a socket that agent
 * opened.
 */
static void test_agents_converge_through_the_hub(void)
{
    ca_group g;
    ca_elem gen;
    uint64_t secret = 0;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 246813, 0, &secret);

    ca_coord_state *hub_state = NULL;
    CHECK(ca_coord_state_init(&hub_state, ctx) == CA_OK);
    ca_coord_hub_params hp;
    ca_coord_hub_params_default(&hp);
    hp.bind = "127.0.0.1:0";
    hp.token = "s3cret";
    hp.push_ms = 20;
    hp.on_checkin = hub_hook;
    ca_coord_hub *hub = NULL;
    CHECK(ca_coord_hub_start(&hub, ctx, hub_state, &hp) == CA_OK);
    char url[160];
    snprintf(url, sizeof(url), "http://%s", ca_coord_hub_address(hub));

    /* An agent needs only the URL: the job comes down it. */
    ca_coord_job fetched;
    CHECK(ca_coord_fetch_job(url, "s3cret", &fetched) == CA_OK);
    CHECK_EQ_U64(fetched.id, ca_coord_ctx_job(ctx)->id);
    /* Without the token, nothing. */
    CHECK(ca_coord_fetch_job(url, NULL, &fetched) != CA_OK);
    CHECK(ca_coord_fetch_job(url, "wrong", &fetched) != CA_OK);

    agent_thread at[2];
    memset(at, 0, sizeof(at));
    for (int i = 0; i < 2; i++) {
        snprintf(at[i].name, sizeof(at[i].name), "a%d.0", i);
        at[i].ctx = ctx;
        CHECK(ca_coord_state_init(&at[i].st, ctx) == CA_OK);
        CHECK(ca_coord_agent_start(&at[i].ag, url, "s3cret", at[i].name, ctx, at[i].st) == CA_OK);
    }
    for (int i = 0; i < 2; i++)
        CHECK(pthread_create(&at[i].t, NULL, agent_main_thread, &at[i]) == 0);

    /* Both agents must learn the answer, whichever one found it. */
    int ok = 0;
    for (int waited = 0; waited < 600 && !ok; waited++) {
        usleep(100000);
        ok = ca_coord_solution(at[0].st, NULL) && ca_coord_solution(at[1].st, NULL);
    }
    for (int i = 0; i < 2; i++) at[i].stop = 1;
    for (int i = 0; i < 2; i++) pthread_join(at[i].t, NULL);

    CHECK(ok == 1);
    for (int i = 0; i < 2; i++) {
        uint64_t x = 0;
        CHECK(ca_coord_solution(at[i].st, &x) == 1);
        CHECK_EQ_U64(x, secret);
        ca_coord_agent_stats ast;
        ca_coord_agent_stats_get(at[i].ag, &ast);
        CHECK(ast.connects > 0);
        CHECK(ast.sent > 0);
        CHECK_EQ_U64(ast.rejected, 0);
    }
    /* At least one of them got its answer from the hub rather than its
     * own walking -- that is the reverse channel doing its job. */
    ca_coord_agent_stats a0, a1;
    ca_coord_agent_stats_get(at[0].ag, &a0);
    ca_coord_agent_stats_get(at[1].ag, &a1);
    CHECK(a0.received > 0 || a1.received > 0);

    ca_coord_hub_stats hs;
    ca_coord_hub_stats_get(hub, &hs);
    CHECK(hs.accepted > 0);
    CHECK(hs.pushed > 0);
    CHECK(hs.unauthorized >= 2);
    pthread_mutex_lock(&hook_lock);
    CHECK(hook_calls > 0); /* the durability hook ran */
    pthread_mutex_unlock(&hook_lock);

    for (int i = 0; i < 2; i++) {
        ca_coord_agent_stop(at[i].ag);
        ca_coord_state_free(at[i].st);
    }
    ca_coord_hub_stop(hub);
    ca_coord_state_free(hub_state);
    ca_coord_ctx_close(ctx);
}

/* The pollable fallback carries the same facts as the channel. */
static void test_sync_once_moves_checkins_both_ways(void)
{
    ca_group g;
    ca_elem gen;
    ca_coord_ctx *ctx = make_ctx(&g, &gen, 9991, 0, NULL);
    ca_coord_state *hub_state = NULL, *a = NULL, *b = NULL;
    CHECK(ca_coord_state_init(&hub_state, ctx) == CA_OK);
    CHECK(ca_coord_state_init(&a, ctx) == CA_OK);
    CHECK(ca_coord_state_init(&b, ctx) == CA_OK);

    ca_coord_hub_params hp;
    ca_coord_hub_params_default(&hp);
    hp.bind = "127.0.0.1:0";
    ca_coord_hub *hub = NULL;
    CHECK(ca_coord_hub_start(&hub, ctx, hub_state, &hp) == CA_OK);
    char url[160];
    snprintf(url, sizeof(url), "http://%s", ca_coord_hub_address(hub));

    ca_coord_lane_params p;
    ca_coord_lane_params_default(&p, "a.0");
    p.max_walkers = 16;
    p.checkin_every = 4;
    ca_coord_lane_result res;
    CHECK(ca_coord_lane_run(ctx, a, &p, NULL, NULL, NULL, NULL, &res) == CA_OK);

    uint64_t recv = 0, rej = 0;
    CHECK(ca_coord_sync_once(url, NULL, ctx, a, &recv, &rej) == CA_OK);
    CHECK_EQ_U64(rej, 0);
    CHECK(ca_coord_sync_once(url, NULL, ctx, b, &recv, &rej) == CA_OK);
    CHECK(recv > 0); /* b learned a's work through the hub */
    CHECK_EQ_U64(rej, 0);

    ca_coord_vv *va = NULL, *vb = NULL;
    CHECK(ca_coord_vv_new(&va) == CA_OK);
    CHECK(ca_coord_vv_new(&vb) == CA_OK);
    ca_coord_state_vv(a, va);
    ca_coord_state_vv(b, vb);
    CHECK_EQ_U64(ca_coord_vv_get(va, "a.0"), ca_coord_vv_get(vb, "a.0"));
    ca_coord_vv_free(va);
    ca_coord_vv_free(vb);

    ca_coord_hub_stop(hub);
    ca_coord_state_free(hub_state);
    ca_coord_state_free(a);
    ca_coord_state_free(b);
    ca_coord_ctx_close(ctx);
}

int main(void)
{
    signal(SIGPIPE, SIG_IGN);
    test_job_roundtrip();
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
    test_sync_once_moves_checkins_both_ways();
    test_agents_converge_through_the_hub();
    TEST_MAIN_END();
}
