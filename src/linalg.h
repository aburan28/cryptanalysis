/*
 * linalg.h - sparse linear algebra modulo a prime (internal).
 *
 * Systems arising from index calculus: many rows (relations), each with a
 * few small integer coefficients, unknowns = logarithms.  We solve
 * A x == b (mod q) for a prime q with structured Gaussian elimination
 * (singleton removal with back-substitution) followed by the Lanczos
 * iteration on A^T D A, falling back to dense elimination for small
 * systems.
 */
#ifndef CA_LINALG_H
#define CA_LINALG_H

#include "cryptanalysis/ca_types.h"

/* Sparse matrix in CSR form; values are small signed integers. */
typedef struct ca_spmat {
    uint32_t rows, cols;
    uint32_t *row_ptr;   /* rows + 1 */
    uint32_t *col;       /* nnz */
    int32_t *val;        /* nnz */
    uint32_t nnz, cap;   /* cap: slots allocated for col/val */
    size_t row_cap;      /* slots allocated for row_ptr */
} ca_spmat;

ca_status ca_spmat_init(ca_spmat *m, uint32_t cols, uint32_t expected_rows, uint32_t expected_nnz);
void ca_spmat_free(ca_spmat *m);
/* Append a row given (col, val) pairs; duplicate columns are merged. */
ca_status ca_spmat_add_row(ca_spmat *m, const uint32_t *cols, const int32_t *vals, uint32_t n);

typedef struct ca_linsolve_report {
    uint32_t active_rows, active_cols;   /* after structured elimination */
    uint32_t lanczos_iters;
    uint32_t attempts;
    int used_dense;
    double seconds;
} ca_linsolve_report;

/*
 * Solve A x == b (mod q), q an odd prime.  x has A->cols entries;
 * known[j] is set to 1 for every unknown that was determined.  Unknowns
 * that do not appear in any row (or only in rows that cannot be resolved)
 * are left with known[j] == 0.  b entries are taken modulo q.
 */
ca_status ca_linsolve_mod_prime(const ca_spmat *A, const uint64_t *b, uint64_t q, uint64_t *x,
                                uint8_t *known, uint64_t seed, ca_linsolve_report *rep);

/* Dense Gaussian elimination mod q on an n x n (+rhs) system given as a
 * row-major array; returns CA_ERR_SINGULAR if not uniquely solvable.  Used
 * as a fallback and for tests. */
ca_status ca_dense_solve_mod_prime(uint64_t *M, uint32_t n, uint64_t *rhs, uint64_t q, uint64_t *x);

#endif
