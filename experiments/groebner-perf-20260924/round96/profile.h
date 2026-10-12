#pragma once
#include <cstdint>
#include <limits>

// Diagnostic attribution of the existing logical budget, not CPU operations.
enum class WorkStage : uint64_t {
    Decode,
    Compute,
    Canonical,
    Multiply,
    Add,
    OrderedMultiple,
    OrderedAdd,
    Normal,
    Install,
    Chain,
    Symbolic,
    Column,
    Packed,
    Sparse,
    Compaction,
    Count
};
constexpr uint64_t work_stage_count = static_cast<uint64_t>(WorkStage::Count);
struct WorkProfile {
    uint64_t exclusive[work_stage_count]{};
    uint64_t inclusive[work_stage_count]{};
    uint64_t calls[work_stage_count]{};
    uint64_t overflow = 0, active = 0, depth = 0, peak_depth = 0;
};
static thread_local WorkProfile work_profile{};

inline void profile_add(uint64_t &destination, uint64_t amount) noexcept
{
    if (amount > std::numeric_limits<uint64_t>::max() - destination) {
        destination = std::numeric_limits<uint64_t>::max();
        work_profile.overflow = 1;
    } else {
        destination += amount;
    }
}
inline void profile_charge(uint64_t amount) noexcept
{
    profile_add(work_profile.exclusive[work_profile.active], amount);
}
struct WorkScope {
    const uint64_t &work;
    uint64_t before, stage, previous;
    WorkScope(WorkStage category, const uint64_t &counter) noexcept
        : work(counter), before(counter), stage(static_cast<uint64_t>(category)),
          previous(work_profile.active)
    {
        work_profile.active = stage;
        profile_add(work_profile.calls[stage], 1);
        profile_add(work_profile.depth, 1);
        if (work_profile.depth > work_profile.peak_depth)
            work_profile.peak_depth = work_profile.depth;
    }
    ~WorkScope() noexcept
    {
        if (work < before)
            work_profile.overflow = 1;
        else
            profile_add(work_profile.inclusive[stage], work - before);
        work_profile.active = previous;
        --work_profile.depth;
    }
    WorkScope(const WorkScope &) = delete;
    WorkScope &operator=(const WorkScope &) = delete;
};
