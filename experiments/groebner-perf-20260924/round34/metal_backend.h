#pragma once
#include <cstddef>
#include <cstdint>
void *multiplier_metal_create(uint32_t branches, uint32_t features, uint32_t equations);
void multiplier_metal_destroy(void *context);
const uint32_t *multiplier_metal_solve(void *context, const void *input, size_t bytes,
                                       double &device_seconds);
const char *multiplier_metal_device(void *context);
uint64_t multiplier_metal_bytes(void *context);
