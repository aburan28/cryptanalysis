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
#include "generated/tau3_fused.h"
#include "generated/tau3_atlas.h"
#include "generated/tau3_sparse.h"
#include "generated/tau3_radix27.h"
#include "generated/tau3_scatter.h"
#include "generated/tau3_scatter_atlas.h"
#include "generated/joint_window4.h"
#include "generated/joint_window4_hot.h"
#include "generated/joint_pair_map.h"
#include "generated/joint_pair_top_map.h"
#include "generated/tau8_orbit_map.h"
#include "generated/tau8_hot_map.h"
#include "generated/tau8_pair_map.h"
#include "generated/tau8_steer_map.h"
#include "generated/tau_wide_orbits.h"
#include "generated/tau_wide_graph.h"
#include "generated/tau_wide_packed_graph.h"
#include <float.h>
#include <limits.h>
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

int ca_ec_joint_pair_qcorr_available(void)
{
#if FLT_RADIX == 2 && DBL_MANT_DIG >= 53
    return 1;
#else
    return 0;
#endif
}

/* Exact quotient of a positive study numerator. The estimate only chooses
 * a starting integer; the signed remainder inequalities determine the
 * answer. The checked wrappers bound k, multiplier, and denominator. */
static ca_i128 round_div_float_corrected(uint64_t k, uint64_t multiplier, uint64_t denominator,
                                         uint64_t *corrections)
{
#if FLT_RADIX == 2 && DBL_MANT_DIG >= 53
    double estimate = (double)k * (double)multiplier / (double)denominator;
    if (estimate >= 0.0 && estimate < (double)multiplier + 2.0) {
        uint64_t q = (uint64_t)(estimate + 0.5);
        ca_i128 d = denominator;
        ca_i128 rem = (ca_i128)k * multiplier - (ca_i128)q * d;
        uint64_t count = 0;
        while (2 * rem >= d) {
            q++;
            rem -= d;
            count++;
        }
        while (2 * rem < -d) {
            q--;
            rem += d;
            count++;
        }
        if (corrections) *corrections += count;
        return q;
    }
#else
    (void)corrections;
#endif
    return round_div((ca_i128)k * multiplier, denominator);
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

static void reduce_with_lattice_eisenstein(tau_vec v1, tau_vec v2, ca_i128 det, uint64_t k,
                                           ca_i128 *out_x, ca_i128 *out_y, ca_i128 *out_u0,
                                           ca_i128 *out_v0)
{
    ca_i128 u0 = round_div((ca_i128)k * v2.y, det);
    ca_i128 v0 = round_div(-(ca_i128)k * v1.y, det);
    if (out_u0) *out_u0 = u0;
    if (out_v0) *out_v0 = v0;
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
    *out_x = bx;
    *out_y = by;
}

static void reduce_with_lattice(tau_vec v1, tau_vec v2, ca_i128 det, uint64_t k, ca_i128 *out_a,
                                ca_i128 *out_b)
{
    ca_i128 x, y;
    reduce_with_lattice_eisenstein(v1, v2, det, k, &x, &y, NULL, NULL);
    /* omega = 1 - tau, hence x + y*omega = (x+y) - y*tau. */
    *out_a = x + y;
    *out_b = -y;
}

/* For the two exact bounded-pair study lattices, the design certificate
 * proves only the four axial vectors can improve on rounded Babai. */
static void reduce_lattice_five_from_center(tau_vec v1, tau_vec v2, ca_i128 center_x,
                                            ca_i128 center_y, ca_i128 *out_a, ca_i128 *out_b)
{
    static const int offsets[5][2] = {{-1, 0}, {0, -1}, {0, 0}, {0, 1}, {1, 0}};
    ca_i128 best = -1, bx = 0, by = 0;
    for (unsigned i = 0; i < 5; i++) {
        ca_i128 x = center_x - offsets[i][0] * v1.x - offsets[i][1] * v2.x;
        ca_i128 y = center_y - offsets[i][0] * v1.y - offsets[i][1] * v2.y;
        ca_i128 score = iabs128(x) + iabs128(y);
        if (best < 0 || score < best) {
            best = score;
            bx = x;
            by = y;
        }
    }
    *out_a = bx + by;
    *out_b = -by;
}

static void reduce_with_lattice_five(tau_vec v1, tau_vec v2, ca_i128 det, uint64_t k,
                                     ca_i128 *out_a, ca_i128 *out_b)
{
    ca_i128 u0 = round_div((ca_i128)k * v2.y, det);
    ca_i128 v0 = round_div(-(ca_i128)k * v1.y, det);
    ca_i128 x = (ca_i128)k - u0 * v1.x - v0 * v2.x;
    ca_i128 y = -u0 * v1.y - v0 * v2.y;
    reduce_lattice_five_from_center(v1, v2, x, y, out_a, out_b);
}

/* This strict test proves the rounded center beats every axial neighbor.
 * The supported-lattice check in the public wrappers supplies the separate
 * certificate that no other translation can improve on those five points. */
static void reduce_with_lattice_guard(tau_vec v1, tau_vec v2, ca_i128 det, uint64_t k,
                                      ca_i128 *out_a, ca_i128 *out_b, uint64_t *guard_hit,
                                      int float_quotients, uint64_t *quotient_corrections)
{
    ca_i128 u0 = float_quotients ? round_div_float_corrected(k, (uint64_t)v2.y, (uint64_t)det,
                                                             quotient_corrections)
                                 : round_div((ca_i128)k * v2.y, det);
    ca_i128 v0 = float_quotients ? round_div_float_corrected(k, (uint64_t)(-v1.y), (uint64_t)det,
                                                             quotient_corrections)
                                 : round_div(-(ca_i128)k * v1.y, det);
    ca_i128 x = (ca_i128)k - u0 * v1.x - v0 * v2.x;
    ca_i128 y = -u0 * v1.y - v0 * v2.y;
    ca_i128 tx = iabs128(v2.x) - iabs128(v2.y);
    ca_i128 ty = iabs128(v1.y) - iabs128(v1.x);
    if (2 * iabs128(x) < tx && 2 * iabs128(y) < ty) {
        *out_a = x + y;
        *out_b = -y;
        if (guard_hit) *guard_hit = 1;
        return;
    }
    if (guard_hit) *guard_hit = 0;
    reduce_lattice_five_from_center(v1, v2, x, y, out_a, out_b);
}

static int reduce_scalar(uint64_t n, uint64_t lambda, uint64_t k, ca_i128 *out_a, ca_i128 *out_b)
{
    tau_vec v1, v2;
    ca_i128 det;
    if (!make_lattice(n, lambda, &v1, &v2, &det)) return 0;
    reduce_with_lattice(v1, v2, det, k, out_a, out_b);
    return 1;
}

size_t ca_ec_endo_radix8_point_entries(const ca_group *g)
{
    if (!g || g->order < 2) return 0;
    unsigned bits = 0;
    for (uint64_t n = g->order - 1; n; n >>= 1) bits++;
    return (bits <= 32 ? 3u : 4u) * CA_ENDO_RADIX8_MAGNITUDES;
}

int ca_ec_endo_radix8_prepare(const ca_group *g, const ca_elem *point, ca_endo_radix8_precomp *out,
                              uint64_t *doubles, uint64_t *adds, uint64_t *inversions)
{
    if (!g || !point || !out || g->kind != CA_GROUP_EC || g->endo_kind != 1 || g->a != 0 ||
        g->p % 3 != 1 || g->order % 3 != 1 || !g->endo_lambda)
        return 0;
    size_t entries = ca_ec_endo_radix8_point_entries(g);
    if (!entries || entries > 4 * CA_ENDO_RADIX8_MAGNITUDES) return 0;
    ca_endo_radix8_precomp pre = {0};
    pre.g = g;
    pre.base_point = *point;
    pre.beta = g->endo_c_mont;
    pre.positions = (unsigned)(entries / CA_ENDO_RADIX8_MAGNITUDES);
    pre.identity = point->w[2] != 0;
    tau_vec v1, v2;
    if (!make_lattice(g->order, g->order - g->endo_lambda, &v1, &v2, &pre.det)) return 0;
    pre.v1x = v1.x;
    pre.v1y = v1.y;
    pre.v2x = v2.x;
    pre.v2y = v2.y;
    if (doubles) *doubles = 0;
    if (adds) *adds = 0;
    if (inversions) *inversions = 0;
    if (pre.identity) {
        *out = pre;
        return 1;
    }
    pre.point = malloc(entries * sizeof(*pre.point));
    if (!pre.point) return 0;
    tau_jac projective[4 * CA_ENDO_RADIX8_MAGNITUDES];
    uint64_t prefixes[4 * CA_ENDO_RADIX8_MAGNITUDES];
    tau_jac basis = {point->w[0], point->w[1], g->mont.r1};
    for (unsigned position = 0; position < pre.positions; position++) {
        tau_jac multiple = basis;
        for (unsigned magnitude = 1; magnitude <= CA_ENDO_RADIX8_MAGNITUDES; magnitude++) {
            projective[(size_t)position * CA_ENDO_RADIX8_MAGNITUDES + magnitude - 1] = multiple;
            if (magnitude < CA_ENDO_RADIX8_MAGNITUDES) {
                multiple = jac_add(g, multiple, basis);
                if (adds) (*adds)++;
            }
        }
        if (position + 1 < pre.positions)
            for (unsigned bit = 0; bit < 8; bit++) {
                basis = jac_double(g, basis);
                if (doubles) (*doubles)++;
            }
    }
    if (!jac_batch_to_affine_scratch(g, pre.point, projective, entries, prefixes, inversions)) {
        free(pre.point);
        return 0;
    }
    *out = pre;
    return 1;
}

int ca_ec_endo_radix8_prepare_verify(const ca_endo_radix8_precomp *pre)
{
    if (!pre || !pre->g || !pre->positions || pre->positions > 4) return 0;
    if (pre->identity) return pre->point == NULL;
    if (!pre->point) return 0;
    uint64_t power = 1;
    for (unsigned position = 0; position < pre->positions; position++) {
        for (unsigned magnitude = 1; magnitude <= CA_ENDO_RADIX8_MAGNITUDES; magnitude++) {
            ca_elem expected;
            ca_group_mul(pre->g, &expected, &pre->base_point, power * magnitude, NULL);
            if (!ca_group_equal(
                    pre->g, &expected,
                    &pre->point[(size_t)position * CA_ENDO_RADIX8_MAGNITUDES + magnitude - 1]))
                return 0;
        }
        power *= 256;
    }
    return 1;
}

int ca_ec_endo_radix8_mul_profile(const ca_group *g, const ca_endo_radix8_precomp *pre,
                                  ca_elem *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                  uint64_t *fallbacks)
{
    if (!g || !pre || !out || pre->g != g || !pre->positions || pre->positions > 4) return 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (fallbacks) *fallbacks = 0;
    k %= g->order;
    if (!k || pre->identity) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    if (!pre->point) return 0;
    ca_i128 a, b;
    reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y}, pre->det, k,
                        &a, &b);
    ca_i128 coordinate[2] = {a + b, -b};
    int16_t digits[2][4] = {{0}};
    for (unsigned axis = 0; axis < 2; axis++) {
        for (unsigned position = 0; position < pre->positions; position++) {
            ca_i128 remainder = coordinate[axis] % 256;
            if (remainder < 0) remainder += 256;
            int16_t digit = (int16_t)(remainder >= 128 ? remainder - 256 : remainder);
            digits[axis][position] = digit;
            coordinate[axis] = (coordinate[axis] - digit) / 256;
        }
        if (coordinate[axis]) {
            if (fallbacks) *fallbacks = 1;
            ca_group_mul(g, out, &pre->base_point, k, NULL);
            return 1;
        }
    }
    tau_jac accumulator = {0, g->mont.r1, 0};
    uint64_t na = 0, nr = 0;
    for (unsigned position = 0; position < pre->positions; position++)
        for (unsigned axis = 0; axis < 2; axis++) {
            int digit = digits[axis][position];
            if (!digit) continue;
            unsigned magnitude = (unsigned)(digit < 0 ? -digit : digit);
            ca_elem point =
                pre->point[(size_t)position * CA_ENDO_RADIX8_MAGNITUDES + magnitude - 1];
            if (axis && !point.w[2]) {
                point.w[0] = fm(g, pre->beta, point.w[0]);
                nr++;
            }
            if (digit < 0 && !point.w[2] && point.w[1]) point.w[1] = g->p - point.w[1];
            if (!point.w[2]) {
                accumulator = jac_add_mixed(g, accumulator, &point);
                na++;
            }
        }
    jac_to_affine(g, out, accumulator);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    return 1;
}

void ca_ec_endo_radix8_clear(ca_endo_radix8_precomp *pre)
{
    if (!pre) return;
    free(pre->point);
    *pre = (ca_endo_radix8_precomp){0};
}

static tau_vec joint_window4_unit_coeff(tau_vec value, unsigned code)
{
    for (unsigned power = 0; power < code % 3; power++)
        value = (tau_vec){-value.y, value.x - value.y};
    if (code >= 3) value = (tau_vec){-value.x, -value.y};
    return value;
}

size_t ca_ec_joint_window4_static_bytes(void)
{
    return sizeof(ca_joint_window4_rep_x) + sizeof(ca_joint_window4_rep_y) +
           sizeof(ca_joint_window4_action);
}

size_t ca_ec_joint_window4_hot_static_bytes(void)
{
    return sizeof(ca_joint_window4_hot_rep_x) + sizeof(ca_joint_window4_hot_rep_y) +
           sizeof(ca_joint_window4_hot_action);
}

int ca_ec_joint_window4_hot_verify_map(void)
{
    if (!ca_ec_joint_window4_verify_map()) return 0;
    for (unsigned curve = 0; curve < 2; curve++) {
        uint8_t seen[CA_JOINT_WINDOW4_ORBITS] = {0};
        for (unsigned orbit = 0; orbit < CA_JOINT_WINDOW4_ORBITS; orbit++) {
            tau_vec rep = {ca_joint_window4_hot_rep_x[curve][orbit],
                           ca_joint_window4_hot_rep_y[curve][orbit]};
            tau_vec lex = rep;
            if (!rep.x && !rep.y) return 0;
            for (unsigned code = 0; code < 6; code++) {
                tau_vec moved = joint_window4_unit_coeff(rep, code);
                if (moved.x < lex.x || (moved.x == lex.x && moved.y < lex.y)) lex = moved;
            }
            if (lex.x != ca_joint_window4_rep_x[orbit] || lex.y != ca_joint_window4_rep_y[orbit])
                return 0;
        }
        for (unsigned index = 0; index < 256; index++) {
            int x = (int)(index / 16) - 8, y = (int)(index % 16) - 8;
            unsigned packed = ca_joint_window4_hot_action[curve][index];
            unsigned orbit = packed & 127u, code = packed >> 7;
            if (!x && !y) {
                if (orbit != CA_JOINT_WINDOW4_ZERO || code) return 0;
                continue;
            }
            if (orbit >= CA_JOINT_WINDOW4_ORBITS || code >= 6 ||
                orbit != (ca_joint_window4_action[index] & 127u))
                return 0;
            seen[orbit] = 1;
            tau_vec actual =
                joint_window4_unit_coeff((tau_vec){ca_joint_window4_hot_rep_x[curve][orbit],
                                                   ca_joint_window4_hot_rep_y[curve][orbit]},
                                         code);
            if (actual.x != x || actual.y != y) return 0;
        }
        for (unsigned orbit = 0; orbit < CA_JOINT_WINDOW4_ORBITS; orbit++)
            if (!seen[orbit]) return 0;
    }
    return 1;
}

int ca_ec_joint_window4_verify_map(void)
{
    uint8_t seen[CA_JOINT_WINDOW4_ORBITS] = {0};
    for (unsigned orbit = 0; orbit < CA_JOINT_WINDOW4_ORBITS; orbit++) {
        tau_vec rep = {ca_joint_window4_rep_x[orbit], ca_joint_window4_rep_y[orbit]};
        if (!rep.x && !rep.y) return 0;
        if (orbit && (rep.x < ca_joint_window4_rep_x[orbit - 1] ||
                      (rep.x == ca_joint_window4_rep_x[orbit - 1] &&
                       rep.y <= ca_joint_window4_rep_y[orbit - 1])))
            return 0;
        for (unsigned code = 0; code < 6; code++) {
            tau_vec moved = joint_window4_unit_coeff(rep, code);
            if (moved.x < rep.x || (moved.x == rep.x && moved.y < rep.y)) return 0;
        }
    }
    for (unsigned index = 0; index < 256; index++) {
        int x = (int)(index / 16) - 8, y = (int)(index % 16) - 8;
        unsigned packed = ca_joint_window4_action[index];
        unsigned orbit = packed & 127u, code = packed >> 7;
        if (!x && !y) {
            if (orbit != CA_JOINT_WINDOW4_ZERO || code) return 0;
            continue;
        }
        if (orbit >= CA_JOINT_WINDOW4_ORBITS || code >= 6) return 0;
        seen[orbit] = 1;
        tau_vec actual = joint_window4_unit_coeff(
            (tau_vec){ca_joint_window4_rep_x[orbit], ca_joint_window4_rep_y[orbit]}, code);
        if (actual.x != x || actual.y != y) return 0;
    }
    for (unsigned orbit = 0; orbit < CA_JOINT_WINDOW4_ORBITS; orbit++)
        if (!seen[orbit]) return 0;
    return 1;
}

size_t ca_ec_joint_window4_point_entries(const ca_group *g)
{
    if (!g || g->order < 2) return 0;
    unsigned bits = 0;
    for (uint64_t n = g->order - 1; n; n >>= 1) bits++;
    return (bits <= 32 ? 4u : 7u) * CA_JOINT_WINDOW4_ORBITS;
}

static int joint_window4_prepare_impl(const ca_group *g, const ca_elem *point,
                                      ca_joint_window4_precomp *out, uint64_t *doubles,
                                      uint64_t *adds, uint64_t *rotations, uint64_t *inversions,
                                      int hot)
{
    if (!g || !point || !out || g->kind != CA_GROUP_EC || g->endo_kind != 1 || g->a != 0 ||
        g->p % 3 != 1 || g->order % 3 != 1 || !g->endo_lambda)
        return 0;
    size_t entries = ca_ec_joint_window4_point_entries(g);
    if (!entries || entries > 7 * CA_JOINT_WINDOW4_ORBITS) return 0;
    ca_joint_window4_precomp pre = {0};
    pre.g = g;
    pre.base_point = *point;
    pre.hot = hot;
    if (hot) {
        unsigned curve;
        if (g->p == UINT64_C(4294967377) && g->b == 15 && g->order == UINT64_C(23729779) &&
            g->endo_lambda == UINT64_C(16027563))
            curve = 0;
        else if (g->p == UINT64_C(2305843009213693951) && g->b == 7 &&
                 g->order == UINT64_C(53624256071278747) &&
                 g->endo_lambda == UINT64_C(1212946466324730))
            curve = 1;
        else
            return 0;
        pre.rep_x = ca_joint_window4_hot_rep_x[curve];
        pre.rep_y = ca_joint_window4_hot_rep_y[curve];
        pre.action = ca_joint_window4_hot_action[curve];
    } else {
        pre.rep_x = ca_joint_window4_rep_x;
        pre.rep_y = ca_joint_window4_rep_y;
        pre.action = ca_joint_window4_action;
    }
    pre.beta = g->endo_c_mont;
    pre.beta2 = fm(g, pre.beta, pre.beta);
    pre.positions = (unsigned)(entries / CA_JOINT_WINDOW4_ORBITS);
    pre.identity = point->w[2] != 0;
    tau_vec v1, v2;
    if (!make_lattice(g->order, g->order - g->endo_lambda, &v1, &v2, &pre.det)) return 0;
    pre.v1x = v1.x;
    pre.v1y = v1.y;
    pre.v2x = v2.x;
    pre.v2y = v2.y;
    if (doubles) *doubles = 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (inversions) *inversions = 0;
    if (pre.identity) {
        *out = pre;
        return 1;
    }
    pre.point = malloc(entries * sizeof(*pre.point));
    if (!pre.point) return 0;
    tau_jac projective[7 * CA_JOINT_WINDOW4_ORBITS];
    uint64_t prefixes[7 * CA_JOINT_WINDOW4_ORBITS];
    tau_jac basis = {point->w[0], point->w[1], g->mont.r1};
    for (unsigned position = 0; position < pre.positions; position++) {
        tau_jac multiple[16], omega_multiple[9];
        multiple[0] = (tau_jac){0, g->mont.r1, 0};
        multiple[1] = basis;
        for (unsigned magnitude = 2; magnitude < 16; magnitude++) {
            multiple[magnitude] = jac_add(g, multiple[magnitude - 1], basis);
            if (adds) (*adds)++;
        }
        omega_multiple[0] = multiple[0];
        for (unsigned magnitude = 1; magnitude <= 8; magnitude++) {
            omega_multiple[magnitude] = multiple[magnitude];
            omega_multiple[magnitude].x = fm(g, pre.beta, omega_multiple[magnitude].x);
            if (rotations) (*rotations)++;
        }
        for (unsigned orbit = 0; orbit < CA_JOINT_WINDOW4_ORBITS; orbit++) {
            int x = pre.rep_x[orbit], y = pre.rep_y[orbit];
            unsigned ux = (unsigned)(x < 0 ? -x : x), uy = (unsigned)(y < 0 ? -y : y);
            if (ux >= 16 || uy > 8) {
                free(pre.point);
                return 0;
            }
            tau_jac left = multiple[ux], right = omega_multiple[uy];
            if (x < 0 && left.z && left.y) left.y = g->p - left.y;
            if (y < 0 && right.z && right.y) right.y = g->p - right.y;
            projective[(size_t)position * CA_JOINT_WINDOW4_ORBITS + orbit] =
                jac_add(g, left, right);
            if (adds && ux && uy) (*adds)++;
        }
        if (position + 1 < pre.positions)
            for (unsigned bit = 0; bit < 4; bit++) {
                basis = jac_double(g, basis);
                if (doubles) (*doubles)++;
            }
    }
    if (!jac_batch_to_affine_scratch(g, pre.point, projective, entries, prefixes, inversions)) {
        free(pre.point);
        return 0;
    }
    *out = pre;
    return 1;
}

