#pragma once
#include <cstddef>
#include <cstdint>
#include <stdexcept>

namespace producer_transform
{
struct Unavailable : std::runtime_error {
    using std::runtime_error::runtime_error;
};
enum class Mode : uint32_t { staged = 1, tiled = 2 };
struct Stats {
    uint64_t logical_xors = 0, encoded_dispatches = 0, submitted_dispatches = 0,
             completed_dispatches = 0, dispatched_threads = 0, input_bytes = 0, output_bytes = 0,
             scratch_bytes = 0;
    double copy_in = 0, encode = 0, wait = 0, copy_out = 0, device = 0, wall = 0;
};
inline size_t extent(uint32_t variables, uint32_t stride)
{
    if (!variables || variables > 20 || stride < 2 || stride > 56)
        throw std::invalid_argument("producer transform shape");
    const size_t bytes = size_t(1u << variables) * stride * sizeof(uint32_t);
    if (bytes > (64u << 20)) throw std::length_error("producer transform exceeds 64 MiB");
    return bytes;
}
// Same ascending, branch-major order as round51's producer. This portable
// reference remains available independently of Metal capability.
inline void cpu(uint32_t *values, uint32_t variables, uint32_t stride)
{
    extent(variables, stride);
    if (!values) throw std::invalid_argument("producer transform null input");
    const uint32_t branches = 1u << variables;
    for (uint32_t bit = 1; bit < branches; bit <<= 1)
        for (uint32_t base = 0; base < branches; base += 2 * bit)
            for (uint32_t row = 0; row < bit; ++row) {
                auto *dst = values + size_t(base + bit + row) * stride;
                const auto *src = values + size_t(base + row) * stride;
                for (uint32_t feature = 0; feature < stride; ++feature)
                    dst[feature] ^= src[feature];
            }
}
// Owner serializes use and destruction. Only layout/pipelines/allocation persist;
// apply overwrites every input byte, waits, and copies every output byte back.
void *create(uint32_t variables, uint32_t stride, Mode mode);
void destroy(void *context);
const char *device(void *context);
void apply(void *context, void *values, size_t bytes, Stats &stats);
} // namespace producer_transform
