#include "transform.h"
namespace producer_transform
{
void *create(uint32_t variables, uint32_t stride, Mode mode)
{
    extent(variables, stride);
    if (mode != Mode::staged && mode != Mode::tiled)
        throw std::invalid_argument("producer transform mode");
    throw Unavailable("producer transform built without Metal");
}
void destroy(void *) {}
const char *device(void *) { return "unavailable"; }
void apply(void *, void *, size_t, Stats &stats)
{
    stats = {};
    throw Unavailable("producer transform built without Metal");
}
} // namespace producer_transform
