/*
 * volcano.c - l-isogeny volcanoes over F_p, l = 2 or 3 (ca_volcano.h).
 *
 * Rational kernels are the F_p-roots of the l-division polynomial, found
 * as gcd(f, x^p - x) and split by Cantor-Zassenhaus; the polynomials have
 * degree <= 4, so they live in fixed arrays.  Velu's formulas (Washington,
 * Thm 12.16, with a1 = a3 = 0) give codomain and map from x0 alone.  A
 * vertex's level is depth - (distance to the nearest curve with exactly one
 * rational l-kernel), the floor of an ordinary volcano of depth >= 1.
 */
#include "cryptanalysis/ca_volcano.h"
#include "cryptanalysis/ca_group.h"
#include "cryptanalysis/ca_modarith.h"
#include "ca_internal.h"

#include <stdlib.h>
#include <string.h>

/* ---- F_p[x], degree < PMAX ---------------------------------------------- */

#define PMAX 9 /* a product of two residues mod a quartic */

typedef struct poly {
    uint64_t c[PMAX];
    int deg; /* -1 for the zero polynomial */
} poly;

static void p_trim(poly *a)
{
    while (a->deg >= 0 && a->c[a->deg] == 0) a->deg--;
}

static void p_monic(poly *a, uint64_t p)
{
    if (a->deg < 0) return;
    uint64_t inv = ca_invmod(a->c[a->deg], p);
    for (int i = 0; i <= a->deg; i++) a->c[i] = ca_mulmod(a->c[i], inv, p);
}

/* q = a / f and a = a mod f, f monic; q may be NULL. */
static void p_divrem(poly *a, const poly *f, poly *q, uint64_t p)
{
    if (q) {
        memset(q, 0, sizeof(*q));
        q->deg = a->deg - f->deg;
    }
    for (int i = a->deg; i >= f->deg; i--) {
        uint64_t c = a->c[i];
        if (q) q->c[i - f->deg] = c;
        if (!c) continue;
        for (int k = 0; k <= f->deg; k++) {
            uint64_t *t = &a->c[i - f->deg + k];
            *t = ca_submod(*t, ca_mulmod(c, f->c[k], p), p);
        }
    }
    p_trim(a);
    if (q) p_trim(q);
}

static void p_mulmod(poly *r, const poly *a, const poly *b, const poly *f, uint64_t p)
{
    poly t;
    memset(&t, 0, sizeof(t));
    t.deg = -1;
    if (a->deg >= 0 && b->deg >= 0) {
        t.deg = a->deg + b->deg;
        for (int i = 0; i <= a->deg; i++)
            for (int j = 0; j <= b->deg; j++)
                t.c[i + j] = ca_addmod(t.c[i + j], ca_mulmod(a->c[i], b->c[j], p), p);
        p_divrem(&t, f, NULL, p);
    }
    *r = t;
}

/* (x + c)^e mod f. */
static void p_pow_lin(poly *r, uint64_t c, uint64_t e, const poly *f, uint64_t p)
{
    poly base, acc;
    memset(&base, 0, sizeof(base));
    memset(&acc, 0, sizeof(acc));
    base.c[0] = c % p;
    base.c[1] = 1;
    base.deg = 1;
    p_divrem(&base, f, NULL, p);
    acc.c[0] = 1;
    acc.deg = 0;
    while (e) {
        if (e & 1) p_mulmod(&acc, &acc, &base, f, p);
        p_mulmod(&base, &base, &base, f, p);
        e >>= 1;
    }
    *r = acc;
}

/* Monic gcd. */
static void p_gcd(poly *r, poly a, poly b, uint64_t p)
{
    p_trim(&a);
    p_trim(&b);
    while (b.deg >= 0) {
        p_monic(&b, p);
        poly t = a;
        p_divrem(&t, &b, NULL, p);
        a = b;
        b = t;
    }
    p_monic(&a, p);
    *r = a;
}

/* Roots of the monic squarefree split g, appended to out[n..]. */
static unsigned p_split(const poly *g, uint64_t p, uint64_t *salt, uint64_t *out, unsigned n)
{
    if (g->deg <= 0) return n;
    if (g->deg == 1) {
        out[n++] = ca_submod(0, g->c[0], p);
        return n;
    }
    for (;;) {
        poly t, s;
        p_pow_lin(&t, ca_mix64((*salt)++) % p, (p - 1) / 2, g, p);
        if (t.deg < 0) {
            t.deg = 0;
            t.c[0] = 0;
        }
        t.c[0] = ca_submod(t.c[0], 1, p);
        p_trim(&t);
        p_gcd(&s, *g, t, p);
        if (s.deg > 0 && s.deg < g->deg) {
            poly q, rem = *g;
            p_divrem(&rem, &s, &q, p);
            p_monic(&q, p);
            n = p_split(&s, p, salt, out, n);
            return p_split(&q, p, salt, out, n);
        }
    }
}

