/*
 * Width-2 tau-NAF for E: y^2 = x^3 + b over a prime field, p = 1 (mod 3).
 *
 * Xu--Yu--Han--Lu, "On Efficient Computations of y^2=x^3+b/Fp for Primes
 * p=1 (mod 3)", Proposition 3.1 supplies the Jacobian tau formula.  We use
 * its unit orbit {+/-1,+/-omega,+/-omega^2} as the width-2 digit set.  The
 * scalar is first reduced to a short pair in Z[omega] by exact Euclidean
 * lattice arithmetic; this is deliberately independent of the paper's
 * 256-bit fixed-width reduction formula.  All field values are Montgomery
 * residues, matching group_ec.c.
 */
#include "ca_internal.h"
#include "cryptanalysis/ca_group.h"
#include "ec_tau_internal.h"
#include "generated/tau4_residue_atlas.h"

typedef __int128 ca_i128;

typedef struct tau_jac {
    uint64_t x, y, z;
} tau_jac;

typedef struct tau_vec {
    ca_i128 x, y;
} tau_vec;

static inline uint64_t fa(const ca_group *g, uint64_t x, uint64_t y)
{
    return ca_addmod(x, y, g->p);
}
static inline uint64_t fs(const ca_group *g, uint64_t x, uint64_t y)
{
    return ca_submod(x, y, g->p);
}
static inline uint64_t fm(const ca_group *g, uint64_t x, uint64_t y)
{
    return ca_mont_mul(&g->mont, x, y);
}
static inline uint64_t fq(const ca_group *g, uint64_t x) { return ca_mont_sqr(&g->mont, x); }
static inline uint64_t f2(const ca_group *g, uint64_t x) { return fa(g, x, x); }
static inline uint64_t f3(const ca_group *g, uint64_t x) { return fa(g, f2(g, x), x); }
static inline uint64_t f4(const ca_group *g, uint64_t x) { return f2(g, f2(g, x)); }
static inline uint64_t f8(const ca_group *g, uint64_t x) { return f2(g, f4(g, x)); }

static tau_jac jac_double(const ca_group *g, tau_jac p)
{
    if (!p.z || !p.y) return (tau_jac){0, g->mont.r1, 0};
    uint64_t A = fq(g, p.x), B = fq(g, p.y), C = fq(g, B);
    uint64_t D = f2(g, fs(g, fs(g, fq(g, fa(g, p.x, B)), A), C));
    uint64_t E = f3(g, A), F = fq(g, E);
    tau_jac r;
    r.x = fs(g, F, f2(g, D));
    r.y = fs(g, fm(g, E, fs(g, D, r.x)), f8(g, C));
    r.z = f2(g, fm(g, p.y, p.z));
    return r;
}

/* Proposition 3.1, equation (8): tau(P) = P - omega(P).  It is an
 * isogeny of degree 3, so X=0 (the rational 3-torsion kernel) maps to O. */
static tau_jac jac_tau(const ca_group *g, tau_jac p, uint64_t one_minus_beta)
{
    if (!p.z || !p.x) return (tau_jac){0, g->mont.r1, 0};
    uint64_t x3 = fm(g, fq(g, p.x), p.x);
    uint64_t y2 = fq(g, p.y);
    tau_jac r;
    r.x = fs(g, f4(g, y2), f3(g, x3));
    r.y = fm(g, p.y, fs(g, f3(g, x3), f2(g, r.x)));
    r.z = fm(g, fm(g, one_minus_beta, p.x), p.z);
    return r;
}

static tau_jac jac_triple(const ca_group *g, tau_jac p)
{
    if (!p.z || !p.x) return (tau_jac){0, g->mont.r1, 0};
    uint64_t x3 = fm(g, fq(g, p.x), p.x), y2 = fq(g, p.y);
    uint64_t tx = fs(g, f4(g, y2), f3(g, x3));
    uint64_t ty = fm(g, p.y, fs(g, f3(g, x3), f2(g, tx)));
    uint64_t tx3 = fm(g, fq(g, tx), tx), ty2 = fq(g, ty);
    tau_jac r;
    r.x = fs(g, f4(g, ty2), f3(g, tx3));
    r.y = fm(g, ty, fs(g, f3(g, tx3), f2(g, r.x)));
    r.z = f3(g, fm(g, tx, fm(g, p.x, p.z)));
    return r;
}

