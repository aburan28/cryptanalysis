#pragma once
#include "../round47/abi.h"
struct IdentityCheckStats {
    uint64_t mode = 0, attempted_records = 0, reused_records = 0;
    uint64_t dense_equivalent_parities = 0, parities = 0;
    uint64_t ands = 0, accumulator_xors = 0, witness_xors = 0, identity_xors = 0;
    uint64_t table_loads = 0, cached_loads = 0, copy_words = 0;
    uint64_t layout_bytes = 0, cache_stack_bytes = 0, identity_stack_bytes = 0;
    uint64_t audit_records = 0, audit_coefficients = 0, audit_parities = 0;
};
