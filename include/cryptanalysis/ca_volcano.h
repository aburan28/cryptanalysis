/*
 * ca_volcano.h - the l-isogeny volcano of an ordinary curve over F_p
 * (l = 2 or 3), walked with explicit Velu isogenies.
 *
 * The l-isogeny graph of an ordinary curve E/F_p is a volcano: a crater
 * (a cycle, a single edge or a point) with complete l-ary trees hanging
 * below it, depth v_l(f) where t^2 - 4p = f^2 D_K.  Every rational
 * l-kernel of a curve is <(x0, .)> with x0 an F_p-root of the l-division
 * polynomial (l = 2: x^3 + ax + b; l = 3: psi_3 = 3x^4 + 6ax^2 + 12bx - a^2),
 * and Velu's formulas give the codomain and the map.  An l-isogeny with
 * l not dividing n is injective on a subgroup of order n, so one discrete
 * log instance can be carried to every curve of the volcano.
 *
 * p must be a prime with 3 < p < 2^62.  Points are plain words
 * {x, y, inf} as ca_group_decode returns them.
 */
#ifndef CA_VOLCANO_H
#define CA_VOLCANO_H

#include "ca_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CA_VOLCANO_MAX_NBRS 4 /* l + 1 for l <= 3 */

typedef struct ca_volcano_vertex {
    uint64_t a, b, j;  /* y^2 = x^3 + ax + b, j-invariant; vertices are distinct j */
    int32_t level;     /* 0 = crater ... depth = floor; -1 when not determined */
    uint32_t dist;     /* breadth-first distance from the root */
    int32_t parent;    /* index of the vertex this one was reached from; -1 for the root */
    uint64_t kernel_x; /* x0 of the kernel of the edge parent -> this, in the parent's model */
    uint32_t kernels;  /* number of rational l-kernels of this curve */
    uint32_t n_nbrs;
    uint32_t nbrs[CA_VOLCANO_MAX_NBRS];
} ca_volcano_vertex;

typedef struct ca_volcano {
    uint64_t p, order; /* #E(F_p), shared by every curve of the class */
    int64_t trace;     /* t = p + 1 - order */
    unsigned ell, depth;
    int crater;         /* (D_K / l): +1 split (cycle), -1 inert (one vertex), 0 ramified */
    uint32_t radius;    /* vertices with dist <= radius carry a level */
    uint32_t count;     /* vertices found (index 0 is the root) */
    uint32_t edges;     /* distinct edges among them */
    uint32_t special_j; /* edges skipped because the codomain had j = 0 or 1728 */
    ca_volcano_vertex *v;
} ca_volcano;

/* Depth v_l(f) and crater shape (D_K / l) from t^2 - 4p alone. */
CA_API ca_status ca_volcano_depth(uint64_t p, uint64_t order, unsigned ell, unsigned *depth,
                                  int *crater);

/* The x-coordinates generating the rational l-kernels of E (at most l + 1),
 * sorted; returns how many. */
CA_API unsigned ca_isogeny_kernels(uint64_t p, uint64_t a, uint64_t b, unsigned ell,
                                   uint64_t xs[CA_VOLCANO_MAX_NBRS]);

/* Velu's codomain of the l-isogeny with kernel <(x0, .)>. */
CA_API ca_status ca_velu_codomain(uint64_t p, uint64_t a, uint64_t b, unsigned ell, uint64_t x0,
                                  uint64_t *a2, uint64_t *b2);

/* The image of the point `in` under that isogeny. */
CA_API ca_status ca_velu_map(uint64_t p, uint64_t a, uint64_t b, unsigned ell, uint64_t x0,
                             const uint64_t in[3], uint64_t out[3]);

/* Walk breadth first from E to distance radius + depth (at most
 * max_vertices curves; 0 => 20000), and give every vertex within `radius`
 * its level.  order = #E(F_p) (0 => counted).  Free with ca_volcano_free. */
CA_API ca_status ca_volcano_walk(uint64_t p, uint64_t a, uint64_t b, uint64_t order, unsigned ell,
                                 uint32_t radius, uint32_t max_vertices, ca_volcano *out);

CA_API void ca_volcano_free(ca_volcano *v);

#ifdef __cplusplus
}
#endif
#endif /* CA_VOLCANO_H */
