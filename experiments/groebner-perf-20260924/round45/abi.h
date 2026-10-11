#pragma once
#include "../round44/abi.h"
struct SymmetryCheckStats {
    uint64_t requested = 0;
    uint64_t enabled = 0;
    uint64_t shape_fallback = 0;
    uint64_t workspace_fallback = 0;
    uint64_t budget_fallback = 0;
    uint64_t asymmetric_fallback = 0;
    uint64_t guard_terms = 0;
    uint64_t guard_pairs = 0;
    uint64_t guard_coefficients = 0;
    uint64_t proof_pairs = 0;
    uint64_t proof_words = 0;
    uint64_t proof_mismatches = 0;
    uint64_t representatives = 0;
    uint64_t inferred_aliases = 0;
    uint64_t constant_aliases = 0;
    uint64_t multiplier_aliases = 0;
    uint64_t partial_aliases = 0;
    uint64_t enumerated_aliases = 0;
    uint64_t derived_partial_rank = 0;
    uint64_t derived_partial_assignments = 0;
    uint64_t derived_partial_inconsistent = 0;
    uint64_t work = 0;
    uint64_t workspace_bytes = 0;
    uint64_t avoided_constant_parities = 0;
    uint64_t avoided_multiplier_parities = 0;
    uint64_t avoided_assignments = 0;
    double guard_seconds = 0;
};
#ifndef SYMMETRY_CHECK_WORK_BUDGET
#    define SYMMETRY_CHECK_WORK_BUDGET UINT64_C(67108864)
#endif
#ifndef SYMMETRY_CHECK_AUX_BYTES
#    define SYMMETRY_CHECK_AUX_BYTES UINT64_C(8388608)
#endif
