/* Tests for the distributed (van Oorschot-Wiener) rho protocol.
 *
 * The properties under test are the ones a fleet depends on and that a
 * single-process solver never has to have: that units are replayable, that
 * points from different units merge, that the merger rejects anything it
 * cannot verify, and that the wire format round-trips.  The "does rho
 * work" question is test_rho's.
 */
#include "test_fixtures.h"
#include "cryptanalysis/ca_dist.h"

typedef struct collector {
    ca_dist_point *pts;
    size_t count, cap;
    size_t limit; /* stop the walk after this many (0 = no limit) */
} collector;

static ca_status collect(void *ctx, const ca_dist_point *pt)
{
    collector *c = ctx;
    if (c->count == c->cap) {
        size_t cap = c->cap ? c->cap * 2 : 256;
        ca_dist_point *p = realloc(c->pts, cap * sizeof(*p));
        if (!p) return CA_ERR_NOMEM;
        c->pts = p;
        c->cap = cap;
    }
    c->pts[c->count++] = *pt;
    if (c->limit && c->count >= c->limit) return CA_ERR_LIMIT;
    return CA_OK;
}

static void collector_free(collector *c)
{
    free(c->pts);
    memset(c, 0, sizeof(*c));
}

/* Walk one unit to completion, returning its points. */
static ca_status walk_unit(const ca_group *g, const ca_elem *base, const ca_elem *target,
                           const ca_dist_campaign *c, uint64_t id, uint64_t steps, uint32_t walks,
                           collector *out)
{
    ca_dist_unit u = {0};
    u.id = id;
    u.walks = walks;
    u.max_steps = steps;
    ca_stats st = {0};
    return ca_dist_walk(g, base, target, c, &u, collect, out, &st);
}

/* ---- the properties ---------------------------------------------------- */

/* A unit run twice produces exactly the same points, on any machine.
 *
 * This is what lets a scheduler hand a unit to a second agent when it
 * cannot tell whether the first one died: the duplicate work is wasted, but
 * the corpus is unchanged, so at-least-once delivery needs no dedupe
 * protocol beyond the merger's own. */
static void test_units_are_replayable(const ca_group *g, const ca_elem *gen, const ca_elem *h,
                                      const ca_dist_campaign *c)
{
    collector a = {0}, b = {0};
    CHECK(walk_unit(g, gen, h, c, 7, 20000, 8, &a) == CA_OK);
    CHECK(walk_unit(g, gen, h, c, 7, 20000, 8, &b) == CA_OK);
    CHECK(a.count > 0);
    CHECK_EQ_U64(a.count, b.count);
    int same = 1;
    for (size_t i = 0; i < a.count && i < b.count; i++)
        same &= a.pts[i].w0 == b.pts[i].w0 && a.pts[i].w1 == b.pts[i].w1 &&
                a.pts[i].a == b.pts[i].a && a.pts[i].b == b.pts[i].b;
    CHECK(same);
    printf("replay: %zu points, identical\n", a.count);
    collector_free(&a);
    collector_free(&b);
}

/* Two different units produce different trails. */
static void test_units_differ(const ca_group *g, const ca_elem *gen, const ca_elem *h,
                              const ca_dist_campaign *c)
{
    collector a = {0}, b = {0};
    CHECK(walk_unit(g, gen, h, c, 1, 20000, 8, &a) == CA_OK);
    CHECK(walk_unit(g, gen, h, c, 2, 20000, 8, &b) == CA_OK);
    CHECK(a.count > 0 && b.count > 0);
    int identical = a.count == b.count;
    for (size_t i = 0; identical && i < a.count; i++)
        identical &= a.pts[i].w0 == b.pts[i].w0 && a.pts[i].a == b.pts[i].a;
    CHECK(!identical);
    collector_free(&a);
    collector_free(&b);
}

