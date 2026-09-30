#pragma once
#include "../round35/abi.h"

struct DeferredStats {
    uint64_t inserted_pivots, dependency_toggles, reconstruction_attempts;
    uint64_t reconstruction_pivots, reconstruction_word_xors, reconstructed_proofs;
    uint64_t source_toggles, workspace_bytes;
    double reconstruction_seconds;
};
#ifndef DEFERRED_RECONSTRUCTION_BUDGET
#    define DEFERRED_RECONSTRUCTION_BUDGET MULTIPLIER_WORK_BUDGET
#endif