int ca_ec_joint_window4_prepare(const ca_group *g, const ca_elem *point,
                                ca_joint_window4_precomp *out, uint64_t *doubles, uint64_t *adds,
                                uint64_t *rotations, uint64_t *inversions)
{
    return joint_window4_prepare_impl(g, point, out, doubles, adds, rotations, inversions, 0);
}

int ca_ec_joint_window4_hot_prepare(const ca_group *g, const ca_elem *point,
                                    ca_joint_window4_precomp *out, uint64_t *doubles,
                                    uint64_t *adds, uint64_t *rotations, uint64_t *inversions)
{
    return joint_window4_prepare_impl(g, point, out, doubles, adds, rotations, inversions, 1);
}

int ca_ec_joint_window4_xplane_prepare(const ca_group *g, const ca_elem *point,
                                       ca_joint_window4_precomp *out, uint64_t *doubles,
                                       uint64_t *adds, uint64_t *rotations, uint64_t *inversions,
                                       uint64_t *plane_muls)
{
    _Static_assert(sizeof(ca_joint_window4_plane_point) == sizeof(ca_elem),
                   "the x-coordinate plane must use one ordinary point slot");
    if (plane_muls) *plane_muls = 0;
    if (!joint_window4_prepare_impl(g, point, out, doubles, adds, rotations, inversions, 1))
        return 0;
    if (fa(g, fa(g, out->beta2, out->beta), g->mont.r1)) {
        ca_ec_joint_window4_clear(out);
        return 0;
    }
    if (out->identity) {
        out->plane_format = 1;
        return 1;
    }
    size_t entries = ca_ec_joint_window4_point_entries(g);
    ca_joint_window4_plane_point *packed = malloc(entries * sizeof(*packed));
    if (!packed) {
        ca_ec_joint_window4_clear(out);
        return 0;
    }
    uint64_t multiplies = 0;
    for (size_t i = 0; i < entries; i++) {
        ca_elem ordinary = out->point[i];
        packed[i].x = ordinary.w[0];
        packed[i].y = ordinary.w[1];
        packed[i].identity = ordinary.w[2];
        packed[i].x_beta = ordinary.w[2] ? 0 : fm(g, out->beta, ordinary.w[0]);
        multiplies += !ordinary.w[2];
    }
    free(out->point);
    out->point = NULL;
    out->plane_point = packed;
    out->plane_format = 1;
    if (plane_muls) *plane_muls = multiplies;
    return 1;
}

static unsigned joint_window4_residue16(ca_i128 value)
{
    ca_i128 residue = value % 16;
    return (unsigned)(residue < 0 ? residue + 16 : residue);
}

int ca_ec_joint_window4_zero_prepare(const ca_group *g, const ca_elem *point,
                                     ca_joint_window4_precomp *out, uint64_t *doubles,
                                     uint64_t *adds, uint64_t *rotations, uint64_t *inversions,
                                     uint64_t *plane_muls)
{
    if (!ca_ec_joint_window4_xplane_prepare(g, point, out, doubles, adds, rotations, inversions,
                                            plane_muls))
        return 0;
    unsigned determinant = joint_window4_residue16(out->det);
    for (unsigned inverse = 1; inverse < 16; inverse += 2) {
        if ((determinant * inverse) % 16 == 1) {
            out->zero_mode = 1;
            out->det_inverse16 = inverse;
            return 1;
        }
    }
    ca_ec_joint_window4_clear(out);
    return 0;
}

int ca_ec_joint_window4_prepare_verify(const ca_joint_window4_precomp *pre)
{
    if (!pre || !pre->g || !pre->positions || pre->positions > 7 || !pre->rep_x || !pre->rep_y ||
        !pre->action ||
        !(pre->hot ? ca_ec_joint_window4_hot_verify_map() : ca_ec_joint_window4_verify_map()))
        return 0;
    if (pre->zero_mode && (!pre->plane_format || !pre->det_inverse16 ||
                           (joint_window4_residue16(pre->det) * pre->det_inverse16) % 16 != 1))
        return 0;
    if (pre->identity) return pre->point == NULL && pre->plane_point == NULL;
    if (pre->plane_format ? (!pre->plane_point || pre->point) : (!pre->point || pre->plane_point))
        return 0;
    if (pre->plane_format && fa(pre->g, fa(pre->g, pre->beta2, pre->beta), pre->g->mont.r1))
        return 0;
    ca_i128 omega = (ca_i128)pre->g->order - pre->g->endo_lambda;
    ca_i128 power = 1;
    for (unsigned position = 0; position < pre->positions; position++) {
        for (unsigned orbit = 0; orbit < CA_JOINT_WINDOW4_ORBITS; orbit++) {
            ca_i128 scalar = power * (pre->rep_x[orbit] + omega * pre->rep_y[orbit]);
            scalar %= pre->g->order;
            if (scalar < 0) scalar += pre->g->order;
            ca_elem expected;
            ca_group_mul(pre->g, &expected, &pre->base_point, (uint64_t)scalar, NULL);
            size_t index = (size_t)position * CA_JOINT_WINDOW4_ORBITS + orbit;
            ca_elem stored;
            if (pre->plane_format) {
                ca_joint_window4_plane_point entry = pre->plane_point[index];
                stored = (ca_elem){{entry.x, entry.y, entry.identity, 0}};
                if (entry.x_beta != (entry.identity ? 0 : fm(pre->g, pre->beta, entry.x))) return 0;
                if (!entry.identity && fs(pre->g, 0, fa(pre->g, entry.x, entry.x_beta)) !=
                                           fm(pre->g, pre->beta2, entry.x))
                    return 0;
            } else {
                stored = pre->point[index];
            }
            if (!ca_group_equal(pre->g, &expected, &stored)) return 0;
        }
        power *= 16;
    }
    return 1;
}

static int joint_window4_recode(const ca_joint_window4_precomp *pre, ca_i128 x, ca_i128 y,
                                uint16_t action[7], unsigned *nonzero)
{
    *nonzero = 0;
    for (unsigned position = 0; position < pre->positions; position++) {
        ca_i128 rx = x % 16, ry = y % 16;
        if (rx < 0) rx += 16;
        if (ry < 0) ry += 16;
        int dx = (int)(rx >= 8 ? rx - 16 : rx);
        int dy = (int)(ry >= 8 ? ry - 16 : ry);
        action[position] = pre->action[(unsigned)(dx + 8) * 16 + (unsigned)(dy + 8)];
        *nonzero += dx != 0 || dy != 0;
        x = (x - dx) / 16;
        y = (y - dy) / 16;
    }
    return x == 0 && y == 0;
}

static int joint_window4_mul_impl(const ca_group *g, const ca_joint_window4_precomp *pre,
                                  ca_elem *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                  uint64_t *unit_adds, uint64_t *fallbacks, int zero_steer,
                                  uint64_t *candidate_attempts, uint64_t *candidate_feasible,
                                  uint64_t *candidate_selected)
{
    if (!g || !pre || !out || pre->g != g || !pre->positions || pre->positions > 7 || !pre->action)
        return 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (unit_adds) *unit_adds = 0;
    if (fallbacks) *fallbacks = 0;
    if (candidate_attempts) *candidate_attempts = 0;
    if (candidate_feasible) *candidate_feasible = 0;
    if (candidate_selected) *candidate_selected = 0;
    k %= g->order;
    if (!k || pre->identity) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    if (pre->plane_format ? !pre->plane_point : !pre->point) return 0;
    ca_i128 x, y, u0 = 0, v0 = 0;
    if (zero_steer) {
        reduce_with_lattice_eisenstein((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y},
                                       pre->det, k, &x, &y, &u0, &v0);
    } else {
        ca_i128 a, b;
        reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y}, pre->det,
                            k, &a, &b);
        x = a + b;
        y = -b;
    }
    uint16_t action[7];
    unsigned baseline_nonzero = 0;
    int fits = joint_window4_recode(pre, x, y, action, &baseline_nonzero);
    if (zero_steer) {
        if (!pre->zero_mode || !pre->plane_format || !pre->det_inverse16) return 0;
        if (candidate_attempts) *candidate_attempts = 1;
        unsigned target_u = joint_window4_residue16((ca_i128)k * pre->v2y * pre->det_inverse16);
        unsigned target_v = joint_window4_residue16(-(ca_i128)k * pre->v1y * pre->det_inverse16);
        int du = (int)joint_window4_residue16((ca_i128)target_u - u0);
        int dv = (int)joint_window4_residue16((ca_i128)target_v - v0);
        if (du >= 8) du -= 16;
        if (dv >= 8) dv -= 16;
        ca_i128 u = u0 + du, v = v0 + dv;
        ca_i128 candidate_x = (ca_i128)k - u * pre->v1x - v * pre->v2x;
        ca_i128 candidate_y = -u * pre->v1y - v * pre->v2y;
        if (joint_window4_residue16(candidate_x) || joint_window4_residue16(candidate_y)) return 0;
        uint16_t directed_action[7];
        unsigned directed_nonzero = 0;
        int directed_fits =
            joint_window4_recode(pre, candidate_x, candidate_y, directed_action, &directed_nonzero);
        if (directed_fits) {
            if (candidate_feasible) *candidate_feasible = 1;
            if (!fits || directed_nonzero < baseline_nonzero) {
                memcpy(action, directed_action, pre->positions * sizeof(action[0]));
                fits = 1;
                if (candidate_selected) *candidate_selected = 1;
            }
        }
    }
    if (!fits) {
        if (fallbacks) *fallbacks = 1;
        ca_group_mul(g, out, &pre->base_point, k, NULL);
        return 1;
    }
    tau_jac accumulator = {0, g->mont.r1, 0};
    uint64_t na = 0, nr = 0, nu = 0;
    for (unsigned position = 0; position < pre->positions; position++) {
        unsigned orbit = action[position] & 127u, code = action[position] >> 7;
        if (orbit == CA_JOINT_WINDOW4_ZERO) continue;
        if (orbit >= CA_JOINT_WINDOW4_ORBITS || code >= 6) return 0;
        size_t index = (size_t)position * CA_JOINT_WINDOW4_ORBITS + orbit;
        ca_elem point;
        if (pre->plane_format) {
            ca_joint_window4_plane_point entry = pre->plane_point[index];
            point = (ca_elem){{entry.x, entry.y, entry.identity, 0}};
        } else {
            point = pre->point[index];
        }
        if (!point.w[2]) {
            unsigned power = code % 3;
            if (pre->plane_format) {
                if (power == 1) point.w[0] = pre->plane_point[index].x_beta;
                if (power == 2) {
                    point.w[0] = fs(g, 0, fa(g, point.w[0], pre->plane_point[index].x_beta));
                    nu += 2;
                }
            } else {
                if (power == 1) point.w[0] = fm(g, pre->beta, point.w[0]);
                if (power == 2) point.w[0] = fm(g, pre->beta2, point.w[0]);
                nr += power != 0;
            }
            if (code >= 3 && point.w[1]) point.w[1] = g->p - point.w[1];
            accumulator = jac_add_mixed(g, accumulator, &point);
            na++;
        }
    }
    jac_to_affine(g, out, accumulator);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (unit_adds) *unit_adds = nu;
    return 1;
}

int ca_ec_joint_window4_mul_profile(const ca_group *g, const ca_joint_window4_precomp *pre,
                                    ca_elem *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                    uint64_t *fallbacks)
{
    return joint_window4_mul_impl(g, pre, out, k, adds, rotations, NULL, fallbacks, 0, NULL, NULL,
                                  NULL);
}

int ca_ec_joint_window4_xplane_mul_profile(const ca_group *g, const ca_joint_window4_precomp *pre,
                                           ca_elem *out, uint64_t k, uint64_t *adds,
                                           uint64_t *rotations, uint64_t *unit_adds,
                                           uint64_t *fallbacks)
{
    if (!pre || !pre->plane_format) return 0;
    return joint_window4_mul_impl(g, pre, out, k, adds, rotations, unit_adds, fallbacks, 0, NULL,
                                  NULL, NULL);
}

int ca_ec_joint_window4_zero_mul_profile(const ca_group *g, const ca_joint_window4_precomp *pre,
                                         ca_elem *out, uint64_t k, uint64_t *adds,
                                         uint64_t *unit_adds, uint64_t *fallbacks,
                                         uint64_t *candidate_attempts, uint64_t *candidate_feasible,
                                         uint64_t *candidate_selected)
{
    if (!pre || !pre->plane_format || !pre->zero_mode) return 0;
    return joint_window4_mul_impl(g, pre, out, k, adds, NULL, unit_adds, fallbacks, 1,
                                  candidate_attempts, candidate_feasible, candidate_selected);
}

void ca_ec_joint_window4_clear(ca_joint_window4_precomp *pre)
{
    if (!pre) return;
    free(pre->point);
    free(pre->plane_point);
    *pre = (ca_joint_window4_precomp){0};
}

size_t ca_ec_joint_pair_static_bytes(void)
{
    return sizeof(ca_joint_pair_digit_x) + sizeof(ca_joint_pair_digit_y) +
           sizeof(ca_joint_pair_rep_x) + sizeof(ca_joint_pair_rep_y) + sizeof(ca_joint_pair_action);
}

size_t ca_ec_joint_pair_top_static_bytes(void)
{
    return ca_ec_joint_pair_static_bytes() + sizeof(ca_joint_pair_top_small_orbit) +
           sizeof(ca_joint_pair_top_large_orbit) + sizeof(ca_joint_pair_top_small_rank) +
           sizeof(ca_joint_pair_top_large_rank);
}

static int joint_pair_curve_index(const ca_group *g)
{
    if (!g || g->kind != CA_GROUP_EC) return -1;
    if (g->p == UINT64_C(4294967377) && g->b == 15 && g->order == UINT64_C(23729779) &&
        g->endo_lambda == UINT64_C(16027563))
        return 0;
    if (g->p == UINT64_C(2305843009213693951) && g->b == 7 &&
        g->order == UINT64_C(53624256071278747) && g->endo_lambda == UINT64_C(1212946466324730))
        return 1;
    return -1;
}

static int joint_pair_five_supported(const ca_joint_pair_precomp *pre)
{
    if (!pre || !pre->g || !pre->top_compressed) return 0;
    int curve = joint_pair_curve_index(pre->g);
    if (curve == 0)
        return pre->v1x == 2323 && pre->v1y == -3275 && pre->v2x == 5598 && pre->v2y == 2323 &&
               pre->det == UINT64_C(23729779);
    if (curve == 1)
        return pre->v1x == 140057 && pre->v1y == -231499057 && pre->v2x == 231639114 &&
               pre->v2y == 140057 && pre->det == UINT64_C(53624256071278747);
    return 0;
}

size_t ca_ec_joint_pair_point_entries(const ca_group *g)
{
    int curve = joint_pair_curve_index(g);
    return curve < 0 ? 0 : (size_t)(curve ? 4 : 2) * CA_JOINT_PAIR_ORBITS;
}

size_t ca_ec_joint_pair_top_point_entries(const ca_group *g)
{
    int curve = joint_pair_curve_index(g);
    if (curve < 0) return 0;
    return (size_t)(curve ? 3 : 1) * CA_JOINT_PAIR_ORBITS +
           (curve ? CA_JOINT_PAIR_TOP_LARGE_ORBITS : CA_JOINT_PAIR_TOP_SMALL_ORBITS);
}

int ca_ec_joint_pair_verify_map(void)
{
    uint8_t seen[CA_JOINT_PAIR_ORBITS] = {0};
    for (unsigned orbit = 0; orbit < CA_JOINT_PAIR_ORBITS; orbit++) {
        tau_vec rep = {ca_joint_pair_rep_x[orbit], ca_joint_pair_rep_y[orbit]};
        if (!rep.x && !rep.y) return 0;
        if (orbit &&
            (rep.x < ca_joint_pair_rep_x[orbit - 1] ||
             (rep.x == ca_joint_pair_rep_x[orbit - 1] && rep.y <= ca_joint_pair_rep_y[orbit - 1])))
            return 0;
        for (unsigned code = 0; code < 6; code++) {
            tau_vec moved = joint_window4_unit_coeff(rep, code);
            if (moved.x < rep.x || (moved.x == rep.x && moved.y < rep.y)) return 0;
        }
    }
    for (unsigned residue = 0; residue < 256; residue++) {
        int x = ca_joint_pair_digit_x[residue], y = ca_joint_pair_digit_y[residue];
        if (joint_window4_residue16(x) != residue / 16 ||
            joint_window4_residue16(y) != residue % 16)
            return 0;
    }
    for (unsigned first = 0; first < 256; first++) {
        for (unsigned second = 0; second < 256; second++) {
            unsigned packed = ca_joint_pair_action[(first << 8) | second];
            unsigned orbit = packed & CA_JOINT_PAIR_ZERO, code = packed >> CA_JOINT_PAIR_ORBIT_BITS;
            tau_vec pair = {
                ca_joint_pair_digit_x[first] + 16 * (ca_i128)ca_joint_pair_digit_x[second],
                ca_joint_pair_digit_y[first] + 16 * (ca_i128)ca_joint_pair_digit_y[second]};
            if (!pair.x && !pair.y) {
                if (orbit != CA_JOINT_PAIR_ZERO || code) return 0;
                continue;
            }
            if (orbit >= CA_JOINT_PAIR_ORBITS || code >= 6) return 0;
            seen[orbit] = 1;
            tau_vec actual = joint_window4_unit_coeff(
                (tau_vec){ca_joint_pair_rep_x[orbit], ca_joint_pair_rep_y[orbit]}, code);
            if (actual.x != pair.x || actual.y != pair.y) return 0;
        }
    }
    for (unsigned orbit = 0; orbit < CA_JOINT_PAIR_ORBITS; orbit++)
        if (!seen[orbit]) return 0;
    return 1;
}

static int joint_pair_top_verify_one(const uint16_t *top_orbit, const uint16_t *top_rank,
                                     unsigned top_count, int bound)
{
    for (unsigned slot = 0; slot < top_count; slot++) {
        unsigned orbit = top_orbit[slot];
        if (orbit >= CA_JOINT_PAIR_ORBITS || top_rank[orbit] != slot ||
            (slot && orbit <= top_orbit[slot - 1]))
            return 0;
    }
    for (unsigned orbit = 0; orbit < CA_JOINT_PAIR_ORBITS; orbit++) {
        unsigned slot = top_rank[orbit];
        if (slot != CA_JOINT_PAIR_TOP_MISSING && (slot >= top_count || top_orbit[slot] != orbit))
            return 0;
    }
    for (int x0 = -bound; x0 <= bound; x0++) {
        for (int y0 = -bound; y0 <= bound; y0++) {
            int x = x0, y = y0;
            unsigned residue[2];
            for (unsigned digit = 0; digit < 2; digit++) {
                unsigned rx = joint_window4_residue16(x), ry = joint_window4_residue16(y);
                residue[digit] = (rx << 4) | ry;
                x = (x - ca_joint_pair_digit_x[residue[digit]]) / 16;
                y = (y - ca_joint_pair_digit_y[residue[digit]]) / 16;
            }
            if (x || y) return 0;
            unsigned packed = ca_joint_pair_action[(residue[0] << 8) | residue[1]];
            unsigned orbit = packed & CA_JOINT_PAIR_ZERO;
            if (!x0 && !y0) {
                if (orbit != CA_JOINT_PAIR_ZERO) return 0;
            } else if (orbit >= CA_JOINT_PAIR_ORBITS ||
                       top_rank[orbit] == CA_JOINT_PAIR_TOP_MISSING) {
                return 0;
            }
        }
    }
    return 1;
}

int ca_ec_joint_pair_top_verify_map(void)
{
    return ca_ec_joint_pair_verify_map() &&
           joint_pair_top_verify_one(ca_joint_pair_top_small_orbit, ca_joint_pair_top_small_rank,
                                     CA_JOINT_PAIR_TOP_SMALL_ORBITS, 27) &&
           joint_pair_top_verify_one(ca_joint_pair_top_large_orbit, ca_joint_pair_top_large_rank,
                                     CA_JOINT_PAIR_TOP_LARGE_ORBITS, 14);
}

