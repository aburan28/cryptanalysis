#pragma once
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>
#include "../round48/multiplier.h"

namespace multiplier_gpu
{
constexpr uint32_t valid_identity = UINT32_MAX;
struct Group {
    uint32_t mask = 0, main = UINT32_MAX, degree = 0;
    uint32_t feature[3]{}, slot[3]{};
};
static_assert(sizeof(Group) == 9 * sizeof(uint32_t));
struct Shape {
    uint32_t x, y, equations, limbs, word_bits, branches, features, groups;
    size_t coefficient_bytes, capacity;
    std::vector<uint32_t> masks;
    std::vector<Group> layout;
    independent_identity::Layout cpu_layout;
    Shape(uint32_t x, uint32_t y, uint32_t equations, size_t capacity);
};
struct Input {
    const void *coefficients;
    size_t coefficient_bytes;
    const uint32_t *branches;
    size_t records;
    const uint64_t *witnesses;
    size_t witness_words;
};
struct Output {
    uint32_t *first_bad;
    size_t records;
    // Optional dense-by-group identity output, record-major, for exact audits.
    uint8_t *coefficients = nullptr;
    size_t coefficient_bytes = 0;
};
struct Stats {
    uint64_t records = 0, coefficient_checks = 0, first_invalid_record = UINT64_MAX;
    uint64_t records_after_first_invalid = 0, input_bytes = 0, output_bytes = 0;
    uint64_t dispatched_threads = 0, submitted_dispatches = 0, completed_dispatches = 0;
    uint64_t coefficient_table_bytes = 0, witness_bytes = 0, index_bytes = 0;
    uint64_t result_bytes = 0, materialized_bytes = 0, workspace_bytes = 0;
    uint64_t initialized_bytes = 0;
    double validation = 0, copy_in = 0, encode = 0, wait = 0, copy_out = 0, device = 0, wall = 0;
};
struct Unavailable : std::runtime_error {
    using std::runtime_error::runtime_error;
};
void validate(const Shape &, const Input &, const Output &);
void finish_stats(const Shape &, const Input &, const Output &, Stats &);
uint64_t coefficient(const Shape &, const Input &, uint32_t feature, uint32_t limb,
                     uint32_t branch);
// Numeric-mask dense multiplication oracle, distinct from the GPU formula.
void oracle(const Shape &, const Input &, const Output &, Stats &);
// Existing factored/local CPU checker; same complete-operation interface.
void cpu(const Shape &, const Input &, const Output &, Stats &);
void *create(uint32_t x, uint32_t y, uint32_t equations, size_t capacity);
void destroy(void *);
const char *device(void *);
// mode 1: one thread/record; mode 2: one thread/output coefficient.
void check(void *, uint32_t mode, const Input &, const Output &, Stats &);
} // namespace multiplier_gpu
