#pragma once
#include "../round48/abi.h"

struct PartialLocalityStats {
    uint64_t mode = 0, records = 0, copied_records = 0;
    uint64_t table_loads = 0, cached_loads = 0, copy_words = 0;
    uint64_t cache_stack_bytes = 0, audit_words = 0;
};
