#pragma once
#include <stdint.h>

// Durations are exclusive and cover one seeded_produce call. The C API below
// returns a thread-local snapshot valid until that thread calls it again.
struct SeededPhaseStats {
    uint64_t preparation_ns;
    uint64_t f4_ns;
    uint64_t packing_ns;
    uint64_t composition_ns;
    uint64_t finalization_ns;
    uint64_t total_ns;
    uint32_t completed;
    uint32_t stage_at_exit;
};

extern "C" const SeededPhaseStats *seeded_last_phases();
