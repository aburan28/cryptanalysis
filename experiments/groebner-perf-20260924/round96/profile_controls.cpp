#include "profiled_engine.inc"
#include <cassert>
#include <iostream>
#include <thread>

static uint64_t total()
{
    uint64_t value = 0;
    for (auto amount : work_profile.exclusive) value += amount;
    return value;
}
int main()
{
    work_profile = {};
    Engine engine(5, 100, 100, 1, true);
    {
        WorkScope outer(WorkStage::Compute, engine.work);
        engine.charge(1);
        try {
            WorkScope inner(WorkStage::Normal, engine.work);
            engine.charge_ones_product(2, 3);
            assert(false);
        } catch (const Budget &) {
        }
    }
    assert(engine.work == 5 && total() == 5);
    assert(work_profile.exclusive[static_cast<size_t>(WorkStage::Compute)] == 1);
    assert(work_profile.inclusive[static_cast<size_t>(WorkStage::Compute)] == 5);
    assert(work_profile.exclusive[static_cast<size_t>(WorkStage::Normal)] == 4);
    assert(work_profile.depth == 0 && work_profile.active == 0 && work_profile.peak_depth == 2);
    assert(!work_profile.overflow);
    work_profile = {};
    Engine atomic(5, 100, 100, 1, true);
    atomic.charge(4);
    try {
        atomic.charge(2);
        assert(false);
    } catch (const Budget &) {
    }
    assert(atomic.work == 4 && total() == 4);
    // Zero multiplicands and exact-limit products preserve the original budget.
    atomic.charge_ones_product(0, UINT64_MAX);
    atomic.charge_ones_product(1, 1);
    assert(atomic.work == 5 && total() == 5);
    std::thread other([] {
        assert(total() == 0 && work_profile.depth == 0);
        Engine local(9, 100, 100, 1, true);
        local.charge(9);
        assert(total() == 9);
    });
    other.join();
    assert(total() == 5);
    uint64_t saturated = UINT64_MAX - 1;
    profile_add(saturated, 2);
    assert(saturated == UINT64_MAX && work_profile.overflow == 1);
    std::cout << "PROFILE_CONTROLS_PASS\n";
}
