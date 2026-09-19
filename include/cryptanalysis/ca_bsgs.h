/*
 * ca_bsgs.h - Shanks' baby-step giant-step for the interval discrete log.
 *
 * Finds x in [lo, hi] (inclusive) with x * base == target.  If lo == hi == 0
 * the whole subgroup [0, order-1] is searched (requires g->order != 0).
 *
 * Cost: table_size group operations + (width / table_size) group
 * operations; memory 24 bytes per table entry (64-bit fingerprint + index).
 */
#ifndef CA_BSGS_H
#define CA_BSGS_H

#include "ca_group.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ca_bsgs_params {
    uint64_t table_size;  /* number of baby steps; 0 => ceil(sqrt(width)) */
    uint64_t max_ops;     /* abort with CA_ERR_LIMIT after this many ops; 0 => none */
} ca_bsgs_params;

CA_API void ca_bsgs_params_default(ca_bsgs_params *p);

CA_API ca_status ca_bsgs_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                               uint64_t lo, uint64_t hi, const ca_bsgs_params *params,
                               uint64_t *x, ca_stats *st);

/*
 * Precomputed baby-step table for solving many logarithms to the same base
 * (amortised BSGS).  Each subsequent solve costs width / table_size ops.
 */
typedef struct ca_bsgs_table ca_bsgs_table;
CA_API ca_status ca_bsgs_table_new(const ca_group *g, const ca_elem *base, uint64_t table_size,
                                   ca_bsgs_table **out);
CA_API void ca_bsgs_table_free(ca_bsgs_table *t);
CA_API ca_status ca_bsgs_table_solve(const ca_bsgs_table *t, const ca_elem *target, uint64_t lo,
                                     uint64_t hi, uint64_t *x, ca_stats *st);

#ifdef __cplusplus
}
#endif
#endif /* CA_BSGS_H */
