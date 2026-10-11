#pragma once
#include <cstdint>

namespace constant_identity
{
struct Stats {
    uint64_t requested = 0, used = 0, workspace_bytes = 0, prepared_words = 0;
    uint64_t features = 0, avoided_parities = 0, audit_features = 0;
    double preparation_seconds = 0, seconds = 0;
};
} // namespace constant_identity
