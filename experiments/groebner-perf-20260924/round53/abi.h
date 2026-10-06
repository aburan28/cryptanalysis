#pragma once
#include "../round52/abi.h"

struct PreparationStats {
    uint64_t attempted = 0, ready = 0, used = 0, input_bytes = 0;
    uint64_t bound_words = 0, transform_xors = 0, guard_work = 0;
    uint64_t recomputed = 0, discarded = 0;
    uint64_t table_bytes = 0, mirror_words = 0, audit_words = 0, audit_xors = 0, audit_bytes = 0;
    double seconds = 0;
};
