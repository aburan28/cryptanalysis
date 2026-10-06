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
#include "generated/tau_tail_oracle.h"
#include "generated/tau_tail_gate.h"
#include "generated/tau_tail_double.h"
#include "generated/tau_tail_double_fold.h"
#include "generated/tau_tail_double_residue.h"
#include "generated/tau_pair_fused.h"
#include "generated/tau_pair_periodic.h"
#include "generated/tau_pair_firstword_gate.h"
#include "generated/tau_pair_mixed_radix_tail.h"
#include "generated/tau_pair_mixed_full_digits.h"
#include "generated/tau8_orbit_map.h"
#include "generated/tau8_hot_map.h"
#include "generated/tau8_pair_map.h"
#include "generated/tau8_steer_map.h"
#include "generated/tau_wide_orbits.h"
#include "generated/tau_wide_graph.h"
#include "generated/tau_wide_packed_graph.h"
#include <stdlib.h>

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

/* Normalize an arbitrary output block with caller-owned prefix scratch.
 * An all-identity block avoids inversion entirely. */
static int jac_batch_to_affine_scratch(const ca_group *g, ca_elem *out, const tau_jac *in, size_t n,
                                       uint64_t *prefixes, uint64_t *inversions)
{
    uint64_t product = g->mont.r1;
    int has_point = 0;
    for (size_t i = 0; i < n; i++) {
        uint64_t z = in[i].z ? in[i].z : g->mont.r1;
        has_point |= in[i].z != 0;
        product = fm(g, product, z);
        prefixes[i] = product;
    }
    if (!has_point) {
        for (size_t i = 0; i < n; i++) out[i] = (ca_elem){{0, 0, 1, 0}};
        if (inversions) *inversions = 0;
        return 1;
    }
    uint64_t inverse = ca_mont_inv(&g->mont, product);
    if (!inverse) return 0;
    for (size_t i = n; i-- > 0;) {
        tau_jac p = in[i];
        uint64_t invz = fm(g, inverse, i ? prefixes[i - 1] : g->mont.r1);
        inverse = fm(g, inverse, p.z ? p.z : g->mont.r1);
        if (!p.z) {
            out[i] = (ca_elem){{0, 0, 1, 0}};
            continue;
        }
        uint64_t invz2 = fq(g, invz);
        out[i].w[0] = fm(g, p.x, invz2);
        out[i].w[1] = fm(g, p.y, fm(g, invz2, invz));
        out[i].w[2] = out[i].w[3] = 0;
    }
    if (inversions) *inversions = 1;
    return 1;
}

/* Fixed-base binary comb, retained as a conventional control for every
 * prepared-point tau experiment. Column j represents 2^(j*depth) P. */
int ca_ec_fixed_comb_prepare(const ca_group *g, const ca_elem *point,
                             ca_fixed_comb_precomp *out, uint64_t *doubles,
                             uint64_t *adds, uint64_t *inversions)
{
    if (!g || !point || !out || g->kind != CA_GROUP_EC || g->order < 2) return 0;
    unsigned bits = 0;
    for (uint64_t n = g->order - 1; n; n >>= 1) bits++;
    unsigned depth = (bits + CA_FIXED_COMB_WIDTH - 1) / CA_FIXED_COMB_WIDTH;
    if (!depth || depth > 8) return 0;
    out->g = g;
    out->depth = depth;
    out->identity = point->w[2] != 0;
    if (doubles) *doubles = 0;
    if (adds) *adds = 0;
    if (inversions) *inversions = 0;
    if (out->identity) {
        for (unsigned i = 0; i < CA_FIXED_COMB_ENTRIES; i++)
            out->point[i] = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    tau_jac basis[CA_FIXED_COMB_WIDTH];
    tau_jac projective[CA_FIXED_COMB_ENTRIES];
    uint64_t prefixes[CA_FIXED_COMB_ENTRIES];
    basis[0] = (tau_jac){point->w[0], point->w[1], g->mont.r1};
    for (unsigned j = 1; j < CA_FIXED_COMB_WIDTH; j++) {
        basis[j] = basis[j - 1];
        for (unsigned i = 0; i < depth; i++) {
            basis[j] = jac_double(g, basis[j]);
            if (doubles) (*doubles)++;
        }
    }
    projective[0] = (tau_jac){0, g->mont.r1, 0};
    for (unsigned mask = 1; mask < CA_FIXED_COMB_ENTRIES; mask++) {
        unsigned bit = 0;
        while ((mask & (1u << bit)) == 0) bit++;
        unsigned previous = mask ^ (1u << bit);
        projective[mask] = jac_add(g, projective[previous], basis[bit]);
        if (previous && adds) (*adds)++;
    }
    return jac_batch_to_affine_scratch(g, out->point, projective,
                                       CA_FIXED_COMB_ENTRIES, prefixes, inversions);
}

int ca_ec_fixed_comb_mul_profile(const ca_group *g, const ca_fixed_comb_precomp *pre,
                                  ca_elem *out, uint64_t k, uint64_t *doubles,
                                  uint64_t *adds)
{
    if (!g || !pre || !out || pre->g != g || !pre->depth || pre->depth > 8) return 0;
    if (doubles) *doubles = 0;
    if (adds) *adds = 0;
    if (pre->identity || k % g->order == 0) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    k %= g->order;
    tau_jac acc = {0, g->mont.r1, 0};
    for (unsigned i = pre->depth; i-- > 0;) {
        if (acc.z) {
            acc = jac_double(g, acc);
            if (doubles) (*doubles)++;
        }
        unsigned mask = 0;
        for (unsigned j = 0; j < CA_FIXED_COMB_WIDTH; j++) {
            unsigned bit_index = j * pre->depth + i;
            if (bit_index < 64) mask |= (unsigned)((k >> bit_index) & 1u) << j;
        }
        if (mask && !pre->point[mask].w[2]) {
            acc = jac_add_mixed(g, acc, &pre->point[mask]);
            if (adds) (*adds)++;
        }
    }
    jac_to_affine(g, out, acc);
    return 1;
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

static unsigned tau4_weighted_cost(const uint8_t digits[256], size_t nd,
                                   const ca_tau4_digit table[81])
{
    unsigned triples = 0, adds = 0, rotations = 0;
    for (size_t i = 0; i < nd; i++) {
        if (digits[i] == 255) continue;
        ca_tau4_digit d = table[digits[i]];
        triples = (unsigned)(i / 2);
        adds++;
        rotations += (unsigned)((d.power + (int)((i / 2) % 3)) % 3 != 0);
    }
    return 10 * triples + 16 * adds + rotations;
}

static int tau_tail_step(ca_i128 *x, ca_i128 *y, unsigned phase, const ca_tau4_digit table[81],
                         uint8_t *even, uint8_t *odd_digit)
{
    uint8_t action =
        ca_tau_tail_action[phase][(int)*x + CA_TAU_TAIL_BOUND][(int)*y + CA_TAU_TAIL_BOUND];
    if (action == 254) return 0;
    uint8_t slot = action == 255 ? 255 : action >= 128 ? action - 128 : action;
    int odd = action >= 128 && action != 254 && action != 255;
    if (slot != 255 && table[slot].seed < 0) return 0;
    *even = odd ? 255 : slot;
    *odd_digit = odd ? slot : 255;
    ca_i128 da = 0, db = 0;
    if (slot != 255) {
        da = table[slot].a;
        db = table[slot].b;
        if (odd) {
            ca_i128 old_a = da;
            da = -3 * db;
            db = old_a + 3 * db;
        }
    }
    ca_i128 ax = *x - da, by = *y - db;
    if (ax % 3 || by % 3) return 0;
    *x = 2 * (ax / 3) + by;
    *y = -(ax + by) / 3;
    if (odd && *x % 3) return 0;
    return *x >= -CA_TAU_TAIL_BOUND && *x <= CA_TAU_TAIL_BOUND && *y >= -CA_TAU_TAIL_BOUND &&
           *y <= CA_TAU_TAIL_BOUND;
}

static int tau_double_apply(ca_i128 *x, ca_i128 *y, const ca_tau4_digit table[81],
                            uint16_t action, uint8_t *even, uint8_t *odd)
{
    if (action == UINT16_C(0xfefe)) return 0;
    *even = (uint8_t)(action >> 8);
    *odd = (uint8_t)action;
    ca_i128 da = 0, db = 0;
    if (*even != 255) {
        ca_tau4_digit digit = table[*even];
        if (digit.seed < 0) return 0;
        da += digit.a;
        db += digit.b;
    }
    if (*odd != 255) {
        ca_tau4_digit digit = table[*odd];
        if (digit.seed < 0) return 0;
        da -= 3 * (ca_i128)digit.b;
        db += (ca_i128)digit.a + 3 * (ca_i128)digit.b;
    }
    ca_i128 ax = *x - da, by = *y - db;
    if (ax % 3 || by % 3) return 0;
    *x = 2 * (ax / 3) + by;
    *y = -(ax + by) / 3;
    return *x >= -CA_TAU_DOUBLE_BOUND && *x <= CA_TAU_DOUBLE_BOUND && *y >= -CA_TAU_DOUBLE_BOUND &&
           *y <= CA_TAU_DOUBLE_BOUND;
}

static int tau_double_step(ca_i128 *x, ca_i128 *y, unsigned phase, const ca_tau4_digit table[81],
                           uint8_t *even, uint8_t *odd)
{
    uint16_t action =
        ca_tau_double_action[phase][(int)*x + CA_TAU_DOUBLE_BOUND][(int)*y + CA_TAU_DOUBLE_BOUND];
    return tau_double_apply(x, y, table, action, even, odd);
}

static size_t tau_double_fold_index(ca_i128 x, ca_i128 y, unsigned phase, int *negative)
{
    *negative = x < 0 || (x == 0 && y < 0);
    if (*negative) {
        x = -x;
        y = -y;
    }
    size_t half = x == 0 ? (size_t)y
                         : (size_t)(CA_TAU_DOUBLE_BOUND + 1 + (x - 1) * CA_TAU_DOUBLE_SIDE +
                                    y + CA_TAU_DOUBLE_BOUND);
    return phase * CA_TAU_DOUBLE_HALF + half;
}

static int tau_double_fold_step(ca_i128 *x, ca_i128 *y, unsigned phase,
                                const ca_tau4_digit table[81], uint8_t *even, uint8_t *odd)
{
    int negative;
    size_t pos = tau_double_fold_index(*x, *y, phase, &negative);
    size_t bit = 10 * pos, byte = bit >> 3;
    uint32_t word = (uint32_t)ca_tau_double_fold_code[byte] |
                    (uint32_t)ca_tau_double_fold_code[byte + 1] << 8 |
                    (uint32_t)ca_tau_double_fold_code[byte + 2] << 16;
    unsigned code = (word >> (bit & 7)) & 1023u;
    if (code >= CA_TAU_DOUBLE_FOLD_DICT_WIDTH) return 0;
    uint16_t action = ca_tau_double_fold_dictionary[phase][code];
    if (negative && action != UINT16_C(0xfefe)) {
        uint8_t e = (uint8_t)(action >> 8), o = (uint8_t)action;
        if (e != 255) e = ca_tau_double_fold_negate[e];
        if (o != 255) o = ca_tau_double_fold_negate[o];
        action = ((uint16_t)e << 8) | o;
    }
    return tau_double_apply(x, y, table, action, even, odd);
}

size_t ca_ec_tau4_fold_static_bytes(void)
{
    return sizeof(ca_tau_double_fold_code) + sizeof(ca_tau_double_fold_gate) +
           sizeof(ca_tau_double_fold_negate) + sizeof(ca_tau_double_fold_dictionary);
}

static int tau_double_residue_step(ca_i128 *x, ca_i128 *y, unsigned phase,
                                   const ca_tau4_digit table[81], uint8_t *even, uint8_t *odd)
{
    int negative;
    size_t pos = tau_double_fold_index(*x, *y, phase, &negative);
    ca_i128 ra = negative ? -*x : *x;
    ca_i128 rb = negative ? -*y : *y;
    int bmod = (int)(rb % 3);
    if (bmod < 0) bmod += 3;
    unsigned residue = (unsigned)(ra % 3) * 3 + (unsigned)bmod;
    unsigned code = ca_tau_double_residue_code[pos];
    if (code >= ca_tau_double_residue_length[phase][residue]) return 0;
    uint16_t action = ca_tau_double_residue_dictionary[
        ca_tau_double_residue_offset[phase][residue] + code];
    if (negative && action != UINT16_C(0xfefe)) {
        uint8_t e = (uint8_t)(action >> 8), o = (uint8_t)action;
        if (e != 255) e = ca_tau_double_residue_negate[e];
        if (o != 255) o = ca_tau_double_residue_negate[o];
        action = ((uint16_t)e << 8) | o;
    }
    return tau_double_apply(x, y, table, action, even, odd);
}

size_t ca_ec_tau4_residue_static_bytes(void)
{
    return sizeof(ca_tau_double_residue_code) + sizeof(ca_tau_double_residue_gate) +
           sizeof(ca_tau_double_residue_negate) + sizeof(ca_tau_double_residue_offset) +
           sizeof(ca_tau_double_residue_length) + sizeof(ca_tau_double_residue_dictionary);
}

/* A small offline shortest-path oracle changes only the low-coefficient tail.
 * Each two-tau step keeps the width-four one-digit-per-pair property and uses
 * the same 18 prepared seed/odd-seed points.  Recode cost is charged online;
 * a path is accepted only when its exact modeled evaluation cost is lower. */
static size_t gen_tau4_digits_tail(ca_i128 x, ca_i128 y, const ca_tau4_digit table[81],
                                   uint8_t digits[256])
{
    uint8_t baseline[256], candidate[256];
    size_t base_nd = gen_tau4_digits_fast(x, y, table, baseline);
    if (!base_nd) return 0;
    const ca_i128 limit = (ca_i128)1 << 55;
    if (x <= -limit || x >= limit || y <= -limit || y >= limit) {
        memcpy(digits, baseline, base_nd);
        return base_nd;
    }
    size_t nd = 0;
    while (x < -CA_TAU_TAIL_BOUND || x > CA_TAU_TAIL_BOUND || y < -CA_TAU_TAIL_BOUND ||
           y > CA_TAU_TAIL_BOUND) {
        if (nd > 253) goto baseline_fallback;
        for (size_t j = 0; j < 2; j++) {
            uint8_t slot = nd < base_nd ? baseline[nd] : 255;
            candidate[nd++] = slot;
            if (slot != 255) {
                x -= table[slot].a;
                y -= table[slot].b;
            }
            ca_i128 old_x = x;
            if (old_x % 3) goto baseline_fallback;
            x += y;
            y = -old_x / 3;
        }
    }
    while (x || y) {
        if (nd > 253) goto baseline_fallback;
        unsigned phase = (unsigned)((nd / 2) % 3);
        uint8_t even, odd;
        if (!tau_tail_step(&x, &y, phase, table, &even, &odd)) goto baseline_fallback;
        candidate[nd++] = even;
        candidate[nd++] = odd;
    }
    while (nd && candidate[nd - 1] == 255) nd--;
    if (nd &&
        tau4_weighted_cost(candidate, nd, table) < tau4_weighted_cost(baseline, base_nd, table)) {
        memcpy(digits, candidate, nd);
        return nd;
    }
baseline_fallback:
    memcpy(digits, baseline, base_nd);
    return base_nd;
}

/* The gate compares the full canonical tail with the bounded oracle offline.
 * It preserves mode 3's digit stream while emitting the shared prefix once. */
static size_t gen_tau4_digits_tail_gated_impl(ca_i128 x, ca_i128 y, const ca_tau4_digit table[81],
                                              uint8_t digits[256], int double_policy)
{
    ca_i128 original_x = x, original_y = y;
    const ca_i128 limit = (ca_i128)1 << 55;
    if (x <= -limit || x >= limit || y <= -limit || y >= limit)
        return gen_tau4_digits_fast(x, y, table, digits);
    size_t nd = 0;
    while (x < -CA_TAU_TAIL_BOUND || x > CA_TAU_TAIL_BOUND || y < -CA_TAU_TAIL_BOUND ||
           y > CA_TAU_TAIL_BOUND) {
        if (nd > 253) goto canonical_fallback;
        for (size_t j = 0; j < 2; j++) {
            uint8_t slot = 255;
            if (x % 3) {
                int xm = (int)((x % 9 + 9) % 9);
                int ym = (int)((y % 9 + 9) % 9);
                slot = (uint8_t)(9 * xm + ym);
                if (table[slot].seed < 0) goto canonical_fallback;
                x -= table[slot].a;
                y -= table[slot].b;
            }
            digits[nd++] = slot;
            ca_i128 old_x = x;
            if (old_x % 3) goto canonical_fallback;
            x += y;
            y = -old_x / 3;
        }
    }
    if (x || y) {
        size_t pos =
            ((nd / 2) % 3 * CA_TAU_TAIL_SIDE + (size_t)(x + CA_TAU_TAIL_BOUND)) * CA_TAU_TAIL_SIDE +
            (size_t)(y + CA_TAU_TAIL_BOUND);
        int selected;
        if (double_policy >= 2) {
            int negative;
            size_t folded = tau_double_fold_index(x, y, (unsigned)((nd / 2) % 3), &negative);
            uint8_t gate = double_policy == 3 ? ca_tau_double_residue_gate[folded >> 3]
                                               : ca_tau_double_fold_gate[folded >> 3];
            selected = (gate >> (folded & 7)) & 1;
        } else {
            uint8_t gate = double_policy ? ca_tau_double_gate[pos >> 3] : ca_tau_tail_gate[pos >> 3];
            selected = (gate >> (pos & 7)) & 1;
        }
        if (selected) {
            while (x || y) {
                if (nd > 253) goto canonical_fallback;
                uint8_t even, odd;
                unsigned phase = (unsigned)((nd / 2) % 3);
                int good = double_policy == 3
                               ? tau_double_residue_step(&x, &y, phase, table, &even, &odd)
                           : double_policy == 2
                               ? tau_double_fold_step(&x, &y, phase, table, &even, &odd)
                           : double_policy ? tau_double_step(&x, &y, phase, table, &even, &odd)
                                           : tau_tail_step(&x, &y, phase, table, &even, &odd);
                if (!good) goto canonical_fallback;
                digits[nd++] = even;
                digits[nd++] = odd;
            }
        } else {
            uint8_t tail[256];
            size_t remaining = gen_tau4_digits_fast(x, y, table, tail);
            if (!remaining || remaining > 256 - nd) goto canonical_fallback;
            memcpy(digits + nd, tail, remaining);
            nd += remaining;
        }
    }
    while (nd && digits[nd - 1] == 255) nd--;
    return nd;
canonical_fallback:
    return gen_tau4_digits_fast(original_x, original_y, table, digits);
}

static size_t gen_tau4_digits_tail_gated(ca_i128 x, ca_i128 y, const ca_tau4_digit table[81],
                                         uint8_t digits[256])
{
    return gen_tau4_digits_tail_gated_impl(x, y, table, digits, 0);
}

static size_t gen_tau4_digits_double_gated(ca_i128 x, ca_i128 y, const ca_tau4_digit table[81],
                                           uint8_t digits[256])
{
    return gen_tau4_digits_tail_gated_impl(x, y, table, digits, 1);
}

static size_t gen_tau4_digits_double_fold(ca_i128 x, ca_i128 y, const ca_tau4_digit table[81],
                                          uint8_t digits[256])
{
    return gen_tau4_digits_tail_gated_impl(x, y, table, digits, 2);
}

static size_t gen_tau4_digits_double_residue(ca_i128 x, ca_i128 y,
                                             const ca_tau4_digit table[81], uint8_t digits[256])
{
    return gen_tau4_digits_tail_gated_impl(x, y, table, digits, 3);
}

int ca_ec_tau4_tail_recode_compare_scalar(const ca_tau4_precomp *pre, uint64_t k)
{
    if (!pre || !pre->g) return 0;
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y}, pre->det,
                        k % pre->g->order, &x, &y);
    uint8_t original[256], gated[256];
    size_t a = gen_tau4_digits_tail(x, y, pre->digit, original);
    size_t b = gen_tau4_digits_tail_gated(x, y, pre->digit, gated);
    return a == b && memcmp(original, gated, a) == 0;
}

