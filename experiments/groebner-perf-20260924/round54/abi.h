#pragma once
#include "../round53/abi.h"

struct PartialReservationStats {
    uint64_t mode = 0, reservation_attempts = 0, reserved_rows = 0;
    uint64_t budget_fallbacks = 0, flushes = 0, exception_flushes = 0;
    uint64_t charged_words = 0, parity_words = 0, max_row_words = 0;
};