static tau_jac jac_add_mixed(const ca_group *g, tau_jac p, const ca_elem *q)
{
    if (!p.z) return (tau_jac){q->w[0], q->w[1], g->mont.r1};
    uint64_t zz = fq(g, p.z);
    uint64_t u = fm(g, q->w[0], zz);
    uint64_t s = fm(g, q->w[1], fm(g, p.z, zz));
    uint64_t h = fs(g, u, p.x), v = fs(g, s, p.y);
    if (!h) {
        if (!v) return jac_double(g, p);
        return (tau_jac){0, g->mont.r1, 0};
    }
    uint64_t hh = fq(g, h), hhh = fm(g, h, hh), xhh = fm(g, p.x, hh);
    tau_jac r;
    r.x = fs(g, fs(g, fq(g, v), hhh), f2(g, xhh));
    r.y = fs(g, fm(g, v, fs(g, xhh, r.x)), fm(g, p.y, hhh));
    r.z = fm(g, p.z, h);
    return r;
}

static tau_jac jac_add(const ca_group *g, tau_jac p, tau_jac q)
{
    if (!p.z) return q;
    if (!q.z) return p;
    uint64_t z1z1 = fq(g, p.z), z2z2 = fq(g, q.z);
    uint64_t u1 = fm(g, p.x, z2z2), u2 = fm(g, q.x, z1z1);
    uint64_t s1 = fm(g, p.y, fm(g, q.z, z2z2));
    uint64_t s2 = fm(g, q.y, fm(g, p.z, z1z1));
    uint64_t h = fs(g, u2, u1), v = fs(g, s2, s1);
    if (!h) {
        if (!v) return jac_double(g, p);
        return (tau_jac){0, g->mont.r1, 0};
    }
    uint64_t hh = fq(g, h), hhh = fm(g, h, hh), u1hh = fm(g, u1, hh);
    tau_jac r;
    r.x = fs(g, fs(g, fq(g, v), hhh), f2(g, u1hh));
    r.y = fs(g, fm(g, v, fs(g, u1hh, r.x)), fm(g, s1, hhh));
    r.z = fm(g, h, fm(g, p.z, q.z));
    return r;
}

static void jac_to_affine(const ca_group *g, ca_elem *r, tau_jac p)
{
    if (!p.z) {
        *r = (ca_elem){{0, 0, 1, 0}};
        return;
    }
    uint64_t iz = ca_mont_inv(&g->mont, p.z);
    uint64_t iz2 = fq(g, iz);
    r->w[0] = fm(g, p.x, iz2);
    r->w[1] = fm(g, p.y, fm(g, iz2, iz));
    r->w[2] = r->w[3] = 0;
}

/* Normalize up to 18 projective seed points with one inversion.  Replacing
 * zero Z by one in the inversion product keeps subgroup edge cases valid. */
static void jac_batch_to_affine(const ca_group *g, ca_elem *out, const tau_jac *in, size_t n)
{
    uint64_t zs[18], prefixes[18], product = g->mont.r1;
    for (size_t i = 0; i < n; i++) {
        zs[i] = in[i].z ? in[i].z : g->mont.r1;
        product = fm(g, product, zs[i]);
        prefixes[i] = product;
    }
    uint64_t inv = ca_mont_inv(&g->mont, product);
    for (size_t i = n; i-- > 0;) {
        uint64_t invz = fm(g, inv, i ? prefixes[i - 1] : g->mont.r1);
        inv = fm(g, inv, zs[i]);
        if (!in[i].z) {
            out[i] = (ca_elem){{0, 0, 1, 0}};
            continue;
        }
        uint64_t invz2 = fq(g, invz);
        out[i].w[0] = fm(g, in[i].x, invz2);
        out[i].w[1] = fm(g, in[i].y, fm(g, invz2, invz));
        out[i].w[2] = out[i].w[3] = 0;
    }
}

int ca_ec_triple_j0(const ca_group *g, ca_elem *r, const ca_elem *a)
{
    if (!g || !r || !a || g->kind != CA_GROUP_EC || g->a != 0 || g->b == 0 || g->p % 3 != 1)
        return 0;
    if (a->w[2]) {
        *r = *a;
        return 1;
    }
    jac_to_affine(g, r, jac_triple(g, (tau_jac){a->w[0], a->w[1], g->mont.r1}));
    return 1;
}

