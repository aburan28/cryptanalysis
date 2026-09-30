#pragma once
#include "../round34/abi.h"

// The checker and proof wire format remain round34's. This is diagnostics
// for actual representative work and fully expanded certificate output.
struct SymmetryStats {
    uint64_t enabled, shape_fallback, asymmetric_fallback;
    uint64_t compared_pairs, compared_coefficients;
    uint64_t representatives, aliases, constant_copies, affine_copies;
    uint64_t affine_copy_words, copy_budget_skips, copied_roots, rootless_aliases;
    uint64_t gpu_linearized_branches, workspace_bytes;
    double check_seconds, expand_seconds;
};
#ifndef SYMMETRY_COPY_WORDS_BUDGET
#    define SYMMETRY_COPY_WORDS_BUDGET MULTIPLIER_PROOF_WORDS_LIMIT
#endif
