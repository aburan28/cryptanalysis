#pragma once
#include <cstdint>

struct BranchStats {
    uint64_t branches, consistent, roots, standard, work;
    uint64_t lifted_candidates, fallback_branches, fallback_assignments;
    uint64_t max_nullity, features, workspace_bytes, transform_xors;
    uint64_t gpu_used, gpu_shape_fallback;
    double specialization, evaluation, interpolation, gpu_wall, gpu_device;
};
constexpr uint32_t ROOT_LIMIT = 256;
constexpr uint32_t TERM_LIMIT = 1000000;
constexpr uint64_t TABLE_BYTES_LIMIT = UINT64_C(64) << 20;
#ifndef QUADRATIC_ENUMERATION_BUDGET
#    define QUADRATIC_ENUMERATION_BUDGET 4194304
#endif
constexpr uint64_t ENUMERATION_BUDGET = QUADRATIC_ENUMERATION_BUDGET;