int ca_ec_tau4_double_recode_verify_scalar(const ca_tau4_precomp *pre, uint64_t k)
{
    if (!pre || !pre->g) return 0;
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y}, pre->det,
                        k % pre->g->order, &x, &y);
    uint8_t prior[256], candidate[256];
    size_t old_nd = gen_tau4_digits_tail_gated(x, y, pre->digit, prior);
    size_t new_nd = gen_tau4_digits_double_gated(x, y, pre->digit, candidate);
    if ((!old_nd || !new_nd) && (x || y)) return 0;
    if (tau4_weighted_cost(candidate, new_nd, pre->digit) >
        tau4_weighted_cost(prior, old_nd, pre->digit))
        return 0;
    ca_i128 a = 0, b = 0;
    for (size_t i = new_nd; i-- > 0;) {
        ca_i128 next_a = -3 * b, next_b = a + 3 * b;
        if (candidate[i] != 255) {
            ca_tau4_digit digit = pre->digit[candidate[i]];
            if (digit.seed < 0) return 0;
            next_a += digit.a;
            next_b += digit.b;
        }
        a = next_a;
        b = next_b;
    }
    return a == x && b == y;
}

int ca_ec_tau4_fold_recode_verify_scalar(const ca_tau4_precomp *pre, uint64_t k)
{
    if (!pre || !pre->g) return 0;
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y}, pre->det,
                        k % pre->g->order, &x, &y);
    uint8_t prior[256], candidate[256];
    size_t old_nd = gen_tau4_digits_double_gated(x, y, pre->digit, prior);
    size_t new_nd = gen_tau4_digits_double_fold(x, y, pre->digit, candidate);
    if ((!old_nd || !new_nd) && (x || y)) return 0;
    if (tau4_weighted_cost(candidate, new_nd, pre->digit) !=
        tau4_weighted_cost(prior, old_nd, pre->digit))
        return 0;
    ca_i128 a = 0, b = 0;
    for (size_t i = new_nd; i-- > 0;) {
        ca_i128 next_a = -3 * b, next_b = a + 3 * b;
        if (candidate[i] != 255) {
            ca_tau4_digit digit = pre->digit[candidate[i]];
            if (digit.seed < 0) return 0;
            next_a += digit.a;
            next_b += digit.b;
        }
        a = next_a;
        b = next_b;
    }
    return a == x && b == y;
}

int ca_ec_tau4_residue_recode_verify_scalar(const ca_tau4_precomp *pre, uint64_t k)
{
    if (!pre || !pre->g) return 0;
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y}, pre->det,
                        k % pre->g->order, &x, &y);
    uint8_t prior[256], candidate[256];
    size_t old_nd = gen_tau4_digits_double_fold(x, y, pre->digit, prior);
    size_t new_nd = gen_tau4_digits_double_residue(x, y, pre->digit, candidate);
    if ((!old_nd || !new_nd) && (x || y)) return 0;
    if (tau4_weighted_cost(candidate, new_nd, pre->digit) !=
        tau4_weighted_cost(prior, old_nd, pre->digit))
        return 0;
    ca_i128 a = 0, b = 0;
    for (size_t i = new_nd; i-- > 0;) {
        ca_i128 next_a = -3 * b, next_b = a + 3 * b;
        if (candidate[i] != 255) {
            ca_tau4_digit digit = pre->digit[candidate[i]];
            if (digit.seed < 0) return 0;
            next_a += digit.a;
            next_b += digit.b;
        }
        a = next_a;
        b = next_b;
    }
    return a == x && b == y;
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
        nd = recoder == 7   ? gen_tau4_digits_double_residue(x, y, pre->digit, digits)
             : recoder == 6 ? gen_tau4_digits_double_fold(x, y, pre->digit, digits)
             : recoder == 5 ? gen_tau4_digits_double_gated(x, y, pre->digit, digits)
             : recoder == 4 ? gen_tau4_digits_tail_gated(x, y, pre->digit, digits)
             : recoder == 3 ? gen_tau4_digits_tail(x, y, pre->digit, digits)
             : recoder == 2 ? gen_tau4_digits_atlas(x, y, pre->digit, digits)
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
        if (has_odd && digits[even] != 255) {
            if (recoder != 5 && recoder != 6 && recoder != 7) return 0;
            ca_tau4_digit first = pre->digit[digits[even]];
            ca_elem first_seed = pre->seed[first.seed];
            if (!first_seed.w[2]) {
                int first_power = (first.power + (int)(qi % 3)) % 3;
                int first_sign = first.sign * ((qi & 1) ? -1 : 1);
                nr += first_power != 0;
                if (first_power == 1)
                    first_seed.w[0] = fm(g, pre->beta, first_seed.w[0]);
                else if (first_power == 2)
                    first_seed.w[0] = fm(g, pre->beta2, first_seed.w[0]);
                if (first_sign < 0 && first_seed.w[1]) first_seed.w[1] = g->p - first_seed.w[1];
                acc = jac_add_mixed(g, acc, &first_seed);
                na++;
            }
        }
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
    if (recoder < 0 || recoder > 7) return 0;
    return tau4_mul_prepared_impl(g, pre, out, k, triples, adds, rotations, recoder);
}

static int tau_pair_seed_point(const ca_group *g, const ca_tau4_precomp *base, uint8_t slot,
                               int odd, ca_elem *out, uint64_t *rotations)
{
    if (slot >= 81 || base->digit[slot].seed < 0) return 0;
    ca_tau4_digit digit = base->digit[slot];
    *out = odd ? base->tau_seed[digit.seed] : base->seed[digit.seed];
    if (out->w[2]) return 1;
    if (digit.power == 1)
        out->w[0] = fm(g, base->beta, out->w[0]);
    else if (digit.power == 2)
        out->w[0] = fm(g, base->beta2, out->w[0]);
    if (digit.sign < 0 && out->w[1]) out->w[1] = g->p - out->w[1];
    if (rotations) *rotations += digit.power != 0;
    return 1;
}

int ca_ec_tau_pair_fused_prepare(const ca_group *g, const ca_elem *point,
                                 ca_tau_pair_fused_precomp *out, uint64_t *seed_ops,
                                 uint64_t *pair_adds, uint64_t *pair_rotations,
                                 uint64_t *inversions)
{
    if (!g || !point || !out) return 0;
    _Static_assert(CA_TAU_PAIR_FUSED_REP_COUNT == CA_TAU_PAIR_FUSED_REPS,
                   "pair-point orbit count changed");
    ca_tau_pair_fused_precomp pre = {0};
    uint64_t base_ops = 0, additions = 0, rotations = 0, extra_inversions = 0;
    if (!ca_ec_tau4_prepare(g, point, &pre.base, &base_ops)) return 0;
    if (pre.base.identity) {
        for (size_t i = 0; i < CA_TAU_PAIR_FUSED_REPS; i++) pre.orbit[i] = (ca_elem){{0, 0, 1, 0}};
    } else {
        tau_jac projective[CA_TAU_PAIR_FUSED_REPS];
        uint64_t prefixes[CA_TAU_PAIR_FUSED_REPS];
        for (size_t i = 0; i < CA_TAU_PAIR_FUSED_REPS; i++) {
            uint8_t even = ca_tau_pair_fused_rep_even[i];
            uint8_t odd = ca_tau_pair_fused_rep_odd[i];
            tau_jac q = {0, g->mont.r1, 0};
            if (even != 255) {
                ca_elem first;
                if (!tau_pair_seed_point(g, &pre.base, even, 0, &first, &rotations)) return 0;
                if (!first.w[2]) q = (tau_jac){first.w[0], first.w[1], g->mont.r1};
            }
            if (odd != 255) {
                ca_elem second;
                if (!tau_pair_seed_point(g, &pre.base, odd, 1, &second, &rotations)) return 0;
                if (!second.w[2]) {
                    if (q.z) {
                        q = jac_add_mixed(g, q, &second);
                        additions++;
                    } else {
                        q = (tau_jac){second.w[0], second.w[1], g->mont.r1};
                    }
                }
            }
            projective[i] = q;
        }
        if (!jac_batch_to_affine_scratch(g, pre.orbit, projective, CA_TAU_PAIR_FUSED_REPS, prefixes,
                                         &extra_inversions))
            return 0;
    }
    *out = pre;
    if (seed_ops) *seed_ops = base_ops;
    if (pair_adds) *pair_adds = additions;
    if (pair_rotations) *pair_rotations = rotations;
    if (inversions) *inversions = (pre.base.identity ? 0 : 1) + extra_inversions;
    return 1;
}

size_t ca_ec_tau_pair_fused_static_bytes(void)
{
    return sizeof(ca_tau_pair_fused_code) + sizeof(ca_tau_pair_fused_gate) +
           sizeof(ca_tau_pair_fused_dictionary) + sizeof(ca_tau_pair_fused_rep_a) +
           sizeof(ca_tau_pair_fused_rep_b) + sizeof(ca_tau_pair_fused_rep_even) +
           sizeof(ca_tau_pair_fused_rep_odd) + sizeof(ca_tau_pair_fused_even_word) +
           sizeof(ca_tau_pair_fused_odd_word) + sizeof(ca_tau_pair_fused_offset) +
           sizeof(ca_tau_pair_fused_length);
}

int ca_ec_tau_pair_fused_prepare_verify(const ca_tau_pair_fused_precomp *pre)
{
    if (!pre || !pre->base.g) return 0;
    const ca_group *g = pre->base.g;
    if (pre->base.identity) {
        for (size_t i = 0; i < CA_TAU_PAIR_FUSED_REPS; i++)
            if (!ca_group_is_identity(g, &pre->orbit[i])) return 0;
        return 1;
    }
    /* The group's j=0 eigenvalue is for psi = -omega, so tau = 1 + psi. */
    ca_i128 lambda_tau = (ca_i128)1 + g->endo_lambda;
    for (size_t i = 0; i < CA_TAU_PAIR_FUSED_REPS; i++) {
        ca_i128 scalar =
            (ca_i128)ca_tau_pair_fused_rep_a[i] + (ca_i128)ca_tau_pair_fused_rep_b[i] * lambda_tau;
        scalar %= g->order;
        if (scalar < 0) scalar += g->order;
        ca_elem expected;
        ca_group_mul(g, &expected, &pre->base.seed[0], (uint64_t)scalar, NULL);
        if (!ca_group_equal(g, &expected, &pre->orbit[i])) return 0;
    }
    return 1;
}

static int tau_pair_contribution(uint16_t word, ca_i128 *a, ca_i128 *b)
{
    if (word == CA_TAU_PAIR_FUSED_ZERO) {
        *a = *b = 0;
        return 1;
    }
    unsigned id = word & 127u, power = (word >> 7) & 3u;
    if (word == CA_TAU_PAIR_FUSED_UNREACHABLE || id >= CA_TAU_PAIR_FUSED_REPS || power >= 3)
        return 0;
    ca_i128 x = ca_tau_pair_fused_rep_a[id], y = ca_tau_pair_fused_rep_b[id];
    for (unsigned j = 0; j < power; j++) {
        ca_i128 next_x = x + 3 * y, next_y = -x - 2 * y;
        x = next_x;
        y = next_y;
    }
    if (word & 512u) x = -x, y = -y;
    *a = x;
    *b = y;
    return 1;
}

static uint16_t tau_pair_single_word(uint8_t even, uint8_t odd)
{
    if (even != 255 && odd != 255) return CA_TAU_PAIR_FUSED_UNREACHABLE;
    if (even != 255) return ca_tau_pair_fused_even_word[even];
    if (odd != 255) return ca_tau_pair_fused_odd_word[odd];
    return CA_TAU_PAIR_FUSED_ZERO;
}

static uint16_t tau_pair_policy_word(ca_i128 x, ca_i128 y, unsigned phase)
{
    int negative;
    size_t pos = tau_double_fold_index(x, y, phase, &negative);
    ca_i128 a = negative ? -x : x, b = negative ? -y : y;
    unsigned residue = residue3(a) * 3 + residue3(b);
    unsigned code = ca_tau_pair_fused_code[pos];
    if (code >= ca_tau_pair_fused_length[phase][residue]) return CA_TAU_PAIR_FUSED_UNREACHABLE;
    uint16_t word = ca_tau_pair_fused_dictionary[ca_tau_pair_fused_offset[phase][residue] + code];
    if (negative && word != CA_TAU_PAIR_FUSED_ZERO && word != CA_TAU_PAIR_FUSED_UNREACHABLE)
        word ^= 512u;
    return word;
}