/* ---- curves and isogenies ---------------------------------------------- */

static int valid_prime(uint64_t p) { return p > 3 && p < (1ULL << 62) && ca_is_prime(p); }

/* j = 1728 * 4a^3 / (4a^3 + 27b^2); 0 return for a singular curve. */
static int j_invariant(uint64_t p, uint64_t a, uint64_t b, uint64_t *j)
{
    uint64_t a3 = ca_mulmod(4, ca_mulmod(a, ca_mulmod(a, a, p), p), p);
    uint64_t den = ca_addmod(a3, ca_mulmod(27, ca_mulmod(b, b, p), p), p);
    if (!den) return 0;
    *j = ca_mulmod(ca_mulmod(1728 % p, a3, p), ca_invmod(den, p), p);
    return 1;
}

unsigned ca_isogeny_kernels(uint64_t p, uint64_t a, uint64_t b, unsigned ell,
                            uint64_t xs[CA_VOLCANO_MAX_NBRS])
{
    poly f, xp, g;
    memset(&f, 0, sizeof(f));
    a %= p;
    b %= p;
    if (ell == 2) { /* x^3 + ax + b */
        f.c[0] = b;
        f.c[1] = a;
        f.c[3] = 1;
        f.deg = 3;
    } else { /* psi_3 / 3 = x^4 + 2a x^2 + 4b x - a^2/3 */
        f.c[0] = ca_submod(0, ca_mulmod(ca_mulmod(a, a, p), ca_invmod(3, p), p), p);
        f.c[1] = ca_mulmod(4, b, p);
        f.c[2] = ca_mulmod(2, a, p);
        f.c[4] = 1;
        f.deg = 4;
    }
    p_pow_lin(&xp, 0, p, &f, p);
    if (xp.deg < 1) {
        for (int i = xp.deg + 1; i <= 1; i++) xp.c[i] = 0;
        xp.deg = 1;
    }
    xp.c[1] = ca_submod(xp.c[1], 1, p);
    p_trim(&xp);
    p_gcd(&g, f, xp, p);
    uint64_t salt = 0x766f6c63616e6fULL;
    unsigned n = p_split(&g, p, &salt, xs, 0);
    for (unsigned i = 1; i < n; i++)
        for (unsigned k = i; k > 0 && xs[k - 1] > xs[k]; k--) {
            uint64_t t = xs[k];
            xs[k] = xs[k - 1];
            xs[k - 1] = t;
        }
    return n;
}

/* t_Q, u_Q of Velu for the kernel <(x0, .)> (one representative of +-Q). */
static void velu_tu(uint64_t p, uint64_t a, uint64_t b, unsigned ell, uint64_t x0, uint64_t *tq,
                    uint64_t *uq)
{
    uint64_t gx = ca_addmod(ca_mulmod(3, ca_mulmod(x0, x0, p), p), a, p);
    if (ell == 2) {
        *tq = gx;
        *uq = 0;
    } else {
        uint64_t rhs = ca_addmod(ca_mulmod(ca_addmod(ca_mulmod(x0, x0, p), a, p), x0, p), b, p);
        *tq = ca_addmod(gx, gx, p);
        *uq = ca_mulmod(4, rhs, p);
    }
}

ca_status ca_velu_codomain(uint64_t p, uint64_t a, uint64_t b, unsigned ell, uint64_t x0,
                           uint64_t *a2, uint64_t *b2)
{
    if (!valid_prime(p) || (ell != 2 && ell != 3)) {
        ca_set_error("ca_velu_codomain: need a prime 3 < p < 2^62 and l = 2 or 3");
        return CA_ERR_INVALID;
    }
    uint64_t tq, uq;
    a %= p;
    b %= p;
    velu_tu(p, a, b, ell, x0 % p, &tq, &uq);
    uint64_t w = ca_addmod(uq, ca_mulmod(x0 % p, tq, p), p);
    *a2 = ca_submod(a, ca_mulmod(5, tq, p), p);
    *b2 = ca_submod(b, ca_mulmod(7, w, p), p);
    return CA_OK;
}