static int joint_pair_prepare_impl(const ca_group *g, const ca_elem *point,
                                   ca_joint_pair_precomp *out, uint64_t *doubles, uint64_t *adds,
                                   uint64_t *inversions, uint64_t *plane_muls, int top_compressed,
                                   unsigned point_words)
{
    if (!g || !point || !out || g->kind != CA_GROUP_EC || g->endo_kind != 1 || g->a != 0 ||
        g->p % 3 != 1 || g->order % 3 != 1 || !g->endo_lambda ||
        (point_words != 4 && point_words != 3 && point_words != 2) ||
        (!top_compressed && point_words != 4) ||
        !(top_compressed ? ca_ec_joint_pair_top_verify_map() : ca_ec_joint_pair_verify_map()))
        return 0;
    int curve = joint_pair_curve_index(g);
    size_t entries =
        top_compressed ? ca_ec_joint_pair_top_point_entries(g) : ca_ec_joint_pair_point_entries(g);
    if (!entries) return 0;
    ca_joint_pair_precomp pre = {0};
    pre.g = g;
    pre.base_point = *point;
    pre.pairs = curve ? 4 : 2;
    pre.top_compressed = top_compressed;
    pre.point_words = point_words;
    if (top_compressed) {
        pre.top_count = curve ? CA_JOINT_PAIR_TOP_LARGE_ORBITS : CA_JOINT_PAIR_TOP_SMALL_ORBITS;
        pre.top_orbit = curve ? ca_joint_pair_top_large_orbit : ca_joint_pair_top_small_orbit;
        pre.top_rank = curve ? ca_joint_pair_top_large_rank : ca_joint_pair_top_small_rank;
    }
    pre.beta = g->endo_c_mont;
    pre.beta2 = fm(g, pre.beta, pre.beta);
    pre.identity = point->w[2] != 0;
    if (fa(g, fa(g, pre.beta2, pre.beta), g->mont.r1)) return 0;
    tau_vec v1, v2;
    if (!make_lattice(g->order, g->order - g->endo_lambda, &v1, &v2, &pre.det)) return 0;
    pre.v1x = v1.x;
    pre.v1y = v1.y;
    pre.v2x = v2.x;
    pre.v2y = v2.y;
    if (doubles) *doubles = 0;
    if (adds) *adds = 0;
    if (inversions) *inversions = 0;
    if (plane_muls) *plane_muls = 0;
    if (pre.identity) {
        *out = pre;
        return 1;
    }
    if (point_words == 4)
        pre.plane_point = malloc(entries * sizeof(*pre.plane_point));
    else if (point_words == 3)
        pre.triple_point = malloc(entries * sizeof(*pre.triple_point));
    else
        pre.double_point = malloc(entries * sizeof(*pre.double_point));
    tau_jac *projective = malloc(CA_JOINT_PAIR_ORBITS * sizeof(*projective));
    ca_elem *affine = malloc(CA_JOINT_PAIR_ORBITS * sizeof(*affine));
    uint64_t *prefixes = malloc(CA_JOINT_PAIR_ORBITS * sizeof(*prefixes));
    if (!(pre.plane_point || pre.triple_point || pre.double_point) || !projective || !affine ||
        !prefixes) {
        free(pre.plane_point);
        free(pre.triple_point);
        free(pre.double_point);
        free(projective);
        free(affine);
        free(prefixes);
        return 0;
    }
    tau_jac basis = {point->w[0], point->w[1], g->mont.r1};
    for (unsigned pair_position = 0; pair_position < pre.pairs; pair_position++) {
        int sparse_top = pre.top_compressed && pair_position + 1 == pre.pairs;
        unsigned current_orbits = sparse_top ? pre.top_count : CA_JOINT_PAIR_ORBITS;
        unsigned max_coordinate = sparse_top ? (curve ? 28u : 54u) : 170u;
        tau_jac x_multiple[171], y_multiple[171];
        tau_jac omega_basis = basis;
        omega_basis.x = fm(g, pre.beta, basis.x);
        x_multiple[0] = y_multiple[0] = (tau_jac){0, g->mont.r1, 0};
        x_multiple[1] = basis;
        y_multiple[1] = omega_basis;
        for (unsigned magnitude = 2; magnitude <= max_coordinate; magnitude++) {
            x_multiple[magnitude] = jac_add(g, x_multiple[magnitude - 1], basis);
            y_multiple[magnitude] = jac_add(g, y_multiple[magnitude - 1], omega_basis);
            if (adds) (*adds) += 2;
        }
        for (unsigned orbit = 0; orbit < current_orbits; orbit++) {
            unsigned global_orbit = sparse_top ? pre.top_orbit[orbit] : orbit;
            int x = ca_joint_pair_rep_x[global_orbit], y = ca_joint_pair_rep_y[global_orbit];
            unsigned ax = (unsigned)(x < 0 ? -x : x), ay = (unsigned)(y < 0 ? -y : y);
            if (ax > max_coordinate || ay > max_coordinate) goto failure;
            tau_jac left = x_multiple[ax], right = y_multiple[ay];
            if (x < 0 && left.z && left.y) left.y = g->p - left.y;
            if (y < 0 && right.z && right.y) right.y = g->p - right.y;
            projective[orbit] = jac_add(g, left, right);
            if (adds && ax && ay) (*adds)++;
        }
        uint64_t current_inversions = 0;
        if (!jac_batch_to_affine_scratch(g, affine, projective, current_orbits, prefixes,
                                         &current_inversions))
            goto failure;
        if (inversions) *inversions += current_inversions;
        for (unsigned orbit = 0; orbit < current_orbits; orbit++) {
            ca_elem ordinary = affine[orbit];
            size_t index = (size_t)pair_position * CA_JOINT_PAIR_ORBITS + orbit;
            if (point_words == 4) {
                pre.plane_point[index] = (ca_joint_window4_plane_point){
                    ordinary.w[0], ordinary.w[1],
                    ordinary.w[2] ? 0 : fm(g, pre.beta, ordinary.w[0]), ordinary.w[2]};
                if (plane_muls) (*plane_muls) += !ordinary.w[2];
            } else {
                if (ordinary.w[2]) goto failure;
                if (point_words == 3) {
                    pre.triple_point[index] = (ca_joint_pair_triple_point){
                        ordinary.w[0], ordinary.w[1], fm(g, pre.beta, ordinary.w[0])};
                    if (plane_muls) (*plane_muls)++;
                } else {
                    pre.double_point[index] =
                        (ca_joint_pair_double_point){ordinary.w[0], ordinary.w[1]};
                }
            }
        }
        if (pair_position + 1 < pre.pairs)
            for (unsigned bit = 0; bit < 8; bit++) {
                basis = jac_double(g, basis);
                if (doubles) (*doubles)++;
            }
    }
    free(projective);
    free(affine);
    free(prefixes);
    *out = pre;
    return 1;
failure:
    free(pre.plane_point);
    free(pre.triple_point);
    free(pre.double_point);
    free(projective);
    free(affine);
    free(prefixes);
    return 0;
}

int ca_ec_joint_pair_prepare(const ca_group *g, const ca_elem *point, ca_joint_pair_precomp *out,
                             uint64_t *doubles, uint64_t *adds, uint64_t *inversions,
                             uint64_t *plane_muls)
{
    return joint_pair_prepare_impl(g, point, out, doubles, adds, inversions, plane_muls, 0, 4);
}

int ca_ec_joint_pair_top_prepare(const ca_group *g, const ca_elem *point,
                                 ca_joint_pair_precomp *out, uint64_t *doubles, uint64_t *adds,
                                 uint64_t *inversions, uint64_t *plane_muls)
{
    return joint_pair_prepare_impl(g, point, out, doubles, adds, inversions, plane_muls, 1, 4);
}

int ca_ec_joint_pair_width_prepare(const ca_group *g, const ca_elem *point,
                                   ca_joint_pair_precomp *out, unsigned point_words,
                                   uint64_t *doubles, uint64_t *adds, uint64_t *inversions,
                                   uint64_t *plane_muls)
{
    if (point_words != 2 && point_words != 3) return 0;
    return joint_pair_prepare_impl(g, point, out, doubles, adds, inversions, plane_muls, 1,
                                   point_words);
}

int ca_ec_joint_pair_prepare_verify(const ca_joint_pair_precomp *pre)
{
    if (!pre || !pre->g || !pre->pairs || pre->pairs > 4 || !ca_ec_joint_pair_verify_map())
        return 0;
    if (pre->top_compressed && (!pre->top_orbit || !pre->top_rank || !pre->top_count ||
                                !ca_ec_joint_pair_top_verify_map()))
        return 0;
    if (pre->identity)
        return (pre->point_words == 4 || pre->point_words == 3 || pre->point_words == 2) &&
               !pre->plane_point && !pre->triple_point && !pre->double_point;
    if ((pre->point_words == 4 && (!pre->plane_point || pre->triple_point || pre->double_point)) ||
        (pre->point_words == 3 && (!pre->triple_point || pre->plane_point || pre->double_point)) ||
        (pre->point_words == 2 && (!pre->double_point || pre->plane_point || pre->triple_point)) ||
        (pre->point_words != 4 && pre->point_words != 3 && pre->point_words != 2))
        return 0;
    const ca_group *g = pre->g;
    ca_i128 omega = (ca_i128)g->order - g->endo_lambda;
    ca_i128 power = 1;
    for (unsigned pair_position = 0; pair_position < pre->pairs; pair_position++) {
        int sparse_top = pre->top_compressed && pair_position + 1 == pre->pairs;
        unsigned current_orbits = sparse_top ? pre->top_count : CA_JOINT_PAIR_ORBITS;
        for (unsigned orbit = 0; orbit < current_orbits; orbit++) {
            unsigned global_orbit = sparse_top ? pre->top_orbit[orbit] : orbit;
            ca_i128 scalar = power * (ca_joint_pair_rep_x[global_orbit] +
                                      omega * ca_joint_pair_rep_y[global_orbit]);
            scalar %= g->order;
            if (scalar < 0) scalar += g->order;
            ca_elem expected;
            ca_group_mul(g, &expected, &pre->base_point, (uint64_t)scalar, NULL);
            size_t index = (size_t)pair_position * CA_JOINT_PAIR_ORBITS + orbit;
            ca_elem actual;
            if (pre->point_words == 4) {
                ca_joint_window4_plane_point packed = pre->plane_point[index];
                actual = (ca_elem){{packed.x, packed.y, packed.identity, 0}};
                if (packed.x_beta != (packed.identity ? 0 : fm(g, pre->beta, packed.x))) return 0;
            } else if (pre->point_words == 3) {
                ca_joint_pair_triple_point packed = pre->triple_point[index];
                actual = (ca_elem){{packed.x, packed.y, 0, 0}};
                if (packed.x_beta != fm(g, pre->beta, packed.x)) return 0;
            } else {
                ca_joint_pair_double_point packed = pre->double_point[index];
                actual = (ca_elem){{packed.x, packed.y, 0, 0}};
            }
            if (!ca_group_equal(g, &expected, &actual)) return 0;
        }
        power *= 256;
    }
    return 1;
}

static int joint_pair_mul_impl(const ca_group *g, const ca_joint_pair_precomp *pre, ca_elem *out,
                               uint64_t k, uint64_t *adds, uint64_t *rotations, uint64_t *unit_adds,
                               uint64_t *fallbacks, int reduction_mode, uint64_t *guard_hits,
                               uint64_t *quotient_corrections)
{
    if (!g || !pre || !out || pre->g != g || !pre->pairs || pre->pairs > 4) return 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (unit_adds) *unit_adds = 0;
    if (fallbacks) *fallbacks = 0;
    if (guard_hits) *guard_hits = 0;
    if (quotient_corrections) *quotient_corrections = 0;
    k %= g->order;
    if (!k || pre->identity) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    if ((pre->point_words == 4 && !pre->plane_point) ||
        (pre->point_words == 3 && !pre->triple_point) ||
        (pre->point_words == 2 && !pre->double_point) ||
        (pre->point_words != 4 && pre->point_words != 3 && pre->point_words != 2))
        return 0;
    ca_i128 a, b;
    if (reduction_mode == 2 || reduction_mode == 3)
        reduce_with_lattice_guard((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y},
                                  pre->det, k, &a, &b, guard_hits, reduction_mode == 3,
                                  quotient_corrections);
    else if (reduction_mode == 1)
        reduce_with_lattice_five((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y},
                                 pre->det, k, &a, &b);
    else
        reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y}, pre->det,
                            k, &a, &b);
    ca_i128 x = a + b, y = -b;
    uint32_t action[4];
    for (unsigned pair_position = 0; pair_position < pre->pairs; pair_position++) {
        unsigned residues[2];
        for (unsigned digit = 0; digit < 2; digit++) {
            unsigned rx = joint_window4_residue16(x), ry = joint_window4_residue16(y);
            residues[digit] = (rx << 4) | ry;
            x = (x - ca_joint_pair_digit_x[residues[digit]]) / 16;
            y = (y - ca_joint_pair_digit_y[residues[digit]]) / 16;
        }
        action[pair_position] = ca_joint_pair_action[(residues[0] << 8) | residues[1]];
    }
    if (x || y) {
        if (fallbacks) *fallbacks = 1;
        ca_group_mul(g, out, &pre->base_point, k, NULL);
        return 1;
    }
    if (pre->top_compressed) {
        if (!pre->top_rank || !pre->top_orbit) return 0;
        unsigned top_orbit = action[pre->pairs - 1] & CA_JOINT_PAIR_ZERO;
        if (top_orbit != CA_JOINT_PAIR_ZERO &&
            (top_orbit >= CA_JOINT_PAIR_ORBITS ||
             pre->top_rank[top_orbit] == CA_JOINT_PAIR_TOP_MISSING)) {
            if (fallbacks) *fallbacks = 1;
            ca_group_mul(g, out, &pre->base_point, k, NULL);
            return 1;
        }
    }
    tau_jac accumulator = {0, g->mont.r1, 0};
    uint64_t na = 0, nr = 0, nu = 0;
    for (unsigned pair_position = 0; pair_position < pre->pairs; pair_position++) {
        unsigned orbit = action[pair_position] & CA_JOINT_PAIR_ZERO;
        unsigned code = action[pair_position] >> CA_JOINT_PAIR_ORBIT_BITS;
        if (orbit == CA_JOINT_PAIR_ZERO) continue;
        if (orbit >= CA_JOINT_PAIR_ORBITS || code >= 6) return 0;
        if (pre->top_compressed && pair_position + 1 == pre->pairs) orbit = pre->top_rank[orbit];
        size_t index = (size_t)pair_position * CA_JOINT_PAIR_ORBITS + orbit;
        ca_elem point;
        if (pre->point_words == 4) {
            ca_joint_window4_plane_point packed = pre->plane_point[index];
            point = (ca_elem){{packed.x, packed.y, packed.identity, 0}};
            if (point.w[2]) continue;
            if (code % 3 == 1) point.w[0] = packed.x_beta;
            if (code % 3 == 2) {
                point.w[0] = fs(g, 0, fa(g, packed.x, packed.x_beta));
                nu += 2;
            }
        } else if (pre->point_words == 3) {
            ca_joint_pair_triple_point packed = pre->triple_point[index];
            point = (ca_elem){{packed.x, packed.y, 0, 0}};
            if (code % 3 == 1) point.w[0] = packed.x_beta;
            if (code % 3 == 2) {
                point.w[0] = fs(g, 0, fa(g, packed.x, packed.x_beta));
                nu += 2;
            }
        } else if (pre->point_words == 2) {
            ca_joint_pair_double_point packed = pre->double_point[index];
            point = (ca_elem){{packed.x, packed.y, 0, 0}};
            if (code % 3 == 1) {
                point.w[0] = fm(g, pre->beta, packed.x);
                nr++;
            }
            if (code % 3 == 2) {
                point.w[0] = fm(g, pre->beta2, packed.x);
                nr++;
            }
        } else {
            return 0;
        }
        if (code >= 3 && point.w[1]) point.w[1] = g->p - point.w[1];
        accumulator = jac_add_mixed(g, accumulator, &point);
        na++;
    }
    jac_to_affine(g, out, accumulator);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (unit_adds) *unit_adds = nu;
    return 1;
}

int ca_ec_joint_pair_mul_profile(const ca_group *g, const ca_joint_pair_precomp *pre, ca_elem *out,
                                 uint64_t k, uint64_t *adds, uint64_t *unit_adds,
                                 uint64_t *fallbacks)
{
    if (!pre || pre->point_words != 4) return 0;
    return joint_pair_mul_impl(g, pre, out, k, adds, NULL, unit_adds, fallbacks, 0, NULL, NULL);
}

int ca_ec_joint_pair_width_mul_profile(const ca_group *g, const ca_joint_pair_precomp *pre,
                                       ca_elem *out, uint64_t k, uint64_t *adds,
                                       uint64_t *rotations, uint64_t *unit_adds,
                                       uint64_t *fallbacks)
{
    if (!pre || (pre->point_words != 3 && pre->point_words != 2)) return 0;
    return joint_pair_mul_impl(g, pre, out, k, adds, rotations, unit_adds, fallbacks, 0, NULL,
                               NULL);
}

int ca_ec_joint_pair_width_five_mul_profile(const ca_group *g, const ca_joint_pair_precomp *pre,
                                            ca_elem *out, uint64_t k, uint64_t *adds,
                                            uint64_t *rotations, uint64_t *unit_adds,
                                            uint64_t *fallbacks)
{
    if (!joint_pair_five_supported(pre) || (pre->point_words != 3 && pre->point_words != 2))
        return 0;
    return joint_pair_mul_impl(g, pre, out, k, adds, rotations, unit_adds, fallbacks, 1, NULL,
                               NULL);
}

int ca_ec_joint_pair_width_guard_mul_profile(const ca_group *g, const ca_joint_pair_precomp *pre,
                                             ca_elem *out, uint64_t k, uint64_t *adds,
                                             uint64_t *rotations, uint64_t *unit_adds,
                                             uint64_t *fallbacks, uint64_t *guard_hits)
{
    if (!joint_pair_five_supported(pre) || (pre->point_words != 3 && pre->point_words != 2))
        return 0;
    return joint_pair_mul_impl(g, pre, out, k, adds, rotations, unit_adds, fallbacks, 2, guard_hits,
                               NULL);
}

int ca_ec_joint_pair_width_qcorr_mul_profile(const ca_group *g, const ca_joint_pair_precomp *pre,
                                             ca_elem *out, uint64_t k, uint64_t *adds,
                                             uint64_t *rotations, uint64_t *unit_adds,
                                             uint64_t *fallbacks, uint64_t *guard_hits,
                                             uint64_t *quotient_corrections)
{
    if (!joint_pair_five_supported(pre) || (pre->point_words != 3 && pre->point_words != 2))
        return 0;
    return joint_pair_mul_impl(g, pre, out, k, adds, rotations, unit_adds, fallbacks, 3, guard_hits,
                               quotient_corrections);
}

static int joint_pair_width_mul_wave_impl(const ca_group *g, const ca_joint_pair_precomp *pre,
                                          ca_elem *out, const uint64_t *scalars, size_t count,
                                          size_t block_size, uint64_t *adds, uint64_t *rotations,
                                          uint64_t *unit_adds, uint64_t *output_inversions,
                                          uint64_t *fallbacks, int reduction_mode,
                                          uint64_t *guard_hits, uint64_t *quotient_corrections)
{
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (unit_adds) *unit_adds = 0;
    if (output_inversions) *output_inversions = 0;
    if (fallbacks) *fallbacks = 0;
    if (guard_hits) *guard_hits = 0;
    if (quotient_corrections) *quotient_corrections = 0;
    if (!count) return 1;
    if (!g || !pre || !out || !scalars || pre->g != g || !pre->top_compressed || !pre->top_rank ||
        !pre->pairs || pre->pairs > 4 || (pre->point_words != 3 && pre->point_words != 2) ||
        (!pre->identity && ((pre->point_words == 3 && !pre->triple_point) ||
                            (pre->point_words == 2 && !pre->double_point))) ||
        !block_size || block_size > 4096)
        return 0;

    uint32_t *actions = malloc(block_size * 4 * sizeof(*actions));
    ca_elem *queries = malloc(block_size * sizeof(*queries));
    uint64_t *scratch = malloc(block_size * 2 * sizeof(*scratch));
    uint8_t *active = malloc(block_size * sizeof(*active));
    if (!actions || !queries || !scratch || !active) goto failure;

    uint64_t na = 0, nr = 0, nu = 0, ni = 0, nf = 0;
    const ca_elem identity = {{0, 0, 1, 0}};
    for (size_t offset = 0; offset < count;) {
        size_t n = count - offset;
        if (n > block_size) n = block_size;
        for (size_t i = 0; i < n; i++) {
            uint64_t k = scalars[offset + i] % g->order;
            out[offset + i] = identity;
            active[i] = k && !pre->identity;
            if (!active[i]) continue;
            ca_i128 a, b;
            if (reduction_mode == 2 || reduction_mode == 3) {
                uint64_t hit = 0, corrected = 0;
                reduce_with_lattice_guard((tau_vec){pre->v1x, pre->v1y},
                                          (tau_vec){pre->v2x, pre->v2y}, pre->det, k, &a, &b, &hit,
                                          reduction_mode == 3, &corrected);
                if (guard_hits) *guard_hits += hit;
                if (quotient_corrections) *quotient_corrections += corrected;
            } else if (reduction_mode == 1)
                reduce_with_lattice_five((tau_vec){pre->v1x, pre->v1y},
                                         (tau_vec){pre->v2x, pre->v2y}, pre->det, k, &a, &b);
            else
                reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y},
                                    pre->det, k, &a, &b);
            ca_i128 x = a + b, y = -b;
            for (unsigned position = 0; position < pre->pairs; position++) {
                unsigned residues[2];
                for (unsigned digit = 0; digit < 2; digit++) {
                    unsigned rx = joint_window4_residue16(x), ry = joint_window4_residue16(y);
                    residues[digit] = (rx << 4) | ry;
                    x = (x - ca_joint_pair_digit_x[residues[digit]]) / 16;
                    y = (y - ca_joint_pair_digit_y[residues[digit]]) / 16;
                }
                actions[4 * i + position] = ca_joint_pair_action[(residues[0] << 8) | residues[1]];
            }
            unsigned top_orbit = actions[4 * i + pre->pairs - 1] & CA_JOINT_PAIR_ZERO;
            if (x || y ||
                (top_orbit != CA_JOINT_PAIR_ZERO &&
                 (top_orbit >= CA_JOINT_PAIR_ORBITS ||
                  pre->top_rank[top_orbit] == CA_JOINT_PAIR_TOP_MISSING))) {
                ca_group_mul(g, &out[offset + i], &pre->base_point, k, NULL);
                active[i] = 0;
                nf++;
            }
        }
        for (unsigned position = 0; position < pre->pairs; position++) {
            int any_query = 0, need_inverse = 0;
            for (size_t i = 0; i < n; i++) {
                ca_elem point = identity;
                if (active[i]) {
                    unsigned packed_action = actions[4 * i + position];
                    unsigned orbit = packed_action & CA_JOINT_PAIR_ZERO;
                    unsigned code = packed_action >> CA_JOINT_PAIR_ORBIT_BITS;
                    if (orbit != CA_JOINT_PAIR_ZERO) {
                        if (orbit >= CA_JOINT_PAIR_ORBITS || code >= 6) goto failure;
                        if (position + 1 == pre->pairs) orbit = pre->top_rank[orbit];
                        size_t index = (size_t)position * CA_JOINT_PAIR_ORBITS + orbit;
                        if (pre->point_words == 3) {
                            ca_joint_pair_triple_point stored = pre->triple_point[index];
                            point = (ca_elem){{stored.x, stored.y, 0, 0}};
                            if (code % 3 == 1) point.w[0] = stored.x_beta;
                            if (code % 3 == 2) {
                                point.w[0] = fs(g, 0, fa(g, stored.x, stored.x_beta));
                                nu += 2;
                            }
                        } else {
                            ca_joint_pair_double_point stored = pre->double_point[index];
                            point = (ca_elem){{stored.x, stored.y, 0, 0}};
                            if (code % 3 == 1) point.w[0] = fm(g, pre->beta, stored.x);
                            if (code % 3 == 2) point.w[0] = fm(g, pre->beta2, stored.x);
                            nr += code % 3 != 0;
                        }
                        if (code >= 3 && point.w[1]) point.w[1] = g->p - point.w[1];
                        na++;
                    }
                }
                queries[i] = point;
                if (!point.w[2]) {
                    any_query = 1;
                    need_inverse |= !out[offset + i].w[2];
                }
            }
            if (!any_query) continue;
            if (need_inverse) {
                ca_group_batch_op(g, out + offset, out + offset, queries, n, scratch);
                ni++;
            } else {
                for (size_t i = 0; i < n; i++)
                    if (out[offset + i].w[2]) out[offset + i] = queries[i];
            }
        }
        offset += n;
    }
    free(active);
    free(scratch);
    free(queries);
    free(actions);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (unit_adds) *unit_adds = nu;
    if (output_inversions) *output_inversions = ni;
    if (fallbacks) *fallbacks = nf;
    return 1;
