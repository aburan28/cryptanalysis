#pragma once
#include <cstddef>
#include <cstdint>
void *compact_metal_create(uint32_t branches, uint32_t features, uint32_t equations,
                           uint32_t variables);
void compact_metal_destroy(void *context);
const uint64_t *compact_metal_solve(void *context, const void *input, size_t bytes, bool symmetric,
                                    bool projection, double &device_seconds);
const char *compact_metal_device(void *context);
uint64_t compact_metal_bytes(void *context);
uint64_t compact_metal_dispatched_branches(void *context);
const uint64_t *compact_metal_projection(void *context);
uint64_t compact_metal_projection_bytes(void *context);
