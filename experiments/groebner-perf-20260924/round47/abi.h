#pragma once
#include "../round45/abi.h"
struct TransformCheckStats {
    uint64_t requested_mode = 0, selected_mode = 0;
    uint64_t shape_fallback = 0, symmetry_fallback = 0;
    uint64_t slices = 0, word_bits = 0;
    uint64_t full_xors = 0, actual_xors = 0, mirror_words = 0;
    uint64_t audit_words = 0, audit_bytes = 0, audit_xors = 0;
    double seconds = 0;
};
