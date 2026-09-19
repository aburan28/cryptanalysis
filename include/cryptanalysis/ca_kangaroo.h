/*
 * ca_kangaroo.h - Pollard's kangaroo (lambda) method for the interval
 * discrete logarithm, van Oorschot-Wiener style with herds of tame and
 * wild kangaroos and distinguished points.
 *
 * Finds x in [lo, hi] with x * base == target using about 2 sqrt(hi - lo)
 * group operations and negligible memory.  Unlike BSGS the interval width
 * may be far larger than available memory allows.
 */
#ifndef CA_KANGAROO_H
#define CA_KANGAROO_H

#include "ca_group.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Largest herd the solver will build.  A larger request is clamped to this
 * rather than rejected: two herds of this size are already 64 MB of state,
 * and 2 * herd_size must not overflow the 32-bit count. */
#define CA_KANGAROO_MAX_HERD 1048576u

typedef struct ca_kangaroo_params {
    uint32_t herd_size;   /* kangaroos per herd (tame and wild each), 0 => auto,
                             clamped to CA_KANGAROO_MAX_HERD */
    int32_t dp_bits;      /* distinguished point bits, -1 => auto, clamped to 62 */
    uint32_t jumps;       /* number of jump sizes (powers of two), 0 => auto */
    uint64_t seed;        /* 0 => random */
    uint64_t max_ops;     /* 0 => none */
} ca_kangaroo_params;

CA_API void ca_kangaroo_params_default(ca_kangaroo_params *p);

CA_API ca_status ca_kangaroo_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                                   uint64_t lo, uint64_t hi, const ca_kangaroo_params *params,
                                   uint64_t *x, ca_stats *st);

#ifdef __cplusplus
}
#endif
#endif /* CA_KANGAROO_H */