static size_t tau_pair_canonical_words(ca_i128 x, ca_i128 y, const ca_tau4_digit digit[81],
                                       uint16_t words[128])
{
    uint8_t digits[256];
    size_t nd = gen_tau4_digits_fast(x, y, digit, digits);
    if (!nd && (x || y)) return 0;
    size_t pairs = (nd + 1) / 2;
    for (size_t i = 0; i < pairs; i++) {
        uint8_t even = digits[2 * i], odd = 2 * i + 1 < nd ? digits[2 * i + 1] : 255;
        words[i] = tau_pair_single_word(even, odd);
        if (words[i] == CA_TAU_PAIR_FUSED_UNREACHABLE) return 0;
    }
    return pairs;
}

static size_t tau_pair_fused_plan(ca_i128 x, ca_i128 y, const ca_tau4_digit digit[81],
                                  uint16_t words[128])
{
    ca_i128 original_x = x, original_y = y;
    const ca_i128 limit = (ca_i128)1 << 55;
    if (x <= -limit || x >= limit || y <= -limit || y >= limit)
        return tau_pair_canonical_words(x, y, digit, words);
    size_t pairs = 0;
    while (x < -CA_TAU_DOUBLE_BOUND || x > CA_TAU_DOUBLE_BOUND || y < -CA_TAU_DOUBLE_BOUND ||
           y > CA_TAU_DOUBLE_BOUND) {
        if (pairs >= 127) goto canonical_fallback;
        uint8_t slots[2] = {255, 255};
        for (size_t j = 0; j < 2; j++) {
            if (x % 3) {
                int xm = (int)((x % 9 + 9) % 9);
                int ym = (int)((y % 9 + 9) % 9);
                slots[j] = (uint8_t)(9 * xm + ym);
                if (digit[slots[j]].seed < 0) goto canonical_fallback;
                x -= digit[slots[j]].a;
                y -= digit[slots[j]].b;
            }
            ca_i128 old_x = x;
            if (old_x % 3) goto canonical_fallback;
            x += y;
            y = -old_x / 3;
        }
        words[pairs] = tau_pair_single_word(slots[0], slots[1]);
        if (words[pairs] == CA_TAU_PAIR_FUSED_UNREACHABLE) goto canonical_fallback;
        pairs++;
    }
    if (x || y) {
        int negative;
        size_t pos = tau_double_fold_index(x, y, (unsigned)(pairs % 3), &negative);
        int selected = (ca_tau_pair_fused_gate[pos >> 3] >> (pos & 7)) & 1;
        if (selected) {
            while (x || y) {
                if (pairs >= 128) goto canonical_fallback;
                uint16_t word = tau_pair_policy_word(x, y, (unsigned)(pairs % 3));
                ca_i128 da, db;
                if (!tau_pair_contribution(word, &da, &db)) goto canonical_fallback;
                ca_i128 ax = x - da, by = y - db;
                if (ax % 3 || by % 3) goto canonical_fallback;
                x = 2 * (ax / 3) + by;
                y = -(ax + by) / 3;
                if (x < -CA_TAU_DOUBLE_BOUND || x > CA_TAU_DOUBLE_BOUND ||
                    y < -CA_TAU_DOUBLE_BOUND || y > CA_TAU_DOUBLE_BOUND)
                    goto canonical_fallback;
                words[pairs++] = word;
            }
        } else {
            uint16_t tail[128];
            size_t remaining = tau_pair_canonical_words(x, y, digit, tail);
            if (!remaining || remaining > 128 - pairs) goto canonical_fallback;
            memcpy(words + pairs, tail, remaining * sizeof(*words));
            pairs += remaining;
        }
    }
    while (pairs && words[pairs - 1] == CA_TAU_PAIR_FUSED_ZERO) pairs--;
    return pairs;
canonical_fallback:
    return tau_pair_canonical_words(original_x, original_y, digit, words);
}

static int tau_pair_recode_verify_base(const ca_tau4_precomp *base, uint64_t k)
{
    if (!base || !base->g) return 0;
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){base->v1x, base->v1y}, (tau_vec){base->v2x, base->v2y}, base->det,
                        k % base->g->order, &x, &y);
    uint16_t words[128];
    size_t pairs = tau_pair_fused_plan(x, y, base->digit, words);
    if (!pairs && (x || y)) return 0;
    ca_i128 a = 0, b = 0;
    unsigned additions = 0, triples = 0, rotations = 0;
    for (size_t i = pairs; i-- > 0;) {
        ca_i128 next_a = -3 * a - 9 * b, next_b = 3 * a + 6 * b;
        ca_i128 da, db;
        if (!tau_pair_contribution(words[i], &da, &db)) return 0;
        a = next_a + da;
        b = next_b + db;
        if (words[i] != CA_TAU_PAIR_FUSED_ZERO) {
            if (!additions) triples = (unsigned)i;
            additions++;
            rotations += (unsigned)((((words[i] >> 7) & 3u) + i % 3) % 3 != 0);
        }
    }
    if (a != x || b != y) return 0;
    uint8_t old_digits[256];
    size_t old_nd = gen_tau4_digits_double_residue(x, y, base->digit, old_digits);
    if (!old_nd && (x || y)) return 0;
    return 10 * triples + 16 * additions + rotations <=
           tau4_weighted_cost(old_digits, old_nd, base->digit);
}

int ca_ec_tau_pair_fused_recode_verify_scalar(const ca_tau_pair_fused_precomp *pre, uint64_t k)
{
    return pre && tau_pair_recode_verify_base(&pre->base, k);
}

int ca_ec_tau_pair_fused_mul_profile(const ca_group *g, const ca_tau_pair_fused_precomp *pre,
                                     ca_elem *out, uint64_t k, uint64_t *triples, uint64_t *adds,
                                     uint64_t *rotations)
{
    if (!g || !pre || !out || pre->base.g != g) return 0;
    if (triples) *triples = 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (pre->base.identity || k % g->order == 0) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->base.v1x, pre->base.v1y},
                        (tau_vec){pre->base.v2x, pre->base.v2y}, pre->base.det, k % g->order, &x,
                        &y);
    uint16_t words[128];
    size_t pairs = tau_pair_fused_plan(x, y, pre->base.digit, words);
    if (!pairs) return 0;
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t na = 0, n3 = 0, nr = 0;
    for (size_t i = pairs; i-- > 0;) {
        if (acc.z) {
            acc = jac_triple(g, acc);
            n3++;
        }
        uint16_t word = words[i];
        if (word == CA_TAU_PAIR_FUSED_ZERO) continue;
        unsigned id = word & 127u, power = (word >> 7) & 3u;
        if (id >= CA_TAU_PAIR_FUSED_REPS || power >= 3) return 0;
        ca_elem point = pre->orbit[id];
        if (point.w[2]) continue;
        power = (power + (unsigned)(i % 3)) % 3;
        nr += power != 0;
        if (power == 1)
            point.w[0] = fm(g, pre->base.beta, point.w[0]);
        else if (power == 2)
            point.w[0] = fm(g, pre->base.beta2, point.w[0]);
        int negative = ((word & 512u) != 0) != ((i & 1) != 0);
        if (negative && point.w[1]) point.w[1] = g->p - point.w[1];
        acc = jac_add_mixed(g, acc, &point);
        na++;
    }
    jac_to_affine(g, out, acc);
    if (triples) *triples = n3;
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    return 1;
}

int ca_ec_tau_pair_complete_prepare(const ca_group *g, const ca_elem *point,
                                    ca_tau_pair_complete_precomp *out, uint64_t *seed_ops,
                                    uint64_t *pair_adds, uint64_t *pair_rotations,
                                    uint64_t *inversions)
{
    if (!g || !point || !out) return 0;
    _Static_assert(CA_TAU_PAIR_COMPLETE_COUNT == 726, "exact pair count changed");
    ca_tau_pair_fused_precomp folded;
    uint64_t base_ops = 0, additions = 0, rotations = 0, base_inversions = 0;
    if (!ca_ec_tau_pair_fused_prepare(g, point, &folded, &base_ops, &additions, &rotations,
                                      &base_inversions))
        return 0;
    ca_tau_pair_complete_precomp pre = {0};
    pre.base = folded.base;
    for (size_t i = 0; i < CA_TAU_PAIR_FUSED_REPS; i++) {
        ca_elem original = folded.orbit[i];
        pre.exact[6 * i] = original;
        ca_elem first = original, second = original;
        if (!original.w[2]) {
            first.w[0] = fm(g, folded.base.beta, original.w[0]);
            second.w[0] = fm(g, folded.base.beta2, original.w[0]);
            rotations += 2;
        }
        pre.exact[6 * i + 1] = first;
        pre.exact[6 * i + 2] = second;
        for (size_t power = 0; power < 3; power++) {
            ca_elem negative = pre.exact[6 * i + power];
            if (!negative.w[2] && negative.w[1]) negative.w[1] = g->p - negative.w[1];
            pre.exact[6 * i + 3 + power] = negative;
        }
    }
    *out = pre;
    if (seed_ops) *seed_ops = base_ops;
    if (pair_adds) *pair_adds = additions;
    if (pair_rotations) *pair_rotations = rotations;
    if (inversions) *inversions = base_inversions;
    return 1;
}

size_t ca_ec_tau_pair_complete_static_bytes(void) { return ca_ec_tau_pair_fused_static_bytes(); }

int ca_ec_tau_pair_complete_prepare_verify(const ca_tau_pair_complete_precomp *pre)
{
    if (!pre || !pre->base.g) return 0;
    const ca_group *g = pre->base.g;
    if (pre->base.identity) {
        for (size_t i = 0; i < CA_TAU_PAIR_COMPLETE_COUNT; i++)
            if (!ca_group_is_identity(g, &pre->exact[i])) return 0;
        return 1;
    }
    ca_i128 lambda_tau = (ca_i128)1 + g->endo_lambda;
    for (size_t i = 0; i < CA_TAU_PAIR_FUSED_REPS; i++) {
        ca_i128 a = ca_tau_pair_fused_rep_a[i], b = ca_tau_pair_fused_rep_b[i];
        for (size_t power = 0; power < 3; power++) {
            ca_i128 scalar = (a + b * lambda_tau) % g->order;
            if (scalar < 0) scalar += g->order;
            for (size_t negative = 0; negative < 2; negative++) {
                ca_i128 signed_scalar = negative && scalar ? g->order - scalar : scalar;
                ca_elem expected;
                ca_group_mul(g, &expected, &pre->base.seed[0], (uint64_t)signed_scalar, NULL);
                if (!ca_group_equal(g, &expected, &pre->exact[6 * i + 3 * negative + power]))
                    return 0;
            }
            ca_i128 next_a = a + 3 * b, next_b = -a - 2 * b;
            a = next_a;
            b = next_b;
        }
    }
    return 1;
}

int ca_ec_tau_pair_complete_recode_verify_scalar(const ca_tau_pair_complete_precomp *pre,
                                                 uint64_t k)
{
    return pre && tau_pair_recode_verify_base(&pre->base, k);
}

int ca_ec_tau_pair_complete_mul_profile(const ca_group *g, const ca_tau_pair_complete_precomp *pre,
                                        ca_elem *out, uint64_t k, uint64_t *triples, uint64_t *adds,
                                        uint64_t *rotations)
{
    if (!g || !pre || !out || pre->base.g != g) return 0;
    if (triples) *triples = 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (pre->base.identity || k % g->order == 0) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->base.v1x, pre->base.v1y},
                        (tau_vec){pre->base.v2x, pre->base.v2y}, pre->base.det, k % g->order, &x,
                        &y);
    uint16_t words[128];
    size_t pairs = tau_pair_fused_plan(x, y, pre->base.digit, words);
    if (!pairs) return 0;
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t na = 0, n3 = 0;
    for (size_t i = pairs; i-- > 0;) {
        if (acc.z) {
            acc = jac_triple(g, acc);
            n3++;
        }
        uint16_t word = words[i];
        if (word == CA_TAU_PAIR_FUSED_ZERO) continue;
        unsigned orbit = word & 127u, power = (word >> 7) & 3u;
        if (orbit >= CA_TAU_PAIR_FUSED_REPS || power >= 3) return 0;
        unsigned negative = ((word & 512u) != 0) ^ ((i & 1) != 0);
        size_t index = 6 * orbit + 3 * negative + (power + (unsigned)(i % 3)) % 3;
        const ca_elem *point = &pre->exact[index];
        if (point->w[2]) continue;
        acc = jac_add_mixed(g, acc, point);
        na++;
    }
    jac_to_affine(g, out, acc);
    if (triples) *triples = n3;
    if (adds) *adds = na;
    return 1;
}

/* In the lattice norm N(a,b)=a*a+3*a*b+3*b*b, every pair word has
 * N(d)<=532 and N(tau^2*q)=9*N(q).  The reduced inputs satisfy
 * |a|,|b|<2^55, so sqrt(N)<sqrt(7)*2^55 initially and remains below
 * that bound under q=(s-d)/tau^2.  Thus |a|<2^58 and |b|<2^57 at every
 * completed step; the intermediate sums below also fit signed int64_t.
 * Larger reduced inputs use the existing wide canonical path. */
static int tau_pair_periodic_bounded(int64_t a, int64_t b)
{
    return a >= -CA_TAU_PAIR_PERIODIC_BOUND && a <= CA_TAU_PAIR_PERIODIC_BOUND &&
           b >= -CA_TAU_PAIR_PERIODIC_BOUND && b <= CA_TAU_PAIR_PERIODIC_BOUND;
}

static size_t tau_pair_periodic_tail_index(int64_t a, int64_t b)
{
    return (size_t)(a + CA_TAU_PAIR_PERIODIC_BOUND) * CA_TAU_PAIR_PERIODIC_SIDE +
           (size_t)(b + CA_TAU_PAIR_PERIODIC_BOUND);
}

static size_t tau_pair_periodic_atlas_index(int64_t a, int64_t b)
{
    int ra = (int)((a % 27 + 27) % 27), rb = (int)((b % 27 + 27) % 27);
    if (ra > 13) ra -= 27;
    if (rb > 13) rb -= 27;
    return (size_t)(ra + 13) * CA_TAU_PAIR_PERIODIC_MODULUS + (size_t)(rb + 13);
}

static int tau_pair_periodic_quotient(int64_t a, int64_t b, int64_t da, int64_t db,
                                      int64_t *qa, int64_t *qb)
{
    int64_t ax = a - da, by = b - db;
    if (ax % 3 || by % 3) return 0;
    *qa = 2 * (ax / 3) + by;
    *qb = -(ax + by) / 3;
    return 1;
}

static int tau_pair_periodic_canonical_step(int64_t *a, int64_t *b,
                                             const ca_tau4_digit digit[81], uint16_t *word)
{
    uint8_t slots[2] = {255, 255};
    for (size_t j = 0; j < 2; j++) {
        if (*a % 3) {
            int slot = 9 * (int)((*a % 9 + 9) % 9) + (int)((*b % 9 + 9) % 9);
            if (digit[slot].seed < 0) return 0;
            slots[j] = (uint8_t)slot;
            *a -= digit[slot].a;
            *b -= digit[slot].b;
        }
        int64_t old_a = *a;
        if (old_a % 3) return 0;
        *a += *b;
        *b = -old_a / 3;
    }
    *word = tau_pair_single_word(slots[0], slots[1]);
    return *word != CA_TAU_PAIR_FUSED_UNREACHABLE;
}

/* Returns 2 only for the specified 128-word periodic fallback. */
static int tau_pair_periodic_plan(int64_t a, int64_t b, const ca_tau4_digit digit[81],
                                  int periodic, uint16_t words[128], size_t *count,
                                  uint64_t *lookups)
{
    size_t length = 0;
    while (a || b) {
        if (length == 128) return periodic ? 2 : 0;
        uint16_t word = CA_TAU_PAIR_FUSED_UNREACHABLE;
        if (tau_pair_periodic_bounded(a, b))
            word = ca_tau_pair_periodic_tail[tau_pair_periodic_tail_index(a, b)];
        if (word == CA_TAU_PAIR_FUSED_UNREACHABLE && periodic) {
            word = ca_tau_pair_periodic_atlas[tau_pair_periodic_atlas_index(a, b)];
            if (lookups) (*lookups)++;
        }
        if (word == CA_TAU_PAIR_FUSED_UNREACHABLE) {
            if (!tau_pair_periodic_canonical_step(&a, &b, digit, &word)) return 0;
        } else {
            ca_i128 wide_da, wide_db;
            int64_t qa, qb;
            if (!tau_pair_contribution(word, &wide_da, &wide_db) ||
                !tau_pair_periodic_quotient(a, b, (int64_t)wide_da, (int64_t)wide_db,
                                            &qa, &qb))
                return 0;
            if (tau_pair_periodic_bounded(a, b) &&
                ca_tau_pair_periodic_tail[tau_pair_periodic_tail_index(a, b)] == word &&
                !tau_pair_periodic_bounded(qa, qb))
                return 0;
            a = qa;
            b = qb;
        }
        words[length++] = word;
    }
    while (length && words[length - 1] == CA_TAU_PAIR_FUSED_ZERO) length--;
    *count = length;
    return 1;
}

