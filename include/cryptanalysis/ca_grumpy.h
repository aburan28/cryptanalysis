/*
 * ca_grumpy.h - "Two grumpy giants and a baby" (Bernstein-Lange 2012).
 *
 * Interval discrete logarithm x in [lo, hi] with x * base == target.  Three
 * walks are interleaved: a baby walk j*base, a giant walk target + i*m*base
 * and a second giant walk 2*target - i*(m+1)*base.  Every point goes into
 * one hash table; a collision between any two walks reveals x.
 *
 * Measured average cost (see docs/ALGORITHMS.md, exact simulation and the
 * ca_bench tool), with the default step m = 0.7 sqrt(width):
 *   whole group of order n : 1.21 sqrt(n)  (interleaved BSGS: 1.33 sqrt(n))
 *   sub-interval, no wrap  : 1.72 sqrt(width)  (kangaroo: ~2 sqrt(width))
 * Memory is O(sqrt(width)) table entries (24 bytes each).
 */
#ifndef CA_GRUMPY_H
#define CA_GRUMPY_H

#include "ca_group.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ca_grumpy_params {
    uint64_t m;           /* giant step; 0 => round(alpha * sqrt(width)) */
    double   alpha;       /* step factor used when m == 0; 0 => 0.7 */
    uint64_t max_ops;     /* 0 => none */
} ca_grumpy_params;

CA_API void ca_grumpy_params_default(ca_grumpy_params *p);

CA_API ca_status ca_grumpy_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                                 uint64_t lo, uint64_t hi, const ca_grumpy_params *params,
                                 uint64_t *x, ca_stats *st);

#ifdef __cplusplus
}
#endif
#endif /* CA_GRUMPY_H */
