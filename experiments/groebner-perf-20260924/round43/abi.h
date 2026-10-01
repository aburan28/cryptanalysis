#ifndef PARTIAL_AFFINE_ABI_H
#define PARTIAL_AFFINE_ABI_H
#include <cstdint>

// Witness rows contain equation bits only; no rank or root claim is trusted.
// Columns are original packed ANF coefficients; duplicate terms XOR together.
// All returned outputs are atomic: an unsuccessful call leaves output_count=0.
enum PartialStatus : int {
    PARTIAL_OK = 0,
    PARTIAL_INVALID = 1,
    PARTIAL_NONLINEAR = 2,
    PARTIAL_BUDGET = 3,
    PARTIAL_CAPACITY = 4,
    PARTIAL_INTERNAL = 5,
};

struct PartialStats {
    uint64_t input_terms = 0;
    uint64_t input_word_xors = 0;
    uint64_t elimination_row_xors = 0;
    uint64_t witness_parities = 0;
    uint64_t affine_row_xors = 0;
    uint64_t assignments = 0;
    uint64_t equation_word_xors = 0;
    uint64_t work = 0;
    uint64_t workspace_bytes = 0;
    uint64_t witness_rows = 0;
    uint64_t rank = 0;
    uint64_t inconsistent = 0;
};

// Each library exposes its own create/destroy functions and owns its workspace.
// Producer and checker are compiled separately and share only this ABI.
extern "C" uint64_t partial_stats_size();
extern "C" void *partial_create(uint32_t variables, uint32_t equations);
extern "C" void partial_destroy(void *context);
extern "C" int partial_produce(void *context, const uint32_t *masks, const uint64_t *coefficients,
                               uint32_t terms, uint64_t work_budget, uint64_t *witnesses,
                               uint32_t witness_capacity, uint32_t *witness_count,
                               PartialStats *stats);
extern "C" int partial_check(void *context, const uint32_t *masks, const uint64_t *coefficients,
                             uint32_t terms, const uint64_t *witnesses, uint32_t witness_count,
                             uint64_t work_budget, uint32_t assignment_budget, uint32_t *roots,
                             uint32_t root_capacity, uint32_t *root_count, PartialStats *stats);
#endif
