// Native continuation takes borrowed views for the duration of one call.
// Returned handles own their data. A produced candidate still requires checking.
#pragma once
#include "proof_abi.h"

struct CompositionStats {
    uint64_t work, seed_nodes, continuation_nodes, combined_nodes;
    uint64_t retained_nodes, retained_outputs;
};
struct SeededStats {
    uint64_t work, bridge_work, scan_work, f4_started, composition_started;
    uint64_t reserved_seed_nodes, status;
    ProducerStats producer;
    CompositionStats composition;
    double total_seconds;
};

extern "C" {
void *seeded_produce(const PackedInput *, const ProofView *, uint64_t max_work, uint32_t max_nodes,
                     uint32_t max_rows, uint32_t batch, uint32_t capture_continuation,
                     SeededStats *);
void *seeded_compose(const ProofView *, const ProofView *, uint32_t originals, uint64_t max_work,
                     uint32_t max_nodes, CompositionStats *, uint32_t *status);
const ProofView *seeded_view(void *);
const ProofView *seeded_continuation_view(void *);
void seeded_destroy(void *);
const char *seeded_error();
uint64_t seeded_stats_size();
uint64_t seeded_composition_stats_size();
}
