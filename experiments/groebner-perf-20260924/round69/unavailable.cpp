#include "api.h"
namespace multiplier_gpu
{
void *create(uint32_t x, uint32_t y, uint32_t e, size_t capacity)
{
    Shape shape(x, y, e, capacity);
    throw Unavailable("independent multiplier Metal unavailable");
}
void destroy(void *) {}
const char *device(void *) { return "unavailable"; }
void check(void *, uint32_t, const Input &, const Output &, Stats &stats)
{
    stats = {};
    throw Unavailable("independent multiplier Metal unavailable");
}
} // namespace multiplier_gpu