static unsigned tau_pair_periodic_score(const uint16_t words[128], size_t count)
{
    if (!count) return 0;
    unsigned nonzero = 0;
    for (size_t i = 0; i < count; i++) nonzero += words[i] != CA_TAU_PAIR_FUSED_ZERO;
    return 10 * (unsigned)(count - 1) + 16 * nonzero;
}

int ca_ec_tau_pair_periodic_recode_words(const ca_tau_pair_complete_precomp *pre, uint64_t k,
                                         int gated, uint16_t words[128], size_t *count,
                                         uint64_t *lookups, uint64_t *accepted,
                                         uint64_t *fallbacks)
{
    if (!pre || !pre->base.g || !words || !count || (gated != 0 && gated != 1 && gated != 2))
        return 0;
    if (lookups) *lookups = 0;
    if (accepted) *accepted = 0;
    if (fallbacks) *fallbacks = 0;
    *count = 0;
    const ca_group *g = pre->base.g;
    if (k % g->order == 0) return 1;
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->base.v1x, pre->base.v1y},
                        (tau_vec){pre->base.v2x, pre->base.v2y}, pre->base.det, k % g->order, &x,
                        &y);
    const ca_i128 limit = (ca_i128)1 << 55;
    if (x <= -limit || x >= limit || y <= -limit || y >= limit) {
        *count = tau_pair_canonical_words(x, y, pre->base.digit, words);
        return *count != 0;
    }
    if (gated == 2) {
        int64_t a = (int64_t)x, b = (int64_t)y;
        uint16_t first = CA_TAU_PAIR_FUSED_UNREACHABLE;
        if (tau_pair_periodic_bounded(a, b))
            first = ca_tau_pair_periodic_tail[tau_pair_periodic_tail_index(a, b)];
        if (first == CA_TAU_PAIR_FUSED_UNREACHABLE) {
            first = ca_tau_pair_periodic_atlas[tau_pair_periodic_atlas_index(a, b)];
            if (lookups) (*lookups)++;
        }
        if (first >= 1024) return 0;
        if (ca_tau_pair_firstword_gate[first >> 3] & (1u << (first & 7))) {
            int status = tau_pair_periodic_plan(a, b, pre->base.digit, 1, words, count, lookups);
            if (status == 1) {
                if (accepted) *accepted = 1;
                return 1;
            }
            if (status != 2) return 0;
            if (fallbacks) *fallbacks = 1;
        }
        return tau_pair_periodic_plan(a, b, pre->base.digit, 0, words, count, NULL) == 1;
    }
    int status =
        tau_pair_periodic_plan((int64_t)x, (int64_t)y, pre->base.digit, 0, words, count, NULL);
    if (status != 1) return 0;
    if (!gated) return 1;
    uint16_t periodic_words[128];
    size_t periodic_count = 0;
    status = tau_pair_periodic_plan((int64_t)x, (int64_t)y, pre->base.digit, 1, periodic_words,
                                    &periodic_count, lookups);
    if (status == 2) {
        if (fallbacks) *fallbacks = 1;
        return 1;
    }
    if (status != 1) return 0;
    if (tau_pair_periodic_score(periodic_words, periodic_count) <
        tau_pair_periodic_score(words, *count)) {
        memcpy(words, periodic_words, periodic_count * sizeof(*words));
        *count = periodic_count;
        if (accepted) *accepted = 1;
    }
    return 1;
}

int ca_ec_tau_pair_periodic_recode_verify_scalar(const ca_tau_pair_complete_precomp *pre,
                                                 uint64_t k, int gated)
{
    if (!pre || !pre->base.g) return 0;
    uint16_t words[128];
    size_t count = 0;
    if (!ca_ec_tau_pair_periodic_recode_words(pre, k, gated, words, &count, NULL, NULL, NULL))
        return 0;
    ca_i128 a = 0, b = 0, da, db;
    for (size_t i = count; i-- > 0;) {
        ca_i128 next_a = -3 * a - 9 * b, next_b = 3 * a + 6 * b;
        if (!tau_pair_contribution(words[i], &da, &db)) return 0;
        a = next_a + da;
        b = next_b + db;
    }
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->base.v1x, pre->base.v1y},
                        (tau_vec){pre->base.v2x, pre->base.v2y}, pre->base.det,
                        k % pre->base.g->order, &x, &y);
    return a == x && b == y;
}

size_t ca_ec_tau_pair_periodic_static_bytes(void)
{
    return ca_ec_tau_pair_complete_static_bytes() + sizeof(ca_tau_pair_periodic_tail) +
           sizeof(ca_tau_pair_periodic_atlas);
}

size_t ca_ec_tau_pair_firstword_static_bytes(void)
{
    return ca_ec_tau_pair_periodic_static_bytes() + sizeof(ca_tau_pair_firstword_gate);
}

int ca_ec_tau_pair_periodic_mul_profile(const ca_group *g, const ca_tau_pair_complete_precomp *pre,
                                        ca_elem *out, uint64_t k, int gated, uint64_t *triples,
                                        uint64_t *adds, uint64_t *lookups, uint64_t *accepted,
                                        uint64_t *fallbacks)
{
    if (!g || !pre || !out || pre->base.g != g) return 0;
    if (triples) *triples = 0;
    if (adds) *adds = 0;
    if (lookups) *lookups = 0;
    if (accepted) *accepted = 0;
    if (fallbacks) *fallbacks = 0;
    if (pre->base.identity || k % g->order == 0) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    uint16_t words[128];
    size_t count = 0;
    if (!ca_ec_tau_pair_periodic_recode_words(pre, k, gated, words, &count, lookups, accepted,
                                               fallbacks) || !count)
        return 0;
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t na = 0, n3 = 0;
    for (size_t i = count; i-- > 0;) {
        if (acc.z) {
            acc = jac_triple(g, acc);
            n3++;
        }
        uint16_t word = words[i];
        if (word == CA_TAU_PAIR_FUSED_ZERO) continue;
        unsigned orbit = word & 127u, power = (word >> 7) & 3u;
        if (orbit >= CA_TAU_PAIR_FUSED_REPS || power >= 3) return 0;
        unsigned negative = ((word & 512u) != 0) ^ ((i & 1) != 0);
        size_t index = 6 * orbit + 3 * negative + (power + (unsigned)(i % 3)) % 3;
        const ca_elem *point = &pre->exact[index];
        if (point->w[2]) continue;
        acc = jac_add_mixed(g, acc, point);
        na++;
    }
    jac_to_affine(g, out, acc);
    if (triples) *triples = n3;
    if (adds) *adds = na;
    return 1;
}

/* The low 10 bits retain the existing pair word. Bits 10-11 select
 * tau^2, tau, or doubling. All mixed-tail paths stay inside [-64,64]^2. */
static int tau_pair_mixed_step(int64_t a, int64_t b, uint16_t action,
                                int64_t *qa, int64_t *qb)
{
    unsigned kind = action >> 10;
    uint16_t word = action & 1023u;
    ca_i128 wide_da, wide_db;
    if (kind > 2 || !tau_pair_contribution(word, &wide_da, &wide_db)) return 0;
    int64_t da = (int64_t)wide_da, db = (int64_t)wide_db;
    int64_t ax = a - da, by = b - db;
    if (kind == 0) return tau_pair_periodic_quotient(a, b, da, db, qa, qb);
    if (kind == 1) {
        if (ax % 3) return 0;
        *qa = by + ax;
        *qb = -ax / 3;
        return 1;
    }
    if (ax % 2 || by % 2) return 0;
    *qa = ax / 2;
    *qb = by / 2;
    return 1;
}

static int tau_pair_mixed_verify_map(const uint16_t *map)
{
    for (int64_t start_a = -CA_TAU_PAIR_MIXED_BOUND;
         start_a <= CA_TAU_PAIR_MIXED_BOUND; start_a++)
        for (int64_t start_b = -CA_TAU_PAIR_MIXED_BOUND;
             start_b <= CA_TAU_PAIR_MIXED_BOUND; start_b++) {
            int64_t a = start_a, b = start_b;
            uint16_t actions[128];
            size_t count = 0;
            while (a || b) {
                if (!tau_pair_periodic_bounded(a, b) || count == 128) return 0;
                uint16_t action = map[tau_pair_periodic_tail_index(a, b)];
                int64_t qa, qb;
                if (!tau_pair_mixed_step(a, b, action, &qa, &qb)) return 0;
                actions[count++] = action;
                a = qa;
                b = qb;
            }
            ca_i128 rebuilt_a = 0, rebuilt_b = 0;
            for (size_t i = count; i-- > 0;) {
                unsigned kind = actions[i] >> 10;
                ca_i128 da, db;
                if (!tau_pair_contribution(actions[i] & 1023u, &da, &db)) return 0;
                ca_i128 next_a, next_b;
                if (kind == 0) {
                    next_a = -3 * rebuilt_a - 9 * rebuilt_b;
                    next_b = 3 * rebuilt_a + 6 * rebuilt_b;
                } else if (kind == 1) {
                    next_a = -3 * rebuilt_b;
                    next_b = rebuilt_a + 3 * rebuilt_b;
                } else if (kind == 2) {
                    next_a = 2 * rebuilt_a;
                    next_b = 2 * rebuilt_b;
                } else return 0;
                rebuilt_a = next_a + da;
                rebuilt_b = next_b + db;
            }
            if (rebuilt_a != start_a || rebuilt_b != start_b) return 0;
        }
    return 1;
}

int ca_ec_tau_pair_mixed_verify_map(void)
{
    return tau_pair_mixed_verify_map(ca_tau_pair_mixed_action);
}

int ca_ec_tau_pair_mixed_full_verify_map(void)
{
    return tau_pair_mixed_verify_map(ca_tau_pair_mixed_full_action);
}

int ca_ec_tau_pair_mixed_verify_tau_kernel(const ca_group *g, const ca_elem *point)
{
    if (!g || !point || point->w[2] || point->w[0]) return 0;
    uint64_t one_minus_beta = fs(g, g->mont.r1, g->endo_c_mont);
    tau_jac tau_point = jac_tau(g, (tau_jac){point->w[0], point->w[1], g->mont.r1},
                                one_minus_beta);
    ca_elem result;
    jac_to_affine(g, &result, tau_point);
    return ca_group_is_identity(g, &result);
}

static int tau_pair_mixed_recode_actions(const ca_tau_pair_complete_precomp *pre, uint64_t k,
                                         uint16_t actions[128], size_t *count,
                                         uint64_t *lookups, uint64_t *fallbacks,
                                         const uint16_t *map)
{
    if (!pre || !pre->base.g || !actions || !count) return 0;
    _Static_assert(CA_TAU_PAIR_MIXED_BOUND == CA_TAU_PAIR_PERIODIC_BOUND,
                   "mixed and canonical tail bounds differ");
    _Static_assert(CA_TAU_PAIR_MIXED_SIDE == CA_TAU_PAIR_PERIODIC_SIDE,
                   "mixed and canonical tail layouts differ");
    *count = 0;
    if (lookups) *lookups = 0;
    if (fallbacks) *fallbacks = 0;
    const ca_group *g = pre->base.g;
    if (k % g->order == 0) return 1;
    ca_i128 wide_a, wide_b;
    reduce_with_lattice((tau_vec){pre->base.v1x, pre->base.v1y},
                        (tau_vec){pre->base.v2x, pre->base.v2y}, pre->base.det, k % g->order,
                        &wide_a, &wide_b);
    const ca_i128 limit = (ca_i128)1 << 55;
    if (wide_a <= -limit || wide_a >= limit || wide_b <= -limit || wide_b >= limit)
        goto canonical_fallback;
    int64_t a = (int64_t)wide_a, b = (int64_t)wide_b;
    while (a || b) {
        if (*count == 128) goto canonical_fallback;
        uint16_t action;
        if (tau_pair_periodic_bounded(a, b) &&
            ca_tau_pair_periodic_tail[tau_pair_periodic_tail_index(a, b)] !=
                CA_TAU_PAIR_FUSED_UNREACHABLE) {
            action = map[tau_pair_periodic_tail_index(a, b)];
            if (lookups) (*lookups)++;
            int64_t qa, qb;
            if (!tau_pair_mixed_step(a, b, action, &qa, &qb) ||
                !tau_pair_periodic_bounded(qa, qb))
                return 0;
            a = qa;
            b = qb;
        } else {
            uint16_t word;
            if (!tau_pair_periodic_canonical_step(&a, &b, pre->base.digit, &word)) return 0;
            action = word;
        }
        actions[(*count)++] = action;
    }
    return 1;
canonical_fallback:
    *count = tau_pair_canonical_words(wide_a, wide_b, pre->base.digit, actions);
    if (!*count) return 0;
    if (fallbacks) *fallbacks = 1;
    return 1;
}

int ca_ec_tau_pair_mixed_recode_actions(const ca_tau_pair_complete_precomp *pre, uint64_t k,
                                         uint16_t actions[128], size_t *count,
                                         uint64_t *lookups, uint64_t *fallbacks)
{
    return tau_pair_mixed_recode_actions(pre, k, actions, count, lookups, fallbacks,
                                         ca_tau_pair_mixed_action);
}

int ca_ec_tau_pair_mixed_full_recode_actions(const ca_tau_pair_complete_precomp *pre, uint64_t k,
                                              uint16_t actions[128], size_t *count,
                                              uint64_t *lookups, uint64_t *fallbacks)
{
    return tau_pair_mixed_recode_actions(pre, k, actions, count, lookups, fallbacks,
                                         ca_tau_pair_mixed_full_action);
}

static int tau_pair_mixed_recode_verify_scalar(const ca_tau_pair_complete_precomp *pre,
                                                uint64_t k, const uint16_t *map)
{
    if (!pre || !pre->base.g) return 0;
    uint16_t actions[128];
    size_t count = 0;
    if (!tau_pair_mixed_recode_actions(pre, k, actions, &count, NULL, NULL, map)) return 0;
    ca_i128 a = 0, b = 0;
    for (size_t i = count; i-- > 0;) {
        unsigned kind = actions[i] >> 10;
        ca_i128 da, db;
        if (kind > 2 || !tau_pair_contribution(actions[i] & 1023u, &da, &db)) return 0;
        ca_i128 next_a, next_b;
        if (kind == 0) {
            next_a = -3 * a - 9 * b;
            next_b = 3 * a + 6 * b;
        } else if (kind == 1) {
            next_a = -3 * b;
            next_b = a + 3 * b;
        } else {
            next_a = 2 * a;
            next_b = 2 * b;
        }
        a = next_a + da;
        b = next_b + db;
    }
    ca_i128 expected_a, expected_b;
    reduce_with_lattice((tau_vec){pre->base.v1x, pre->base.v1y},
                        (tau_vec){pre->base.v2x, pre->base.v2y}, pre->base.det,
                        k % pre->base.g->order, &expected_a, &expected_b);
    return a == expected_a && b == expected_b;
}

int ca_ec_tau_pair_mixed_recode_verify_scalar(const ca_tau_pair_complete_precomp *pre, uint64_t k)
{
    return tau_pair_mixed_recode_verify_scalar(pre, k, ca_tau_pair_mixed_action);
}

int ca_ec_tau_pair_mixed_full_recode_verify_scalar(const ca_tau_pair_complete_precomp *pre,
                                                    uint64_t k)
{
    return tau_pair_mixed_recode_verify_scalar(pre, k, ca_tau_pair_mixed_full_action);
}

size_t ca_ec_tau_pair_mixed_static_bytes(void)
{
    return ca_ec_tau_pair_complete_static_bytes() + sizeof(ca_tau_pair_periodic_tail) +
           sizeof(ca_tau_pair_mixed_action);
}

size_t ca_ec_tau_pair_mixed_full_static_bytes(void)
{
    return ca_ec_tau_pair_complete_static_bytes() + sizeof(ca_tau_pair_periodic_tail) +
           sizeof(ca_tau_pair_mixed_full_action);
}

