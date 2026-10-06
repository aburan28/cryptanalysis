#pragma once
#include <chrono>

// All counters concern this proof call. Dense fallback remains exact.
struct ProofStats {
    uint32_t mode, root_list_used, staircase_used, fallback_reason;
    uint64_t root_blocks_scanned, root_parity_tests, divisibility_tests;
    uint64_t standard_visited, workspace_bytes, dense_table_bytes, budget_limit;
    double seconds;
};

struct ProofStorage {
    std::array<uint32_t, 256> roots{};
    std::array<uint32_t, 256> standard{};
    std::vector<uint32_t> leading;
};

#ifndef SPARSE_PROOF_BUDGET
#define SPARSE_PROOF_BUDGET 65536
#endif
