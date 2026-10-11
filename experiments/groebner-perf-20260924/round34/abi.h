#pragma once
#include "../round33/abi.h"

// Only metadata and bounds are shared. The two libraries implement their
// polynomial arithmetic and certificate construction/checking independently.
struct MultiplierStats {
    uint64_t attempts, certified_branches, failed_branches, budget_skips;
    uint64_t rows, row_xors, word_xors, avoided_assignments;
    uint64_t proof_words, proof_capacity_words, workspace_bytes;
    double seconds;
};
struct MultiplierCheckStats {
    uint64_t branches, contradictions, enumerated_branches, assignments;
    uint64_t roots, standard, work, workspace_bytes, proof_bytes, transform_xors;
    double specialization, contradiction_check, enumeration, basis_check;
    uint64_t extended_contradictions, multiplier_parities, multiplier_words;
    double multiplier_check;
};
#ifndef MULTIPLIER_WORK_BUDGET
#    define MULTIPLIER_WORK_BUDGET 67108864
#endif
#ifndef MULTIPLIER_BRANCH_BUDGET
#    define MULTIPLIER_BRANCH_BUDGET 65536
#endif
constexpr uint64_t MULTIPLIER_PROOF_WORDS_LIMIT = TABLE_BYTES_LIMIT / sizeof(uint64_t);