static int tau_pair_mixed_mul_profile(const ca_group *g,
                                      const ca_tau_pair_complete_precomp *pre,
                                      ca_elem *out, uint64_t k, uint64_t *triples,
                                      uint64_t *tau_steps, uint64_t *doubles, uint64_t *adds,
                                      uint64_t *lookups, uint64_t *fallbacks,
                                      const uint16_t *map)
{
    if (!g || !pre || !out || pre->base.g != g) return 0;
    if (triples) *triples = 0;
    if (tau_steps) *tau_steps = 0;
    if (doubles) *doubles = 0;
    if (adds) *adds = 0;
    if (lookups) *lookups = 0;
    if (fallbacks) *fallbacks = 0;
    if (pre->base.identity || k % g->order == 0) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    uint16_t actions[128];
    size_t count = 0;
    if (!tau_pair_mixed_recode_actions(pre, k, actions, &count, lookups, fallbacks, map) ||
        !count)
        return 0;
    uint8_t pair_below[128];
    unsigned pairs = 0;
    for (size_t i = 0; i < count; i++) {
        pair_below[i] = (uint8_t)(pairs % 6);
        pairs += (actions[i] >> 10) == 0;
    }
    uint64_t one_minus_beta = fs(g, g->mont.r1, g->endo_c_mont);
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t n3 = 0, nt = 0, nd = 0, na = 0;
    for (size_t i = count; i-- > 0;) {
        unsigned kind = actions[i] >> 10;
        if (kind > 2) return 0;
        if (acc.z) {
            if (kind == 0) {
                acc = jac_triple(g, acc);
                n3++;
            } else if (kind == 1) {
                acc = jac_tau(g, acc, one_minus_beta);
                nt++;
            } else {
                acc = jac_double(g, acc);
                nd++;
            }
        }
        uint16_t word = actions[i] & 1023u;
        if (word == CA_TAU_PAIR_FUSED_ZERO) continue;
        unsigned orbit = word & 127u, power = (word >> 7) & 3u;
        if (orbit >= CA_TAU_PAIR_FUSED_REPS || power >= 3) return 0;
        unsigned phase = pair_below[i];
        unsigned negative = ((word & 512u) != 0) ^ ((phase & 1u) != 0);
        size_t point_index = 6 * orbit + 3 * negative + (power + phase % 3) % 3;
        const ca_elem *point = &pre->exact[point_index];
        if (point->w[2]) continue;
        acc = jac_add_mixed(g, acc, point);
        na++;
    }
    jac_to_affine(g, out, acc);
    if (triples) *triples = n3;
    if (tau_steps) *tau_steps = nt;
    if (doubles) *doubles = nd;
    if (adds) *adds = na;
    return 1;
}

int ca_ec_tau_pair_mixed_mul_profile(const ca_group *g, const ca_tau_pair_complete_precomp *pre,
                                     ca_elem *out, uint64_t k, uint64_t *triples,
                                     uint64_t *tau_steps, uint64_t *doubles, uint64_t *adds,
                                     uint64_t *lookups, uint64_t *fallbacks)
{
    return tau_pair_mixed_mul_profile(g, pre, out, k, triples, tau_steps, doubles, adds,
                                      lookups, fallbacks, ca_tau_pair_mixed_action);
}

int ca_ec_tau_pair_mixed_full_mul_profile(const ca_group *g,
                                          const ca_tau_pair_complete_precomp *pre,
                                          ca_elem *out, uint64_t k, uint64_t *triples,
                                          uint64_t *tau_steps, uint64_t *doubles, uint64_t *adds,
                                          uint64_t *lookups, uint64_t *fallbacks)
{
    return tau_pair_mixed_mul_profile(g, pre, out, k, triples, tau_steps, doubles, adds,
                                      lookups, fallbacks, ca_tau_pair_mixed_full_action);
}

int ca_ec_tau4_pos_prepare(const ca_group *g, const ca_elem *point, ca_tau4_pos_precomp *out,
                           uint64_t *precompute_triples)
{
    if (!g || !point || !out) return 0;
    if (precompute_triples) *precompute_triples = 0;
    ca_tau4_pos_precomp pre = {0};
    if (!ca_ec_tau4_prepare(g, point, &pre.base, NULL)) return 0;
    if (pre.base.identity) {
        ca_elem identity;
        ca_group_identity(g, &identity);
        for (size_t q = 0; q < CA_TAU_POS_Q; q++)
            for (size_t parity = 0; parity < 2; parity++)
                for (size_t j = 0; j < 9; j++) pre.point[q][parity][j] = identity;
        *out = pre;
        return 1;
    }
    for (size_t j = 0; j < 9; j++) {
        pre.point[0][0][j] = pre.base.seed[j];
        pre.point[0][1][j] = pre.base.tau_seed[j];
    }
    uint64_t triples = 0;
    for (size_t q = 1; q < CA_TAU_POS_Q; q++) {
        tau_jac projective[18];
        ca_elem affine[18];
        for (size_t parity = 0; parity < 2; parity++) {
            for (size_t j = 0; j < 9; j++) {
                const ca_elem *prior = &pre.point[q - 1][parity][j];
                size_t slot = parity * 9 + j;
                if (prior->w[2]) {
                    projective[slot] = (tau_jac){0, g->mont.r1, 0};
                } else {
                    projective[slot] =
                        jac_triple(g, (tau_jac){prior->w[0], prior->w[1], g->mont.r1});
                    triples++;
                }
            }
        }
        jac_batch_to_affine(g, affine, projective, 18);
        for (size_t parity = 0; parity < 2; parity++)
            for (size_t j = 0; j < 9; j++) pre.point[q][parity][j] = affine[parity * 9 + j];
    }
    *out = pre;
    if (precompute_triples) *precompute_triples = triples;
    return 1;
}

/* Prepare the identical affine table by retaining all intermediate layers
 * in Jacobian form. The sole batch inversion occurs after the final layer.
 * Every zero Z is replaced by one in the prefix product, then restored as
 * the canonical identity in the output. */
int ca_ec_tau4_pos_global_prepare(const ca_group *g, const ca_elem *point, ca_tau4_pos_precomp *out,
                                  uint64_t *precompute_triples)
{
    if (!g || !point || !out) return 0;
    if (precompute_triples) *precompute_triples = 0;
    ca_tau4_pos_precomp pre = {0};
    if (!ca_ec_tau4_prepare(g, point, &pre.base, NULL)) return 0;
    if (pre.base.identity) {
        ca_elem identity;
        ca_group_identity(g, &identity);
        for (size_t q = 0; q < CA_TAU_POS_Q; q++)
            for (size_t parity = 0; parity < 2; parity++)
                for (size_t j = 0; j < 9; j++) pre.point[q][parity][j] = identity;
        *out = pre;
        return 1;
    }
    const size_t count = (size_t)CA_TAU_POS_Q * 2 * 9;
    tau_jac *projective = malloc(count * sizeof(*projective));
    uint64_t *prefixes = malloc(count * sizeof(*prefixes));
    if (!projective || !prefixes) {
        free(prefixes);
        free(projective);
        return 0;
    }
    for (size_t parity = 0; parity < 2; parity++) {
        for (size_t j = 0; j < 9; j++) {
            const ca_elem *seed = parity ? &pre.base.tau_seed[j] : &pre.base.seed[j];
            projective[parity * 9 + j] = seed->w[2] ? (tau_jac){0, g->mont.r1, 0}
                                                    : (tau_jac){seed->w[0], seed->w[1], g->mont.r1};
        }
    }
    uint64_t triples = 0;
    for (size_t q = 1; q < CA_TAU_POS_Q; q++) {
        for (size_t slot = 0; slot < 18; slot++) {
            tau_jac prior = projective[(q - 1) * 18 + slot];
            if (prior.z) {
                projective[q * 18 + slot] = jac_triple(g, prior);
                triples++;
            } else {
                projective[q * 18 + slot] = (tau_jac){0, g->mont.r1, 0};
            }
        }
    }
    uint64_t product = g->mont.r1;
    for (size_t i = 0; i < count; i++) {
        uint64_t z = projective[i].z ? projective[i].z : g->mont.r1;
        product = fm(g, product, z);
        prefixes[i] = product;
    }
    uint64_t inverse = ca_mont_inv(&g->mont, product);
    if (!inverse) {
        free(prefixes);
        free(projective);
        return 0;
    }
    ca_elem *affine = &pre.point[0][0][0];
    for (size_t i = count; i-- > 0;) {
        tau_jac p = projective[i];
        uint64_t invz = fm(g, inverse, i ? prefixes[i - 1] : g->mont.r1);
        inverse = fm(g, inverse, p.z ? p.z : g->mont.r1);
        if (!p.z) {
            affine[i] = (ca_elem){{0, 0, 1, 0}};
            continue;
        }
        uint64_t invz2 = fq(g, invz);
        affine[i].w[0] = fm(g, p.x, invz2);
        affine[i].w[1] = fm(g, p.y, fm(g, invz2, invz));
        affine[i].w[2] = affine[i].w[3] = 0;
    }
    free(prefixes);
    free(projective);
    *out = pre;
    if (precompute_triples) *precompute_triples = triples;
    return 1;
}

static int tau4_pos_mul_jac(const ca_group *g, const ca_tau4_pos_precomp *pre, tau_jac *out,
                            uint64_t k, uint64_t *adds, uint64_t *rotations)
{
    if (!g || !pre || !out || pre->base.g != g) return 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (pre->base.identity || k % g->order == 0) {
        *out = (tau_jac){0, g->mont.r1, 0};
        return 1;
    }
    k %= g->order;
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->base.v1x, pre->base.v1y},
                        (tau_vec){pre->base.v2x, pre->base.v2y}, pre->base.det, k, &x, &y);
    uint8_t digits[256];
    size_t nd = gen_tau4_digits_fast(x, y, pre->base.digit, digits);
    if (!nd || (nd - 1) / 2 >= CA_TAU_POS_Q) return 0;
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t na = 0, nr = 0;
    for (size_t i = nd; i-- > 0;) {
        int slot = digits[i];
        if (slot == 255) continue;
        size_t q = i / 2;
        ca_tau4_digit d = pre->base.digit[slot];
        ca_elem seed = pre->point[q][i & 1][d.seed];
        if (seed.w[2]) continue;
        int power = (d.power + (int)(q % 3)) % 3;
        int sign = d.sign * ((q & 1) ? -1 : 1);
        if (power == 1)
            seed.w[0] = fm(g, pre->base.beta, seed.w[0]);
        else if (power == 2)
            seed.w[0] = fm(g, pre->base.beta2, seed.w[0]);
        nr += power != 0;
        if (sign < 0 && seed.w[1]) seed.w[1] = g->p - seed.w[1];
        acc = jac_add_mixed(g, acc, &seed);
        na++;
    }
    *out = acc;
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    return 1;
}

int ca_ec_tau4_pos_mul(const ca_group *g, const ca_tau4_pos_precomp *pre, ca_elem *out, uint64_t k,
                       uint64_t *adds, uint64_t *rotations)
{
    if (!out) return 0;
    tau_jac projective;
    if (!tau4_pos_mul_jac(g, pre, &projective, k, adds, rotations)) return 0;
    jac_to_affine(g, out, projective);
    return 1;
}

int ca_ec_tau4_pos_mul_batch(const ca_group *g, const ca_tau4_pos_precomp *pre, ca_elem *out,
                             const uint64_t *scalars, size_t count, size_t block_size,
                             uint64_t *adds, uint64_t *rotations, uint64_t *output_inversions)
{
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (output_inversions) *output_inversions = 0;
    if (!count) return 1;
    if (!g || !pre || !out || !scalars || pre->base.g != g || block_size == 0 || block_size > 4096)
        return 0;
    tau_jac *projective = malloc(block_size * sizeof(*projective));
    uint64_t *prefixes = malloc(block_size * sizeof(*prefixes));
    if (!projective || !prefixes) {
        free(prefixes);
        free(projective);
        return 0;
    }
    uint64_t total_adds = 0, total_rotations = 0, total_inversions = 0;
    for (size_t offset = 0; offset < count;) {
        size_t n = count - offset;
        if (n > block_size) n = block_size;
        for (size_t i = 0; i < n; i++) {
            uint64_t a = 0, r = 0;
            if (!tau4_pos_mul_jac(g, pre, &projective[i], scalars[offset + i], &a, &r)) {
                free(prefixes);
                free(projective);
                return 0;
            }
            total_adds += a;
            total_rotations += r;
        }
        uint64_t inversions = 0;
        if (!jac_batch_to_affine_scratch(g, out + offset, projective, n, prefixes, &inversions)) {
            free(prefixes);
            free(projective);
            return 0;
        }
        total_inversions += inversions;
        offset += n;
    }
    free(prefixes);
    free(projective);
    if (adds) *adds = total_adds;
    if (rotations) *rotations = total_rotations;
    if (output_inversions) *output_inversions = total_inversions;
    return 1;
}

static tau_jac jac_from_affine(const ca_group *g, const ca_elem *p)
{
    return p->w[2] ? (tau_jac){0, g->mont.r1, 0} : (tau_jac){p->w[0], p->w[1], g->mont.r1};
}

static ca_elem tau8_pattern_point(const ca_group *g, const ca_tau4_pos_precomp *pre, size_t block,
                                  size_t half, ca_tau4_atlas_pattern pattern, uint64_t *rotations)
{
    if (pattern.slot == 255) return (ca_elem){{0, 0, 1, 0}};
    size_t position = 8 * block + 4 * half + pattern.position;
    size_t q = position / 2;
    ca_tau4_digit d = pre->base.digit[pattern.slot];
    ca_elem seed = pre->point[q][position & 1][d.seed];
    if (seed.w[2]) return seed;
    int power = (d.power + (int)(q % 3)) % 3;
    int sign = d.sign * ((q & 1) ? -1 : 1);
    if (power == 1)
        seed.w[0] = fm(g, pre->base.beta, seed.w[0]);
    else if (power == 2)
        seed.w[0] = fm(g, pre->base.beta2, seed.w[0]);
    *rotations += power != 0;
    if (sign < 0 && seed.w[1]) seed.w[1] = g->p - seed.w[1];
    return seed;
}

void ca_ec_tau8_fused_clear(ca_tau8_fused_precomp *pre)
{
    if (pre) {
        free(pre->point);
        memset(pre, 0, sizeof(*pre));
    }
}

static tau_jac tau8_pair_point(const ca_group *g, const ca_elem *first, const ca_elem *second,
                               uint64_t *adds)
{
    tau_jac p = jac_from_affine(g, first);
    if (!second->w[2]) {
        if (p.z) (*adds)++;
        p = jac_add_mixed(g, p, second);
    }
    return p;
}

static int tau8_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                        ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                        uint64_t *rotations, uint64_t *inversions, int orbit)
{
    if (triples) *triples = 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (inversions) *inversions = 0;
    if (!g || !point || !out || blocks < 1 || blocks > CA_TAU_POS_Q / 4) return 0;
    ca_tau8_fused_precomp pre = {0};
    uint64_t n3 = 0, na = 0, nr = 0, ni = 0;
    if (!ca_ec_tau4_pos_global_prepare(g, point, &pre.pos, &n3)) return 0;
    pre.blocks = blocks;
    pre.orbit = orbit;
    if (pre.pos.base.identity) {
        *out = pre;
        return 1;
    }
    size_t entries = orbit == 2   ? CA_TAU8_HOT_COUNT
                     : orbit == 1 ? CA_TAU8_ORBIT_COUNT
                                  : CA_TAU8_PAIR_COUNT;
    size_t count = blocks * entries;
    pre.point = malloc(count * sizeof(*pre.point));
    tau_jac *projective = malloc(entries * sizeof(*projective));
    uint64_t *prefixes = malloc(entries * sizeof(*prefixes));
    if (!pre.point || !projective || !prefixes) {
        free(prefixes);
        free(projective);
        ca_ec_tau8_fused_clear(&pre);
        return 0;
    }
    for (size_t block = 0; block < blocks; block++) {
        ca_elem first[217], second[217];
        for (size_t id = 0; id < 217; id++) {
            ca_tau4_atlas_pattern pattern = ca_tau4_atlas_patterns[id];
            first[id] = tau8_pattern_point(g, &pre.pos, block, 0, pattern, &nr);
            second[id] = tau8_pattern_point(g, &pre.pos, block, 1, pattern, &nr);
        }
        if (orbit == 2) {
            for (size_t id = 0; id < entries; id++) {
                uint8_t u = ca_tau8_hot_rep_u[id];
                uint8_t v = ca_tau8_hot_rep_v[id];
                projective[id] = tau8_pair_point(g, &first[u], &second[v], &na);
            }
        } else if (orbit == 1) {
            for (size_t id = 0; id < entries; id++) {
                uint8_t u = ca_tau8_orbit_rep_u[id];
                uint8_t v = ca_tau8_orbit_rep_v[id];
                projective[id] = tau8_pair_point(g, &first[u], &second[v], &na);
            }
        } else {
            for (size_t u = 0; u < 217; u++) {
                for (size_t v = 0; v < 217; v++) {
                    uint16_t index = ca_tau8_pair_map[217 * u + v];
                    if (index == UINT16_MAX) continue;
                    projective[index] = tau8_pair_point(g, &first[u], &second[v], &na);
                }
            }
        }
        uint64_t normalized = 0;
        if (!jac_batch_to_affine_scratch(g, pre.point + block * entries, projective, entries,
                                         prefixes, &normalized)) {
            free(prefixes);
            free(projective);
            ca_ec_tau8_fused_clear(&pre);
            return 0;
        }
        ni += normalized;
    }
    free(prefixes);
    free(projective);
    *out = pre;
    if (triples) *triples = n3;
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (inversions) *inversions = ni + 1; /* global positional preparation */
    return 1;
}