static ca_i128 iabs128(ca_i128 a) { return a < 0 ? -a : a; }

static ca_i128 round_div(ca_i128 a, ca_i128 b)
{
    if (b < 0) {
        a = -a;
        b = -b;
    }
    return a < 0 ? -((-a + b / 2) / b) : (a + b / 2) / b;
}

/* Consecutive extended-Euclid remainders give an exact basis for
 * {(u,v): u + v*lambda = 0 (mod n)}.  Round the rational coordinates of
 * (k,0), then check nearby lattice points for a shorter representative.
 * All products here fit signed 128 bits for 64-bit n: at the sqrt(n)
 * crossing, the Euclidean coefficients are O(sqrt(n)). */
static int make_lattice(uint64_t n, uint64_t lambda, tau_vec *v1, tau_vec *v2, ca_i128 *det)
{
    if (n < 5 || lambda <= 1 || lambda >= n) return 0;
    ca_i128 r0 = n, r1 = lambda, t0 = 0, t1 = 1;
    uint64_t root = ca_isqrt(n);
    while (r1 > root) {
        ca_i128 q = r0 / r1;
        ca_i128 r2 = r0 - q * r1, t2 = t0 - q * t1;
        r0 = r1;
        r1 = r2;
        t0 = t1;
        t1 = t2;
        if (!r1) return 0;
    }
    *v1 = (tau_vec){r1, -t1};
    *v2 = (tau_vec){r0, -t0};
    *det = v1->x * v2->y - v2->x * v1->y;
    return *det == (ca_i128)n || *det == -(ca_i128)n;
}

static void reduce_with_lattice(tau_vec v1, tau_vec v2, ca_i128 det, uint64_t k, ca_i128 *out_a,
                                ca_i128 *out_b)
{
    ca_i128 u0 = round_div((ca_i128)k * v2.y, det);
    ca_i128 v0 = round_div(-(ca_i128)k * v1.y, det);
    ca_i128 best = -1, bx = 0, by = 0;
    for (int du = -2; du <= 2; du++) {
        for (int dv = -2; dv <= 2; dv++) {
            ca_i128 u = u0 + du, v = v0 + dv;
            ca_i128 x = (ca_i128)k - u * v1.x - v * v2.x;
            ca_i128 y = -u * v1.y - v * v2.y;
            ca_i128 score = iabs128(x) + iabs128(y);
            if (best < 0 || score < best) {
                best = score;
                bx = x;
                by = y;
            }
        }
    }
    /* omega = 1 - tau, hence x + y*omega = (x+y) - y*tau. */
    *out_a = bx + by;
    *out_b = -by;
}

static int reduce_scalar(uint64_t n, uint64_t lambda, uint64_t k, ca_i128 *out_a, ca_i128 *out_b)
{
    tau_vec v1, v2;
    ca_i128 det;
    if (!make_lattice(n, lambda, &v1, &v2, &det)) return 0;
    reduce_with_lattice(v1, v2, det, k, out_a, out_b);
    return 1;
}

static unsigned residue3(ca_i128 x)
{
    ca_i128 r = x % 3;
    return (unsigned)(r < 0 ? r + 3 : r);
}

/* Unit representatives modulo tau^2 ~ 3.  Digit encoding is +/-(1,omega,
 * omega^2): 1,2,3 and -1,-2,-3. */
static int digit_for(ca_i128 a, ca_i128 b)
{
    unsigned x = residue3(a), y = residue3(b);
    if (x == 1) return y == 0 ? 1 : (y == 2 ? 2 : 3);
    if (x == 2) return y == 0 ? -1 : (y == 1 ? -2 : -3);
    return 0;
}

/* Table 5 in the paper: one seed in each orbit under the six units.  The
 * residue slots are (a mod 9, b mod 9), since tau^4 is associated to 9. */
