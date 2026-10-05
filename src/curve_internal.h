#ifndef CA_CURVE_INTERNAL_H
#define CA_CURVE_INTERNAL_H

#include "cryptanalysis/ca_group.h"

/* Private sixfold j=0 orbit representative.  Returns k such that the
 * resulting point is psi^k of its input. */
uint32_t ca_ec_j0_coord_canonicalize(const ca_group *g, ca_elem *Y);

#endif