/* The whole point of the protocol: points from units that never shared a
 * process still collide, and the collision yields the planted secret.
 *
 * The unit budget is deliberately a fraction of the expected work, so the
 * answer cannot come from one unit finding its own collision -- which is
 * just ca_rho_solve with extra steps.  It has to come from two units that
 * shared nothing but the campaign, which is what a fleet is.  Everything
 * here is deterministic (fixed campaign seed, fixed unit ids, a PRNG with
 * no entropy from the environment), so `solvedAfter` is a fixed number for
 * these parameters rather than something that might flake.
 */
static void test_units_merge_into_a_solution(const ca_group *g, const ca_elem *gen, uint64_t x,
                                             uint64_t unitSteps, int dpBits)
{
    ca_elem h;
    fx_instance(g, gen, x, &h);
    ca_dist_campaign c;
    ca_dist_campaign_default(&c);
    c.seed = 424242;
    c.dp_bits = dpBits;
    CHECK(ca_dist_resolve(g, &c) == CA_OK);

    ca_dist_merger *m = NULL;
    CHECK(ca_dist_merger_new(&m, g, gen, &h, &c, 0) == CA_OK);
    uint64_t got = 0;
    size_t totalPoints = 0;
    int solvedAfter = 0;
    for (uint64_t id = 0; id < 512 && !ca_dist_merger_solved(m, &got); id++) {
        collector pts = {0};
        CHECK(walk_unit(g, gen, &h, &c, id, unitSteps, 16, &pts) == CA_OK);
        size_t acc = 0, dup = 0, rej = 0;
        CHECK(ca_dist_merger_add(m, pts.pts, pts.count, &acc, &dup, &rej) == CA_OK);
        CHECK_EQ_U64(rej, 0); /* the walker's own points always verify */
        totalPoints += pts.count;
        solvedAfter = (int)id + 1;
        collector_free(&pts);
    }
    CHECK(ca_dist_merger_solved(m, &got));
    CHECK_EQ_U64(got, x);
    CHECK(solvedAfter > 1); /* a cross-unit collision, not a local one */
    printf("merge:  solved after %d units x %" PRIu64 " steps, %zu points, %zu stored\n",
           solvedAfter, unitSteps, totalPoints, ca_dist_merger_size(m));
    ca_dist_merger_free(m);
}

/* The merger verifies, so a fabricated point cannot enter the corpus.
 *
 * Three ways to be wrong, all of which a buggy agent produces sooner or
 * later and a hostile one produces on purpose: exponents that do not match
 * the point, a point that is not distinguished, and coordinates that are
 * not on the curve at all. */
static void test_merger_rejects_bad_points(const ca_group *g, const ca_elem *gen, uint64_t x)
{
    ca_elem h;
    fx_instance(g, gen, x, &h);
    ca_dist_campaign c;
    ca_dist_campaign_default(&c);
    c.seed = 5150;
    c.dp_bits = 4;
    CHECK(ca_dist_resolve(g, &c) == CA_OK);

    collector pts = {0};
    pts.limit = 32;
    ca_status rc = walk_unit(g, gen, &h, &c, 3, 1000000, 8, &pts);
    CHECK(rc == CA_OK || rc == CA_ERR_LIMIT);
    CHECK(pts.count > 2);

    ca_dist_merger *m = NULL;
    CHECK(ca_dist_merger_new(&m, g, gen, &h, &c, 0) == CA_OK);

    /* Honest points go in. */
    size_t acc = 0, dup = 0, rej = 0;
    CHECK(ca_dist_merger_add(m, pts.pts, 1, &acc, &dup, &rej) == CA_OK);
    CHECK_EQ_U64(acc, 1);
    CHECK_EQ_U64(rej, 0);

    /* The same point again: a duplicate, not a collision. */
    CHECK(ca_dist_merger_add(m, pts.pts, 1, &acc, &dup, &rej) == CA_OK);
    CHECK_EQ_U64(dup, 1);
    CHECK_EQ_U64(acc, 0);
    CHECK(!ca_dist_merger_solved(m, NULL));

    /* Exponents that do not produce the point. */
    ca_dist_point bad = pts.pts[1];
    bad.a ^= 1;
    CHECK(ca_dist_merger_add(m, &bad, 1, &acc, &dup, &rej) == CA_OK);
    CHECK_EQ_U64(rej, 1);

    /* Coordinates that are not a group element. */
    bad = pts.pts[1];
    bad.w0 = g->p - 1;
    bad.w1 = g->p - 2;
    CHECK(ca_dist_merger_add(m, &bad, 1, &acc, &dup, &rej) == CA_OK);
    CHECK_EQ_U64(rej, 1);

    /* Exponents out of range. */
    bad = pts.pts[1];
    bad.b = g->order;
    CHECK(ca_dist_merger_add(m, &bad, 1, &acc, &dup, &rej) == CA_OK);
    CHECK_EQ_U64(rej, 1);

    /* And none of that left a solution behind. */
    CHECK(!ca_dist_merger_solved(m, NULL));
    CHECK_EQ_U64(ca_dist_merger_size(m), 1);
    ca_dist_merger_free(m);
    collector_free(&pts);
}