static int make_tau4_table(ca_tau4_digit table[81])
{
    static const int seeds[9][2] = {{1, 0}, {2, 0}, {4, 0}, {1, 1}, {2, 2},
                                    {1, 2}, {2, 4}, {2, 1}, {1, -2}};
    for (size_t i = 0; i < 81; i++) table[i].seed = -1;
    for (int s = 0; s < 9; s++) {
        int a = seeds[s][0], b = seeds[s][1];
        for (int power = 0; power < 3; power++) {
            for (int sign = -1; sign <= 1; sign += 2) {
                int x = sign * a, y = sign * b;
                int xm = (x % 9 + 9) % 9, ym = (y % 9 + 9) % 9;
                int slot = 9 * xm + ym;
                if (xm % 3 == 0 || table[slot].seed >= 0) return 0;
                table[slot] =
                    (ca_tau4_digit){(int8_t)x, (int8_t)y, (int8_t)s, (int8_t)power, (int8_t)sign};
            }
            /* omega * (a+b*tau) = (a+3b) + (-a-2b)*tau. */
            int next_a = a + 3 * b, next_b = -a - 2 * b;
            a = next_a;
            b = next_b;
        }
    }
    for (int x = 0; x < 9; x++) {
        if (x % 3 == 0) continue;
        for (int y = 0; y < 9; y++)
            if (table[9 * x + y].seed < 0) return 0;
    }
    return 1;
}

static size_t gen_tau4_digits(ca_i128 x, ca_i128 y, const ca_tau4_digit table[81],
                              uint8_t digits[256])
{
    size_t nd = 0;
    while (x || y) {
        if (nd == 256) return 0;
        int slot = 255;
        if (residue3(x)) {
            slot = 9 * (int)((x % 9 + 9) % 9) + (int)((y % 9 + 9) % 9);
            if (table[slot].seed < 0) return 0;
            x -= table[slot].a;
            y -= table[slot].b;
        }
        digits[nd++] = (uint8_t)slot;
        ca_i128 old_x = x;
        if (old_x % 3) return 0;
        x += y;
        y = -old_x / 3;
    }
    return nd;
}

/* Scalar reduction normally leaves coordinates near sqrt(order).  Keep the
 * prepared hot path in native signed arithmetic; the explicit bound leaves
 * ample headroom for x+y and the small digit corrections. */
static size_t gen_tau4_digits_fast(ca_i128 wide_x, ca_i128 wide_y, const ca_tau4_digit table[81],
                                   uint8_t digits[256])
{
    const ca_i128 limit = (ca_i128)1 << 55;
    if (wide_x <= -limit || wide_x >= limit || wide_y <= -limit || wide_y >= limit)
        return gen_tau4_digits(wide_x, wide_y, table, digits);
    int64_t x = (int64_t)wide_x, y = (int64_t)wide_y;
    size_t nd = 0;
    while (x || y) {
        if (nd == 256) return 0;
        int slot = 255;
        if (x % 3) {
            int xm = (int)((x % 9 + 9) % 9);
            int ym = (int)((y % 9 + 9) % 9);
            slot = 9 * xm + ym;
            if (table[slot].seed < 0) return 0;
            x -= table[slot].a;
            y -= table[slot].b;
        }
        digits[nd++] = (uint8_t)slot;
        int64_t old_x = x;
        if (old_x % 3) return 0;
        x += y;
        y = -old_x / 3;
    }
    return nd;
}

/* Four width-4 decisions in one lookup.  Congruence modulo 81 preserves the
 * first four digits because 81 is associated to tau^8.  The correction is
 * the exact contribution of those digits, not a representative modulo 81. */
static size_t gen_tau4_digits_atlas(ca_i128 wide_x, ca_i128 wide_y, const ca_tau4_digit table[81],
                                    uint8_t digits[256])
{
    const ca_i128 limit = (ca_i128)1 << 55;
    if (wide_x <= -limit || wide_x >= limit || wide_y <= -limit || wide_y >= limit)
        return gen_tau4_digits(wide_x, wide_y, table, digits);
    int64_t x = (int64_t)wide_x, y = (int64_t)wide_y;
    size_t nd = 0;
    while (x || y) {
        if (nd > 252) return 0;
        int ax = (int)((x % 81 + 81) % 81);
        int by = (int)((y % 81 + 81) % 81);
        ca_tau4_atlas_pattern p = ca_tau4_atlas_patterns[ca_tau4_atlas_index[81 * ax + by]];
        for (size_t j = 0; j < 4; j++) digits[nd + j] = j == p.position ? p.slot : 255;
        nd += 4;
        int64_t a = x - p.correction_a, b = y - p.correction_b;
        int64_t nx = a + 3 * b, ny = -a - 2 * b;
        if (nx % 9 || ny % 9) return 0;
        x = nx / 9;
        y = ny / 9;
    }
    while (nd && digits[nd - 1] == 255) nd--;
    return nd;
}