ca_status ca_velu_map(uint64_t p, uint64_t a, uint64_t b, unsigned ell, uint64_t x0,
                      const uint64_t in[3], uint64_t out[3])
{
    if (!valid_prime(p) || (ell != 2 && ell != 3)) {
        ca_set_error("ca_velu_map: need a prime 3 < p < 2^62 and l = 2 or 3");
        return CA_ERR_INVALID;
    }
    x0 %= p;
    if (in[2] || in[0] == x0) { /* O and the kernel go to O */
        out[0] = out[1] = 0;
        out[2] = 1;
        return CA_OK;
    }
    uint64_t tq, uq;
    velu_tu(p, a % p, b % p, ell, x0, &tq, &uq);
    uint64_t x = in[0], y = in[1];
    uint64_t i1 = ca_invmod(ca_submod(x, x0, p), p);
    uint64_t i2 = ca_mulmod(i1, i1, p), i3 = ca_mulmod(i2, i1, p);
    out[0] = ca_addmod(x, ca_addmod(ca_mulmod(tq, i1, p), ca_mulmod(uq, i2, p), p), p);
    uint64_t s = ca_addmod(ca_mulmod(ca_addmod(uq, uq, p), i3, p), ca_mulmod(tq, i2, p), p);
    out[1] = ca_submod(y, ca_mulmod(y, s, p), p);
    out[2] = 0;
    return CA_OK;
}

static unsigned val(uint64_t x, uint64_t l)
{
    unsigned v = 0;
    while (x && x % l == 0) {
        x /= l;
        v++;
    }
    return v;
}

ca_status ca_volcano_depth(uint64_t p, uint64_t order, unsigned ell, unsigned *depth, int *crater)
{
    if (!valid_prime(p) || (ell != 2 && ell != 3)) {
        ca_set_error("ca_volcano_depth: need a prime 3 < p < 2^62 and l = 2 or 3");
        return CA_ERR_INVALID;
    }
    int64_t t = (int64_t)p + 1 - (int64_t)order;
    ca_u128 t2 = (ca_u128)((ca_i128)t * t);
    if (t2 >= (ca_u128)4 * p) {
        ca_set_error("ca_volcano_depth: order is outside the Hasse interval or t^2 = 4p");
        return CA_ERR_INVALID;
    }
    uint64_t d = (uint64_t)((ca_u128)4 * p - t2); /* |D| = 4p - t^2 */
    if (ell == 2) {
        unsigned e = val(d, 2);
        uint64_t m = d >> e;
        if (e % 2) { /* D_K = -8m' */
            *depth = (e - 3) / 2;
            *crater = 0;
        } else if ((4 - m % 4) % 4 == 1) { /* -m = 1 mod 4: D_K odd */
            *depth = e / 2;
            *crater = (8 - m % 8) % 8 == 1 ? 1 : -1;
        } else { /* D_K = 4(-m) */
            *depth = e / 2 - 1;
            *crater = 0;
        }
    } else {
        unsigned e = val(d, 3), k = e / 2;
        uint64_t m = d;
        for (unsigned i = 0; i < 2 * k; i++) m /= 3;
        uint64_t r = (3 - m % 3) % 3; /* -m mod 3 */
        *depth = k;
        *crater = r == 0 ? 0 : (r == 1 ? 1 : -1);
    }
    return CA_OK;
}

void ca_volcano_free(ca_volcano *v)
{
    if (!v) return;
    free(v->v);
    v->v = NULL;
    v->count = 0;
}

static void link_edge(ca_volcano *vo, uint32_t i, uint32_t w)
{
    if (i == w) return;
    ca_volcano_vertex *a = &vo->v[i], *b = &vo->v[w];
    for (uint32_t k = 0; k < a->n_nbrs; k++)
        if (a->nbrs[k] == w) return;
    if (a->n_nbrs < CA_VOLCANO_MAX_NBRS) a->nbrs[a->n_nbrs++] = w;
    if (b->n_nbrs < CA_VOLCANO_MAX_NBRS) b->nbrs[b->n_nbrs++] = i;
    vo->edges++;
}

