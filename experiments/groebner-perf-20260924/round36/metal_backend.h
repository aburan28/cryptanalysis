#pragma once
#include <cstddef>
#include <cstdint>
void *deferred_metal_create(uint32_t branches, uint32_t features, uint32_t equations);
void deferred_metal_destroy(void *context);
const uint32_t *deferred_metal_solve(void *context, const void *input, size_t bytes,
                                     double &device_seconds);
const char *deferred_metal_device(void *context);
uint64_t deferred_metal_bytes(void *context);
