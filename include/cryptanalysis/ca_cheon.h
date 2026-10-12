/*
 * ca_cheon.h - Cheon's algorithm for the strong Diffie-Hellman problem
 * (EUROCRYPT 2006 / J. Cryptology 2010).
 *
 * Setting: G = <g> has prime order p.  Given g, g^alpha and g^(alpha^d)
 * for some d | p-1, recover alpha with about
 *     2 sqrt((p-1)/d) + 2 sqrt(d)  exponentiations
 * instead of the sqrt(p) group operations of a generic attack.  Since
 * each exponentiation costs ~1.5 log2(p) group operations, the attack wins
 * whenever d is a suitably balanced divisor of p-1 (ideally d ~ sqrt(p)).
 *
 * The algorithm writes alpha = zeta^k for a generator zeta of (Z/pZ)^*
 * and recovers k modulo (p-1)/d from g^(alpha^d) (a BSGS in the
 * exponent), then k modulo d from g^alpha.  Both phases are BSGS over
 * exponentiation orbits, so memory is O(sqrt((p-1)/d) + sqrt(d)).
 *
 * The d | p+1 variant (which needs arithmetic in F_{p^2} exponents) is
 * not implemented; see docs/ALGORITHMS.md.
 */
#ifndef CA_CHEON_H
#define CA_CHEON_H

#include "ca_group.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ca_cheon_params {
    uint64_t max_exps;  /* abort with CA_ERR_LIMIT after this many exponentiations (0 = none) */
} ca_cheon_params;

CA_API void ca_cheon_params_default(ca_cheon_params *p);

/* Given g, g1 = alpha*g, gd = alpha^d * g (additive notation) with
 * d | p-1 where p = g->order is prime, recover alpha in [1, p-1].
 * Stats: group_ops counts group operations, iterations counts
 * exponentiations. */
CA_API ca_status ca_cheon_solve(const ca_group *g, const ca_elem *gen, const ca_elem *g_alpha,
                                const ca_elem *g_alpha_d, uint64_t d,
                                const ca_cheon_params *params, uint64_t *alpha, ca_stats *st);

/* Helper for experiments: produce (alpha*g, alpha^d*g) from alpha. */
CA_API ca_status ca_cheon_make_instance(const ca_group *g, const ca_elem *gen, uint64_t alpha,
                                        uint64_t d, ca_elem *g_alpha, ca_elem *g_alpha_d);

/* Best divisor d of p-1 for the attack (minimises sqrt((p-1)/d) + sqrt(d)
 * over the divisors), and the corresponding cost estimate in
 * exponentiations. */
CA_API uint64_t ca_cheon_best_divisor(uint64_t p, double *cost_exps);

#ifdef __cplusplus
}
#endif
#endif /* CA_CHEON_H */
