#pragma once
#include "../round67/transform.h"

struct ProducerTransformStats {
    uint64_t requested_mode = 0, executed_mode = 0, generation = 0, projection_reused_bytes = 0,
             projection_uploaded_bytes = 0, additional_table_bytes = 0;
    producer_transform::Stats kernel{};
};

namespace producer_transform
{
// Objective-C strong references retained internally. The caller supplies the
// existing producer device, ordinary queue and explicitly tracked shared buffer.
void *create_borrowed(uint32_t variables, uint32_t stride, Mode mode, void *device, void *queue,
                      void *buffer);
} // namespace producer_transform

void compact_metal_configure_transform(void *context, uint32_t mode);
uint64_t compact_metal_begin(void *context);
void compact_metal_invalidate(void *context) noexcept;
void compact_metal_transform(void *context, void *values, size_t bytes, uint64_t generation,
                             producer_transform::Stats &stats);
const uint64_t *compact_metal_solve_prepared(void *context, const void *input, size_t bytes,
                                             bool symmetric, bool projection, uint64_t generation,
                                             double &device_seconds);

// The producer holds its existing mutex throughout this scope. Every exit,
// including failed validation, failed GPU work and later proof-budget failures,
// revokes any device-table readiness from this invocation.
struct ProducerTransformCall {
    void *context;
    uint64_t generation;
    explicit ProducerTransformCall(void *p) : context(p), generation(p ? compact_metal_begin(p) : 0)
    {
    }
    ~ProducerTransformCall() { compact_metal_invalidate(context); }
    ProducerTransformCall(const ProducerTransformCall &) = delete;
    ProducerTransformCall &operator=(const ProducerTransformCall &) = delete;
};
