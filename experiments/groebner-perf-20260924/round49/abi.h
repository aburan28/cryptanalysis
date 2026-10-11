#pragma once
#include "../round44/abi.h"

struct GPUProjectionStats {
    uint64_t requested = 0, enabled = 0, dispatched_branches = 0, consumed_branches = 0;
    uint64_t affine_rows = 0, output_bytes = 0, consumed_row_xors = 0;
};
