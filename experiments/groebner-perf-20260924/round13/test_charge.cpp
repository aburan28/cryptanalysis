// Check exact logical budget semantics, including multiplication overflow.
#include "build/frontier.inc"
#include <cassert>

static bool grouped(Engine& engine, uint64_t a, uint64_t b) {
    try {
        engine.charge_ones_product(a, b);
        return true;
    } catch (const Budget&) {
        return false;
    }
}

int main() {
    uint64_t cases = 0;
    for (uint64_t limit = 0; limit < 32; ++limit) {
        for (uint64_t initial = 0; initial <= limit; ++initial) {
            for (uint64_t a = 0; a < 16; ++a) {
                for (uint64_t b = 0; b < 16; ++b) {
                    Engine original(limit, 100, 100, 1, false);
                    Engine candidate(limit, 100, 100, 1, false);
                    original.work = candidate.work = initial;
                    bool complete = true;
                    try {
                        for (uint64_t i = 0; i < a; ++i)
                            for (uint64_t j = 0; j < b; ++j)
                                original.charge();
                    } catch (const Budget&) {
                        complete = false;
                    }
                    assert(grouped(candidate, a, b) == complete);
                    assert(candidate.work == original.work);
                    ++cases;
                }
            }
        }
    }
    const uint64_t top = UINT64_MAX;
    struct Wide { uint64_t initial, a, b, final; bool complete; };
    const Wide wide[] = {
        {0, top, 1, top, true}, {0, top, 2, top, false},
        {0, top, top, top, false}, {0, uint64_t(1) << 63, 2, top, false},
        {top, 0, top, top, true}, {top, top, 0, top, true},
        {top, 1, 1, top, false}, {top - 5, 2, 2, top - 1, true},
        {top - 5, 2, 3, top, false}, {top - 5, 1, 5, top, true}
    };
    for (const auto& item : wide) {
        Engine candidate(top, 100, 100, 1, false);
        candidate.work = item.initial;
        assert(grouped(candidate, item.a, item.b) == item.complete);
        assert(candidate.work == item.final);
        ++cases;
    }
    Engine all_or_nothing(3, 100, 100, 1, false);
    all_or_nothing.work = 2;
    try { all_or_nothing.charge(2); assert(false); }
    catch (const Budget&) { assert(all_or_nothing.work == 2); }
    std::cout << "{\"budget_cases\":" << cases << "}\n";
}
