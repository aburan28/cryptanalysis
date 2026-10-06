// Test-only raw device output. No query uses this ABI or trusts its ranks.
#include "metal_backend.h"
#include <stdexcept>
#include <string>
static thread_local std::string error;
extern "C" const char *probe_error() { return error.c_str(); }
extern "C" void *probe_create(uint32_t branches, uint32_t variables, uint32_t equations)
{
    try {
        return compact_metal_create(branches, variables * (variables + 1) / 2, equations,
                                    variables);
    } catch (const std::exception &e) {
        error = e.what();
        return nullptr;
    }
}
extern "C" void probe_destroy(void *context) { compact_metal_destroy(context); }
extern "C" const char *probe_device(void *context) { return compact_metal_device(context); }
extern "C" const uint64_t *probe_solve(void *context, const uint32_t *input, uint64_t bytes,
                                       uint32_t symmetric, uint32_t projection)
{
    try {
        if (!context || symmetric > 1 || projection > 1)
            throw std::invalid_argument("invalid probe arguments");
        double unused = 0;
        compact_metal_solve(context, input, bytes, symmetric, projection, unused);
        return compact_metal_projection(context);
    } catch (const std::exception &e) {
        error = e.what();
        return nullptr;
    }
}
