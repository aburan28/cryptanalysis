#pragma once
#include <cstddef>
#include <cstdint>
#include <stdexcept>

struct IndependentMetalUnavailable : std::runtime_error {
    using std::runtime_error::runtime_error;
};

struct DeviceTransformStats {
    uint64_t requested = 0, executed = 0, dispatches = 0;
    uint64_t input_bytes = 0, output_bytes = 0, scratch_bytes = 0;
    uint64_t kernel_mode = 0, fused_stages = 0;
    double copy_in = 0, encode = 0, wait = 0, copy_out = 0, device = 0, seconds = 0;
};

// The owner serializes calls and destruction. Contexts retain ring layout and
// scratch capacity only. Every invocation replaces every input byte.
void *independent_metal_create(uint32_t variables, uint32_t slices, uint32_t word_bits,
                               bool fused = false);
void independent_metal_destroy(void *context);
const char *independent_metal_device(void *context);
void independent_metal_transform(void *context, void *values, size_t bytes,
                                 DeviceTransformStats &stats);