ca_status ca_volcano_walk(uint64_t p, uint64_t a, uint64_t b, uint64_t order, unsigned ell,
                          uint32_t radius, uint32_t max_vertices, ca_volcano *out)
{
    memset(out, 0, sizeof(*out));
    uint64_t j0;
    if (!valid_prime(p) || (ell != 2 && ell != 3)) {
        ca_set_error("ca_volcano_walk: need a prime 3 < p < 2^62 and l = 2 or 3");
        return CA_ERR_INVALID;
    }
    a %= p;
    b %= p;
    if (!j_invariant(p, a, b, &j0)) {
        ca_set_error("ca_volcano_walk: singular curve");
        return CA_ERR_INVALID;
    }
    if (!order) {
        ca_status rc = ca_ec_count_points(p, a, b, &order, NULL);
        if (rc != CA_OK) return rc;
    }
    unsigned depth;
    int crater;
    ca_status rc = ca_volcano_depth(p, order, ell, &depth, &crater);
    if (rc != CA_OK) return rc;
    if (!max_vertices) max_vertices = 20000;

    size_t hsize = 1;
    while (hsize < 2 * (size_t)max_vertices) hsize <<= 1;
    ca_volcano_vertex *v = calloc(max_vertices, sizeof(*v));
    int32_t *tab = malloc(hsize * sizeof(*tab));
    uint32_t *queue = malloc(max_vertices * sizeof(*queue));
    uint32_t *stamp = calloc(max_vertices, sizeof(*stamp));
    uint32_t *hops = malloc(max_vertices * sizeof(*hops));
    if (!v || !tab || !queue || !stamp || !hops) {
        free(v);
        free(tab);
        free(queue);
        free(stamp);
        free(hops);
        return CA_ERR_NOMEM;
    }
    memset(tab, 0xff, hsize * sizeof(*tab));
    out->p = p;
    out->order = order;
    out->trace = (int64_t)p + 1 - (int64_t)order;
    out->ell = ell;
    out->depth = depth;
    out->crater = crater;
    out->radius = radius;
    out->v = v;

    v[0] = (ca_volcano_vertex){.a = a, .b = b, .j = j0, .level = -1, .parent = -1};
    tab[ca_mix64(j0) & (hsize - 1)] = 0;
    out->count = 1;
    uint32_t explore = radius + depth;
    for (uint32_t i = 0; i < out->count; i++) {
        uint64_t xs[CA_VOLCANO_MAX_NBRS] = {0};
        unsigned nk = ca_isogeny_kernels(p, v[i].a, v[i].b, ell, xs);
        v[i].kernels = nk;
        for (unsigned k = 0; k < nk; k++) {
            uint64_t a2 = 0, b2 = 0, j2 = 0;
            if (ca_velu_codomain(p, v[i].a, v[i].b, ell, xs[k], &a2, &b2) != CA_OK) continue;
            if (!j_invariant(p, a2, b2, &j2)) continue; /* cannot happen for a separable isogeny */
            if (j2 == 0 || j2 == 1728 % p) {
                out->special_j++;
                continue;
            }
            size_t h = ca_mix64(j2) & (hsize - 1);
            while (tab[h] >= 0 && v[tab[h]].j != j2) h = (h + 1) & (hsize - 1);
            if (tab[h] < 0) {
                if (v[i].dist >= explore || out->count >= max_vertices) continue;
                uint32_t w = out->count++;
                v[w] = (ca_volcano_vertex){.a = a2,
                                           .b = b2,
                                           .j = j2,
                                           .level = -1,
                                           .dist = v[i].dist + 1,
                                           .parent = (int32_t)i,
                                           .kernel_x = xs[k]};
                tab[h] = (int32_t)w;
            }
            link_edge(out, i, (uint32_t)tab[h]);
        }
    }

    /* Levels: depth - distance to the nearest curve with one rational kernel. */
    for (uint32_t i = 0; i < out->count; i++) {
        if (v[i].dist > radius) continue;
        if (depth == 0) {
            v[i].level = 0;
            continue;
        }
        uint32_t head = 0, tail = 0, mark = i + 1;
        queue[tail++] = i;
        stamp[i] = mark;
        hops[i] = 0;
        while (head < tail) {
            uint32_t u = queue[head++];
            if (v[u].kernels == 1) {
                v[i].level = (int32_t)(depth - hops[u]);
                break;
            }
            if (hops[u] == depth) continue;
            for (uint32_t k = 0; k < v[u].n_nbrs; k++) {
                uint32_t w = v[u].nbrs[k];
                if (stamp[w] == mark) continue;
                stamp[w] = mark;
                hops[w] = hops[u] + 1;
                queue[tail++] = w;
            }
        }
    }
    free(tab);
    free(queue);
    free(stamp);
    free(hops);
    return CA_OK;
}
