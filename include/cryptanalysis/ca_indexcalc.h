/*
 * ca_indexcalc.h - index calculus for discrete logarithms in (Z/pZ)^*.
 *
 * Two relation collectors are provided:
 *
 *   CA_IC_LINEAR_SIEVE (default) - Coppersmith-Odlyzko-Schroeppel linear
 *     sieve.  With H = ceil(sqrt(p)) and J = H^2 - p, the residues
 *     (H+c1)(H+c2) mod p = J + (c1+c2)H + c1 c2 are only O(C sqrt(p)) in
 *     size, so they are B-smooth far more often than random residues.
 *     Unknowns are the logs of the primes <= B and of the H+c, |c| <= C.
 *     Heuristic complexity L_p[1/2, 1].
 *
 *   CA_IC_RANDOM_EXPONENT - the textbook method (g^e mod p tested for
 *     smoothness by trial division), L_p[1/2, 2].  Kept for comparison.
 *
 * Linear algebra: the logs are needed modulo p-1 = prod q^e.  For q below
 * 2^24 the factor-base logs are obtained directly with Pohlig-Hellman in
 * the small subgroups; for larger q the relation matrix is solved modulo
 * q with structured Gaussian elimination + Lanczos (Hensel-lifted for
 * e > 1).  Every factor-base logarithm is verified (g^log == prime) before
 * use, so a wrong answer is never returned.
 *
 * Individual logarithms: h g^e is tested for B-smoothness for random e
 * until it factors over the (verified) factor base.
 *
 * Scope: p < 2^64.  This is a working single-machine index calculus, not
 * the number field sieve; see docs/ALGORITHMS.md for the relationship to
 * the state of the art (NFS for F_p, and why no index calculus exists for
 * prime-field elliptic curves).
 */
#ifndef CA_INDEXCALC_H
#define CA_INDEXCALC_H

#include "ca_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum ca_ic_method {
    CA_IC_LINEAR_SIEVE = 0,
    CA_IC_RANDOM_EXPONENT = 1
} ca_ic_method;

typedef struct ca_ic_params {
    ca_ic_method method;
    uint32_t factor_base_bound;  /* B; 0 => auto from the size of p */
    uint32_t sieve_radius;       /* C (linear sieve only); 0 => auto */
    uint32_t threads;            /* relation collection threads; 0 => 1 */
    uint32_t extra_relations;    /* relations beyond #unknowns; 0 => auto */
    uint64_t seed;               /* 0 => random */
    uint64_t max_relation_tries; /* random-exponent method: abort bound (0 = none) */
    int verbose;                 /* stage reports on stderr */
} ca_ic_params;

typedef struct ca_ic_stats {
    uint32_t factor_base_size;   /* primes in the factor base */
    uint32_t unknowns;           /* columns of the relation matrix */
    uint32_t relations;          /* relations collected */
    uint32_t verified_logs;      /* factor-base logs verified */
    uint64_t sieve_candidates;   /* values passed to trial division */
    uint64_t smooth_tests;       /* random-exponent method: candidates tested */
    double   sieve_seconds;
    double   linalg_seconds;
    double   total_seconds;
    uint32_t lanczos_iterations;
    uint32_t threads;
} ca_ic_stats;

typedef struct ca_ic_ctx ca_ic_ctx;

CA_API void ca_ic_params_default(ca_ic_params *p);

/* Choose (B, C) automatically for a modulus of the given bit length. */
CA_API void ca_ic_auto_params(unsigned bits, uint32_t *B, uint32_t *C);

/* Precompute the factor-base logarithms with respect to g (any element of
 * (Z/pZ)^*; internally a primitive root is used and the base change is
 * done in ca_ic_log).  p must be an odd prime. */
CA_API ca_status ca_ic_precompute(uint64_t p, uint64_t g, const ca_ic_params *params,
                                  ca_ic_ctx **out, ca_ic_stats *st);
CA_API void ca_ic_free(ca_ic_ctx *ctx);

/* Individual logarithm: find x with g^x == h (mod p), x in [0, ord(g)). */
CA_API ca_status ca_ic_log(ca_ic_ctx *ctx, uint64_t h, uint64_t *x, ca_stats *st);

/* One-shot convenience wrapper. */
CA_API ca_status ca_ic_solve(uint64_t p, uint64_t g, uint64_t h, const ca_ic_params *params,
                             uint64_t *x, ca_ic_stats *st);

/* Introspection */
CA_API uint64_t ca_ic_modulus(const ca_ic_ctx *ctx);
CA_API uint32_t ca_ic_factor_base_size(const ca_ic_ctx *ctx);
/* Logarithm (w.r.t. the internal primitive root) of the i-th factor-base
 * prime; returns 0 and sets *known = 0 if it was not determined. */
CA_API uint64_t ca_ic_factor_base_log(const ca_ic_ctx *ctx, uint32_t i, uint32_t *prime, int *known);
CA_API uint64_t ca_ic_primitive_root(const ca_ic_ctx *ctx);

#ifdef __cplusplus
}
#endif
#endif /* CA_INDEXCALC_H */
