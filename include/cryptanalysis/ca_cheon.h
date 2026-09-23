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
 * The d | p+1 variant is also implemented.  It needs the stronger
 * auxiliary sequence g, g^alpha, ..., g^(alpha^(2d)); it is not a bare
 * ECDLP attack.  Internally it works in the norm-one torus of F_{p^2}^*.
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

/* Cheon's p+1 algorithm (DLP with auxiliary inputs).
 *
 * Given P_i = [alpha^i]gen for 0 <= i <= 2d, with d | p+1 and prime
 * p = g->order, recover alpha.  The 2d+1 auxiliary points are essential:
 * this routine does not derive them from an ordinary public key.
 *
 * The implementation follows Cheon's norm-one-torus construction over
 * F_{p^2}.  Its search cost is O(sqrt((p+1)/d) + sqrt(d)); constructing
 * the degree-2d projective encoding costs O(d) scalar multiplications, so
 * the overall p+1 attack has the usual O(sqrt((p+1)/d) + d) accounting.
 *
 * Current implementation guard: 2d < p, which covers the cryptanalytic
 * regime where the auxiliary sequence is much shorter than the group order.
 */
CA_API ca_status ca_cheon_solve_p_plus_1(const ca_group *g, const ca_elem *g_pows,
                                         size_t powers_len, uint64_t d,
                                         const ca_cheon_params *params,
                                         uint64_t *alpha, ca_stats *st);

/* Helper for tests/benchmarks: fill out[i] = [alpha^i]gen, i=0..2d. */
CA_API ca_status ca_cheon_make_instance_p_plus_1(const ca_group *g, const ca_elem *gen,
                                                 uint64_t alpha, uint64_t d,
                                                 ca_elem *out, size_t out_len);

/* Best divisor d of p-1 for the attack (minimises sqrt((p-1)/d) + sqrt(d)
 * over the divisors), and the corresponding cost estimate in
 * exponentiations. */
CA_API uint64_t ca_cheon_best_divisor(uint64_t p, double *cost_exps);

#ifdef __cplusplus
}
#endif
#endif /* CA_CHEON_H */
