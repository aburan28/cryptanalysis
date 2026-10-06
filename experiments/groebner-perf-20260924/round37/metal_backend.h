#pragma once
#include <cstddef>
#include <cstdint>
void *fixed_width_metal_create(uint32_t branches, uint32_t features, uint32_t equations);
void fixed_width_metal_destroy(void *context);
const uint32_t *fixed_width_metal_solve(void *context, const void *input, size_t bytes,
                                        double &device_seconds);
const char *fixed_width_metal_device(void *context);
uint64_t fixed_width_metal_bytes(void *context);
