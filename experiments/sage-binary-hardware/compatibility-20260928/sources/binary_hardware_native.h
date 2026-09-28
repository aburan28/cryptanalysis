// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>
#include <string>
#ifdef _WIN32
#define BH_EXPORT __declspec(dllexport)
#else
#define BH_EXPORT __attribute__((visibility("default")))
#endif
void bh_set_error(const std::string& message);
extern "C" {
BH_EXPORT const char* bh_last_error();
BH_EXPORT int bh_cpu_apply(const uint32_t*, const uint32_t*, uint32_t*,
                           uint64_t, uint32_t, uint32_t, uint32_t);
BH_EXPORT void* bh_metal_create(const char*, const uint32_t*, uint32_t, uint32_t, uint32_t);
BH_EXPORT void bh_metal_destroy(void*);
BH_EXPORT const char* bh_metal_name(void*);
BH_EXPORT int bh_metal_apply(void*, const uint32_t*, uint32_t*, uint64_t, double*);
}