int ca_ec_tau4_recode_compare(int64_t x, int64_t y)
{
    ca_tau4_digit table[81];
    uint8_t baseline[256], atlas[256];
    if (!make_tau4_table(table)) return 0;
    size_t a = gen_tau4_digits_fast(x, y, table, baseline);
    size_t b = gen_tau4_digits_atlas(x, y, table, atlas);
    return (a || !(x || y)) && a == b && memcmp(baseline, atlas, a) == 0;
}

int ca_ec_tau4_recode_compare_scalar(const ca_tau4_precomp *pre, uint64_t k)
{
    if (!pre || !pre->g) return 0;
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y}, pre->det,
                        k % pre->g->order, &x, &y);
    if (x < INT64_MIN || x > INT64_MAX || y < INT64_MIN || y > INT64_MAX) return 0;
    return ca_ec_tau4_recode_compare((int64_t)x, (int64_t)y);
}

/* Search the same 25 lattice representatives as reduce_with_lattice, but
 * score their actual prepared width-4 evaluation schedules.  The selected
 * digit stream is retained so it is not recoded a 26th time. */
static size_t reduce_with_lattice_cost(tau_vec v1, tau_vec v2, ca_i128 det, uint64_t k,
                                       const ca_tau4_digit table[81], uint8_t best_digits[256])
{
    ca_i128 u0 = round_div((ca_i128)k * v2.y, det);
    ca_i128 v0 = round_div(-(ca_i128)k * v1.y, det);
    ca_i128 best_l1 = -1;
    unsigned best_cost = 0;
    size_t best_nd = 0;
    for (int du = -2; du <= 2; du++) {
        for (int dv = -2; dv <= 2; dv++) {
            ca_i128 u = u0 + du, v = v0 + dv;
            ca_i128 x = (ca_i128)k - u * v1.x - v * v2.x;
            ca_i128 y = -u * v1.y - v * v2.y;
            ca_i128 l1 = iabs128(x) + iabs128(y);
            uint8_t digits[256];
            size_t nd = gen_tau4_digits_fast(x + y, -y, table, digits);
            if (!nd) return 0;
            unsigned triples = 0, adds = 0, rotations = 0;
            for (size_t i = 0; i < nd; i++) {
                if (digits[i] == 255) continue;
                ca_tau4_digit d = table[digits[i]];
                triples = (unsigned)(i / 2);
                adds++;
                rotations += (unsigned)((d.power + (int)((i / 2) % 3)) % 3 != 0);
            }
            unsigned cost = 10 * triples + 16 * adds + rotations;
            if (best_l1 < 0 || cost < best_cost || (cost == best_cost && l1 < best_l1)) {
                best_cost = cost;
                best_l1 = l1;
                best_nd = nd;
                memcpy(best_digits, digits, nd);
            }
        }
    }
    return best_nd;
}

static uint64_t tau4_seed_jac(const ca_group *g, const ca_elem *p, uint64_t one_minus_beta,
                              tau_jac q[9])
{
    tau_jac base = {p->w[0], p->w[1], g->mont.r1};
    tau_jac t = jac_tau(g, base, one_minus_beta);
    ca_elem neg = *p;
    if (neg.w[1]) neg.w[1] = g->p - neg.w[1];
    q[0] = base;
    q[1] = jac_double(g, base);          /* 2 */
    q[2] = jac_double(g, q[1]);          /* 4 */
    q[3] = jac_add_mixed(g, t, p);       /* 1+tau */
    q[4] = jac_double(g, q[3]);          /* 2+2tau */
    q[5] = jac_add_mixed(g, q[4], &neg); /* 1+2tau */
    q[6] = jac_double(g, q[5]);          /* 2+4tau */
    q[7] = jac_add_mixed(g, q[3], p);    /* 2+tau */
    tau_jac minus_two_tau = jac_double(g, t);
    if (minus_two_tau.z && minus_two_tau.y) minus_two_tau.y = g->p - minus_two_tau.y;
    q[8] = jac_add_mixed(g, minus_two_tau, p); /* 1-2tau */
    return 9;                                  /* five doublings, four mixed additions */
}

static uint64_t tau4_precompute(const ca_group *g, const ca_elem *p, uint64_t one_minus_beta,
                                ca_elem seeds[9])
{
    tau_jac q[9];
    uint64_t ops = tau4_seed_jac(g, p, one_minus_beta, q);
    jac_batch_to_affine(g, seeds, q, 9);
    return ops;
}