failure:
    free(active);
    free(scratch);
    free(queries);
    free(actions);
    return 0;
}

int ca_ec_joint_pair_width_mul_wave_batch_profile(const ca_group *g,
                                                  const ca_joint_pair_precomp *pre, ca_elem *out,
                                                  const uint64_t *scalars, size_t count,
                                                  size_t block_size, uint64_t *adds,
                                                  uint64_t *rotations, uint64_t *unit_adds,
                                                  uint64_t *output_inversions, uint64_t *fallbacks)
{
    return joint_pair_width_mul_wave_impl(g, pre, out, scalars, count, block_size, adds, rotations,
                                          unit_adds, output_inversions, fallbacks, 0, NULL, NULL);
}

int ca_ec_joint_pair_width_five_mul_wave_batch_profile(
    const ca_group *g, const ca_joint_pair_precomp *pre, ca_elem *out, const uint64_t *scalars,
    size_t count, size_t block_size, uint64_t *adds, uint64_t *rotations, uint64_t *unit_adds,
    uint64_t *output_inversions, uint64_t *fallbacks)
{
    if (!joint_pair_five_supported(pre)) return 0;
    return joint_pair_width_mul_wave_impl(g, pre, out, scalars, count, block_size, adds, rotations,
                                          unit_adds, output_inversions, fallbacks, 1, NULL, NULL);
}

int ca_ec_joint_pair_width_guard_mul_wave_batch_profile(
    const ca_group *g, const ca_joint_pair_precomp *pre, ca_elem *out, const uint64_t *scalars,
    size_t count, size_t block_size, uint64_t *adds, uint64_t *rotations, uint64_t *unit_adds,
    uint64_t *output_inversions, uint64_t *fallbacks, uint64_t *guard_hits)
{
    if (!joint_pair_five_supported(pre)) return 0;
    return joint_pair_width_mul_wave_impl(g, pre, out, scalars, count, block_size, adds, rotations,
                                          unit_adds, output_inversions, fallbacks, 2, guard_hits,
                                          NULL);
}

int ca_ec_joint_pair_width_qcorr_mul_wave_batch_profile(
    const ca_group *g, const ca_joint_pair_precomp *pre, ca_elem *out, const uint64_t *scalars,
    size_t count, size_t block_size, uint64_t *adds, uint64_t *rotations, uint64_t *unit_adds,
    uint64_t *output_inversions, uint64_t *fallbacks, uint64_t *guard_hits,
    uint64_t *quotient_corrections)
{
    if (!joint_pair_five_supported(pre)) return 0;
    return joint_pair_width_mul_wave_impl(g, pre, out, scalars, count, block_size, adds, rotations,
                                          unit_adds, output_inversions, fallbacks, 3, guard_hits,
                                          quotient_corrections);
}

void ca_ec_joint_pair_clear(ca_joint_pair_precomp *pre)
{
    if (!pre) return;
    free(pre->plane_point);
    free(pre->triple_point);
    free(pre->double_point);
    *pre = (ca_joint_pair_precomp){0};
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
        da = (ca_i128)table[slot].a;
        db = (ca_i128)table[slot].b;
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
    return (size_t)phase * CA_TAU_DOUBLE_HALF + half;
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

int ca_ec_tau4_joint_prepare(const ca_group *g, const ca_elem *p, const ca_elem *q,
                              ca_tau4_joint_precomp *out, ca_tau4_joint_counts *counts)
{
    if (!g || !p || !q || !out || g->kind != CA_GROUP_EC || g->endo_kind != 1 ||
        g->a != 0 || g->p % 3 != 1 || g->order < 2 || g->order % 3 != 1 ||
        !g->endo_lambda || !ca_group_is_valid(g, p) || !ca_group_is_valid(g, q))
        return 0;
    ca_tau4_joint_precomp pre = {0};
    ca_tau4_joint_counts cost = {0};
    pre.g = g;
    pre.beta = g->endo_c_mont;
    pre.beta2 = fm(g, pre.beta, pre.beta);
    if (!make_tau4_table(pre.digit)) return 0;
    tau_vec v1, v2;
    if (!make_lattice(g->order, g->order - g->endo_lambda, &v1, &v2, &pre.det)) return 0;
    pre.v1x = v1.x;
    pre.v1y = v1.y;
    pre.v2x = v2.x;
    pre.v2y = v2.y;

    const ca_elem *base[2] = {p, q};
    tau_jac projective[18];
    uint64_t one_minus_beta = fs(g, g->mont.r1, pre.beta);
    int nonidentity = 0;
    for (int i = 0; i < 2; i++) {
        pre.identity[i] = !!base[i]->w[2];
        if (pre.identity[i]) {
            for (int j = 0; j < 9; j++)
                projective[9 * i + j] = (tau_jac){0, g->mont.r1, 0};
        } else {
            tau4_seed_jac(g, base[i], one_minus_beta, &projective[9 * i]);
            cost.tau_steps++;
            cost.doubles += 5;
            cost.mixed_adds += 4;
            nonidentity = 1;
        }
    }
    if (nonidentity) {
        ca_elem affine[18];
        jac_batch_to_affine(g, affine, projective, 18);
        for (int i = 0; i < 2; i++)
            for (int j = 0; j < 9; j++) pre.seed[i][j] = affine[9 * i + j];
        cost.inversions = 1;
    } else {
        for (int i = 0; i < 2; i++)
            for (int j = 0; j < 9; j++) pre.seed[i][j] = (ca_elem){{0, 0, 1, 0}};
    }
    *out = pre;
    if (counts) *counts = cost;
    return 1;
}

int ca_ec_tau4_joint_plane_prepare(const ca_group *g, const ca_elem *p, const ca_elem *q,
                                    ca_tau4_joint_plane_precomp *out,
                                    ca_tau4_joint_counts *counts)
{
    if (!out) return 0;
    ca_tau4_joint_plane_precomp plane = {0};
    ca_tau4_joint_counts cost = {0};
    if (!ca_ec_tau4_joint_prepare(g, p, q, &plane.base, &cost)) return 0;
    for (int point_index = 0; point_index < 2; point_index++) {
        for (int seed = 0; seed < 9; seed++) {
            ca_elem point = plane.base.seed[point_index][seed];
            if (point.w[2]) continue;
            plane.x_beta[point_index][seed] = fm(g, plane.base.beta, point.w[0]);
            plane.x_beta2[point_index][seed] = fm(g, plane.base.beta2, point.w[0]);
            cost.rotations += 2;
        }
    }
    *out = plane;
    if (counts) *counts = cost;
    return 1;
}

static int tau4_joint_recode(const ca_tau4_joint_precomp *pre, uint64_t scalar,
                              int point_index, uint8_t digits[256], size_t *length)
{
    scalar %= pre->g->order;
    if (!scalar || pre->identity[point_index]) { *length = 0; return 1; }
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->v1x, pre->v1y}, (tau_vec){pre->v2x, pre->v2y},
                        pre->det, scalar, &x, &y);
    *length = gen_tau4_digits(x, y, pre->digit, digits);
    return *length > 0;
}

static void tau4_joint_add_digit_gauge(const ca_group *g,
                                        const ca_tau4_joint_precomp *pre,
                                        tau_jac *acc, int point_index, uint8_t slot,
                                        unsigned gauge, ca_tau4_joint_counts *counts)
{
    ca_tau4_digit d = pre->digit[slot];
    ca_elem point = pre->seed[point_index][d.seed];
    unsigned power = ((unsigned)d.power + gauge) % 3;
    if (power == 1) point.w[0] = fm(g, pre->beta, point.w[0]);
    else if (power == 2) point.w[0] = fm(g, pre->beta2, point.w[0]);
    if (d.sign < 0 && point.w[1]) point.w[1] = g->p - point.w[1];
    *acc = jac_add_mixed(g, *acc, &point);
    counts->mixed_adds++;
    counts->rotations += power != 0;
}

static void tau4_joint_add_digit_plane(const ca_group *g,
                                        const ca_tau4_joint_plane_precomp *plane,
                                        tau_jac *acc, int point_index, uint8_t slot,
                                        ca_tau4_joint_counts *counts)
{
    const ca_tau4_joint_precomp *pre = &plane->base;
    ca_tau4_digit d = pre->digit[slot];
    ca_elem point = pre->seed[point_index][d.seed];
    if (d.power == 1) point.w[0] = plane->x_beta[point_index][d.seed];
    else if (d.power == 2) point.w[0] = plane->x_beta2[point_index][d.seed];
    if (d.sign < 0 && point.w[1]) point.w[1] = g->p - point.w[1];
    *acc = jac_add_mixed(g, *acc, &point);
    counts->mixed_adds++;
}

static void tau4_joint_add_digit(const ca_group *g, const ca_tau4_joint_precomp *pre,
                                   tau_jac *acc, int point_index, uint8_t slot,
                                   ca_tau4_joint_counts *counts)
{
    tau4_joint_add_digit_gauge(g, pre, acc, point_index, slot, 0, counts);
}

static tau_jac tau4_joint_eval_one(const ca_group *g, const ca_tau4_joint_precomp *pre,
                                    const uint8_t digits[256], size_t length, int point_index,
                                    uint64_t one_minus_beta, ca_tau4_joint_counts *counts)
{
    tau_jac acc = {0, g->mont.r1, 0};
    for (size_t i = length; i-- > 0;) {
        if (acc.z) { acc = jac_tau(g, acc, one_minus_beta); counts->tau_steps++; }
        if (digits[i] != 255) tau4_joint_add_digit(g, pre, &acc, point_index, digits[i], counts);
    }
    return acc;
}

int ca_ec_tau4_joint_mul_profile(const ca_group *g, const ca_tau4_joint_precomp *pre,
                                  ca_elem *out, uint64_t a, uint64_t b, int joint,
                                  ca_tau4_joint_counts *counts)
{
    if (!g || !pre || !out || pre->g != g || (joint != 0 && joint != 1)) return 0;
    ca_tau4_joint_counts cost = {0};
    uint8_t digits[2][256];
    size_t length[2];
    if (!tau4_joint_recode(pre, a, 0, digits[0], &length[0]) ||
        !tau4_joint_recode(pre, b, 1, digits[1], &length[1])) return 0;
    cost.recode_attempts = (a % g->order != 0 && !pre->identity[0]) +
                           (b % g->order != 0 && !pre->identity[1]);
    cost.lattice_points_checked = 25 * cost.recode_attempts;
    uint64_t one_minus_beta = fs(g, g->mont.r1, pre->beta);
    tau_jac acc;
    if (joint) {
        acc = (tau_jac){0, g->mont.r1, 0};
        size_t length_max = length[0] > length[1] ? length[0] : length[1];
        for (size_t i = length_max; i-- > 0;) {
            if (acc.z) { acc = jac_tau(g, acc, one_minus_beta); cost.tau_steps++; }
            if (i < length[0] && i < length[1] &&
                digits[0][i] != 255 && digits[1][i] != 255) cost.overlaps++;
            for (int point_index = 0; point_index < 2; point_index++)
                if (i < length[point_index] && digits[point_index][i] != 255)
                    tau4_joint_add_digit(g, pre, &acc, point_index,
                                         digits[point_index][i], &cost);
        }
    } else {
        tau_jac left = tau4_joint_eval_one(g, pre, digits[0], length[0], 0,
                                            one_minus_beta, &cost);
        tau_jac right = tau4_joint_eval_one(g, pre, digits[1], length[1], 1,
                                             one_minus_beta, &cost);
        cost.full_adds = left.z && right.z;
        acc = jac_add(g, left, right);
    }
    jac_to_affine(g, out, acc);
    cost.inversions = acc.z != 0;
    if (counts) *counts = cost;
    return 1;
}

typedef struct tau4_lattice_stream {
    uint8_t digits[256];
    size_t length;
    unsigned weight, rotations;
    unsigned power_histogram[3];
    ca_i128 l1;
} tau4_lattice_stream;

/* Exact neighboring representatives of one scalar coset. The 25-neighbor
 * enumeration order matches reduce_with_lattice_eisenstein. */
static size_t tau4_lattice_streams(const ca_tau4_joint_precomp *pre, uint64_t scalar,
                                   int point_index, tau4_lattice_stream streams[25],
                                   size_t *baseline_index,
                                   ca_tau4_joint_counts *counts, int mode)
{
    scalar %= pre->g->order;
    if (!scalar || pre->identity[point_index]) {
        streams[0] = (tau4_lattice_stream){0};
        *baseline_index = 0;
        return 1;
    }
    tau_vec v1 = {pre->v1x, pre->v1y}, v2 = {pre->v2x, pre->v2y};
    ca_i128 u0 = round_div((ca_i128)scalar * v2.y, pre->det);
    ca_i128 v0 = round_div(-(ca_i128)scalar * v1.y, pre->det);
    ca_i128 best_l1 = -1;
    size_t n = 0;
    static const int axial[5][2] = {{-1, 0}, {0, -1}, {0, 0}, {0, 1}, {1, 0}};
    unsigned two[2] = {0, 1};
    if (mode == 2 || mode == 3) {
        ca_i128 smallest = -1, second = -1;
        for (unsigned i = 0; i < 5; i++) {
            ca_i128 u = u0 + axial[i][0], v = v0 + axial[i][1];
            ca_i128 x = (ca_i128)scalar - u * v1.x - v * v2.x;
            ca_i128 y = -u * v1.y - v * v2.y;
            ca_i128 l1 = iabs128(x) + iabs128(y);
            if (smallest < 0 || l1 < smallest) {
                second = smallest;
                two[1] = two[0];
                smallest = l1;
                two[0] = i;
            } else if (second < 0 || l1 < second) {
                second = l1;
                two[1] = i;
            }
        }
    }
    size_t candidates = mode == 25 ? 25 : mode == 5 ? 5 : 2;
    counts->lattice_points_checked += mode == 25 ? 25 : 5;
    for (size_t index = 0; index < candidates; index++) {
        unsigned axial_index = (mode == 2 || mode == 3) ? two[index] : (unsigned)index;
        int du = mode == 25 ? (int)(index / 5) - 2 : axial[axial_index][0];
        int dv = mode == 25 ? (int)(index % 5) - 2 : axial[axial_index][1];
        ca_i128 u = u0 + du, v = v0 + dv;
        ca_i128 x = (ca_i128)scalar - u * v1.x - v * v2.x;
        ca_i128 y = -u * v1.y - v * v2.y;
        tau4_lattice_stream *stream = &streams[n];
        stream->l1 = iabs128(x) + iabs128(y);
        stream->length = gen_tau4_digits_atlas(x + y, -y, pre->digit, stream->digits);
        counts->recode_attempts++;
        if (!stream->length) return 0;
        stream->weight = stream->rotations = 0;
        memset(stream->power_histogram, 0, sizeof(stream->power_histogram));
        for (size_t i = 0; i < stream->length; i++) {
            if (stream->digits[i] == 255) continue;
            stream->weight++;
            unsigned power = (unsigned)pre->digit[stream->digits[i]].power;
            stream->power_histogram[power]++;
            stream->rotations += power != 0;
        }
        if (best_l1 < 0 || stream->l1 < best_l1) {
            best_l1 = stream->l1;
            *baseline_index = n;
        }
        n++;
    }
    return n;
}

static int tau4_pair_score_better(unsigned score, unsigned steps, unsigned adds,
                                  unsigned rotations, ca_i128 l1,
                                  unsigned best_score, unsigned best_steps,
                                  unsigned best_adds, unsigned best_rotations,
                                  ca_i128 best_l1)
{
    if (score != best_score) return score < best_score;
    if (steps != best_steps) return steps < best_steps;
    if (adds != best_adds) return adds < best_adds;
    if (rotations != best_rotations) return rotations < best_rotations;
    return best_l1 < 0 || l1 < best_l1;
}

static unsigned tau4_pair_gauge_rotations(const tau4_lattice_stream *left,
                                          const tau4_lattice_stream *right,
                                          unsigned *chosen_gauge)
{
    unsigned weight = left->weight + right->weight;
    unsigned best = weight - left->power_histogram[0] - right->power_histogram[0];
    *chosen_gauge = 0;
    for (unsigned gauge = 1; gauge < 3; gauge++) {
        unsigned zero_power = 3 - gauge;
        unsigned rotations = weight - left->power_histogram[zero_power] -
                             right->power_histogram[zero_power] + 1;
        if (rotations < best) {
            best = rotations;
            *chosen_gauge = gauge;
        }
    }
    return best;
}

static int tau4_paired_lattice_mul_impl(const ca_group *g,
                                        const ca_tau4_joint_precomp *pre,
                                        const ca_tau4_joint_plane_precomp *plane,
                                        ca_elem *out, tau_jac *jac_out,
                                        uint64_t a, uint64_t b,
                                        ca_tau4_joint_counts *counts, int mode)
{
    if (!g || !pre || (!out && !jac_out) || pre->g != g ||
        (plane && &plane->base != pre)) return 0;
    tau4_lattice_stream streams[2][25];
    size_t baseline[2] = {0, 0};
    ca_tau4_joint_counts cost = {0};
    size_t count_a = tau4_lattice_streams(pre, a, 0, streams[0], &baseline[0], &cost, mode);
    size_t count_b = tau4_lattice_streams(pre, b, 1, streams[1], &baseline[1], &cost, mode);
    if (!count_a || !count_b) return 0;
    unsigned best_score = UINT_MAX, best_steps = UINT_MAX, best_adds = UINT_MAX;
    unsigned best_rotations = UINT_MAX;
    ca_i128 best_l1 = -1;
    size_t chosen_a = 0, chosen_b = 0;
    unsigned chosen_gauge = 0;
    for (size_t ia = 0; ia < count_a; ia++) {
        const tau4_lattice_stream *left = &streams[0][ia];
        for (size_t ib = 0; ib < count_b; ib++) {
            const tau4_lattice_stream *right = &streams[1][ib];
            size_t length_max = left->length > right->length ? left->length : right->length;
            unsigned steps = length_max ? (unsigned)(length_max - 1) : 0;
            unsigned adds = left->weight + right->weight;
            unsigned gauge = 0;
            unsigned rotations = mode == 3
                ? tau4_pair_gauge_rotations(left, right, &gauge)
                : left->rotations + right->rotations;
            unsigned score = 6 * steps + 11 * adds + rotations;
            ca_i128 l1 = left->l1 + right->l1;
            cost.pair_scores++;
            if (tau4_pair_score_better(score, steps, adds, rotations, l1,
                                       best_score, best_steps, best_adds,
                                       best_rotations, best_l1)) {
                best_score = score;
                best_steps = steps;
                best_adds = adds;
                best_rotations = rotations;
                best_l1 = l1;
                chosen_a = ia;
                chosen_b = ib;
                chosen_gauge = gauge;
            }
        }
    }
    cost.selected_changed = chosen_a != baseline[0] || chosen_b != baseline[1];
    cost.gauge_selected = chosen_gauge != 0;
    const tau4_lattice_stream *selected[2] = {&streams[0][chosen_a], &streams[1][chosen_b]};
    uint64_t one_minus_beta = fs(g, g->mont.r1, pre->beta);
    tau_jac acc = {0, g->mont.r1, 0};
    size_t length_max = selected[0]->length > selected[1]->length
        ? selected[0]->length : selected[1]->length;
    for (size_t i = length_max; i-- > 0;) {
        if (acc.z) { acc = jac_tau(g, acc, one_minus_beta); cost.tau_steps++; }
        int has_a = i < selected[0]->length && selected[0]->digits[i] != 255;
        int has_b = i < selected[1]->length && selected[1]->digits[i] != 255;
        cost.overlaps += has_a && has_b;
        if (has_a) {
            if (plane) tau4_joint_add_digit_plane(g, plane, &acc, 0,
                                                   selected[0]->digits[i], &cost);
            else tau4_joint_add_digit_gauge(g, pre, &acc, 0,
                                            selected[0]->digits[i], chosen_gauge, &cost);
        }
        if (has_b) {
            if (plane) tau4_joint_add_digit_plane(g, plane, &acc, 1,
                                                   selected[1]->digits[i], &cost);
            else tau4_joint_add_digit_gauge(g, pre, &acc, 1,
                                            selected[1]->digits[i], chosen_gauge, &cost);
        }
    }
    if (chosen_gauge && acc.z) {
        acc.x = fm(g, chosen_gauge == 1 ? pre->beta2 : pre->beta, acc.x);
        cost.rotations++;
    }
    if (jac_out) *jac_out = acc;
    if (out) {
        jac_to_affine(g, out, acc);
        cost.inversions = acc.z != 0;
    }
    if (counts) *counts = cost;
    return 1;
}

int ca_ec_tau4_paired_lattice_mul_profile(const ca_group *g,
                                           const ca_tau4_joint_precomp *pre,
                                           ca_elem *out, uint64_t a, uint64_t b,
                                           ca_tau4_joint_counts *counts)
{
    return tau4_paired_lattice_mul_impl(g, pre, NULL, out, NULL, a, b, counts, 25);
}

int ca_ec_tau4_paired_five_mul_profile(const ca_group *g,
                                        const ca_tau4_joint_precomp *pre,
                                        ca_elem *out, uint64_t a, uint64_t b,
                                        ca_tau4_joint_counts *counts)
{
    return tau4_paired_lattice_mul_impl(g, pre, NULL, out, NULL, a, b, counts, 5);
}

int ca_ec_tau4_paired_two_mul_profile(const ca_group *g,
                                       const ca_tau4_joint_precomp *pre,
                                       ca_elem *out, uint64_t a, uint64_t b,
                                       ca_tau4_joint_counts *counts)
{
    return tau4_paired_lattice_mul_impl(g, pre, NULL, out, NULL, a, b, counts, 2);
}

