// Public data format only. Producer and checker share no polynomial routines.
#pragma once
#include <stdint.h>

struct PackedInput {
    uint32_t nvars, equations;
    uint64_t terms;
    const uint64_t *masks;
    // Term-major equation bitsets, ceil(equations/64) little-endian limbs.
    const uint64_t *coefficients;
};
struct ProofNode {
    uint32_t op, a;
    uint64_t b;
}; // input=0, mul=1, xor=2
struct ProofView {
    uint32_t version, nvars, order, reserved; // version=1, order=1: grevlex x0 first
    uint64_t rows, terms, nodes;
    const uint64_t *basis_terms;
    const uint64_t *offsets; // rows+1 offsets into basis_terms
    const ProofNode *graph;
    const uint32_t *outputs; // one graph index per basis row
};
struct ProducerStats {
    uint64_t work, matrices, matrix_rows, peak_rows, pairs, nodes;
    double decode_seconds, produce_seconds, export_seconds, total_seconds;
    uint32_t status; // 0 produced, 1 invalid, 2 budget, 3 internal
};
struct CheckStats {
    uint64_t work, retained_terms, proof_nodes, generator_checks, basis_pairs;
    uint64_t product_pairs_skipped, field_pairs, reduction_steps;
    double decode_seconds, derivation_seconds, membership_seconds, reducedness_seconds;
    double completion_seconds, total_seconds;
};
