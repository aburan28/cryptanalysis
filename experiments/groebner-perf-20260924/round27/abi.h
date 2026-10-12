#pragma once
#include <cstdint>

// Shared representation only. Producer and checker use separate elimination.
struct BranchStats {
    uint64_t branches, consistent, roots, standard, work;
    double evaluation, interpolation;
};
constexpr uint32_t ROOT_LIMIT = 256;
constexpr uint32_t TERM_LIMIT = 1000000;
#ifndef CONDITIONAL_PROOF_BUDGET
#    define CONDITIONAL_PROOF_BUDGET 1000000
#endif
constexpr uint64_t PROOF_BUDGET = CONDITIONAL_PROOF_BUDGET;