int ca_ec_tau8_fused_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                             ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                             uint64_t *rotations, uint64_t *inversions)
{
    return tau8_prepare(g, point, blocks, out, triples, adds, rotations, inversions, 0);
}

int ca_ec_tau8_orbit_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                             ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                             uint64_t *rotations, uint64_t *inversions)
{
    return tau8_prepare(g, point, blocks, out, triples, adds, rotations, inversions, 1);
}

int ca_ec_tau8_hot_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                           ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                           uint64_t *rotations, uint64_t *inversions)
{
    return tau8_prepare(g, point, blocks, out, triples, adds, rotations, inversions, 2);
}

int ca_ec_tau8_hot_adapt2_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                                  ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                                  uint64_t *rotations, uint64_t *inversions)
{
    if (!tau8_prepare(g, point, blocks, out, triples, adds, rotations, inversions, 2)) return 0;
    out->selector = 1;
    return 1;
}

int ca_ec_tau8_hot_gated_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                                 ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                                 uint64_t *rotations, uint64_t *inversions)
{
    if (!tau8_prepare(g, point, blocks, out, triples, adds, rotations, inversions, 2)) return 0;
    out->selector = 2;
    return 1;
}

int ca_ec_tau8_hot_steer_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                                 ca_tau8_fused_precomp *out, uint64_t *triples, uint64_t *adds,
                                 uint64_t *rotations, uint64_t *inversions)
{
    if (!tau8_prepare(g, point, blocks, out, triples, adds, rotations, inversions, 2)) return 0;
    out->selector = 3;
    return 1;
}

int ca_ec_tau8_hot_gated2_steer_prepare(const ca_group *g, const ca_elem *point, size_t blocks,
                                        ca_tau8_fused_precomp *out, uint64_t *triples,
                                        uint64_t *adds, uint64_t *rotations, uint64_t *inversions)
{
    if (!tau8_prepare(g, point, blocks, out, triples, adds, rotations, inversions, 2)) return 0;
    out->selector = 4;
    return 1;
}

size_t ca_ec_tau8_steer_static_bytes(void) { return sizeof(ca_tau8_steer_pair); }

static int tau8_atlas_step(int64_t *x, int64_t *y, uint8_t *pattern_id)
{
    int ax = (int)((*x % 81 + 81) % 81);
    int by = (int)((*y % 81 + 81) % 81);
    *pattern_id = ca_tau4_atlas_index[81 * ax + by];
    ca_tau4_atlas_pattern p = ca_tau4_atlas_patterns[*pattern_id];
    int64_t a = *x - p.correction_a, b = *y - p.correction_b;
    int64_t nx = a + 3 * b, ny = -a - 2 * b;
    if (nx % 9 || ny % 9) return 0;
    *x = nx / 9;
    *y = ny / 9;
    return 1;
}

typedef struct tau8_hot_plan {
    uint16_t ids[CA_TAU_POS_Q / 4];
    uint8_t units[CA_TAU_POS_Q / 4];
    uint8_t cold_first[CA_TAU_POS_Q / 4];
    uint8_t cold_second[CA_TAU_POS_Q / 4];
    size_t length;
    uint64_t predicted_adds;
    uint64_t cold_two_digit_blocks;
    uint64_t substitutions;
    int fits;
} tau8_hot_plan;

/* Count the complete stream before choosing a representative.  An out-of-span
 * baseline is evaluated by the positional path, whose additions are counted
 * separately here.  A second candidate outside the span is ineligible. */
static int tau8_hot_build_plan(const ca_tau8_fused_precomp *pre, int64_t x, int64_t y,
                               tau8_hot_plan *plan)
{
    *plan = (tau8_hot_plan){0};
    uint64_t positional_adds = 0;
    plan->fits = 1;
    while (x || y) {
        if (pre->selector >= 3 && plan->length >= pre->blocks) {
            plan->fits = 0;
            return 1;
        }
        if (plan->length >= CA_TAU_POS_Q / 4) return 0;
        int64_t old_x = x, old_y = y;
        uint8_t u, v;
        if (!tau8_atlas_step(&x, &y, &u) || !tau8_atlas_step(&x, &y, &v)) return 0;
        size_t pair = 217 * (size_t)u + v;
        uint16_t orbit_id = ca_tau8_orbit_id[pair];
        if (orbit_id >= CA_TAU8_ORBIT_COUNT) return 0;
        uint16_t id = ca_tau8_hot_id[orbit_id];
        if (pre->selector >= 3 && id == UINT16_MAX && u && v) {
            int ra = (int)((old_x % 81 + 81) % 81);
            int rb = (int)((old_y % 81 + 81) % 81);
            uint16_t alternative = ca_tau8_steer_pair[81 * ra + rb];
            if (alternative != UINT16_MAX) {
                if (alternative >= 217 * 217 || ca_tau8_pair_map[alternative] == UINT16_MAX)
                    return 0;
                u = (uint8_t)(alternative / 217);
                v = (uint8_t)(alternative % 217);
                ca_tau4_atlas_pattern first = ca_tau4_atlas_patterns[u];
                ca_tau4_atlas_pattern second = ca_tau4_atlas_patterns[v];
                int64_t ca =
                    first.correction_a - 18 * second.correction_a - 27 * second.correction_b;
                int64_t cb = first.correction_b + 9 * second.correction_a + 9 * second.correction_b;
                int64_t da = old_x - ca, db = old_y - cb;
                if (da % 81 || db % 81) return 0;
                x = (-2 * da - 3 * db) / 81;
                y = (da + db) / 81;
                pair = alternative;
                orbit_id = ca_tau8_orbit_id[pair];
                if (orbit_id >= CA_TAU8_ORBIT_COUNT) return 0;
                id = ca_tau8_hot_id[orbit_id];
                if (id == UINT16_MAX && u && v) return 0;
                plan->substitutions++;
            }
        }
        if (id != UINT16_MAX && id >= CA_TAU8_HOT_COUNT) return 0;
        if (id == UINT16_MAX && u && v) plan->cold_two_digit_blocks++;
        positional_adds += (u != 0) + (v != 0);
        plan->predicted_adds += id == UINT16_MAX ? (u != 0) + (v != 0) : 1;
        if (plan->length >= pre->blocks) plan->fits = 0;
        plan->ids[plan->length] = id;
        plan->units[plan->length] = ca_tau8_orbit_unit[pair];
        plan->cold_first[plan->length] = u;
        plan->cold_second[plan->length] = v;
        plan->length++;
    }
    if (!plan->fits) plan->predicted_adds = positional_adds;
    return 1;
}

static int tau8_hot_evaluate_plan(const ca_group *g, const ca_tau8_fused_precomp *pre,
                                  const tau8_hot_plan *plan, tau_jac *out, uint64_t *adds,
                                  uint64_t *rotations, uint64_t *fallbacks)
{
    const ca_tau4_precomp *base = &pre->pos.base;
    tau_jac acc = {0, g->mont.r1, 0};
    for (size_t i = plan->length; i-- > 0;) {
        if (plan->ids[i] == UINT16_MAX) {
            ca_elem first = tau8_pattern_point(
                g, &pre->pos, i, 0, ca_tau4_atlas_patterns[plan->cold_first[i]], rotations);
            ca_elem second = tau8_pattern_point(
                g, &pre->pos, i, 1, ca_tau4_atlas_patterns[plan->cold_second[i]], rotations);
            if (!first.w[2]) {
                acc = jac_add_mixed(g, acc, &first);
                (*adds)++;
            }
            if (!second.w[2]) {
                acc = jac_add_mixed(g, acc, &second);
                (*adds)++;
            }
            (*fallbacks)++;
            continue;
        }
        ca_elem point = pre->point[i * CA_TAU8_HOT_COUNT + plan->ids[i]];
        if (point.w[2]) continue;
        unsigned power = plan->units[i] % 3;
        if (power == 1)
            point.w[0] = fm(g, base->beta, point.w[0]);
        else if (power == 2)
            point.w[0] = fm(g, base->beta2, point.w[0]);
        *rotations += power != 0;
        if (plan->units[i] >= 3 && point.w[1]) point.w[1] = g->p - point.w[1];
        acc = jac_add_mixed(g, acc, &point);
        (*adds)++;
    }
    *out = acc;
    return 1;
}

static int tau8_hot_adapt2_mul_jac(const ca_group *g, const ca_tau8_fused_precomp *pre,
                                   tau_jac *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                   uint64_t *fallbacks, uint64_t *second_recodes)
{
    *adds = *rotations = *fallbacks = 0;
    *second_recodes = 0;
    if (pre->pos.base.identity || k % g->order == 0) {
        *out = (tau_jac){0, g->mont.r1, 0};
        return 1;
    }
    k %= g->order;
    const ca_tau4_precomp *base = &pre->pos.base;
    tau_vec v1 = {base->v1x, base->v1y}, v2 = {base->v2x, base->v2y};
    ca_i128 u0 = round_div((ca_i128)k * v2.y, base->det);
    ca_i128 v0 = round_div(-(ca_i128)k * v1.y, base->det);
    ca_i128 best_l1 = -1, second_l1 = -1;
    ca_i128 first_a = 0, first_b = 0, second_a = 0, second_b = 0;
    for (int du = -2; du <= 2; du++) {
        for (int dv = -2; dv <= 2; dv++) {
            ca_i128 u = u0 + du, v = v0 + dv;
            ca_i128 x = (ca_i128)k - u * v1.x - v * v2.x;
            ca_i128 y = -u * v1.y - v * v2.y;
            ca_i128 l1 = iabs128(x) + iabs128(y);
            if (best_l1 < 0 || l1 < best_l1) {
                second_l1 = best_l1;
                second_a = first_a;
                second_b = first_b;
                best_l1 = l1;
                first_a = x + y;
                first_b = -y;
            } else if (second_l1 < 0 || l1 < second_l1) {
                second_l1 = l1;
                second_a = x + y;
                second_b = -y;
            }
        }
    }
    const ca_i128 limit = (ca_i128)1 << 55;
    if (first_a <= -limit || first_a >= limit || first_b <= -limit || first_b >= limit)
        goto fallback;
    tau8_hot_plan first;
    if (!tau8_hot_build_plan(pre, (int64_t)first_a, (int64_t)first_b, &first)) return 0;
    tau8_hot_plan second;
    int recode_second = (pre->selector == 1 || !first.fits || first.cold_two_digit_blocks > 0) &&
                        second_a > -limit && second_a < limit && second_b > -limit &&
                        second_b < limit;
    if (recode_second) *second_recodes = 1;
    int second_eligible = recode_second &&
                          tau8_hot_build_plan(pre, (int64_t)second_a, (int64_t)second_b, &second) &&
                          second.fits;
    const tau8_hot_plan *chosen = &first;
    if (second_eligible && second.predicted_adds < first.predicted_adds) chosen = &second;
    if (!chosen->fits) goto fallback;
    return tau8_hot_evaluate_plan(g, pre, chosen, out, adds, rotations, fallbacks);
fallback:
    *fallbacks = 1;
    return tau4_pos_mul_jac(g, &pre->pos, out, k, adds, rotations);
}

static int tau8_hot_steer_mul_jac(const ca_group *g, const ca_tau8_fused_precomp *pre, tau_jac *out,
                                  uint64_t k, uint64_t *adds, uint64_t *rotations,
                                  uint64_t *fallbacks, uint64_t *steered_blocks)
{
    *adds = *rotations = *fallbacks = *steered_blocks = 0;
    if (pre->pos.base.identity || k % g->order == 0) {
        *out = (tau_jac){0, g->mont.r1, 0};
        return 1;
    }
    k %= g->order;
    const ca_tau4_precomp *base = &pre->pos.base;
    ca_i128 wide_x, wide_y;
    reduce_with_lattice((tau_vec){base->v1x, base->v1y}, (tau_vec){base->v2x, base->v2y}, base->det,
                        k, &wide_x, &wide_y);
    const ca_i128 limit = (ca_i128)1 << 55;
    if (wide_x <= -limit || wide_x >= limit || wide_y <= -limit || wide_y >= limit) goto fallback;
    tau8_hot_plan plan;
    if (!tau8_hot_build_plan(pre, (int64_t)wide_x, (int64_t)wide_y, &plan)) return 0;
    if (!plan.fits) goto fallback;
    *steered_blocks = plan.substitutions;
    return tau8_hot_evaluate_plan(g, pre, &plan, out, adds, rotations, fallbacks);
fallback:
    *fallbacks = 1;
    return tau4_pos_mul_jac(g, &pre->pos, out, k, adds, rotations);
}

static int tau8_hot_gated2_steer_mul_jac(const ca_group *g, const ca_tau8_fused_precomp *pre,
                                         tau_jac *out, uint64_t k, uint64_t *adds,
                                         uint64_t *rotations, uint64_t *fallbacks,
                                         uint64_t *second_recodes, uint64_t *steered_blocks)
{
    *adds = *rotations = *fallbacks = *second_recodes = *steered_blocks = 0;
    if (pre->pos.base.identity || k % g->order == 0) {
        *out = (tau_jac){0, g->mont.r1, 0};
        return 1;
    }
    k %= g->order;
    const ca_tau4_precomp *base = &pre->pos.base;
    tau_vec v1 = {base->v1x, base->v1y}, v2 = {base->v2x, base->v2y};
    ca_i128 u0 = round_div((ca_i128)k * v2.y, base->det);
    ca_i128 v0 = round_div(-(ca_i128)k * v1.y, base->det);
    ca_i128 best_l1 = -1, second_l1 = -1;
    ca_i128 first_a = 0, first_b = 0, second_a = 0, second_b = 0;
    for (int du = -2; du <= 2; du++) {
        for (int dv = -2; dv <= 2; dv++) {
            ca_i128 u = u0 + du, v = v0 + dv;
            ca_i128 x = (ca_i128)k - u * v1.x - v * v2.x;
            ca_i128 y = -u * v1.y - v * v2.y;
            ca_i128 l1 = iabs128(x) + iabs128(y);
            if (best_l1 < 0 || l1 < best_l1) {
                second_l1 = best_l1;
                second_a = first_a;
                second_b = first_b;
                best_l1 = l1;
                first_a = x + y;
                first_b = -y;
            } else if (second_l1 < 0 || l1 < second_l1) {
                second_l1 = l1;
                second_a = x + y;
                second_b = -y;
            }
        }
    }
    const ca_i128 limit = (ca_i128)1 << 55;
    if (first_a <= -limit || first_a >= limit || first_b <= -limit || first_b >= limit)
        goto fallback;
    tau8_hot_plan first;
    if (!tau8_hot_build_plan(pre, (int64_t)first_a, (int64_t)first_b, &first)) return 0;
    const tau8_hot_plan *chosen = &first;
    tau8_hot_plan second;
    if ((!first.fits || first.cold_two_digit_blocks > 0) && second_a > -limit && second_a < limit &&
        second_b > -limit && second_b < limit) {
        *second_recodes = 1;
        if (!tau8_hot_build_plan(pre, (int64_t)second_a, (int64_t)second_b, &second)) return 0;
        if (second.fits && (!first.fits || second.predicted_adds < first.predicted_adds))
            chosen = &second;
    }
    if (!chosen->fits) goto fallback;
    *steered_blocks = chosen->substitutions;
    return tau8_hot_evaluate_plan(g, pre, chosen, out, adds, rotations, fallbacks);
fallback:
    *fallbacks = 1;
    return tau4_pos_mul_jac(g, &pre->pos, out, k, adds, rotations);
}