int ca_ec_tau4_paired_two_gauge_mul_profile(const ca_group *g,
                                             const ca_tau4_joint_precomp *pre,
                                             ca_elem *out, uint64_t a, uint64_t b,
                                             ca_tau4_joint_counts *counts)
{
    return tau4_paired_lattice_mul_impl(g, pre, NULL, out, NULL, a, b, counts, 3);
}

int ca_ec_tau4_paired_two_plane_mul_profile(const ca_group *g,
                                             const ca_tau4_joint_plane_precomp *pre,
                                             ca_elem *out, uint64_t a, uint64_t b,
                                             ca_tau4_joint_counts *counts)
{
    if (!pre) return 0;
    return tau4_paired_lattice_mul_impl(g, &pre->base, pre, out, NULL,
                                        a, b, counts, 2);
}

static int tau4_paired_two_batch_impl(const ca_group *g,
                                       const ca_tau4_joint_precomp *pre,
                                       const ca_tau4_joint_plane_precomp *plane,
                                       ca_elem *out, const uint64_t *a,
                                       const uint64_t *b, size_t count,
                                       ca_tau4_joint_counts *counts)
{
    if (!g || !pre || !out || !a || !b || pre->g != g || count > 32 ||
        (plane && &plane->base != pre)) return 0;
    ca_tau4_joint_counts total = {0};
    if (!count) { if (counts) *counts = total; return 1; }
    tau_jac projective[32];
    uint64_t prefixes[32];
    for (size_t i = 0; i < count; i++) {
        ca_tau4_joint_counts one = {0};
        if (!tau4_paired_lattice_mul_impl(g, pre, plane, NULL, &projective[i],
                                           a[i], b[i], &one, 2)) return 0;
        total.tau_steps += one.tau_steps;
        total.mixed_adds += one.mixed_adds;
        total.rotations += one.rotations;
        total.overlaps += one.overlaps;
        total.recode_attempts += one.recode_attempts;
        total.pair_scores += one.pair_scores;
        total.selected_changed += one.selected_changed;
        total.lattice_points_checked += one.lattice_points_checked;
    }
    if (!jac_batch_to_affine_scratch(g, out, projective, count,
                                     prefixes, &total.inversions)) return 0;
    if (counts) *counts = total;
    return 1;
}

int ca_ec_tau4_paired_two_batch_profile(const ca_group *g,
                                          const ca_tau4_joint_precomp *pre,
                                          ca_elem *out, const uint64_t *a,
                                          const uint64_t *b, size_t count,
                                          ca_tau4_joint_counts *counts)
{
    return tau4_paired_two_batch_impl(g, pre, NULL, out, a, b, count, counts);
}

int ca_ec_tau4_paired_two_plane_batch_profile(const ca_group *g,
                                               const ca_tau4_joint_plane_precomp *pre,
                                               ca_elem *out, const uint64_t *a,
                                               const uint64_t *b, size_t count,
                                               ca_tau4_joint_counts *counts)
{
    if (!pre) return 0;
    return tau4_paired_two_batch_impl(g, &pre->base, pre, out, a, b, count, counts);
}

/* Unit action is a power of (x,y)->(beta*x,y), followed by sign on y.
 * It commutes with the group law on the j=0 curve. */
static ca_elem tau4_apply_unit(const ca_group *g, const ca_tau4_joint_precomp *pre,
                               ca_elem point, int power, int sign)
{
    if (point.w[2]) return point;
    if (power == 1) point.w[0] = fm(g, pre->beta, point.w[0]);
    else if (power == 2) point.w[0] = fm(g, pre->beta2, point.w[0]);
    if (sign < 0 && point.w[1]) point.w[1] = g->p - point.w[1];
    return point;
}

int ca_ec_tau4_orbit_prepare(const ca_group *g, const ca_elem *p, const ca_elem *q,
                              ca_tau4_orbit_precomp *out, ca_tau4_joint_counts *counts)
{
    if (!out) return 0;
    ca_tau4_joint_counts cost = {0};
    if (!ca_ec_tau4_joint_prepare(g, p, q, &out->base, &cost)) return 0;
    tau_jac projective[486];
    uint64_t prefixes[486];
    size_t index = 0;
    for (int s = 0; s < 9; s++) {
        const ca_elem *left = &out->base.seed[0][s];
        for (int t = 0; t < 9; t++) {
            for (int relative = 0; relative < 6; relative++) {
                ca_elem right = tau4_apply_unit(g, &out->base,
                    out->base.seed[1][t], relative / 2,
                    (relative & 1) ? -1 : 1);
                if (!right.w[2] && relative / 2) cost.rotations++;
                if (left->w[2]) {
                    projective[index++] = right.w[2]
                        ? (tau_jac){0, g->mont.r1, 0}
                        : (tau_jac){right.w[0], right.w[1], g->mont.r1};
                } else if (right.w[2]) {
                    projective[index++] = (tau_jac){left->w[0], left->w[1], g->mont.r1};
                } else {
                    projective[index++] = jac_add_mixed(g,
                        (tau_jac){left->w[0], left->w[1], g->mont.r1}, &right);
                    cost.mixed_adds++;
                }
            }
        }
    }
    uint64_t inversion = 0;
    if (!jac_batch_to_affine_scratch(g, &out->pair[0][0][0], projective, 486,
                                     prefixes, &inversion)) return 0;
    cost.inversions += inversion;
    if (counts) *counts = cost;
    return 1;
}

int ca_ec_tau4_orbit_mul_profile(const ca_group *g, const ca_tau4_orbit_precomp *pre,
                                  ca_elem *out, uint64_t a, uint64_t b,
                                  ca_tau4_joint_counts *counts)
{
    if (!g || !pre || !out || pre->base.g != g) return 0;
    const ca_tau4_joint_precomp *base = &pre->base;
    ca_tau4_joint_counts cost = {0};
    uint8_t digits[2][256];
    size_t length[2];
    if (!tau4_joint_recode(base, a, 0, digits[0], &length[0]) ||
        !tau4_joint_recode(base, b, 1, digits[1], &length[1])) return 0;
    uint64_t one_minus_beta = fs(g, g->mont.r1, base->beta);
    tau_jac acc = {0, g->mont.r1, 0};
    size_t length_max = length[0] > length[1] ? length[0] : length[1];
    for (size_t i = length_max; i-- > 0;) {
        if (acc.z) { acc = jac_tau(g, acc, one_minus_beta); cost.tau_steps++; }
        int has_a = i < length[0] && digits[0][i] != 255;
        int has_b = i < length[1] && digits[1][i] != 255;
        if (has_a && has_b) {
            ca_tau4_digit da = base->digit[digits[0][i]];
            ca_tau4_digit db = base->digit[digits[1][i]];
            int relative_power = (db.power + 3 - da.power) % 3;
            int relative = 2 * relative_power + (da.sign != db.sign);
            ca_elem point = pre->pair[(int)da.seed][(int)db.seed][relative];
            cost.overlaps++;
            cost.fused_hits++;
            if (!point.w[2]) {
                point = tau4_apply_unit(g, base, point, da.power, da.sign);
                acc = jac_add_mixed(g, acc, &point);
                cost.mixed_adds++;
                cost.rotations += da.power != 0;
            }
        } else if (has_a) {
            tau4_joint_add_digit(g, base, &acc, 0, digits[0][i], &cost);
        } else if (has_b) {
            tau4_joint_add_digit(g, base, &acc, 1, digits[1][i], &cost);
        }
    }
    jac_to_affine(g, out, acc);
    cost.inversions = acc.z != 0;
    if (counts) *counts = cost;
    return 1;
}

int ca_ec_tau4_pair_histogram(const ca_tau4_joint_precomp *pre, uint64_t a, uint64_t b,
                               uint64_t histogram[486])
{
    if (!pre || !pre->g || !histogram) return 0;
    uint8_t digits[2][256];
    size_t length[2];
    if (!tau4_joint_recode(pre, a, 0, digits[0], &length[0]) ||
        !tau4_joint_recode(pre, b, 1, digits[1], &length[1])) return 0;
    size_t length_min = length[0] < length[1] ? length[0] : length[1];
    for (size_t i = 0; i < length_min; i++) {
        if (digits[0][i] == 255 || digits[1][i] == 255) continue;
        ca_tau4_digit da = pre->digit[digits[0][i]];
        ca_tau4_digit db = pre->digit[digits[1][i]];
        int relative = 2 * ((db.power + 3 - da.power) % 3) + (da.sign != db.sign);
        size_t slot = (size_t)(((int)da.seed * 9 + (int)db.seed) * 6 + relative);
        histogram[slot]++;
    }
    return 1;
}

int ca_ec_tau4_hot_prepare(const ca_group *g, const ca_elem *p, const ca_elem *q,
                            const uint16_t selected[64], ca_tau4_hot_precomp *out,
                            ca_tau4_joint_counts *counts)
{
    if (!out || !selected) return 0;
    ca_tau4_hot_precomp pre = {0};
    ca_tau4_joint_counts cost = {0};
    if (!ca_ec_tau4_joint_prepare(g, p, q, &pre.base, &cost)) return 0;
    for (size_t i = 0; i < 486; i++) pre.slot_to_hot[i] = UINT16_MAX;
    tau_jac projective[64];
    uint64_t prefixes[64];
    for (uint16_t i = 0; i < 64; i++) {
        unsigned slot = selected[i];
        if (slot >= 486 || pre.slot_to_hot[slot] != UINT16_MAX) return 0;
        pre.slot_to_hot[slot] = i;
        unsigned s = slot / 54, t = (slot / 6) % 9, relative = slot % 6;
        const ca_elem *left = &pre.base.seed[0][s];
        ca_elem right = tau4_apply_unit(g, &pre.base, pre.base.seed[1][t],
                                        (int)(relative / 2), (relative & 1) ? -1 : 1);
        if (!right.w[2] && relative / 2) cost.rotations++;
        if (left->w[2]) {
            projective[i] = right.w[2]
                ? (tau_jac){0, g->mont.r1, 0}
                : (tau_jac){right.w[0], right.w[1], g->mont.r1};
        } else if (right.w[2]) {
            projective[i] = (tau_jac){left->w[0], left->w[1], g->mont.r1};
        } else {
            projective[i] = jac_add_mixed(g,
                (tau_jac){left->w[0], left->w[1], g->mont.r1}, &right);
            cost.mixed_adds++;
        }
    }
    uint64_t inversion = 0;
    if (!jac_batch_to_affine_scratch(g, pre.point, projective, 64,
                                     prefixes, &inversion)) return 0;
    cost.inversions += inversion;
    *out = pre;
    if (counts) *counts = cost;
    return 1;
}