/* A campaign id changes when anything the walk depends on changes, because
 * two agents with different ids are walking different functions and their
 * points cannot merge. */
static void test_campaign_id_covers_the_walk(const ca_group *g, const ca_elem *gen)
{
    ca_elem h;
    fx_instance(g, gen, 12345, &h);
    ca_dist_campaign a;
    ca_dist_campaign_default(&a);
    a.seed = 1;
    a.r = 32;
    a.dp_bits = 8;
    uint64_t base = ca_dist_campaign_id(g, gen, &h, &a);
    CHECK(base != 0);
    CHECK_EQ_U64(base, ca_dist_campaign_id(g, gen, &h, &a));

    ca_dist_campaign b = a;
    b.seed = 2;
    CHECK(ca_dist_campaign_id(g, gen, &h, &b) != base);
    b = a;
    b.r = 64;
    CHECK(ca_dist_campaign_id(g, gen, &h, &b) != base);
    b = a;
    b.dp_bits = 9;
    CHECK(ca_dist_campaign_id(g, gen, &h, &b) != base);

    ca_elem h2;
    fx_instance(g, gen, 12346, &h2);
    CHECK(ca_dist_campaign_id(g, gen, &h2, &a) != base);
}

/* Auto-resolution has to be a pure function of the group and the campaign:
 * two agents that resolve independently must get the same walk. */
static void test_resolution_is_deterministic(const ca_group *g)
{
    ca_dist_campaign a, b;
    ca_dist_campaign_default(&a);
    a.seed = 99;
    b = a;
    CHECK(ca_dist_resolve(g, &a) == CA_OK);
    CHECK(ca_dist_resolve(g, &b) == CA_OK);
    CHECK_EQ_U64(a.r, b.r);
    CHECK_EQ_U64((uint64_t)a.dp_bits, (uint64_t)b.dp_bits);
    /* Resolving twice changes nothing. */
    ca_dist_campaign again = a;
    CHECK(ca_dist_resolve(g, &again) == CA_OK);
    CHECK_EQ_U64(again.r, a.r);
    CHECK_EQ_U64((uint64_t)again.dp_bits, (uint64_t)a.dp_bits);
    /* A campaign with no seed gets one, and it is not zero. */
    ca_dist_campaign fresh;
    ca_dist_campaign_default(&fresh);
    CHECK(ca_dist_resolve(g, &fresh) == CA_OK);
    CHECK(fresh.seed != 0);
    CHECK(ca_dist_expected_points(g, &a) > 0.0);
}

static void test_wire_format(void)
{
    ca_dist_point p = {0x0123456789ABCDEFULL, 0xFEDCBA9876543210ULL, 42, 0xDEADBEEFCAFEULL};
    unsigned char buf[CA_DIST_POINT_BYTES];
    ca_dist_point_encode(buf, &p);
    /* Little-endian, fixed width: the first byte is the low byte of w0. */
    CHECK_EQ_U64(buf[0], 0xEF);
    CHECK_EQ_U64(buf[7], 0x01);
    ca_dist_point q = {0, 0, 0, 0};
    ca_dist_point_decode(&q, buf);
    CHECK_EQ_U64(q.w0, p.w0);
    CHECK_EQ_U64(q.w1, p.w1);
    CHECK_EQ_U64(q.a, p.a);
    CHECK_EQ_U64(q.b, p.b);
}

