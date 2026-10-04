#ifndef CA_EC_TAU_INTERNAL_H
#define CA_EC_TAU_INTERNAL_H

#include "cryptanalysis/ca_group.h"

/* Per-point width-4 table for repeated scalar multiplications within one rho
 * solve.  It is private to the C implementation and tied to its group. */
typedef struct ca_tau4_digit {
  int8_t a, b, seed, power, sign;
} ca_tau4_digit;

typedef struct ca_tau4_precomp {
  const ca_group *g;
  ca_elem seed[9];
  ca_elem tau_seed[9];
  ca_tau4_digit digit[81];
  uint64_t beta, beta2;
  __int128 v1x, v1y, v2x, v2y, det;
  int identity;
} ca_tau4_precomp;

#define CA_TAU_POS_Q 64
typedef struct ca_tau4_pos_precomp {
    ca_tau4_precomp base;
    ca_elem point[CA_TAU_POS_Q][2][9];
} ca_tau4_pos_precomp;

int ca_ec_tau4_prepare(const ca_group *g, const ca_elem *point,
                       ca_tau4_precomp *out, uint64_t *ops);
int ca_ec_tau4_mul_prepared(const ca_group *g, const ca_tau4_precomp *pre,
                            ca_elem *out, uint64_t k, uint64_t *triples,
                            uint64_t *adds);
/* Public-scalar research variant: score all 25 nearby Eisenstein coset
 * representatives by the prepared tripling/addition/rotation schedule. */
int ca_ec_tau4_mul_prepared_cost(const ca_group *g, const ca_tau4_precomp *pre,
                                 ca_elem *out, uint64_t k, uint64_t *triples,
                                 uint64_t *adds);
int ca_ec_tau4_mul_prepared_profile(const ca_group *g,
                                    const ca_tau4_precomp *pre, ca_elem *out,
                                    uint64_t k, int cost_aware,
                                    uint64_t *triples, uint64_t *adds,
                                    uint64_t *rotations);

/* Fixed-base positional table: 3^q times each seed and tau-seed point.
 * precompute_triples excludes the 19 operations in the base preparation. */
int ca_ec_tau4_pos_prepare(const ca_group *g, const ca_elem *point,
                           ca_tau4_pos_precomp *out,
                           uint64_t *precompute_triples);
int ca_ec_tau4_pos_mul(const ca_group *g, const ca_tau4_pos_precomp *pre,
                       ca_elem *out, uint64_t k, uint64_t *adds,
                       uint64_t *rotations);

#endif
