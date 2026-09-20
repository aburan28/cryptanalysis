/*
 * ca_curve.h - curve-aware dispatch: name or parameters in, the optimised
 * solver out.
 *
 * Some elliptic curves over F_p carry an efficiently computable endomorphism
 * psi(P) = lambda * P (the GLV endomorphism) beyond the always-present
 * negation.  Folding the Pollard rho walk by the automorphism group it
 * generates shrinks the search space and so the operation count:
 *
 *   j-invariant 0     (y^2 = x^3 + b, p = 1 mod 3): psi(x, y) = (beta x, -y),
 *                     an order-6 automorphism group (sqrt 6 fewer operations);
 *   j-invariant 1728  (y^2 = x^3 + a x, p = 1 mod 4): psi(x, y) = (-x, i y),
 *                     an order-4 automorphism group (sqrt 4 fewer operations).
 *
 * (The Frobenius speedup on binary Koblitz curves is the same idea over an
 * extension field; that lives in the fpga/ tree, this core being F_p only.)
 *
 * ca_curve_detect reports the structure from parameters; ca_curve_group
 * builds a group with the endomorphism enabled when it applies; and
 * ca_curve_solve dispatches to the GLV-accelerated rho or, for a generic
 * curve, the negation-map rho -- so a caller just names a curve (or passes
 * p, a, b, order) and gets the fastest available path.
 */
#ifndef CA_CURVE_H
#define CA_CURVE_H

#include "ca_group.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum ca_curve_endo {
    CA_CURVE_ENDO_NONE = 0,  /* generic: only the order-2 negation map */
    CA_CURVE_ENDO_J0 = 1,    /* y^2 = x^3 + b, j = 0: order-6 automorphism */
    CA_CURVE_ENDO_J1728 = 2, /* y^2 = x^3 + a x, j = 1728: order-4 automorphism */
} ca_curve_endo;

typedef struct ca_curve_info {
    ca_curve_endo endo;
    uint32_t aut_order; /* automorphism group the rho walk folds by (2, 4 or 6) */
    uint64_t beta;      /* field constant: cube root of unity (j0) or sqrt(-1) (j1728) mod p */
    uint64_t lambda;    /* psi(P) = lambda * P (mod order); 0 if order unknown or degenerate */
    double rho_speedup; /* sqrt(aut_order): the rho operation-count factor vs a plain sqrt(n) */
    char name[32];      /* registry name, or "" */
} ca_curve_info;

/* Detect the endomorphism structure of y^2 = x^3 + a x + b over F_p for the
 * subgroup of order `order` (0 => leave lambda / rho_speedup unresolved but
 * still report the geometric structure).  Never fails for a valid curve. */
CA_API ca_status ca_curve_detect(uint64_t p, uint64_t a, uint64_t b, uint64_t order,
                                 ca_curve_info *out);

/* Named registry of example curves (one per family).  Fills whichever of
 * p, a, b, order are non-NULL; returns CA_ERR_NOT_FOUND for an unknown name.
 * ca_curve_list writes up to `cap` names and returns the total count. */
CA_API ca_status ca_curve_by_name(const char *name, uint64_t *p, uint64_t *a, uint64_t *b,
                                  uint64_t *order);
CA_API size_t ca_curve_list(const char **names, size_t cap);

/* Initialise `g` for y^2 = x^3 + a x + b over F_p with the given subgroup
 * order and, when the curve has an efficiently computable endomorphism and
 * `order` is a compatible prime, enable it (so ca_curve_solve folds the walk).
 * Fills *info when non-NULL. */
CA_API ca_status ca_curve_group(ca_group *g, uint64_t p, uint64_t a, uint64_t b, uint64_t order,
                                ca_curve_info *info);

/* Solve base^x == target (x in [0, order)) with the optimised solver for the
 * curve: the GLV endomorphism-accelerated rho when `g` carries one, else the
 * negation-map rho.  *info (when non-NULL) reports which path ran. */
CA_API ca_status ca_curve_solve(const ca_group *g, const ca_elem *base, const ca_elem *target,
                                uint64_t seed, uint64_t *x, ca_curve_info *info, ca_stats *st);

#ifdef __cplusplus
}
#endif
#endif /* CA_CURVE_H */