/* A sink that refuses stops the walk and its status comes back to the
 * caller: that is how an agent whose upload queue is full stops walking
 * rather than filling memory. */
static ca_status refuse(void *ctx, const ca_dist_point *pt)
{
    (void)pt;
    (*(int *)ctx)++;
    return CA_ERR_LIMIT;
}

static void test_sink_can_stop_the_walk(const ca_group *g, const ca_elem *gen)
{
    ca_elem h;
    fx_instance(g, gen, 777, &h);
    ca_dist_campaign c;
    ca_dist_campaign_default(&c);
    c.seed = 8;
    c.dp_bits = 2;
    CHECK(ca_dist_resolve(g, &c) == CA_OK);
    ca_dist_unit u = {0};
    u.id = 5;
    u.walks = 4;
    u.max_steps = 1000000;
    int calls = 0;
    ca_stats st = {0};
    CHECK(ca_dist_walk(g, gen, &h, &c, &u, refuse, &calls, &st) == CA_ERR_LIMIT);
    CHECK_EQ_U64(calls, 1);
    CHECK(st.group_ops > 0);
}

/* max_points is the other stop: a unit that is told to produce N points
 * produces at most N. */
static void test_point_budget(const ca_group *g, const ca_elem *gen)
{
    ca_elem h;
    fx_instance(g, gen, 31337, &h);
    ca_dist_campaign c;
    ca_dist_campaign_default(&c);
    c.seed = 11;
    c.dp_bits = 3;
    CHECK(ca_dist_resolve(g, &c) == CA_OK);
    ca_dist_unit u = {0};
    u.id = 9;
    u.walks = 8;
    u.max_steps = 10000000;
    u.max_points = 20;
    collector pts = {0};
    ca_stats st = {0};
    CHECK(ca_dist_walk(g, gen, &h, &c, &u, collect, &pts, &st) == CA_OK);
    CHECK(pts.count >= 20); /* the batch in flight finishes */
    CHECK(pts.count < 20 + 8 + 1);
    CHECK_EQ_U64(st.iterations, pts.count);
    collector_free(&pts);
}

int main(void)
{
    test_wire_format();

    /* Z_p^* subgroup of prime order ~2^30 */
    ca_group zp;
    ca_elem zgen;
    fx_zp_safe(&zp, &zgen, 2000000579ULL);
    test_resolution_is_deterministic(&zp);
    test_campaign_id_covers_the_walk(&zp, &zgen);
    test_sink_can_stop_the_walk(&zp, &zgen);
    test_point_budget(&zp, &zgen);
    test_units_merge_into_a_solution(&zp, &zgen, 918273645ULL % zp.order, 8000, 6);

    /* Elliptic curve, prime-order subgroup */
    ca_group ec;
    ca_elem egen;
    fx_ec(&ec, &egen, 1000000007ULL, 3, 11);
    printf("ec order %" PRIu64 "\n", ec.order);
    ca_dist_campaign c;
    ca_dist_campaign_default(&c);
    c.seed = 31415926;
    c.dp_bits = 7;
    CHECK(ca_dist_resolve(&ec, &c) == CA_OK);
    ca_elem h;
    fx_instance(&ec, &egen, 123456789ULL % ec.order, &h);
    test_units_are_replayable(&ec, &egen, &h, &c);
    test_units_differ(&ec, &egen, &h, &c);
    test_merger_rejects_bad_points(&ec, &egen, 55555ULL % ec.order);
    test_units_merge_into_a_solution(&ec, &egen, 123456789ULL % ec.order, 3000, 5);

    TEST_MAIN_END();
}