int ca_ec_tau4_hot_mul_profile(const ca_group *g, const ca_tau4_hot_precomp *pre,
                                ca_elem *out, uint64_t a, uint64_t b,
                                ca_tau4_joint_counts *counts)
{
    if (!g || !pre || !out || pre->base.g != g) return 0;
    const ca_tau4_joint_precomp *base = &pre->base;
    ca_tau4_joint_counts cost = {0};
    uint8_t digits[2][256];
    size_t length[2];
    if (!tau4_joint_recode(base, a, 0, digits[0], &length[0]) ||
        !tau4_joint_recode(base, b, 1, digits[1], &length[1])) return 0;
    uint64_t one_minus_beta = fs(g, g->mont.r1, base->beta);
    tau_jac acc = {0, g->mont.r1, 0};
    size_t length_max = length[0] > length[1] ? length[0] : length[1];
    for (size_t i = length_max; i-- > 0;) {
        if (acc.z) { acc = jac_tau(g, acc, one_minus_beta); cost.tau_steps++; }
        int has_a = i < length[0] && digits[0][i] != 255;
        int has_b = i < length[1] && digits[1][i] != 255;
        if (has_a && has_b) {
            ca_tau4_digit da = base->digit[digits[0][i]];
            ca_tau4_digit db = base->digit[digits[1][i]];
            int relative = 2 * ((db.power + 3 - da.power) % 3) + (da.sign != db.sign);
            unsigned slot = (unsigned)(((int)da.seed * 9 + (int)db.seed) * 6 + relative);
            cost.overlaps++;
            uint16_t hot = pre->slot_to_hot[slot];
            if (hot == UINT16_MAX) {
                tau4_joint_add_digit(g, base, &acc, 0, digits[0][i], &cost);
                tau4_joint_add_digit(g, base, &acc, 1, digits[1][i], &cost);
            } else {
                cost.fused_hits++;
                ca_elem point = pre->point[hot];
                if (!point.w[2]) {
                    point = tau4_apply_unit(g, base, point, da.power, da.sign);
                    acc = jac_add_mixed(g, acc, &point);
                    cost.mixed_adds++;
                    cost.rotations += da.power != 0;
                }
            }
        } else if (has_a) {
            tau4_joint_add_digit(g, base, &acc, 0, digits[0][i], &cost);
        } else if (has_b) {
            tau4_joint_add_digit(g, base, &acc, 1, digits[1][i], &cost);
        }
    }
    jac_to_affine(g, out, acc);
    cost.inversions = acc.z != 0;
    if (counts) *counts = cost;
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

size_t ca_ec_tau4_pos_compact_layers(const ca_group *g)
{
    if (!g || g->order < 2) return 0;
    unsigned bits = 0;
    for (uint64_t n = g->order - 1; n; n >>= 1) bits++;
    size_t layers = (bits + 2) / 3 + 2;
    return layers < CA_TAU_POS_Q ? layers : CA_TAU_POS_Q;
}

int ca_ec_tau4_pos_compact_prepare(const ca_group *g, const ca_elem *point,
                                   ca_tau4_pos_compact_precomp *out, uint64_t *triples,
                                   uint64_t *inversions)
{
    if (!g || !point || !out) return 0;
    if (triples) *triples = 0;
    if (inversions) *inversions = 0;
    ca_tau4_pos_compact_precomp pre = {0};
    if (!ca_ec_tau4_prepare(g, point, &pre.base, NULL)) return 0;
    pre.base_point = *point;
    pre.layers = ca_ec_tau4_pos_compact_layers(g);
    if (!pre.layers) return 0;
    if (pre.base.identity) {
        *out = pre;
        return 1;
    }
    size_t count = pre.layers * 18;
    pre.point = malloc(count * sizeof(*pre.point));
    tau_jac *projective = malloc(count * sizeof(*projective));
    uint64_t *prefixes = malloc(count * sizeof(*prefixes));
    if (!pre.point || !projective || !prefixes) {
        free(prefixes);
        free(projective);
        free(pre.point);
        return 0;
    }
    for (size_t parity = 0; parity < 2; parity++)
        for (size_t j = 0; j < 9; j++) {
            const ca_elem *seed = parity ? &pre.base.tau_seed[j] : &pre.base.seed[j];
            projective[parity * 9 + j] =
                seed->w[2] ? (tau_jac){0, g->mont.r1, 0}
                           : (tau_jac){seed->w[0], seed->w[1], g->mont.r1};
        }
    uint64_t n3 = 0;
    for (size_t q = 1; q < pre.layers; q++)
        for (size_t slot = 0; slot < 18; slot++) {
            tau_jac prior = projective[(q - 1) * 18 + slot];
            if (prior.z) {
                projective[q * 18 + slot] = jac_triple(g, prior);
                n3++;
            } else {
                projective[q * 18 + slot] = (tau_jac){0, g->mont.r1, 0};
            }
        }
    int ok = jac_batch_to_affine_scratch(g, pre.point, projective, count, prefixes, inversions);
    free(prefixes);
    free(projective);
    if (!ok) {
        free(pre.point);
        return 0;
    }
    if (triples) *triples = n3;
    *out = pre;
    return 1;
}

int ca_ec_tau4_pos_compact_mul_profile(const ca_group *g,
                                       const ca_tau4_pos_compact_precomp *pre,
                                       ca_elem *out, uint64_t k, uint64_t *adds,
                                       uint64_t *rotations, uint64_t *fallbacks)
{
    if (!g || !pre || !out || pre->base.g != g || !pre->layers) return 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (fallbacks) *fallbacks = 0;
    if (pre->base.identity || k % g->order == 0) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    k %= g->order;
    ca_i128 x, y;
    reduce_with_lattice((tau_vec){pre->base.v1x, pre->base.v1y},
                        (tau_vec){pre->base.v2x, pre->base.v2y}, pre->base.det, k, &x, &y);
    uint8_t digits[256];
    size_t nd = gen_tau4_digits_fast(x, y, pre->base.digit, digits);
    if (!nd || (nd - 1) / 2 >= pre->layers) {
        if (fallbacks) *fallbacks = 1;
        ca_group_mul(g, out, &pre->base_point, k, NULL);
        return 1;
    }
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t na = 0, nr = 0;
    for (size_t i = nd; i-- > 0;) {
        int slot = digits[i];
        if (slot == 255) continue;
        size_t q = i / 2;
        ca_tau4_digit d = pre->base.digit[slot];
        ca_elem seed = pre->point[q * 18 + (i & 1u) * 9 + (size_t)d.seed];
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
    jac_to_affine(g, out, acc);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    return 1;
}

void ca_ec_tau4_pos_compact_clear(ca_tau4_pos_compact_precomp *pre)
{
    if (!pre) return;
    free(pre->point);
    *pre = (ca_tau4_pos_compact_precomp){0};
}

/* Width-three tau digits have three six-unit seed orbits. Tau^3 has the
 * coordinate ideal (9,3), so a 27-byte residue table replaces a search. */
static ca_i128 tau3_residue(ca_i128 value, unsigned modulus)
{
    ca_i128 r = value % modulus;
    return r < 0 ? r + modulus : r;
}

static tau_vec tau3_mul_tau(tau_vec v) { return (tau_vec){-3 * v.y, v.x + 3 * v.y}; }

static tau_vec tau3_apply_unit_coeff(tau_vec v, unsigned code)
{
    for (unsigned i = 0; i < code % 3; i++) v = (tau_vec){v.x + 3 * v.y, -v.x - 2 * v.y};
    if (code >= 3) v.x = -v.x, v.y = -v.y;
    return v;
}

static tau_vec tau3_pattern_coeff(unsigned pattern)
{
    if (!pattern) return (tau_vec){0, 0};
    unsigned position = (pattern - 1) / 18;
    unsigned digit = (pattern - 1) % 18 + 1;
    tau_vec v = {ca_tau3_digit_a[digit], ca_tau3_digit_b[digit]};
    for (unsigned i = 0; i < position; i++) v = tau3_mul_tau(v);
    return v;
}

static tau_vec tau3_pair_coeff(unsigned u, unsigned v)
{
    tau_vec a = tau3_pattern_coeff(u), b = tau3_pattern_coeff(v);
    for (unsigned i = 0; i < 3; i++) b = tau3_mul_tau(b);
    return (tau_vec){a.x + b.x, a.y + b.y};
}

static uint64_t tau3_coeff_scalar(const ca_group *g, tau_vec v)
{
    ca_i128 lambda_tau = 1 + (ca_i128)g->endo_lambda;
    ca_i128 scalar = (v.x + v.y * lambda_tau) % (ca_i128)g->order;
    if (scalar < 0) scalar += g->order;
    return (uint64_t)scalar;
}

size_t ca_ec_tau3_fused_blocks(const ca_group *g)
{
    if (!g || g->order < 2) return 0;
    size_t blocks = 1;
    for (uint64_t n = g->order - 1; n; n /= 729) blocks++;
    return blocks <= 16 ? blocks : 0;
}

size_t ca_ec_tau3_fused_static_bytes(void)
{
    return sizeof(ca_tau3_digit_a) + sizeof(ca_tau3_digit_b) + sizeof(ca_tau3_residue) +
           sizeof(ca_tau3_orbit_id) + sizeof(ca_tau3_orbit_unit) + sizeof(ca_tau3_rep_u) +
           sizeof(ca_tau3_rep_v);
}

size_t ca_ec_tau3_atlas_static_bytes(void)
{
    return ca_ec_tau3_fused_static_bytes() + sizeof(ca_tau3_atlas);
}

int ca_ec_tau3_fused_verify_map(void)
{
    for (unsigned a = 0; a < 9; a++)
        for (unsigned b = 0; b < 3; b++) {
            unsigned digit = ca_tau3_residue[3 * a + b];
            if (a % 3 == 0) {
                if (digit) return 0;
            } else if (!digit || digit > 18 ||
                       (unsigned)tau3_residue(ca_tau3_digit_a[digit], 9) != a ||
                       (unsigned)tau3_residue(ca_tau3_digit_b[digit], 3) != b) {
                return 0;
            }
        }
    for (unsigned u = 0; u < 55; u++)
        for (unsigned v = 0; v < 55; v++) {
            size_t index = 55 * u + v;
            int valid = !u || !v || (v - 1) / 18 >= (u - 1) / 18;
            unsigned id = ca_tau3_orbit_id[index], code = ca_tau3_orbit_unit[index];
            if (!valid) {
                if (id != UINT16_MAX || code != UINT8_MAX) return 0;
                continue;
            }
            if (id >= CA_TAU3_FUSED_ORBITS || code >= 6) return 0;
            tau_vec expected = tau3_pair_coeff(u, v);
            tau_vec actual =
                tau3_apply_unit_coeff(tau3_pair_coeff(ca_tau3_rep_u[id], ca_tau3_rep_v[id]), code);
            if (actual.x != expected.x || actual.y != expected.y) return 0;
        }
    return 1;
}

static size_t tau3_recode(ca_i128 a, ca_i128 b, uint8_t digits[128])
{
    size_t count = 0;
    while (a || b) {
        if (count == 128) return 0;
        unsigned key = 3 * (unsigned)tau3_residue(a, 9) + (unsigned)tau3_residue(b, 3);
        unsigned digit = ca_tau3_residue[key];
        if (a % 3 && !digit) return 0;
        if (digit) a -= ca_tau3_digit_a[digit], b -= ca_tau3_digit_b[digit];
        if (a % 3) return 0;
        digits[count++] = (uint8_t)digit;
        ca_i128 old_a = a;
        a += b;
        b = -old_a / 3;
    }
    for (size_t i = 0; i < count; i++)
        if (digits[i] && ((i + 1 < count && digits[i + 1]) || (i + 2 < count && digits[i + 2])))
            return 0;
    return count;
}

static unsigned tau3_block_pattern(const uint8_t digits[128], size_t count, size_t start)
{
    unsigned pattern = 0;
    for (unsigned position = 0; position < 3; position++) {
        size_t index = start + position;
        unsigned digit = index < count ? digits[index] : 0;
        if (!digit) continue;
        if (pattern || digit > 18) return UINT_MAX;
        pattern = 18 * position + digit;
    }
    return pattern;
}

int ca_ec_tau3_atlas_verify_map(void)
{
    if (sizeof(ca_tau3_atlas_entry) != 4 ||
        sizeof(ca_tau3_atlas) != 6561 * sizeof(ca_tau3_atlas_entry))
        return 0;
    for (unsigned a = 0; a < 81; a++)
        for (unsigned b = 0; b < 81; b++) {
            uint8_t digits[128];
            size_t count = tau3_recode(a, b, digits);
            if (!count && (a || b)) return 0;
            tau_vec correction = {0, 0};
            for (size_t i = 6; i-- > 0;) {
                correction = tau3_mul_tau(correction);
                unsigned digit = i < count ? digits[i] : 0;
                if (digit) {
                    correction.x += ca_tau3_digit_a[digit];
                    correction.y += ca_tau3_digit_b[digit];
                }
            }
            const ca_tau3_atlas_entry *entry = &ca_tau3_atlas[81 * a + b];
            if (correction.x != entry->a || correction.y != entry->b ||
                ((ca_i128)a - entry->a) % 27 || ((ca_i128)b - entry->b) % 27)
                return 0;
            unsigned u = tau3_block_pattern(digits, count, 0);
            unsigned v = tau3_block_pattern(digits, count, 3);
            if (u >= 55 || v >= 55) return 0;
            size_t index = 55 * u + v;
            if (ca_tau3_orbit_id[index] >= CA_TAU3_FUSED_ORBITS ||
                entry->action != ((ca_tau3_orbit_id[index] << 3) | ca_tau3_orbit_unit[index]))
                return 0;
        }
    return 1;
}

int ca_ec_tau3_fused_recode_actions(const ca_tau3_fused_precomp *pre, uint64_t k,
                                    uint16_t actions[16], size_t *count)
{
    if (!pre || !pre->base.g || !actions || !count || !pre->blocks) return 0;
    const ca_group *g = pre->base.g;
    k %= g->order;
    *count = 0;
    if (!k) return 1;
    ca_i128 a, b;
    reduce_with_lattice((tau_vec){pre->base.v1x, pre->base.v1y},
                        (tau_vec){pre->base.v2x, pre->base.v2y}, pre->base.det, k, &a, &b);
    uint8_t digits[128];
    size_t nd = tau3_recode(a, b, digits);
    if (!nd) return 0;
    size_t blocks = (nd + 5) / 6;
    if (blocks > pre->blocks || blocks > 16) return 0;
    for (size_t block = 0; block < blocks; block++) {
        unsigned u = tau3_block_pattern(digits, nd, 6 * block);
        unsigned v = tau3_block_pattern(digits, nd, 6 * block + 3);
        if (u >= 55 || v >= 55) return 0;
        size_t index = 55 * u + v;
        unsigned id = ca_tau3_orbit_id[index], code = ca_tau3_orbit_unit[index];
        if (id >= CA_TAU3_FUSED_ORBITS || code >= 6) return 0;
        actions[block] = (uint16_t)((id << 3) | code);
    }
    *count = blocks;
    return 1;
}

static int tau3_atlas_recode_base(const ca_tau4_precomp *base, size_t blocks, uint64_t k,
                                  uint16_t actions[16], size_t *count)
{
    if (!base || !base->g || !actions || !count || !blocks) return 0;
    const ca_group *g = base->g;
    k %= g->order;
    *count = 0;
    if (!k) return 1;
    ca_i128 a, b;
    reduce_with_lattice((tau_vec){base->v1x, base->v1y}, (tau_vec){base->v2x, base->v2y}, base->det,
                        k, &a, &b);
    while (a || b) {
        if (*count >= blocks || *count >= 16) return 0;
        const ca_tau3_atlas_entry *entry =
            &ca_tau3_atlas[81 * (unsigned)tau3_residue(a, 81) + (unsigned)tau3_residue(b, 81)];
        unsigned id = entry->action >> 3, code = entry->action & 7;
        if (id >= CA_TAU3_FUSED_ORBITS || code >= 6 || (a - entry->a) % 27 || (b - entry->b) % 27)
            return 0;
        actions[(*count)++] = entry->action;
        a = (entry->a - a) / 27;
        b = (entry->b - b) / 27;
    }
    return 1;
}

int ca_ec_tau3_atlas_recode_actions(const ca_tau3_fused_precomp *pre, uint64_t k,
                                    uint16_t actions[16], size_t *count)
{
    if (!pre) return 0;
    return tau3_atlas_recode_base(&pre->base, pre->blocks, k, actions, count);
}

int ca_ec_tau3_atlas_recode_verify_scalar(const ca_tau3_fused_precomp *pre, uint64_t k)
{
    uint16_t old_actions[16], new_actions[16];
    size_t old_count = 0, new_count = 0;
    int old_ok = ca_ec_tau3_fused_recode_actions(pre, k, old_actions, &old_count);
    int new_ok = ca_ec_tau3_atlas_recode_actions(pre, k, new_actions, &new_count);
    return old_ok == new_ok &&
           (!old_ok || (old_count == new_count &&
                        memcmp(old_actions, new_actions, old_count * sizeof(uint16_t)) == 0));
}

int ca_ec_tau3_fused_recode_verify_scalar(const ca_tau3_fused_precomp *pre, uint64_t k)
{
    if (!pre || !pre->base.g) return 0;
    uint16_t actions[16];
    size_t count;
    if (!ca_ec_tau3_fused_recode_actions(pre, k, actions, &count)) return 0;
    tau_vec total = {0, 0};
    for (size_t block = 0; block < count; block++) {
        unsigned id = actions[block] >> 3, code = actions[block] & 7;
        if (id >= CA_TAU3_FUSED_ORBITS || code >= 6) return 0;
        tau_vec value =
            tau3_apply_unit_coeff(tau3_pair_coeff(ca_tau3_rep_u[id], ca_tau3_rep_v[id]), code);
        for (size_t i = 0; i < 6 * block; i++) value = tau3_mul_tau(value);
        total.x += value.x;
        total.y += value.y;
    }
    return tau3_coeff_scalar(pre->base.g, total) == k % pre->base.g->order;
}

static tau_jac tau3_apply_unit_jac(const ca_group *g, tau_jac point, unsigned code, uint64_t beta,
                                   uint64_t beta2, uint64_t *rotations)
{
    if (!point.z) return point;
    unsigned power = code % 3;
    if (power == 1) point.x = fm(g, beta, point.x);
    if (power == 2) point.x = fm(g, beta2, point.x);
    if (power && rotations) (*rotations)++;
    if (code >= 3 && point.y) point.y = g->p - point.y;
    return point;
}

static tau_jac tau3_pattern_point(const ca_group *g, tau_jac basis[6][3], unsigned pattern,
                                  unsigned position_offset, uint64_t beta, uint64_t beta2,
                                  uint64_t *rotations)
{
    if (!pattern) return (tau_jac){0, g->mont.r1, 0};
    unsigned position = (pattern - 1) / 18 + position_offset;
    unsigned digit = (pattern - 1) % 18;
    return tau3_apply_unit_jac(g, basis[position][digit / 6], digit % 6, beta, beta2, rotations);
}

int ca_ec_tau3_fused_prepare(const ca_group *g, const ca_elem *point, ca_tau3_fused_precomp *out,
                             uint64_t *seed_ops, uint64_t *triples, uint64_t *tau_steps,
                             uint64_t *adds, uint64_t *rotations, uint64_t *inversions)
{
    if (!g || !point || !out) return 0;
    if (seed_ops) *seed_ops = 0;
    if (triples) *triples = 0;
    if (tau_steps) *tau_steps = 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (inversions) *inversions = 0;
    ca_tau3_fused_precomp pre = {0};
    uint64_t nseed = 0;
    if (!ca_ec_tau4_prepare(g, point, &pre.base, &nseed)) return 0;
    pre.base_point = *point;
    pre.blocks = ca_ec_tau3_fused_blocks(g);
    if (!pre.blocks) return 0;
    if (seed_ops) *seed_ops = nseed;
    if (pre.base.identity) {
        *out = pre;
        return 1;
    }
    const size_t count = pre.blocks * CA_TAU3_FUSED_ORBITS;
    pre.point = malloc(count * sizeof(*pre.point));
    tau_jac *projective = malloc(count * sizeof(*projective));
    uint64_t *prefixes = malloc(count * sizeof(*prefixes));
    if (!pre.point || !projective || !prefixes) {
        free(prefixes);
        free(projective);
        free(pre.point);
        return 0;
    }
    uint64_t beta = pre.base.beta, beta2 = pre.base.beta2;
    uint64_t one_minus_beta = fs(g, g->mont.r1, beta);
    tau_jac start[3];
    const unsigned seed_index[3] = {0, 1, 3};
    for (unsigned seed = 0; seed < 3; seed++) {
        const ca_elem *entry = &pre.base.seed[seed_index[seed]];
        start[seed] = entry->w[2] ? (tau_jac){0, g->mont.r1, 0}
                                  : (tau_jac){entry->w[0], entry->w[1], g->mont.r1};
    }
    uint64_t n3 = 0, nt = 0, na = 0, nr = 0;
    for (size_t block = 0; block < pre.blocks; block++) {
        tau_jac basis[6][3];
        for (unsigned seed = 0; seed < 3; seed++) basis[0][seed] = start[seed];
        for (unsigned position = 1; position < 6; position++)
            for (unsigned seed = 0; seed < 3; seed++) {
                basis[position][seed] = jac_tau(g, basis[position - 1][seed], one_minus_beta);
                nt += basis[position - 1][seed].z != 0;
            }
        for (unsigned id = 0; id < CA_TAU3_FUSED_ORBITS; id++) {
            tau_jac first = tau3_pattern_point(g, basis, ca_tau3_rep_u[id], 0, beta, beta2, &nr);
            tau_jac second = tau3_pattern_point(g, basis, ca_tau3_rep_v[id], 3, beta, beta2, &nr);
            if (first.z && second.z) {
                projective[block * CA_TAU3_FUSED_ORBITS + id] = jac_add(g, first, second);
                na++;
            } else {
                projective[block * CA_TAU3_FUSED_ORBITS + id] = first.z ? first : second;
            }
        }
        if (block + 1 < pre.blocks)
            for (unsigned seed = 0; seed < 3; seed++) {
                tau_jac next = start[seed];
                for (unsigned i = 0; i < 3; i++) {
                    if (next.z) n3++;
                    next = jac_triple(g, next);
                }
                if (next.z && next.y) next.y = g->p - next.y;
                start[seed] = next;
            }
    }
    uint64_t table_inversions = 0;
    int ok =
        jac_batch_to_affine_scratch(g, pre.point, projective, count, prefixes, &table_inversions);
    free(prefixes);
    free(projective);
    if (!ok) {
        free(pre.point);
        return 0;
    }
    if (triples) *triples = n3;
    if (tau_steps) *tau_steps = nt;
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (inversions) *inversions = 1 + table_inversions;
    *out = pre;
    return 1;
}

int ca_ec_tau3_fused_prepare_verify(const ca_tau3_fused_precomp *pre)
{
    if (!pre || !pre->base.g || !pre->blocks) return 0;
    const ca_group *g = pre->base.g;
    if (pre->base.identity) return pre->point == NULL;
    if (!pre->point) return 0;
    for (size_t block = 0; block < pre->blocks; block++)
        for (unsigned id = 0; id < CA_TAU3_FUSED_ORBITS; id++) {
            tau_vec value = tau3_pair_coeff(ca_tau3_rep_u[id], ca_tau3_rep_v[id]);
            for (size_t i = 0; i < 6 * block; i++) value = tau3_mul_tau(value);
            ca_elem expected;
            ca_group_mul(g, &expected, &pre->base_point, tau3_coeff_scalar(g, value), NULL);
            if (!ca_group_equal(g, &expected, &pre->point[block * CA_TAU3_FUSED_ORBITS + id]))
                return 0;
        }
    return 1;
}

static int tau3_mul_profile_impl(const ca_group *g, const ca_tau3_fused_precomp *pre, ca_elem *out,
                                 uint64_t k, uint64_t *adds, uint64_t *rotations,
                                 uint64_t *fallbacks, int atlas)
{
    if (!g || !pre || !out || pre->base.g != g || !pre->blocks) return 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (fallbacks) *fallbacks = 0;
    if (pre->base.identity || k % g->order == 0) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    uint16_t actions[16];
    size_t count = 0;
    int recoded = atlas ? ca_ec_tau3_atlas_recode_actions(pre, k, actions, &count)
                        : ca_ec_tau3_fused_recode_actions(pre, k, actions, &count);
    if (!recoded) {
        if (fallbacks) *fallbacks = 1;
        ca_group_mul(g, out, &pre->base_point, k % g->order, NULL);
        return 1;
    }
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t na = 0, nr = 0;
    for (size_t block = count; block-- > 0;) {
        unsigned id = actions[block] >> 3, code = actions[block] & 7;
        if (!id) continue;
        if (id >= CA_TAU3_FUSED_ORBITS || code >= 6) return 0;
        ca_elem entry = pre->point[block * CA_TAU3_FUSED_ORBITS + id];
        if (entry.w[2]) continue;
        unsigned power = code % 3;
        if (power == 1) entry.w[0] = fm(g, pre->base.beta, entry.w[0]);
        if (power == 2) entry.w[0] = fm(g, pre->base.beta2, entry.w[0]);
        nr += power != 0;
        if (code >= 3 && entry.w[1]) entry.w[1] = g->p - entry.w[1];
        acc = jac_add_mixed(g, acc, &entry);
        na++;
    }
    jac_to_affine(g, out, acc);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    return 1;
}

int ca_ec_tau3_fused_mul_profile(const ca_group *g, const ca_tau3_fused_precomp *pre, ca_elem *out,
                                 uint64_t k, uint64_t *adds, uint64_t *rotations,
                                 uint64_t *fallbacks)
{
    return tau3_mul_profile_impl(g, pre, out, k, adds, rotations, fallbacks, 0);
}

int ca_ec_tau3_atlas_mul_profile(const ca_group *g, const ca_tau3_fused_precomp *pre, ca_elem *out,
                                 uint64_t k, uint64_t *adds, uint64_t *rotations,
                                 uint64_t *fallbacks)
{
    return tau3_mul_profile_impl(g, pre, out, k, adds, rotations, fallbacks, 1);
}

void ca_ec_tau3_fused_clear(ca_tau3_fused_precomp *pre)
{
    if (!pre) return;
    free(pre->point);
    *pre = (ca_tau3_fused_precomp){0};
}

static void tau3_scatter_select(const ca_group *g, const ca_tau3_scatter_entry **entry,
                                const uint16_t **offsets, size_t *count)
{
    *entry = NULL;
    *offsets = NULL;
    *count = 0;
    if (!g) return;
    if (g->order == UINT64_C(23729779) && ca_ec_tau3_fused_blocks(g) == 4) {
        *entry = ca_tau3_scatter_small;
        *offsets = ca_tau3_scatter_small_offsets;
        *count = CA_TAU3_SCATTER_SMALL_COUNT;
    } else if (g->order == UINT64_C(53624256071278747) && ca_ec_tau3_fused_blocks(g) == 7) {
        *entry = ca_tau3_scatter_large;
        *offsets = ca_tau3_scatter_large_offsets;
        *count = CA_TAU3_SCATTER_LARGE_COUNT;
    }
}

size_t ca_ec_tau3_scatter_point_entries(const ca_group *g)
{
    const ca_tau3_scatter_entry *entry;
    const uint16_t *offsets;
    size_t count;
    tau3_scatter_select(g, &entry, &offsets, &count);
    return ca_ec_tau3_fused_blocks(g) * CA_TAU3_FUSED_ORBITS + count;
}

size_t ca_ec_tau3_scatter_static_bytes(void)
{
    return ca_ec_tau3_fused_static_bytes() + sizeof(ca_tau3_scatter_unit_map) +
           sizeof(ca_tau3_scatter_small) + sizeof(ca_tau3_scatter_large) +
           sizeof(ca_tau3_scatter_small_offsets) + sizeof(ca_tau3_scatter_large_offsets) +
           sizeof(ca_tau3_scatter_canonical) + sizeof(ca_tau3_scatter_canonical_unit);
}

size_t ca_ec_tau3_scatter_atlas_static_bytes(void)
{
    return ca_ec_tau3_scatter_static_bytes() + sizeof(ca_tau3_scatter_atlas_rep) +
           sizeof(ca_tau3_scatter_atlas_code) + sizeof(ca_tau3_scatter_atlas_small_pair) +
           sizeof(ca_tau3_scatter_atlas_small_slot) + sizeof(ca_tau3_scatter_atlas_large_pair) +
           sizeof(ca_tau3_scatter_atlas_large_slot);
}

static int tau3_scatter_entry_cmp(ca_tau3_scatter_entry a, ca_tau3_scatter_entry b)
{
    if (a.i != b.i) return a.i < b.i ? -1 : 1;
    if (a.j != b.j) return a.j < b.j ? -1 : 1;
    if (a.u != b.u) return a.u < b.u ? -1 : 1;
    return (a.v > b.v) - (a.v < b.v);
}

static int tau3_scatter_verify_entries(const ca_tau3_scatter_entry *entry,
                                       const uint16_t offsets[401], size_t count,
                                       unsigned max_blocks)
{
    if (offsets[0] != 0 || offsets[400] != count) return 0;
    for (unsigned key = 0; key < 400; key++) {
        if (offsets[key] > offsets[key + 1]) return 0;
        for (size_t n = offsets[key]; n < offsets[key + 1]; n++)
            if (20u * entry[n].i + entry[n].j != key) return 0;
    }
    for (size_t n = 0; n < count; n++) {
        ca_tau3_scatter_entry item = entry[n];
        if (item.i >= item.j || item.j >= max_blocks || item.i / 2 == item.j / 2 || !item.u ||
            item.u > 54 || !item.v || item.v > 54 ||
            (n && tau3_scatter_entry_cmp(entry[n - 1], item) >= 0))
            return 0;
        for (unsigned code = 0; code < 6; code++) {
            unsigned u = ca_tau3_scatter_unit_map[code][item.u];
            unsigned v = ca_tau3_scatter_unit_map[code][item.v];
            if (u < item.u || (u == item.u && v < item.v)) return 0;
        }
    }
    return 1;
}

int ca_ec_tau3_scatter_verify_map(void)
{
    if (!ca_ec_tau3_fused_verify_map() ||
        !tau3_scatter_verify_entries(ca_tau3_scatter_small, ca_tau3_scatter_small_offsets,
                                     CA_TAU3_SCATTER_SMALL_COUNT, 8) ||
        !tau3_scatter_verify_entries(ca_tau3_scatter_large, ca_tau3_scatter_large_offsets,
                                     CA_TAU3_SCATTER_LARGE_COUNT, 14))
        return 0;
    for (unsigned code = 0; code < 6; code++)
        for (unsigned pattern = 0; pattern < 55; pattern++) {
            unsigned moved = ca_tau3_scatter_unit_map[code][pattern];
            if (moved >= 55) return 0;
            tau_vec want = tau3_apply_unit_coeff(tau3_pattern_coeff(pattern), code);
            tau_vec actual = tau3_pattern_coeff(moved);
            if (want.x != actual.x || want.y != actual.y) return 0;
        }
    for (unsigned u = 0; u < 55; u++)
        for (unsigned v = 0; v < 55; v++) {
            unsigned index = 55 * u + v;
            unsigned rep = ca_tau3_scatter_canonical[index];
            unsigned code = ca_tau3_scatter_canonical_unit[index];
            if (rep >= 3025 || code >= 6 || ca_tau3_scatter_unit_map[code][rep / 55] != u ||
                ca_tau3_scatter_unit_map[code][rep % 55] != v)
                return 0;
            for (unsigned other = 0; other < 6; other++) {
                unsigned cu = ca_tau3_scatter_unit_map[other][u];
                unsigned cv = ca_tau3_scatter_unit_map[other][v];
                if (ca_tau3_scatter_canonical[55 * cu + cv] != rep) return 0;
            }
        }
    return 1;
}

static int tau3_scatter_atlas_verify_entries(const uint8_t pair_map[400], const uint16_t *slots,
                                             unsigned pair_count,
                                             const ca_tau3_scatter_entry *entry, size_t entry_count)
{
    uint8_t seen[CA_TAU3_SCATTER_ATLAS_LARGE_PAIRS] = {0};
    if (pair_count > sizeof(seen)) return 0;
    for (unsigned key = 0; key < 400; key++) {
        unsigned pair = pair_map[key];
        if (pair == 255) continue;
        if (pair >= pair_count || seen[pair]++) return 0;
        for (unsigned orbit = 0; orbit < CA_TAU3_SCATTER_ATLAS_ORBITS; orbit++) {
            unsigned slot = slots[(size_t)pair * CA_TAU3_SCATTER_ATLAS_ORBITS + orbit];
            if (slot == UINT16_MAX) continue;
            if (slot >= entry_count) return 0;
            ca_tau3_scatter_entry item = entry[slot];
            if (20u * item.i + item.j != key ||
                55u * item.u + item.v != ca_tau3_scatter_atlas_rep[orbit])
                return 0;
        }
    }
    for (unsigned pair = 0; pair < pair_count; pair++)
        if (!seen[pair]) return 0;
    for (size_t slot = 0; slot < entry_count; slot++) {
        ca_tau3_scatter_entry item = entry[slot];
        unsigned key = 20u * item.i + item.j;
        if (key >= 400 || pair_map[key] == 255) return 0;
        unsigned packed = ca_tau3_scatter_atlas_code[(size_t)55 * item.u + item.v];
        unsigned orbit = packed & 511u;
        unsigned pair = pair_map[key];
        if (orbit >= CA_TAU3_SCATTER_ATLAS_ORBITS ||
            (size_t)slots[(size_t)pair * CA_TAU3_SCATTER_ATLAS_ORBITS + orbit] != slot)
            return 0;
    }
    return 1;
}

int ca_ec_tau3_scatter_atlas_verify_map(void)
{
    if (!ca_ec_tau3_scatter_verify_map()) return 0;
    for (unsigned index = 0; index < 3025; index++) {
        unsigned packed = ca_tau3_scatter_atlas_code[index];
        unsigned orbit = packed & 511u;
        unsigned code = packed >> 9;
        if (orbit >= CA_TAU3_SCATTER_ATLAS_ORBITS || code >= 6 ||
            ca_tau3_scatter_atlas_rep[orbit] != ca_tau3_scatter_canonical[index] ||
            code != ca_tau3_scatter_canonical_unit[index])
            return 0;
    }
    return tau3_scatter_atlas_verify_entries(ca_tau3_scatter_atlas_small_pair,
                                             ca_tau3_scatter_atlas_small_slot,
                                             CA_TAU3_SCATTER_ATLAS_SMALL_PAIRS,
                                             ca_tau3_scatter_small, CA_TAU3_SCATTER_SMALL_COUNT) &&
           tau3_scatter_atlas_verify_entries(ca_tau3_scatter_atlas_large_pair,
                                             ca_tau3_scatter_atlas_large_slot,
                                             CA_TAU3_SCATTER_ATLAS_LARGE_PAIRS,
                                             ca_tau3_scatter_large, CA_TAU3_SCATTER_LARGE_COUNT);
}

static int tau3_scatter_single(const ca_group *g, const ca_tau3_fused_precomp *pre, unsigned block,
                               unsigned pattern, ca_elem *out, uint64_t *rotations)
{
    unsigned u = block % 2 ? 0 : pattern;
    unsigned v = block % 2 ? pattern : 0;
    size_t index = 55 * u + v;
    unsigned id = ca_tau3_orbit_id[index], code = ca_tau3_orbit_unit[index];
    if (!pattern || id >= CA_TAU3_FUSED_ORBITS || code >= 6 || block / 2 >= pre->blocks) return 0;
    *out = pre->point[(block / 2) * CA_TAU3_FUSED_ORBITS + id];
    if (out->w[2]) return 1;
    unsigned power = code % 3;
    if (power == 1) out->w[0] = fm(g, pre->base.beta, out->w[0]);
    if (power == 2) out->w[0] = fm(g, pre->base.beta2, out->w[0]);
    if (code >= 3 && out->w[1]) out->w[1] = g->p - out->w[1];
    if (rotations) *rotations += power != 0;
    return 1;
}

int ca_ec_tau3_scatter_prepare(const ca_group *g, const ca_elem *point,
                               ca_tau3_scatter_precomp *out, uint64_t *seed_ops, uint64_t *triples,
                               uint64_t *tau_steps, uint64_t *adds, uint64_t *rotations,
                               uint64_t *inversions)
{
    if (!g || !point || !out) return 0;
    ca_tau3_scatter_precomp pre = {0};
    if (!ca_ec_tau3_fused_prepare(g, point, &pre.full, seed_ops, triples, tau_steps, adds,
                                  rotations, inversions))
        return 0;
    tau3_scatter_select(g, &pre.entry, &pre.offsets, &pre.extra_count);
    if (pre.entry == ca_tau3_scatter_small) {
        pre.atlas_pair = ca_tau3_scatter_atlas_small_pair;
        pre.atlas_slot = ca_tau3_scatter_atlas_small_slot;
    } else if (pre.entry == ca_tau3_scatter_large) {
        pre.atlas_pair = ca_tau3_scatter_atlas_large_pair;
        pre.atlas_slot = ca_tau3_scatter_atlas_large_slot;
    }
    if (!pre.extra_count || pre.full.base.identity) {
        *out = pre;
        return 1;
    }
    pre.extra = malloc(pre.extra_count * sizeof(*pre.extra));
    tau_jac *projective = malloc(pre.extra_count * sizeof(*projective));
    uint64_t *prefixes = malloc(pre.extra_count * sizeof(*prefixes));
    if (!pre.extra || !projective || !prefixes) {
        free(prefixes);
        free(projective);
        ca_ec_tau3_scatter_clear(&pre);
        return 0;
    }
    uint64_t extra_rotations = 0;
    for (size_t n = 0; n < pre.extra_count; n++) {
        ca_tau3_scatter_entry item = pre.entry[n];
        ca_elem first, second;
        if (!tau3_scatter_single(g, &pre.full, item.i, item.u, &first, &extra_rotations) ||
            !tau3_scatter_single(g, &pre.full, item.j, item.v, &second, &extra_rotations)) {
            free(prefixes);
            free(projective);
            ca_ec_tau3_scatter_clear(&pre);
            return 0;
        }
        tau_jac left = first.w[2] ? (tau_jac){0, g->mont.r1, 0}
                                  : (tau_jac){first.w[0], first.w[1], g->mont.r1};
        projective[n] = second.w[2] ? left : jac_add_mixed(g, left, &second);
    }
    uint64_t extra_inversions = 0;
    int ok = jac_batch_to_affine_scratch(g, pre.extra, projective, pre.extra_count, prefixes,
                                         &extra_inversions);
    free(prefixes);
    free(projective);
    if (!ok) {
        ca_ec_tau3_scatter_clear(&pre);
        return 0;
    }
    if (adds) *adds += pre.extra_count;
    if (rotations) *rotations += extra_rotations;
    if (inversions) *inversions += extra_inversions;
    *out = pre;
    return 1;
}

int ca_ec_tau3_scatter_prepare_verify(const ca_tau3_scatter_precomp *pre)
{
    if (!pre || !ca_ec_tau3_fused_prepare_verify(&pre->full)) return 0;
    if (pre->full.base.identity) return pre->extra == NULL;
    if (pre->extra_count &&
        (!pre->entry || !pre->extra || !pre->offsets || !pre->atlas_pair || !pre->atlas_slot))
        return 0;
    const ca_group *g = pre->full.base.g;
    for (size_t n = 0; n < pre->extra_count; n++) {
        ca_tau3_scatter_entry item = pre->entry[n];
        tau_vec first = tau3_pattern_coeff(item.u);
        tau_vec second = tau3_pattern_coeff(item.v);
        for (unsigned i = 0; i < 3 * item.i; i++) first = tau3_mul_tau(first);
        for (unsigned i = 0; i < 3 * item.j; i++) second = tau3_mul_tau(second);
        tau_vec total = {first.x + second.x, first.y + second.y};
        ca_elem expected;
        ca_group_mul(g, &expected, &pre->full.base_point, tau3_coeff_scalar(g, total), NULL);
        if (!ca_group_equal(g, &expected, &pre->extra[n])) return 0;
    }
    return 1;
}

static size_t tau3_scatter_find(const ca_tau3_scatter_precomp *pre, ca_tau3_scatter_entry key)
{
    if (!pre->offsets || key.i >= 20 || key.j >= 20) return SIZE_MAX;
    unsigned pair = 20 * key.i + key.j;
    size_t low = pre->offsets[pair], high = pre->offsets[pair + 1];
    while (low < high) {
        size_t mid = low + (high - low) / 2;
        int cmp = tau3_scatter_entry_cmp(pre->entry[mid], key);
        if (cmp < 0)
            low = mid + 1;
        else
            high = mid;
    }
    return low < pre->extra_count && !tau3_scatter_entry_cmp(pre->entry[low], key) ? low : SIZE_MAX;
}

static int tau3_scatter_edge(const ca_tau3_scatter_precomp *pre, unsigned i, unsigned j, unsigned u,
                             unsigned v, size_t *slot, unsigned *unit)
{
    if (i / 2 == j / 2) {
        *slot = SIZE_MAX;
        unsigned index = 55 * u + v;
        *unit = ca_tau3_orbit_unit[index];
        return ca_tau3_orbit_id[index] < CA_TAU3_FUSED_ORBITS && *unit < 6;
    }
    unsigned index = 55 * u + v;
    unsigned rep = ca_tau3_scatter_canonical[index];
    *slot = tau3_scatter_find(pre, (ca_tau3_scatter_entry){i, j, rep / 55, rep % 55});
    if (*slot == SIZE_MAX) return 0;
    *unit = ca_tau3_scatter_canonical_unit[index];
    return *unit < 6;
}

static int tau3_scatter_atlas_edge(const ca_tau3_scatter_precomp *pre, unsigned i, unsigned j,
                                   unsigned u, unsigned v, size_t *slot, unsigned *unit)
{
    if (i / 2 == j / 2) return tau3_scatter_edge(pre, i, j, u, v, slot, unit);
    if (!pre->atlas_pair || !pre->atlas_slot || i >= 20 || j >= 20 || i >= j) return 0;
    unsigned pair = pre->atlas_pair[(size_t)20 * i + j];
    if (pair == 255) return 0;
    unsigned packed = ca_tau3_scatter_atlas_code[(size_t)55 * u + v];
    unsigned orbit = packed & 511u;
    if (orbit >= CA_TAU3_SCATTER_ATLAS_ORBITS) return 0;
    unsigned found = pre->atlas_slot[(size_t)pair * CA_TAU3_SCATTER_ATLAS_ORBITS + orbit];
    if (found == UINT16_MAX || found >= pre->extra_count) return 0;
    *slot = found;
    *unit = packed >> 9;
    return *unit < 6;
}

static int tau3_scatter_edge_policy(const ca_tau3_scatter_precomp *pre, unsigned i, unsigned j,
                                    unsigned u, unsigned v, size_t *slot, unsigned *unit, int atlas)
{
    return atlas ? tau3_scatter_atlas_edge(pre, i, j, u, v, slot, unit)
                 : tau3_scatter_edge(pre, i, j, u, v, slot, unit);
}

/* Exhaustively explore simple alternating paths. For this bounded graph it
 * avoids a subset-DP heap allocation while retaining exact cardinality. */
static int tau3_scatter_augment(unsigned vertex, uint32_t used, const uint32_t edge[20],
                                int8_t mate[20])
{
    used |= UINT32_C(1) << vertex;
    for (uint32_t choices = edge[vertex] & ~used; choices; choices &= choices - 1) {
        unsigned other = (unsigned)__builtin_ctz(choices);
        uint32_t next_used = used | (UINT32_C(1) << other);
        if (mate[other] < 0) {
            mate[vertex] = (int8_t)other;
            mate[other] = (int8_t)vertex;
            return 1;
        }
        unsigned paired = (unsigned)mate[other];
        if (!(next_used & (UINT32_C(1) << paired)) &&
            tau3_scatter_augment(paired, next_used, edge, mate)) {
            mate[vertex] = (int8_t)other;
            mate[other] = (int8_t)vertex;
            return 1;
        }
    }
    return 0;
}

unsigned ca_ec_tau3_scatter_match_graph(const uint32_t edge[20], unsigned count, int8_t mate[20])
{
    if (!edge || !mate || count > 20) return UINT_MAX;
    for (unsigned i = 0; i < count; i++) mate[i] = -1;
    unsigned pairs = 0;
    for (unsigned i = 0; i < count && pairs < count / 2; i++)
        if (mate[i] < 0 && tau3_scatter_augment(i, 0, edge, mate)) pairs++;
    return pairs;
}

static ca_elem tau3_scatter_unit_affine(const ca_group *g, const ca_tau3_scatter_precomp *pre,
                                        ca_elem point, unsigned code, uint64_t *rotations)
{
    if (point.w[2]) return point;
    unsigned power = code % 3;
    if (power == 1) point.w[0] = fm(g, pre->full.base.beta, point.w[0]);
    if (power == 2) point.w[0] = fm(g, pre->full.base.beta2, point.w[0]);
    if (code >= 3 && point.w[1]) point.w[1] = g->p - point.w[1];
    if (rotations) *rotations += power != 0;
    return point;
}

static int tau3_scatter_mul_policy(const ca_group *g, const ca_tau3_scatter_precomp *pre,
                                   ca_elem *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                   uint64_t *fallbacks, uint64_t *matched_pairs,
                                   size_t *scratch_bytes, int rematch, int atlas)
{
    if (!g || !pre || !out || pre->full.base.g != g || !pre->full.blocks) return 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (fallbacks) *fallbacks = 0;
    if (matched_pairs) *matched_pairs = 0;
    if (scratch_bytes) *scratch_bytes = 0;
    k %= g->order;
    if (!k || pre->full.base.identity) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    ca_i128 a, b;
    const ca_tau4_precomp *base = &pre->full.base;
    reduce_with_lattice((tau_vec){base->v1x, base->v1y}, (tau_vec){base->v2x, base->v2y}, base->det,
                        k, &a, &b);
    uint8_t digits[128];
    size_t nd = tau3_recode(a, b, digits);
    if (!nd || (nd + 5) / 6 > pre->full.blocks) goto fallback;
    unsigned positions[20], patterns[20], count = 0;
    for (size_t block = 0; block < (nd + 2) / 3; block++) {
        unsigned pattern = tau3_block_pattern(digits, nd, 3 * block);
        if (pattern >= 55) return 0;
        if (!pattern) continue;
        if (count == 20) goto fallback;
        positions[count] = (unsigned)block;
        patterns[count++] = pattern;
    }
    int8_t mate[20];
    for (unsigned i = 0; i < count; i++) mate[i] = -1;
    unsigned baseline_pairs = 0;
    for (unsigned i = 0; i + 1 < count; i++)
        if (positions[i] / 2 == positions[i + 1] / 2) {
            mate[i] = (int8_t)(i + 1);
            mate[i + 1] = (int8_t)i;
            baseline_pairs++;
            i++;
        }
    for (unsigned i = 0; i < count && baseline_pairs < count / 2; i++) {
        if (mate[i] >= 0) continue;
        for (unsigned j = i + 1; j < count; j++) {
            if (mate[j] >= 0) continue;
            size_t slot;
            unsigned unit;
            if (tau3_scatter_edge_policy(pre, positions[i], positions[j], patterns[i], patterns[j],
                                         &slot, &unit, atlas)) {
                mate[i] = (int8_t)j;
                mate[j] = (int8_t)i;
                baseline_pairs++;
                break;
            }
        }
    }
    if (rematch && baseline_pairs < count / 2) {
        uint32_t edge[20] = {0};
        for (unsigned i = 0; i < count; i++)
            for (unsigned j = i + 1; j < count; j++) {
                size_t slot;
                unsigned unit;
                if (tau3_scatter_edge(pre, positions[i], positions[j], patterns[i], patterns[j],
                                      &slot, &unit)) {
                    edge[i] |= UINT32_C(1) << j;
                    edge[j] |= UINT32_C(1) << i;
                }
            }
        for (unsigned i = 0; i < count && baseline_pairs < count / 2; i++)
            if (mate[i] < 0 && tau3_scatter_augment(i, 0, edge, mate)) baseline_pairs++;
    }
    uint32_t mask = (UINT32_C(1) << count) - 1;
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t na = 0, nr = 0, np = 0;
    while (mask) {
        unsigned i = (unsigned)__builtin_ctz(mask);
        uint32_t rest = mask & ~(UINT32_C(1) << i);
        unsigned partner = mate[i] < 0 ? 20 : (unsigned)mate[i];
        ca_elem point;
        if (partner < count) {
            size_t slot;
            unsigned code;
            if (!tau3_scatter_edge_policy(pre, positions[i], positions[partner], patterns[i],
                                          patterns[partner], &slot, &code, atlas)) {
                return 0;
            }
            if (slot == SIZE_MAX) {
                unsigned id = ca_tau3_orbit_id[55 * patterns[i] + patterns[partner]];
                point = pre->full.point[(positions[i] / 2) * CA_TAU3_FUSED_ORBITS + id];
            } else {
                point = pre->extra[slot];
            }
            point = tau3_scatter_unit_affine(g, pre, point, code, &nr);
            rest &= ~(UINT32_C(1) << partner);
            np++;
        } else {
            if (!tau3_scatter_single(g, &pre->full, positions[i], patterns[i], &point, &nr)) {
                return 0;
            }
        }
        if (!point.w[2]) {
            acc = jac_add_mixed(g, acc, &point);
            na++;
        }
        mask = rest;
    }
    jac_to_affine(g, out, acc);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (matched_pairs) *matched_pairs = np;
    return 1;
fallback:
    if (fallbacks) *fallbacks = 1;
    ca_group_mul(g, out, &pre->full.base_point, k, NULL);
    return 1;
}

int ca_ec_tau3_scatter_mul_profile(const ca_group *g, const ca_tau3_scatter_precomp *pre,
                                   ca_elem *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                   uint64_t *fallbacks, uint64_t *matched_pairs,
                                   size_t *scratch_bytes)
{
    return tau3_scatter_mul_policy(g, pre, out, k, adds, rotations, fallbacks, matched_pairs,
                                   scratch_bytes, 1, 0);
}

int ca_ec_tau3_scatter_direct_mul_profile(const ca_group *g, const ca_tau3_scatter_precomp *pre,
                                          ca_elem *out, uint64_t k, uint64_t *adds,
                                          uint64_t *rotations, uint64_t *fallbacks,
                                          uint64_t *matched_pairs, size_t *scratch_bytes)
{
    return tau3_scatter_mul_policy(g, pre, out, k, adds, rotations, fallbacks, matched_pairs,
                                   scratch_bytes, 0, 0);
}

int ca_ec_tau3_scatter_atlas_mul_profile(const ca_group *g, const ca_tau3_scatter_precomp *pre,
                                         ca_elem *out, uint64_t k, uint64_t *adds,
                                         uint64_t *rotations, uint64_t *fallbacks,
                                         uint64_t *matched_pairs, size_t *scratch_bytes)
{
    return tau3_scatter_mul_policy(g, pre, out, k, adds, rotations, fallbacks, matched_pairs,
                                   scratch_bytes, 0, 1);
}

void ca_ec_tau3_scatter_clear(ca_tau3_scatter_precomp *pre)
{
    if (!pre) return;
    free(pre->extra);
    ca_ec_tau3_fused_clear(&pre->full);
    *pre = (ca_tau3_scatter_precomp){0};
}

static void tau3_sparse_select(const ca_group *g, size_t *blocks, size_t *entries,
                               size_t *hot_entries, const uint16_t **offsets, const uint16_t **ids,
                               const uint16_t **slots)
{
    *blocks = ca_ec_tau3_fused_blocks(g);
    *hot_entries = 0;
    *offsets = *ids = *slots = NULL;
    if (g && g->order == UINT64_C(23729779) && *blocks == CA_TAU3_SPARSE_SMALL_BLOCKS) {
        *offsets = ca_tau3_sparse_small_hot_offsets;
        *ids = ca_tau3_sparse_small_hot_ids;
        *slots = ca_tau3_sparse_small_hot_slots;
        *hot_entries = sizeof(ca_tau3_sparse_small_hot_ids) / sizeof(uint16_t);
    } else if (g && g->order == UINT64_C(53624256071278747) &&
               *blocks == CA_TAU3_SPARSE_LARGE_BLOCKS) {
        *offsets = ca_tau3_sparse_large_hot_offsets;
        *ids = ca_tau3_sparse_large_hot_ids;
        *slots = ca_tau3_sparse_large_hot_slots;
        *hot_entries = sizeof(ca_tau3_sparse_large_hot_ids) / sizeof(uint16_t);
    }
    *entries = 18 * *blocks + *hot_entries;
}

size_t ca_ec_tau3_sparse_point_entries(const ca_group *g)
{
    size_t blocks, entries, hot_entries;
    const uint16_t *offsets, *ids, *slots;
    tau3_sparse_select(g, &blocks, &entries, &hot_entries, &offsets, &ids, &slots);
    return entries;
}

size_t ca_ec_tau3_sparse_static_bytes(void)
{
    return ca_ec_tau3_atlas_static_bytes() + sizeof(ca_tau3_sparse_small_hot_offsets) +
           sizeof(ca_tau3_sparse_small_hot_ids) + sizeof(ca_tau3_sparse_small_hot_slots) +
           sizeof(ca_tau3_sparse_large_hot_offsets) + sizeof(ca_tau3_sparse_large_hot_ids) +
           sizeof(ca_tau3_sparse_large_hot_slots);
}

static int tau3_sparse_verify_one_map(size_t blocks, size_t entries, const uint16_t *offsets,
                                      size_t hot_entries, const uint16_t *ids,
                                      const uint16_t *slots)
{
    if (!blocks || offsets[0] || offsets[blocks] != hot_entries ||
        18 * blocks + hot_entries != entries)
        return 0;
    for (size_t block = 0; block < blocks; block++) {
        if (offsets[block] > offsets[block + 1]) return 0;
        uint8_t seen[CA_TAU3_FUSED_ORBITS] = {0};
        for (size_t i = offsets[block]; i < offsets[block + 1]; i++) {
            unsigned id = ids[i];
            if (id >= CA_TAU3_FUSED_ORBITS || seen[id] || !ca_tau3_rep_u[id] ||
                !ca_tau3_rep_v[id] || slots[343 * block + id] != i - offsets[block])
                return 0;
            seen[id] = 1;
        }
        for (unsigned id = 0; id < CA_TAU3_FUSED_ORBITS; id++)
            if (!seen[id] && slots[343 * block + id] != UINT16_MAX) return 0;
    }
    return 1;
}

int ca_ec_tau3_sparse_verify_map(void)
{
    return ca_ec_tau3_fused_verify_map() && ca_ec_tau3_atlas_verify_map() &&
           tau3_sparse_verify_one_map(CA_TAU3_SPARSE_SMALL_BLOCKS, CA_TAU3_SPARSE_SMALL_ENTRIES,
                                      ca_tau3_sparse_small_hot_offsets,
                                      sizeof(ca_tau3_sparse_small_hot_ids) / sizeof(uint16_t),
                                      ca_tau3_sparse_small_hot_ids,
                                      ca_tau3_sparse_small_hot_slots) &&
           tau3_sparse_verify_one_map(CA_TAU3_SPARSE_LARGE_BLOCKS, CA_TAU3_SPARSE_LARGE_ENTRIES,
                                      ca_tau3_sparse_large_hot_offsets,
                                      sizeof(ca_tau3_sparse_large_hot_ids) / sizeof(uint16_t),
                                      ca_tau3_sparse_large_hot_ids, ca_tau3_sparse_large_hot_slots);
}

int ca_ec_tau3_sparse_prepare(const ca_group *g, const ca_elem *point, ca_tau3_sparse_precomp *out,
                              uint64_t *seed_ops, uint64_t *triples, uint64_t *tau_steps,
                              uint64_t *adds, uint64_t *rotations, uint64_t *inversions)
{
    if (!g || !point || !out) return 0;
    if (seed_ops) *seed_ops = 0;
    if (triples) *triples = 0;
    if (tau_steps) *tau_steps = 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (inversions) *inversions = 0;
    ca_tau3_sparse_precomp pre = {0};
    uint64_t nseed = 0;
    if (!ca_ec_tau4_prepare(g, point, &pre.base, &nseed)) return 0;
    pre.base_point = *point;
    tau3_sparse_select(g, &pre.blocks, &pre.point_entries, &pre.hot_entries, &pre.hot_offsets,
                       &pre.hot_ids, &pre.hot_slots);
    if (!pre.blocks || pre.blocks > 16) return 0;
    if (seed_ops) *seed_ops = nseed;
    if (pre.base.identity) {
        *out = pre;
        return 1;
    }
    size_t count = pre.point_entries;
    pre.point = malloc(count * sizeof(*pre.point));
    tau_jac *projective = malloc(count * sizeof(*projective));
    uint64_t *prefixes = malloc(count * sizeof(*prefixes));
    if (!pre.point || !projective || !prefixes) {
        free(prefixes);
        free(projective);
        free(pre.point);
        return 0;
    }
    uint64_t beta = pre.base.beta, beta2 = pre.base.beta2;
    uint64_t one_minus_beta = fs(g, g->mont.r1, beta);
    tau_jac start[3];
    const unsigned seed_index[3] = {0, 1, 3};
    for (unsigned seed = 0; seed < 3; seed++) {
        const ca_elem *entry = &pre.base.seed[seed_index[seed]];
        start[seed] = entry->w[2] ? (tau_jac){0, g->mont.r1, 0}
                                  : (tau_jac){entry->w[0], entry->w[1], g->mont.r1};
    }
    uint64_t n3 = 0, nt = 0, na = 0, nr = 0;
    for (size_t block = 0; block < pre.blocks; block++) {
        tau_jac basis[6][3];
        for (unsigned seed = 0; seed < 3; seed++) basis[0][seed] = start[seed];
        for (unsigned position = 1; position < 6; position++)
            for (unsigned seed = 0; seed < 3; seed++) {
                basis[position][seed] = jac_tau(g, basis[position - 1][seed], one_minus_beta);
                nt += basis[position - 1][seed].z != 0;
            }
        size_t hot_start = pre.hot_offsets ? pre.hot_offsets[block] : 0;
        size_t hot_end = pre.hot_offsets ? pre.hot_offsets[block + 1] : 0;
        size_t base = 18 * block + hot_start;
        for (unsigned position = 0; position < 6; position++)
            for (unsigned seed = 0; seed < 3; seed++)
                projective[base + (size_t)3 * position + seed] = basis[position][seed];
        for (size_t i = hot_start; i < hot_end; i++) {
            unsigned id = pre.hot_ids[i];
            tau_jac first = tau3_pattern_point(g, basis, ca_tau3_rep_u[id], 0, beta, beta2, &nr);
            tau_jac second = tau3_pattern_point(g, basis, ca_tau3_rep_v[id], 3, beta, beta2, &nr);
            if (!first.z || !second.z) {
                free(prefixes);
                free(projective);
                free(pre.point);
                return 0;
            }
            projective[base + 18 + i - hot_start] = jac_add(g, first, second);
            na++;
        }
        if (block + 1 < pre.blocks)
            for (unsigned seed = 0; seed < 3; seed++) {
                tau_jac next = start[seed];
                for (unsigned i = 0; i < 3; i++) {
                    if (next.z) n3++;
                    next = jac_triple(g, next);
                }
                if (next.z && next.y) next.y = g->p - next.y;
                start[seed] = next;
            }
    }
    uint64_t table_inversions = 0;
    int ok =
        jac_batch_to_affine_scratch(g, pre.point, projective, count, prefixes, &table_inversions);
    free(prefixes);
    free(projective);
    if (!ok) {
        free(pre.point);
        return 0;
    }
    if (triples) *triples = n3;
    if (tau_steps) *tau_steps = nt;
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (inversions) *inversions = 1 + table_inversions;
    *out = pre;
    return 1;
}

int ca_ec_tau3_sparse_prepare_verify(const ca_tau3_sparse_precomp *pre)
{
    if (!pre || !pre->base.g || !pre->blocks) return 0;
    const ca_group *g = pre->base.g;
    if (pre->base.identity) return pre->point == NULL;
    if (!pre->point) return 0;
    const tau_vec seeds[3] = {{1, 0}, {2, 0}, {1, 1}};
    for (size_t block = 0; block < pre->blocks; block++) {
        size_t hot_start = pre->hot_offsets ? pre->hot_offsets[block] : 0;
        size_t hot_end = pre->hot_offsets ? pre->hot_offsets[block + 1] : 0;
        size_t base = 18 * block + hot_start;
        for (unsigned position = 0; position < 6; position++)
            for (unsigned seed = 0; seed < 3; seed++) {
                tau_vec value = seeds[seed];
                for (size_t step = 0; step < 6 * block + position; step++)
                    value = tau3_mul_tau(value);
                ca_elem expected;
                ca_group_mul(g, &expected, &pre->base_point, tau3_coeff_scalar(g, value), NULL);
                if (!ca_group_equal(g, &expected,
                                    &pre->point[base + (size_t)3 * position + seed]))
                    return 0;
            }
        for (size_t i = hot_start; i < hot_end; i++) {
            unsigned id = pre->hot_ids[i];
            tau_vec value = tau3_pair_coeff(ca_tau3_rep_u[id], ca_tau3_rep_v[id]);
            for (size_t step = 0; step < 6 * block; step++) value = tau3_mul_tau(value);
            ca_elem expected;
            ca_group_mul(g, &expected, &pre->base_point, tau3_coeff_scalar(g, value), NULL);
            if (!ca_group_equal(g, &expected, &pre->point[base + 18 + i - hot_start])) return 0;
        }
    }
    return 1;
}

int ca_ec_tau3_sparse_recode_actions(const ca_tau3_sparse_precomp *pre, uint64_t k,
                                     uint16_t actions[16], size_t *count)
{
    if (!pre) return 0;
    return tau3_atlas_recode_base(&pre->base, pre->blocks, k, actions, count);
}

static ca_elem tau3_sparse_unit_affine(const ca_group *g, const ca_tau3_sparse_precomp *pre,
                                       ca_elem entry, unsigned code, uint64_t *rotations)
{
    if (entry.w[2]) return entry;
    unsigned power = code % 3;
    if (power == 1) entry.w[0] = fm(g, pre->base.beta, entry.w[0]);
    if (power == 2) entry.w[0] = fm(g, pre->base.beta2, entry.w[0]);
    if (power && rotations) (*rotations)++;
    if (code >= 3 && entry.w[1]) entry.w[1] = g->p - entry.w[1];
    return entry;
}

static int tau3_sparse_add_action(const ca_group *g, const ca_tau3_sparse_precomp *pre,
                                  tau_jac *acc, size_t block, uint16_t action, uint64_t *adds,
                                  uint64_t *rotations, uint64_t *cold_pairs)
{
    unsigned id = action >> 3, code = action & 7;
    if (!id) return code == 0;
    if (id >= CA_TAU3_FUSED_ORBITS || code >= 6 || block >= pre->blocks) return 0;
    size_t hot_start = pre->hot_offsets ? pre->hot_offsets[block] : 0;
    size_t base = 18 * block + hot_start;
    unsigned slot = pre->hot_slots ? pre->hot_slots[343 * block + id] : UINT16_MAX;
    if (slot != UINT16_MAX) {
        ca_elem entry =
            tau3_sparse_unit_affine(g, pre, pre->point[base + 18 + slot], code, rotations);
        if (!entry.w[2]) {
            *acc = jac_add_mixed(g, *acc, &entry);
            if (adds) (*adds)++;
        }
        return 1;
    }
    const unsigned patterns[2] = {ca_tau3_rep_u[id], ca_tau3_rep_v[id]};
    if (patterns[0] && patterns[1] && cold_pairs) (*cold_pairs)++;
    for (unsigned half = 0; half < 2; half++) {
        unsigned pattern = patterns[half];
        if (!pattern) continue;
        unsigned position = (pattern - 1) / 18 + 3 * half;
        unsigned digit = (pattern - 1) % 18;
        unsigned seed = digit / 6, local_unit = digit % 6;
        unsigned unit = (local_unit % 3 + code % 3) % 3 + 3 * ((local_unit >= 3) != (code >= 3));
        ca_elem entry = tau3_sparse_unit_affine(g, pre,
                                                pre->point[base + (size_t)3 * position + seed],
                                                unit, rotations);
        if (!entry.w[2]) {
            *acc = jac_add_mixed(g, *acc, &entry);
            if (adds) (*adds)++;
        }
    }
    return 1;
}

int ca_ec_tau3_sparse_mul_profile(const ca_group *g, const ca_tau3_sparse_precomp *pre,
                                  ca_elem *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                  uint64_t *cold_pairs, uint64_t *fallbacks)
{
    if (!g || !pre || !out || pre->base.g != g || !pre->blocks) return 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (cold_pairs) *cold_pairs = 0;
    if (fallbacks) *fallbacks = 0;
    if (pre->base.identity || k % g->order == 0) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    uint16_t actions[16];
    size_t count = 0;
    if (!ca_ec_tau3_sparse_recode_actions(pre, k, actions, &count)) {
        if (fallbacks) *fallbacks = 1;
        ca_group_mul(g, out, &pre->base_point, k % g->order, NULL);
        return 1;
    }
    if (!pre->point) return 0;
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t na = 0, nr = 0, nc = 0;
    for (size_t block = count; block-- > 0;)
        if (!tau3_sparse_add_action(g, pre, &acc, block, actions[block], &na, &nr, &nc)) return 0;
    jac_to_affine(g, out, acc);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (cold_pairs) *cold_pairs = nc;
    return 1;
}

int ca_ec_tau3_sparse_verify_actions(const ca_tau3_sparse_precomp *pre)
{
    if (!pre || !pre->base.g || !pre->blocks) return 0;
    if (pre->base.identity) return pre->point == NULL;
    if (!pre->point) return 0;
    const ca_group *g = pre->base.g;
    for (size_t block = 0; block < pre->blocks; block++)
        for (unsigned id = 0; id < CA_TAU3_FUSED_ORBITS; id++)
            for (unsigned code = 0; code < 6; code++) {
                if (!id && code) continue;
                tau_jac acc = {0, g->mont.r1, 0};
                if (!tau3_sparse_add_action(g, pre, &acc, block, (uint16_t)((id << 3) | code), NULL,
                                            NULL, NULL))
                    return 0;
                ca_elem actual, expected;
                jac_to_affine(g, &actual, acc);
                tau_vec value = tau3_apply_unit_coeff(
                    tau3_pair_coeff(ca_tau3_rep_u[id], ca_tau3_rep_v[id]), code);
                for (size_t step = 0; step < 6 * block; step++) value = tau3_mul_tau(value);
                ca_group_mul(g, &expected, &pre->base_point, tau3_coeff_scalar(g, value), NULL);
                if (!ca_group_equal(g, &actual, &expected)) return 0;
            }
    return 1;
}

void ca_ec_tau3_sparse_clear(ca_tau3_sparse_precomp *pre)
{
    if (!pre) return;
    free(pre->point);
    *pre = (ca_tau3_sparse_precomp){0};
}

/* Each correction has |a| <= 96 and |b| <= 54. For one starting state,
 * successors at any fixed depth differ by < 192/26 and < 108/26 in the
 * two integer coordinates, respectively. Thus at most 9*6=54 states can
 * occur per depth; 16 depths fit within 1024 memo entries. */
#define CA_TAU3_RADIX27_MEMO_MAX  1024
#define CA_TAU3_RADIX27_HASH_SIZE 2048
#define CA_TAU3_RADIX27_INF       UINT16_MAX

typedef struct tau3_radix27_state {
    ca_i128 a, b;
    uint16_t cost, option;
    uint8_t block;
} tau3_radix27_state;

typedef struct tau3_radix27_memo {
    tau3_radix27_state state[CA_TAU3_RADIX27_MEMO_MAX];
    uint16_t bucket[CA_TAU3_RADIX27_HASH_SIZE];
    size_t count;
    uint64_t options;
    int overflow;
} tau3_radix27_memo;

size_t ca_ec_tau3_radix27_static_bytes(void)
{
    return ca_ec_tau3_sparse_static_bytes() + sizeof(ca_tau3_radix27_offsets) +
           sizeof(ca_tau3_radix27_options);
}

size_t ca_ec_tau3_radix27_online_scratch_bytes(void)
{
    return sizeof(tau3_radix27_memo) + 16 * sizeof(uint16_t);
}

int ca_ec_tau3_radix27_verify_map(void)
{
    if (!ca_ec_tau3_sparse_verify_map() ||
        ca_tau3_radix27_offsets[729] != CA_TAU3_RADIX27_OPTIONS)
        return 0;
    uint8_t seen[CA_TAU3_FUSED_ORBITS * 8] = {0};
    unsigned multiplicity[10] = {0};
    for (unsigned residue = 0; residue < 729; residue++) {
        unsigned first = ca_tau3_radix27_offsets[residue];
        unsigned last = ca_tau3_radix27_offsets[residue + 1];
        if (last > CA_TAU3_RADIX27_OPTIONS || first >= last || last - first > 9) return 0;
        multiplicity[last - first]++;
        for (unsigned i = first; i < last; i++) {
            const ca_tau3_radix27_option *option = &ca_tau3_radix27_options[i];
            unsigned id = option->action >> 3, code = option->action & 7;
            if (id >= CA_TAU3_FUSED_ORBITS || code >= 6 || seen[option->action] ||
                (unsigned)tau3_residue(option->a, 27) != residue / 27 ||
                (unsigned)tau3_residue(option->b, 27) != residue % 27 || option->a < -96 ||
                option->a > 96 || option->b < -54 || option->b > 54)
                return 0;
            seen[option->action] = 1;
            tau_vec expected =
                tau3_apply_unit_coeff(tau3_pair_coeff(ca_tau3_rep_u[id], ca_tau3_rep_v[id]), code);
            if (expected.x != option->a || expected.y != option->b) return 0;
        }
    }
    return multiplicity[1] == 397 && multiplicity[3] == 222 && multiplicity[9] == 110;
}

static uint64_t tau3_radix27_hash(ca_i128 a, ca_i128 b, unsigned block)
{
    uint64_t x =
        (uint64_t)a ^ ((uint64_t)((unsigned __int128)a >> 64) * UINT64_C(0x9e3779b97f4a7c15));
    uint64_t y =
        (uint64_t)b ^ ((uint64_t)((unsigned __int128)b >> 64) * UINT64_C(0xbf58476d1ce4e5b9));
    uint64_t h =
        x ^ (y + UINT64_C(0x94d049bb133111eb)) ^ ((uint64_t)block * UINT64_C(0x632be59bd9b4e019));
    h ^= h >> 30;
    h *= UINT64_C(0xbf58476d1ce4e5b9);
    h ^= h >> 27;
    return h ^ (h >> 31);
}

static tau3_radix27_state *tau3_radix27_find(tau3_radix27_memo *memo, ca_i128 a, ca_i128 b,
                                             unsigned block, size_t *empty)
{
    size_t slot = tau3_radix27_hash(a, b, block) & (CA_TAU3_RADIX27_HASH_SIZE - 1);
    while (memo->bucket[slot]) {
        tau3_radix27_state *state = &memo->state[memo->bucket[slot] - 1];
        if (state->a == a && state->b == b && state->block == block) return state;
        slot = (slot + 1) & (CA_TAU3_RADIX27_HASH_SIZE - 1);
    }
    if (empty) *empty = slot;
    return NULL;
}

static uint16_t tau3_radix27_charge(const ca_tau3_sparse_precomp *pre, unsigned block,
                                    unsigned action)
{
    unsigned id = action >> 3;
    if (!id) return 0;
    if (!ca_tau3_rep_u[id] || !ca_tau3_rep_v[id] ||
        (pre->hot_slots && pre->hot_slots[343 * block + id] != UINT16_MAX))
        return 1;
    return 2;
}

static uint16_t tau3_radix27_solve(const ca_tau3_sparse_precomp *pre, tau3_radix27_memo *memo,
                                   ca_i128 a, ca_i128 b, unsigned block)
{
    if (!a && !b) return 0;
    if (block >= pre->blocks || memo->overflow) return CA_TAU3_RADIX27_INF;
    tau3_radix27_state *cached = tau3_radix27_find(memo, a, b, block, NULL);
    if (cached) return cached->cost;
    unsigned residue = 27 * (unsigned)tau3_residue(a, 27) + (unsigned)tau3_residue(b, 27);
    unsigned first = ca_tau3_radix27_offsets[residue];
    unsigned last = ca_tau3_radix27_offsets[residue + 1];
    uint16_t best_cost = CA_TAU3_RADIX27_INF, best_option = UINT16_MAX;
    unsigned best_norm = UINT_MAX;
    unsigned best_action = UINT_MAX;
    int best_a = INT_MAX, best_b = INT_MAX;
    for (unsigned i = first; i < last; i++) {
        const ca_tau3_radix27_option *option = &ca_tau3_radix27_options[i];
        ca_i128 next_a = ((ca_i128)option->a - a) / 27;
        ca_i128 next_b = ((ca_i128)option->b - b) / 27;
        memo->options++;
        uint16_t tail = tau3_radix27_solve(pre, memo, next_a, next_b, block + 1);
        if (tail == CA_TAU3_RADIX27_INF) continue;
        uint16_t charge = tau3_radix27_charge(pre, block, option->action);
        uint16_t total = (uint16_t)(charge + tail);
        unsigned norm = (unsigned)abs(option->a) + (unsigned)abs(option->b);
        if (total < best_cost ||
            (total == best_cost &&
             (norm < best_norm ||
              (norm == best_norm &&
               (option->action < best_action ||
                (option->action == best_action &&
                 (option->a < best_a || (option->a == best_a && option->b < best_b)))))))) {
            best_cost = total;
            best_option = (uint16_t)i;
            best_norm = norm;
            best_action = option->action;
            best_a = (int)option->a;
            best_b = (int)option->b;
        }
    }
    if (memo->overflow || memo->count >= CA_TAU3_RADIX27_MEMO_MAX) {
        memo->overflow = 1;
        return CA_TAU3_RADIX27_INF;
    }
    size_t empty;
    if (tau3_radix27_find(memo, a, b, block, &empty)) return CA_TAU3_RADIX27_INF;
    memo->state[memo->count] = (tau3_radix27_state){a, b, best_cost, best_option, (uint8_t)block};
    memo->bucket[empty] = (uint16_t)(memo->count + 1);
    memo->count++;
    return best_cost;
}

int ca_ec_tau3_radix27_recode_actions(const ca_tau3_sparse_precomp *pre, uint64_t k,
                                      uint16_t actions[16], size_t *count, uint64_t *dp_states,
                                      uint64_t *dp_options)
{
    if (!pre || !pre->base.g || !pre->blocks || !actions || !count) return 0;
    if (dp_states) *dp_states = 0;
    if (dp_options) *dp_options = 0;
    *count = 0;
    const ca_group *g = pre->base.g;
    k %= g->order;
    if (!k) return 1;
    ca_i128 a, b;
    reduce_with_lattice((tau_vec){pre->base.v1x, pre->base.v1y},
                        (tau_vec){pre->base.v2x, pre->base.v2y}, pre->base.det, k, &a, &b);
    tau3_radix27_memo memo;
    for (size_t i = 0; i < CA_TAU3_RADIX27_HASH_SIZE; i++) memo.bucket[i] = 0;
    memo.count = 0;
    memo.options = 0;
    memo.overflow = 0;
    uint16_t minimum = tau3_radix27_solve(pre, &memo, a, b, 0);
    if (dp_states) *dp_states = memo.count;
    if (dp_options) *dp_options = memo.options;
    if (memo.overflow || minimum == CA_TAU3_RADIX27_INF) return 0;
    for (unsigned block = 0; a || b; block++) {
        if (block >= pre->blocks || block >= 16) return 0;
        const tau3_radix27_state *state = tau3_radix27_find(&memo, a, b, block, NULL);
        if (!state || state->option >= CA_TAU3_RADIX27_OPTIONS) return 0;
        const ca_tau3_radix27_option *option = &ca_tau3_radix27_options[state->option];
        if (((ca_i128)option->a - a) % 27 || ((ca_i128)option->b - b) % 27) return 0;
        actions[(*count)++] = option->action;
        a = ((ca_i128)option->a - a) / 27;
        b = ((ca_i128)option->b - b) / 27;
    }
    return 1;
}

int ca_ec_tau3_radix27_mul_profile(const ca_group *g, const ca_tau3_sparse_precomp *pre,
                                   ca_elem *out, uint64_t k, uint64_t *adds, uint64_t *rotations,
                                   uint64_t *cold_pairs, uint64_t *fallbacks, uint64_t *dp_states,
                                   uint64_t *dp_options)
{
    if (!g || !pre || !out || pre->base.g != g || !pre->blocks) return 0;
    if (adds) *adds = 0;
    if (rotations) *rotations = 0;
    if (cold_pairs) *cold_pairs = 0;
    if (fallbacks) *fallbacks = 0;
    if (dp_states) *dp_states = 0;
    if (dp_options) *dp_options = 0;
    if (pre->base.identity || k % g->order == 0) {
        *out = (ca_elem){{0, 0, 1, 0}};
        return 1;
    }
    uint16_t actions[16];
    size_t count = 0;
    if (!ca_ec_tau3_radix27_recode_actions(pre, k, actions, &count, dp_states, dp_options)) {
        if (fallbacks) *fallbacks = 1;
        ca_group_mul(g, out, &pre->base_point, k % g->order, NULL);
        return 1;
    }
    if (!pre->point) return 0;
    tau_jac acc = {0, g->mont.r1, 0};
    uint64_t na = 0, nr = 0, nc = 0;
    for (size_t block = count; block-- > 0;)
        if (!tau3_sparse_add_action(g, pre, &acc, block, actions[block], &na, &nr, &nc)) return 0;
    jac_to_affine(g, out, acc);
    if (adds) *adds = na;
    if (rotations) *rotations = nr;
    if (cold_pairs) *cold_pairs = nc;
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