static int tau8_fused_mul_jac(const ca_group *g, const ca_tau8_fused_precomp *pre, tau_jac *out,
                              uint64_t k, uint64_t *adds, uint64_t *rotations, uint64_t *fallbacks,
                              uint64_t *second_recodes, uint64_t *steered_blocks)
{
    if (!g || !pre || !out || pre->pos.base.g != g) return 0;
    *second_recodes = *steered_blocks = 0;
    if (pre->selector == 1 || pre->selector == 2)
        return tau8_hot_adapt2_mul_jac(g, pre, out, k, adds, rotations, fallbacks, second_recodes);
    if (pre->selector == 3)
        return tau8_hot_steer_mul_jac(g, pre, out, k, adds, rotations, fallbacks, steered_blocks);
    if (pre->selector == 4)
        return tau8_hot_gated2_steer_mul_jac(g, pre, out, k, adds, rotations, fallbacks,
                                             second_recodes, steered_blocks);
    *adds = *rotations = *fallbacks = 0;
    if (pre->pos.base.identity || k % g->order == 0) {
        *out = (tau_jac){0, g->mont.r1, 0};
        return 1;
    }
    k %= g->order;
    ca_i128 wide_x, wide_y;
    const ca_tau4_precomp *base = &pre->pos.base;
    reduce_with_lattice((tau_vec){base->v1x, base->v1y}, (tau_vec){base->v2x, base->v2y}, base->det,
                        k, &wide_x, &wide_y);
    const ca_i128 limit = (ca_i128)1 << 55;
    if (wide_x <= -limit || wide_x >= limit || wide_y <= -limit || wide_y >= limit) goto fallback;
    int64_t x = (int64_t)wide_x, y = (int64_t)wide_y;
    uint16_t ids[CA_TAU_POS_Q / 4];
    uint8_t units[CA_TAU_POS_Q / 4];
    uint8_t cold_first[CA_TAU_POS_Q / 4], cold_second[CA_TAU_POS_Q / 4];
    size_t length = 0;
    while (x || y) {
        if (length >= pre->blocks) goto fallback;
        uint8_t u, v;
        if (!tau8_atlas_step(&x, &y, &u) || !tau8_atlas_step(&x, &y, &v)) return 0;
        size_t pair = 217 * u + v;
        uint16_t orbit_id = pre->orbit ? ca_tau8_orbit_id[pair] : 0;
        if (pre->orbit && orbit_id >= CA_TAU8_ORBIT_COUNT) return 0;
        uint16_t id = pre->orbit == 2   ? ca_tau8_hot_id[orbit_id]
                      : pre->orbit == 1 ? orbit_id
                                        : ca_tau8_pair_map[pair];
        uint8_t unit = pre->orbit ? ca_tau8_orbit_unit[pair] : 0;
        size_t entries = pre->orbit == 2   ? CA_TAU8_HOT_COUNT
                         : pre->orbit == 1 ? CA_TAU8_ORBIT_COUNT
                                           : CA_TAU8_PAIR_COUNT;
        if (pre->orbit == 2 && id == UINT16_MAX) {
            ids[length] = id;
            units[length] = 0;
            cold_first[length] = u;
            cold_second[length++] = v;
            continue;
        }
        if (id >= entries || unit >= 6) return 0;
        units[length] = unit;
        ids[length++] = id;
    }
    tau_jac acc = {0, g->mont.r1, 0};
    size_t entries = pre->orbit == 2   ? CA_TAU8_HOT_COUNT
                     : pre->orbit == 1 ? CA_TAU8_ORBIT_COUNT
                                       : CA_TAU8_PAIR_COUNT;
    for (size_t i = length; i-- > 0;) {
        if (pre->orbit == 2 && ids[i] == UINT16_MAX) {
            ca_elem first = tau8_pattern_point(g, &pre->pos, i, 0,
                                               ca_tau4_atlas_patterns[cold_first[i]], rotations);
            ca_elem second = tau8_pattern_point(g, &pre->pos, i, 1,
                                                ca_tau4_atlas_patterns[cold_second[i]], rotations);
            if (!first.w[2]) {
                acc = jac_add_mixed(g, acc, &first);
                (*adds)++;
            }
            if (!second.w[2]) {
                acc = jac_add_mixed(g, acc, &second);
                (*adds)++;
            }
            (*fallbacks)++;
            continue;
        }
        ca_elem point = pre->point[i * entries + ids[i]];
        if (point.w[2]) continue;
        unsigned power = units[i] % 3;
        if (power == 1)
            point.w[0] = fm(g, base->beta, point.w[0]);
        else if (power == 2)
            point.w[0] = fm(g, base->beta2, point.w[0]);
        *rotations += power != 0;
        if (units[i] >= 3 && point.w[1]) point.w[1] = g->p - point.w[1];
        acc = jac_add_mixed(g, acc, &point);
        (*adds)++;
    }
    *out = acc;
    return 1;
fallback:
    *fallbacks = 1;
    return tau4_pos_mul_jac(g, &pre->pos, out, k, adds, rotations);
}

int ca_ec_tau8_fused_mul_batch_profile(const ca_group *g, const ca_tau8_fused_precomp *pre,
                                       ca_elem *out, const uint64_t *scalars, size_t count,
                                       size_t block_size, uint64_t *adds, uint64_t *rotations,
                                       uint64_t *output_inversions, uint64_t *fallbacks,
                                       uint64_t *second_recodes, uint64_t *steered_blocks)
{
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (output_inversions) *output_inversions = 0;
    if (fallbacks) *fallbacks = 0;
    if (second_recodes) *second_recodes = 0;
    if (steered_blocks) *steered_blocks = 0;
    if (!count) return 1;
    if (!g || !pre || !out || !scalars || pre->pos.base.g != g ||
        (pre->selector != 0 &&
         ((pre->selector != 1 && pre->selector != 2 && pre->selector != 3 && pre->selector != 4) ||
          pre->orbit != 2)) ||
        (!pre->point && !pre->pos.base.identity) || block_size == 0 || block_size > 4096)
        return 0;
    tau_jac *projective = malloc(block_size * sizeof(*projective));
    uint64_t *prefixes = malloc(block_size * sizeof(*prefixes));
    if (!projective || !prefixes) {
        free(prefixes);
        free(projective);
        return 0;
    }
    uint64_t na = 0, nr = 0, ni = 0, nf = 0, ns = 0, nt = 0;
    for (size_t offset = 0; offset < count;) {
        size_t n = count - offset;
        if (n > block_size) n = block_size;
        for (size_t i = 0; i < n; i++) {
            uint64_t a, r, f, s, t;
            if (!tau8_fused_mul_jac(g, pre, &projective[i], scalars[offset + i], &a, &r, &f, &s,
                                    &t)) {
                free(prefixes);
                free(projective);
                return 0;
            }
            na += a;
            nr += r;
            nf += f;
            ns += s;
            nt += t;
        }
        uint64_t current_inversions = 0;
        if (!jac_batch_to_affine_scratch(g, out + offset, projective, n, prefixes,
                                         &current_inversions)) {
            free(prefixes);
            free(projective);
            return 0;
        }
        ni += current_inversions;
        offset += n;
    }
    free(prefixes);
    free(projective);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (output_inversions) *output_inversions = ni;
    if (fallbacks) *fallbacks = nf;
    if (second_recodes) *second_recodes = ns;
    if (steered_blocks) *steered_blocks = nt;
    return 1;
}

int ca_ec_tau8_fused_mul_batch(const ca_group *g, const ca_tau8_fused_precomp *pre, ca_elem *out,
                               const uint64_t *scalars, size_t count, size_t block_size,
                               uint64_t *adds, uint64_t *rotations, uint64_t *output_inversions,
                               uint64_t *fallbacks)
{
    return ca_ec_tau8_fused_mul_batch_profile(g, pre, out, scalars, count, block_size, adds,
                                              rotations, output_inversions, fallbacks, NULL, NULL);
}

typedef struct tau_wide_atlas {
    int modulus;
    size_t entries;
    const uint32_t *index;
    const ca_tau_wide_correction *correction;
} tau_wide_atlas;

static tau_wide_atlas tau_wide_atlas_for(int width)
{
    switch (width) {
    case 8:
        return (tau_wide_atlas){CA_TAU_WIDE8_MODULUS, CA_TAU_WIDE8_ORBIT_COUNT, ca_tau_wide8_index,
                                ca_tau_wide8_correction};
    case 10:
        return (tau_wide_atlas){CA_TAU_WIDE10_MODULUS, CA_TAU_WIDE10_ORBIT_COUNT,
                                ca_tau_wide10_index, ca_tau_wide10_correction};
    case 12:
        return (tau_wide_atlas){CA_TAU_WIDE12_MODULUS, CA_TAU_WIDE12_ORBIT_COUNT,
                                ca_tau_wide12_index, ca_tau_wide12_correction};
    default: return (tau_wide_atlas){0};
    }
}

static const ca_tau_wide_recipe *tau_wide_recipe_for(int width)
{
    if (width == 8) return ca_tau_wide8_recipe;
    if (width == 10) return ca_tau_wide10_recipe;
    if (width == 12) return ca_tau_wide12_recipe;
    return NULL;
}

static const uint32_t *tau_wide_packed_recipe_for(int width)
{
    if (width == 8) return ca_tau_wide8_packed_recipe;
    if (width == 10) return ca_tau_wide10_packed_recipe;
    if (width == 12) return ca_tau_wide12_packed_recipe;
    return NULL;
}

static void tau_wide_apply_unit(int64_t *a, int64_t *b, unsigned code)
{
    for (unsigned i = 0; i < code % 3; i++) {
        int64_t next_a = *a + 3 * *b, next_b = -*a - 2 * *b;
        *a = next_a;
        *b = next_b;
    }
    if (code >= 3) {
        *a = -*a;
        *b = -*b;
    }
}

static ca_elem tau_wide_digit_point(const ca_group *g, const ca_tau4_pos_precomp *pre,
                                    size_t position, uint8_t slot, uint64_t *rotations)
{
    size_t q = position / 2;
    ca_tau4_digit d = pre->base.digit[slot];
    ca_elem seed = pre->point[q][position & 1][d.seed];
    if (seed.w[2]) return seed;
    int power = (d.power + (int)(q % 3)) % 3;
    int sign = d.sign * ((q & 1) ? -1 : 1);
    if (power == 1)
        seed.w[0] = fm(g, pre->base.beta, seed.w[0]);
    else if (power == 2)
        seed.w[0] = fm(g, pre->base.beta2, seed.w[0]);
    *rotations += power != 0;
    if (sign < 0 && seed.w[1]) seed.w[1] = g->p - seed.w[1];
    return seed;
}

size_t ca_ec_tau_wide_entries(int schedule)
{
    if (schedule == 0) return (size_t)4 * CA_TAU_WIDE10_ORBIT_COUNT;
    if (schedule == 1)
        return (size_t)3 * CA_TAU_WIDE12_ORBIT_COUNT + (size_t)2 * CA_TAU_WIDE8_ORBIT_COUNT;
    return 0;
}

size_t ca_ec_tau_wide_static_bytes(int schedule)
{
    if (schedule == 0) return sizeof(ca_tau_wide10_index) + sizeof(ca_tau_wide10_correction);
    if (schedule == 1)
        return sizeof(ca_tau_wide12_index) + sizeof(ca_tau_wide12_correction) +
               sizeof(ca_tau_wide8_index) + sizeof(ca_tau_wide8_correction);
    return 0;
}

size_t ca_ec_tau_wide_graph_recipe_bytes(int schedule)
{
    if (schedule == 0) return sizeof(ca_tau_wide10_recipe);
    if (schedule == 1) return sizeof(ca_tau_wide12_recipe) + sizeof(ca_tau_wide8_recipe);
    return 0;
}

size_t ca_ec_tau_wide_packed_recipe_bytes(int schedule)
{
    if (schedule == 0) return sizeof(ca_tau_wide10_packed_recipe) + sizeof(ca_tau_wide_packed_slot);
    if (schedule == 1)
        return sizeof(ca_tau_wide12_packed_recipe) + sizeof(ca_tau_wide8_packed_recipe) +
               sizeof(ca_tau_wide_packed_slot);
    return 0;
}

size_t ca_ec_tau_wide_temp_bytes(int schedule)
{
    size_t entries = schedule == 0   ? CA_TAU_WIDE10_ORBIT_COUNT
                     : schedule == 1 ? CA_TAU_WIDE12_ORBIT_COUNT
                                     : 0;
    return entries * (sizeof(tau_jac) + sizeof(uint64_t));
}

typedef struct tau_affine_pair {
    uint64_t x, y;
} tau_affine_pair;

/* Each graph depth is independent once the preceding depth is affine.  Keep
 * digit coordinates and rotated parent coordinates until a single inverse
 * makes every nonexceptional edge in this depth affine. */
static int tau_wide_wavefront_block(const ca_group *g, ca_tau_wide_precomp *pre, size_t block,
                                    tau_wide_atlas atlas, const uint32_t *packed, tau_jac *parents,
                                    tau_affine_pair *digits, uint64_t *prefixes, uint64_t *adds,
                                    uint64_t *rotations, uint64_t *inversions,
                                    uint64_t *slot_lookups, uint64_t *denominators,
                                    uint64_t *exceptions, uint64_t *doublings)
{
    size_t offset = pre->point_offset[block];
    pre->point[offset] = (ca_elem){{0, 0, 1, 0}};
    for (unsigned depth = 1; depth <= 3; depth++) {
        uint64_t product = g->mont.r1;
        size_t nonzero = 0;
        prefixes[0] = product;
        for (size_t id = 1; id < atlas.entries; id++) {
            parents[id].z = 0;
            uint32_t word = packed[id];
            if (word >> 30 != depth) {
                prefixes[id] = product;
                continue;
            }
            unsigned digit_id = (word >> 20) & 63u;
            unsigned position = (word >> 26) & 15u;
            unsigned parent_packed = word & ((1u << 20) - 1);
            if (digit_id >= sizeof(ca_tau_wide_packed_slot) || position >= pre->width[block])
                return 0;
            unsigned digit_slot = ca_tau_wide_packed_slot[digit_id];
            if (digit_slot >= 81) return 0;
            if (slot_lookups) (*slot_lookups)++;
            ca_elem digit = tau_wide_digit_point(g, &pre->pos, pre->position[block] + position,
                                                 digit_slot, rotations);
            if (depth == 1) {
                if (parent_packed) return 0;
                pre->point[offset + id] = digit;
                prefixes[id] = product;
                continue;
            }
            unsigned parent_id = parent_packed & ((1u << CA_TAU_WIDE_ID_BITS) - 1);
            unsigned unit = parent_packed >> CA_TAU_WIDE_ID_BITS;
            if (parent_id >= atlas.entries || unit > 5 || packed[parent_id] >> 30 != depth - 1)
                return 0;
            ca_elem parent = pre->point[offset + parent_id];
            unsigned power = unit % 3;
            if (!parent.w[2]) {
                if (power == 1)
                    parent.w[0] = fm(g, pre->pos.base.beta, parent.w[0]);
                else if (power == 2)
                    parent.w[0] = fm(g, pre->pos.base.beta2, parent.w[0]);
                if (rotations) *rotations += power != 0;
                if (unit >= 3 && parent.w[1]) parent.w[1] = g->p - parent.w[1];
            }
            if (adds) (*adds)++;
            if (parent.w[2]) {
                pre->point[offset + id] = digit;
                if (exceptions) (*exceptions)++;
            } else if (digit.w[2]) {
                pre->point[offset + id] = parent;
                if (exceptions) (*exceptions)++;
            } else if (parent.w[0] == digit.w[0] && (parent.w[1] != digit.w[1] || !parent.w[1])) {
                pre->point[offset + id] = (ca_elem){{0, 0, 1, 0}};
                if (exceptions) (*exceptions)++;
            } else {
                uint64_t denominator;
                if (parent.w[0] == digit.w[0]) {
                    denominator = f2(g, parent.w[1]);
                    if (doublings) (*doublings)++;
                } else {
                    denominator = fs(g, digit.w[0], parent.w[0]);
                }
                if (!denominator) return 0;
                parents[id] = (tau_jac){parent.w[0], parent.w[1], denominator};
                digits[id] = (tau_affine_pair){digit.w[0], digit.w[1]};
                product = fm(g, product, denominator);
                nonzero++;
            }
            prefixes[id] = product;
        }
        if (!nonzero) continue;
        uint64_t inverse = ca_mont_inv(&g->mont, product);
        if (!inverse) return 0;
        if (inversions) (*inversions)++;
        if (denominators) *denominators += nonzero;
        for (size_t id = atlas.entries; id-- > 1;) {
            if (packed[id] >> 30 != depth || !parents[id].z) continue;
            uint64_t inv_denominator = fm(g, inverse, prefixes[id - 1]);
            inverse = fm(g, inverse, parents[id].z);
            uint64_t numerator = parents[id].x == digits[id].x ? f3(g, fq(g, parents[id].x))
                                                               : fs(g, digits[id].y, parents[id].y);
            uint64_t slope = fm(g, numerator, inv_denominator);
            uint64_t x = fs(g, fs(g, fq(g, slope), parents[id].x), digits[id].x);
            uint64_t y = fs(g, fm(g, slope, fs(g, parents[id].x, x)), parents[id].y);
            pre->point[offset + id] = (ca_elem){{x, y, 0, 0}};
        }
    }
    return 1;
}

