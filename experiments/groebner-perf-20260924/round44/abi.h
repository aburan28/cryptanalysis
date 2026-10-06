#pragma once
#include "../round36/abi.h"

// A record's low bits identify a branch. Its high bit distinguishes affine
// consequences from the old degree-one multiplier contradiction. The checker
// derives the consequences and their rank independently from original ANFs.
constexpr uint64_t PARTIAL_AFFINE_RECORD = UINT64_C(1) << 63;

struct PartialProduceStats {
    uint64_t attempts = 0, handled_branches = 0, rank_sum = 0;
    uint64_t assignments = 0, equation_word_xors = 0, roots_found = 0;
    uint64_t proof_rows = 0, proof_words = 0, copied_records = 0;
    uint64_t budget_skips = 0, stack_bytes = 0;
    double seconds = 0;
};

struct PartialCheckStats {
    uint64_t records = 0, checked_rows = 0, witness_parities = 0;
    uint64_t row_xors = 0, rank_sum = 0, inconsistent = 0;
    uint64_t assignments = 0, work = 0, stack_bytes = 0;
    double seconds = 0;
};

#ifndef PARTIAL_CHECK_WORK_BUDGET
#    define PARTIAL_CHECK_WORK_BUDGET 67108864
#endif