int ca_ec_tau4_prepare(const ca_group *g, const ca_elem *point, ca_tau4_precomp *out, uint64_t *ops)
{
    if (!g || !point || !out || g->kind != CA_GROUP_EC || g->endo_kind != 1 || g->a != 0 ||
        g->p % 3 != 1 || g->order % 3 != 1 || !g->endo_lambda)
        return 0;
    ca_tau4_precomp pre = {0};
    if (!make_tau4_table(pre.digit)) return 0;
    pre.g = g;
    pre.identity = !!point->w[2];
    pre.beta = g->endo_c_mont;
    pre.beta2 = fm(g, pre.beta, pre.beta);
    tau_vec v1, v2;
    if (!make_lattice(g->order, g->order - g->endo_lambda, &v1, &v2, &pre.det)) return 0;
    pre.v1x = v1.x;
    pre.v1y = v1.y;
    pre.v2x = v2.x;
    pre.v2y = v2.y;
    uint64_t count = 0;
    if (!pre.identity) {
        uint64_t one_minus_beta = fs(g, g->mont.r1, pre.beta);
        tau_jac q[18];
        count = tau4_seed_jac(g, point, one_minus_beta, q) + 1;
        for (size_t i = 0; i < 9; i++) q[9 + i] = jac_tau(g, q[i], one_minus_beta);
        count += 9;
        ca_elem affine[18];
        jac_batch_to_affine(g, affine, q, 18);
        for (size_t i = 0; i < 9; i++) {
            pre.seed[i] = affine[i];
            pre.tau_seed[i] = affine[9 + i];
        }
    }
    *out = pre;
    if (ops) *ops = count;
    return 1;
}

static int tau4_mul_prepared_impl(const ca_group *g, const ca_tau4_precomp *pre, ca_elem *out,
                                  uint64_t k, uint64_t *triples, uint64_t *adds,
                                  uint64_t *rotations, int recoder)
{
    if (!g || !pre || !out || pre->g != g) return 0;
    if (triples) *triples = 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (pre->identity || k % g->order == 0) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    k %= g->order;
    uint8_t digits[256];
    size_t nd;
    if (recoder == 1) {
        nd = reduce_with_lattice_cost((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y},
                                      pre->det, k, pre->digit, digits);
    } else {
        ca_i128 x, y;
        reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y}, pre->det,
                            k, &x, &y);
        nd = recoder == 2 ? gen_tau4_digits_atlas(x, y, pre->digit, digits)
                          : gen_tau4_digits_fast(x, y, pre->digit, digits);
    }
    if (!nd) return 0;
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t na = 0, n3 = 0, nr = 0;
    size_t nq = (nd + 1) / 2;
    for (size_t qi = nq; qi-- > 0;) {
        if (acc.z) {
            acc = jac_triple(g, acc);
            n3++;
        }
        size_t even = 2 * qi, odd = even + 1;
        int has_odd = odd < nd && digits[odd] != 255;
        int slot = has_odd ? digits[odd] : digits[even];
        if (slot == 255) continue;
        if (has_odd && digits[even] != 255) return 0;
        ca_tau4_digit d = pre->digit[slot];
        ca_elem seed = has_odd ? pre->tau_seed[d.seed] : pre->seed[d.seed];
        if (seed.w[2]) continue;
        int power = (d.power + (int)(qi % 3)) % 3;
        int sign = d.sign * ((qi & 1) ? -1 : 1);
        nr += power != 0;
        if (power == 1)
            seed.w[0] = fm(g, pre->beta, seed.w[0]);
        else if (power == 2)
            seed.w[0] = fm(g, pre->beta2, seed.w[0]);
        if (sign < 0 && seed.w[1]) seed.w[1] = g->p - seed.w[1];
        acc = jac_add_mixed(g, acc, &seed);
        na++;
    }
    jac_to_affine(g, out, acc);
    if (triples) *triples = n3;
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    return 1;
}

int ca_ec_tau4_mul_prepared(const ca_group *g, const ca_tau4_precomp *pre, ca_elem *out, uint64_t k,
                            uint64_t *triples, uint64_t *adds)
{
    return tau4_mul_prepared_impl(g, pre, out, k, triples, adds, NULL, 0);
}