void ca_ec_tau_wide_clear(ca_tau_wide_precomp *pre)
{
    if (pre) {
        free(pre->point);
        memset(pre, 0, sizeof(*pre));
    }
}

static int tau_wide_prepare_impl(const ca_group *g, const ca_elem *point, int schedule,
                                 ca_tau_wide_precomp *out, uint64_t *triples, uint64_t *adds,
                                 uint64_t *rotations, uint64_t *inversions, int graph,
                                 uint64_t *slot_lookups, ca_tau_wide_wavefront_stats *wavefront)
{
    if (triples) *triples = 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (inversions) *inversions = 0;
    if (slot_lookups) *slot_lookups = 0;
    if (wavefront) memset(wavefront, 0, sizeof(*wavefront));
    if (!g || !point || !out || (schedule != 0 && schedule != 1)) return 0;
    ca_tau_wide_precomp pre = {0};
    uint64_t n3 = 0, na = 0, nr = 0, ni = 0;
    if (!ca_ec_tau4_pos_global_prepare(g, point, &pre.pos, &n3)) return 0;
    pre.schedule = schedule;
    pre.blocks = schedule == 0 ? 4 : 5;
    static const uint8_t widths[2][5] = {{10, 10, 10, 10, 0}, {12, 12, 12, 8, 8}};
    for (size_t i = 0; i < pre.blocks; i++) {
        pre.width[i] = widths[schedule][i];
        pre.position[i] = i ? pre.position[i - 1] + pre.width[i - 1] : 0;
        pre.point_offset[i + 1] = pre.point_offset[i] + tau_wide_atlas_for(pre.width[i]).entries;
    }
    if (pre.point_offset[pre.blocks] != ca_ec_tau_wide_entries(schedule)) return 0;
    if (pre.pos.base.identity) {
        *out = pre;
        return 1;
    }
    size_t max_entries = schedule == 0 ? CA_TAU_WIDE10_ORBIT_COUNT : CA_TAU_WIDE12_ORBIT_COUNT;
    pre.point = malloc(pre.point_offset[pre.blocks] * sizeof(*pre.point));
    tau_jac *projective = malloc(max_entries * sizeof(*projective));
    uint64_t *prefixes = malloc(max_entries * sizeof(*prefixes));
    tau_affine_pair *digit_pairs = graph == 3 ? malloc(max_entries * sizeof(*digit_pairs)) : NULL;
    if (!pre.point || !projective || !prefixes || (graph == 3 && !digit_pairs)) {
        free(digit_pairs);
        free(prefixes);
        free(projective);
        ca_ec_tau_wide_clear(&pre);
        return 0;
    }
    for (size_t block = 0; block < pre.blocks; block++) {
        tau_wide_atlas atlas = tau_wide_atlas_for(pre.width[block]);
        if (graph) {
            const ca_tau_wide_recipe *recipes =
                graph == 1 ? tau_wide_recipe_for(pre.width[block]) : NULL;
            const uint32_t *packed =
                graph >= 2 ? tau_wide_packed_recipe_for(pre.width[block]) : NULL;
            if ((!recipes && !packed) || (recipes && recipes[0].depth != 0) ||
                (packed && packed[0] != 0))
                goto fail;
            for (size_t id = 1; id < atlas.entries; id++) {
                unsigned candidate_depth = recipes ? recipes[id].depth : packed[id] >> 30;
                if (candidate_depth < 1 || candidate_depth > 3) goto fail;
            }
            if (graph == 3) {
                if (!tau_wide_wavefront_block(g, &pre, block, atlas, packed, projective,
                                              digit_pairs, prefixes, &na, &nr, &ni,
                                              wavefront ? &wavefront->slot_lookups : NULL,
                                              wavefront ? &wavefront->denominators : NULL,
                                              wavefront ? &wavefront->exceptional_edges : NULL,
                                              wavefront ? &wavefront->doubling_edges : NULL))
                    goto fail;
                continue;
            }
            projective[0] = (tau_jac){0, g->mont.r1, 0};
            for (unsigned depth = 1; depth <= 3; depth++) {
                for (size_t id = 1; id < atlas.entries; id++) {
                    ca_tau_wide_recipe recipe;
                    if (recipes) {
                        recipe = recipes[id];
                        if (recipe.depth != depth) continue;
                    } else {
                        uint32_t word = packed[id];
                        if (word >> 30 != depth) continue;
                        unsigned digit_id = (word >> 20) & 63u;
                        if (digit_id >= sizeof(ca_tau_wide_packed_slot)) goto fail;
                        recipe.parent_packed = word & ((1u << 20) - 1);
                        recipe.digit_slot = ca_tau_wide_packed_slot[digit_id];
                        recipe.position = (uint8_t)((word >> 26) & 15u);
                        recipe.depth = (uint8_t)depth;
                        recipe.reserved = 0;
                        if (slot_lookups) (*slot_lookups)++;
                    }
                    if (recipe.digit_slot >= 81 || recipe.position >= pre.width[block]) goto fail;
                    ca_elem digit = tau_wide_digit_point(
                        g, &pre.pos, pre.position[block] + recipe.position, recipe.digit_slot, &nr);
                    if (digit.w[2]) goto fail;
                    if (depth == 1) {
                        if (recipe.parent_packed != 0) goto fail;
                        projective[id] = jac_from_affine(g, &digit);
                    } else {
                        unsigned parent_id =
                            recipe.parent_packed & ((1u << CA_TAU_WIDE_ID_BITS) - 1);
                        unsigned unit = recipe.parent_packed >> CA_TAU_WIDE_ID_BITS;
                        if (parent_id >= atlas.entries || unit > 5) goto fail;
                        unsigned parent_depth =
                            recipes ? recipes[parent_id].depth : packed[parent_id] >> 30;
                        if (parent_depth != depth - 1) goto fail;
                        tau_jac parent = projective[parent_id];
                        if (!parent.z) goto fail;
                        unsigned power = unit % 3;
                        if (power == 1)
                            parent.x = fm(g, pre.pos.base.beta, parent.x);
                        else if (power == 2)
                            parent.x = fm(g, pre.pos.base.beta2, parent.x);
                        nr += power != 0;
                        if (unit >= 3 && parent.y) parent.y = g->p - parent.y;
                        projective[id] = jac_add_mixed(g, parent, &digit);
                        na++;
                    }
                }
            }
        } else
            for (size_t id = 0; id < atlas.entries; id++) {
                int64_t a = atlas.correction[id].a, b = atlas.correction[id].b;
                if (!a && !b) {
                    projective[id] = (tau_jac){0, g->mont.r1, 0};
                    continue;
                }
                uint8_t digits[256];
                size_t nd = gen_tau4_digits_fast(a, b, pre.pos.base.digit, digits);
                if (!nd || nd > pre.width[block]) goto fail;
                tau_jac acc = {0, g->mont.r1, 0};
                for (size_t position = 0; position < nd; position++) {
                    if (digits[position] == 255) continue;
                    ca_elem seed = tau_wide_digit_point(g, &pre.pos, pre.position[block] + position,
                                                        digits[position], &nr);
                    if (seed.w[2]) continue;
                    if (acc.z) {
                        acc = jac_add_mixed(g, acc, &seed);
                        na++;
                    } else {
                        acc = jac_from_affine(g, &seed);
                    }
                }
                projective[id] = acc;
            }
        uint64_t normalized = 0;
        if (!jac_batch_to_affine_scratch(g, pre.point + pre.point_offset[block], projective,
                                         atlas.entries, prefixes, &normalized)) {
            goto fail;
        }
        ni += normalized;
    }
    free(digit_pairs);
    free(prefixes);
    free(projective);
    *out = pre;
    if (triples) *triples = n3;
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (inversions) *inversions = ni + 1;
    return 1;
fail:
    free(digit_pairs);
    free(prefixes);
    free(projective);
    ca_ec_tau_wide_clear(&pre);
    return 0;
}

int ca_ec_tau_wide_prepare(const ca_group *g, const ca_elem *point, int schedule,
                           ca_tau_wide_precomp *out, uint64_t *triples, uint64_t *adds,
                           uint64_t *rotations, uint64_t *inversions)
{
    return tau_wide_prepare_impl(g, point, schedule, out, triples, adds, rotations, inversions, 0,
                                 NULL, NULL);
}

int ca_ec_tau_wide_prepare_graph(const ca_group *g, const ca_elem *point, int schedule,
                                 ca_tau_wide_precomp *out, uint64_t *triples, uint64_t *adds,
                                 uint64_t *rotations, uint64_t *inversions)
{
    return tau_wide_prepare_impl(g, point, schedule, out, triples, adds, rotations, inversions, 1,
                                 NULL, NULL);
}

int ca_ec_tau_wide_prepare_packed(const ca_group *g, const ca_elem *point, int schedule,
                                  ca_tau_wide_precomp *out, uint64_t *triples, uint64_t *adds,
                                  uint64_t *rotations, uint64_t *inversions, uint64_t *slot_lookups)
{
    return tau_wide_prepare_impl(g, point, schedule, out, triples, adds, rotations, inversions, 2,
                                 slot_lookups, NULL);
}

size_t ca_ec_tau_wide_wavefront_temp_bytes(int schedule)
{
    size_t entries = schedule == 0   ? CA_TAU_WIDE10_ORBIT_COUNT
                     : schedule == 1 ? CA_TAU_WIDE12_ORBIT_COUNT
                                     : 0;
    return entries * (sizeof(tau_jac) + sizeof(uint64_t) + sizeof(tau_affine_pair));
}

int ca_ec_tau_wide_prepare_wavefront(const ca_group *g, const ca_elem *point, int schedule,
                                     ca_tau_wide_precomp *out, uint64_t *triples, uint64_t *adds,
                                     uint64_t *rotations, uint64_t *inversions,
                                     ca_tau_wide_wavefront_stats *stats)
{
    return tau_wide_prepare_impl(g, point, schedule, out, triples, adds, rotations, inversions, 3,
                                 NULL, stats);
}

static int tau_wide_mul_jac(const ca_group *g, const ca_tau_wide_precomp *pre, tau_jac *out,
                            uint64_t k, uint64_t *adds, uint64_t *rotations, uint64_t *fallbacks)
{
    *adds = *rotations = *fallbacks = 0;
    if (pre->pos.base.identity || k % g->order == 0) {
        *out = (tau_jac){0, g->mont.r1, 0};
        return 1;
    }
    k %= g->order;
    const ca_tau4_precomp *base = &pre->pos.base;
    ca_i128 wide_a, wide_b;
    reduce_with_lattice((tau_vec){base->v1x, base->v1y}, (tau_vec){base->v2x, base->v2y}, base->det,
                        k, &wide_a, &wide_b);
    const ca_i128 limit = (ca_i128)1 << 55;
    if (wide_a <= -limit || wide_a >= limit || wide_b <= -limit || wide_b >= limit) goto fallback;
    int64_t a = (int64_t)wide_a, b = (int64_t)wide_b;
    uint32_t ids[5] = {0};
    uint8_t units[5] = {0};
    for (size_t block = 0; block < pre->blocks && (a || b); block++) {
        tau_wide_atlas atlas = tau_wide_atlas_for(pre->width[block]);
        if (!atlas.modulus) return 0;
        int ra = (int)((a % atlas.modulus + atlas.modulus) % atlas.modulus);
        int rb = (int)((b % atlas.modulus + atlas.modulus) % atlas.modulus);
        uint32_t packed = atlas.index[(size_t)atlas.modulus * ra + rb];
        uint32_t id = packed & ((1u << CA_TAU_WIDE_ID_BITS) - 1);
        unsigned unit = packed >> CA_TAU_WIDE_ID_BITS;
        if (id >= atlas.entries || unit > 5) return 0;
        int64_t ca = atlas.correction[id].a, cb = atlas.correction[id].b;
        tau_wide_apply_unit(&ca, &cb, unit);
        int64_t da = a - ca, db = b - cb;
        if (da % atlas.modulus || db % atlas.modulus) return 0;
        a = da / atlas.modulus;
        b = db / atlas.modulus;
        unsigned s = pre->width[block] / 2;
        unsigned inverse = ((3 - s % 3) % 3) + (s % 2 ? 3 : 0);
        tau_wide_apply_unit(&a, &b, inverse);
        ids[block] = id;
        units[block] = (uint8_t)unit;
    }
    if (a || b) goto fallback;
    tau_jac acc = {0, g->mont.r1, 0};
    for (size_t block = pre->blocks; block-- > 0;) {
        if (!ids[block]) continue;
        ca_elem point = pre->point[pre->point_offset[block] + ids[block]];
        if (point.w[2]) continue;
        unsigned power = units[block] % 3;
        if (power == 1)
            point.w[0] = fm(g, base->beta, point.w[0]);
        else if (power == 2)
            point.w[0] = fm(g, base->beta2, point.w[0]);
        *rotations += power != 0;
        if (units[block] >= 3 && point.w[1]) point.w[1] = g->p - point.w[1];
        acc = jac_add_mixed(g, acc, &point);
        (*adds)++;
    }
    *out = acc;
    return 1;
fallback:
    *fallbacks = 1;
    return tau4_pos_mul_jac(g, &pre->pos, out, k, adds, rotations);
}

int ca_ec_tau_wide_mul_batch_profile(const ca_group *g, const ca_tau_wide_precomp *pre,
                                     ca_elem *out, const uint64_t *scalars, size_t count,
                                     size_t block_size, uint64_t *adds, uint64_t *rotations,
                                     uint64_t *output_inversions, uint64_t *fallbacks)
{
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (output_inversions) *output_inversions = 0;
    if (fallbacks) *fallbacks = 0;
    if (!count) return 1;
    if (!g || !pre || !out || !scalars || pre->pos.base.g != g ||
        (pre->schedule != 0 && pre->schedule != 1) || (!pre->point && !pre->pos.base.identity) ||
        block_size == 0 || block_size > 4096)
        return 0;
    tau_jac *projective = malloc(block_size * sizeof(*projective));
    uint64_t *prefixes = malloc(block_size * sizeof(*prefixes));
    if (!projective || !prefixes) {
        free(prefixes);
        free(projective);
        return 0;
    }
    uint64_t na = 0, nr = 0, ni = 0, nf = 0;
    for (size_t offset = 0; offset < count;) {
        size_t n = count - offset;
        if (n > block_size) n = block_size;
        for (size_t i = 0; i < n; i++) {
            uint64_t a = 0, r = 0, f = 0;
            if (!tau_wide_mul_jac(g, pre, &projective[i], scalars[offset + i], &a, &r, &f)) {
                free(prefixes);
                free(projective);
                return 0;
            }
            na += a;
            nr += r;
            nf += f;
        }
        uint64_t current = 0;
        if (!jac_batch_to_affine_scratch(g, out + offset, projective, n, prefixes, &current)) {
            free(prefixes);
            free(projective);
            return 0;
        }
        ni += current;
        offset += n;
    }
    free(prefixes);
    free(projective);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (output_inversions) *output_inversions = ni;
    if (fallbacks) *fallbacks = nf;
    return 1;
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
