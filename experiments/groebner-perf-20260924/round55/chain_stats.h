#pragma once
#include <cstdint>
#ifndef CHECKED_CHAIN_MODE
#define CHECKED_CHAIN_MODE 1
#endif
#ifndef CHAIN_SCAN_LIMIT
#define CHAIN_SCAN_LIMIT 64
#endif
#ifndef CHAIN_PROBE_LIMIT
#define CHAIN_PROBE_LIMIT 2
#endif
#ifndef CHAIN_PROBE_WORK
#define CHAIN_PROBE_WORK 4096
#endif
#ifndef CHAIN_CACHE_LIMIT
#define CHAIN_CACHE_LIMIT 65536
#endif
struct ChainStats {
    uint64_t mode = 0, candidate_pairs = 0, scanned_leaders = 0, eligible_chains = 0;
    uint64_t pruned_pairs = 0, represented_pairs_skipped = 0, field_pairs = 0;
    uint64_t probes = 0, probe_zero = 0, probe_nonzero = 0, probe_soft_limits = 0;
    uint64_t probe_aborted = 0, probe_work = 0, peak_probe_nodes = 0;
    uint64_t cache_hits = 0, product_hits = 0, failed_probe_hits = 0;
    uint64_t represented_entries = 0, failed_entries = 0, cache_saturated = 0;
    uint64_t raw_zero_pairs = 0, overhead_work = 0;
};
static thread_local ChainStats chain_stats{};