int ca_ec_tau4_mul_prepared_cost(const ca_group *g, const ca_tau4_precomp *pre, ca_elem *out,
                                 uint64_t k, uint64_t *triples, uint64_t *adds)
{
    return tau4_mul_prepared_impl(g, pre, out, k, triples, adds, NULL, 1);
}

int ca_ec_tau4_mul_prepared_profile(const ca_group *g, const ca_tau4_precomp *pre, ca_elem *out,
                                    uint64_t k, int recoder, uint64_t *triples, uint64_t *adds,
                                    uint64_t *rotations)
{
    if (recoder < 0 || recoder > 2) return 0;
    return tau4_mul_prepared_impl(g, pre, out, k, triples, adds, rotations, recoder);
}

int ca_ec_mul_tau4(const ca_group *g, ca_elem *r, const ca_elem *a, uint64_t k, uint64_t *tau_steps,
                   uint64_t *adds)
{
    if (!g || !r || !a || g->kind != CA_GROUP_EC || g->endo_kind != 1 || g->a != 0 ||
        g->p % 3 != 1 || g->order % 3 != 1 || !g->endo_lambda)
        return 0;
    if (tau_steps) *tau_steps = 0;
    if (adds) *adds = 0;
    if (a->w[2] || k % g->order == 0) {
        *r = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    k %= g->order;
    ca_i128 x, y;
    if (!reduce_scalar(g->order, g->order - g->endo_lambda, k, &x, &y)) return 0;
    ca_tau4_digit table[81];
    if (!make_tau4_table(table)) return 0;
    uint8_t digits[256];
    size_t nd = gen_tau4_digits(x, y, table, digits);
    if (!nd) return 0;
    uint64_t beta = g->endo_c_mont, beta2 = fm(g, beta, beta);
    uint64_t one_minus_beta = fs(g, g->mont.r1, beta);
    ca_elem seeds[9];
    uint64_t nt = 1; /* tau(P) in precomputation */
    uint64_t na = tau4_precompute(g, a, one_minus_beta, seeds);
    tau_jac acc = {0, g->mont.r1, 0};
    for (size_t i = nd; i-- > 0;) {
        if (acc.z) {
            acc = jac_tau(g, acc, one_minus_beta);
            nt++;
        }
        int slot = digits[i];
        if (slot == 255) continue;
        ca_tau4_digit d = table[slot];
        ca_elem q = seeds[d.seed];
        if (q.w[2]) continue;
        if (d.power == 1)
            q.w[0] = fm(g, beta, q.w[0]);
        else if (d.power == 2)
            q.w[0] = fm(g, beta2, q.w[0]);
        if (d.sign < 0 && q.w[1]) q.w[1] = g->p - q.w[1];
        acc = jac_add_mixed(g, acc, &q);
        na++;
    }
    jac_to_affine(g, r, acc);
    if (tau_steps) *tau_steps = nt;
    if (adds) *adds = na;
    return 1;
}

int ca_ec_mul_tau4_tripling(const ca_group *g, ca_elem *r, const ca_elem *a, uint64_t k,
                            uint64_t *tau_steps, uint64_t *adds, uint64_t *triples)
{
    if (!g || !r || !a || g->kind != CA_GROUP_EC || g->endo_kind != 1 || g->a != 0 ||
        g->p % 3 != 1 || g->order % 3 != 1 || !g->endo_lambda)
        return 0;
    if (tau_steps) *tau_steps = 0;
    if (adds) *adds = 0;
    if (triples) *triples = 0;
    if (a->w[2] || k % g->order == 0) {
        *r = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    k %= g->order;
    ca_i128 x, y;
    if (!reduce_scalar(g->order, g->order - g->endo_lambda, k, &x, &y)) return 0;
    ca_tau4_digit table[81];
    if (!make_tau4_table(table)) return 0;
    uint8_t digits[256];
    size_t nd = gen_tau4_digits(x, y, table, digits);
    if (!nd) return 0;
    uint64_t beta = g->endo_c_mont, beta2 = fm(g, beta, beta);
    uint64_t one_minus_beta = fs(g, g->mont.r1, beta);
    ca_elem seeds[9];
    uint64_t nt = 1, na = tau4_precompute(g, a, one_minus_beta, seeds), n3 = 0;
    tau_jac acc = {0, g->mont.r1, 0};
    size_t nq = (nd + 1) / 2;
    for (size_t qi = nq; qi-- > 0;) {
        if (acc.z) {
            acc = jac_triple(g, acc);
            n3++;
        }
        size_t even = 2 * qi, odd = even + 1;
        int slot = odd < nd && digits[odd] != 255 ? digits[odd] : digits[even];
        if (slot == 255) continue;
        if (odd < nd && digits[odd] != 255 && digits[even] != 255) return 0;
        ca_tau4_digit d = table[slot];
        ca_elem seed = seeds[d.seed];
        if (seed.w[2]) continue;
        int power = (d.power + (int)(qi % 3)) % 3;
        int sign = d.sign * ((qi & 1) ? -1 : 1);
        if (odd < nd && digits[odd] != 255) {
            tau_jac q = jac_tau(g, (tau_jac){seed.w[0], seed.w[1], g->mont.r1}, one_minus_beta);
            nt++;
            if (power == 1)
                q.x = fm(g, beta, q.x);
            else if (power == 2)
                q.x = fm(g, beta2, q.x);
            if (sign < 0 && q.y) q.y = g->p - q.y;
            acc = jac_add(g, acc, q);
        } else {
            if (power == 1)
                seed.w[0] = fm(g, beta, seed.w[0]);
            else if (power == 2)
                seed.w[0] = fm(g, beta2, seed.w[0]);
            if (sign < 0 && seed.w[1]) seed.w[1] = g->p - seed.w[1];
            acc = jac_add_mixed(g, acc, &seed);
        }
        na++;
    }
    jac_to_affine(g, r, acc);
    if (tau_steps) *tau_steps = nt;
    if (adds) *adds = na;
    if (triples) *triples = n3;
    return 1;
}

int ca_ec_mul_tau2(const ca_group *g, ca_elem *r, const ca_elem *a, uint64_t k, uint64_t *tau_steps,
                   uint64_t *adds)
{
    if (!g || !r || !a || g->kind != CA_GROUP_EC || g->endo_kind != 1 || g->a != 0 ||
        g->p % 3 != 1 || g->order % 3 != 1 || !g->endo_lambda)
        return 0;
    if (tau_steps) *tau_steps = 0;
    if (adds) *adds = 0;
    if (a->w[2] || k % g->order == 0) {
        *r = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    k %= g->order;
    /* The enabled rho automorphism is psi=-omega, so its eigenvalue is
     * -lambda_omega, while its field multiplier is beta. */
    uint64_t lambda_omega = g->order - g->endo_lambda;
    ca_i128 x, y;
    if (!reduce_scalar(g->order, lambda_omega, k, &x, &y)) return 0;
    int digits[256];
    size_t nd = 0;
    while (x || y) {
        if (nd == sizeof(digits) / sizeof(digits[0])) return 0;
        int d = digit_for(x, y);
        digits[nd++] = d;
        if (d) {
            /* In the tau basis: omega=1-tau, omega^2=-2+tau. */
            const int dx[4] = {0, 1, 1, -2};
            const int dy[4] = {0, 0, -1, 1};
            int sign = d < 0 ? -1 : 1, j = d < 0 ? -d : d;
            x -= (ca_i128)sign * dx[j];
            y -= (ca_i128)sign * dy[j];
        }
        ca_i128 old_x = x;
        if (old_x % 3) return 0;
        x += y;
        y = -old_x / 3;
    }
    uint64_t beta = g->endo_c_mont, beta2 = fm(g, beta, beta);
    ca_elem units[3] = {*a, *a, *a};
    units[1].w[0] = fm(g, beta, a->w[0]);
    units[2].w[0] = fm(g, beta2, a->w[0]);
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t nt = 0, na = 0;
    uint64_t one_minus_beta = fs(g, g->mont.r1, beta);
    for (size_t i = nd; i-- > 0;) {
        if (acc.z) {
            acc = jac_tau(g, acc, one_minus_beta);
            nt++;
        }
        int d = digits[i];
        if (d) {
            ca_elem q = units[d < 0 ? -d - 1 : d - 1];
            if (d < 0 && q.w[1]) q.w[1] = g->p - q.w[1];
            acc = jac_add_mixed(g, acc, &q);
            na++;
        }
    }
    jac_to_affine(g, r, acc);
    if (tau_steps) *tau_steps = nt;
    if (adds) *adds = na;
    return 1;
}
