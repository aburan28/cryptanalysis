#include "metal_transform.h"
#include <stdexcept>

void *independent_metal_create(uint32_t, uint32_t, uint32_t, bool)
{
    throw IndependentMetalUnavailable("independent Metal transform unavailable in this build");
}
void independent_metal_destroy(void *) {}
const char *independent_metal_device(void *p) { return p ? "unavailable" : "cpu"; }
void independent_metal_transform(void *, void *, size_t, DeviceTransformStats &)
{
    throw IndependentMetalUnavailable("independent Metal transform unavailable in this build");
}
