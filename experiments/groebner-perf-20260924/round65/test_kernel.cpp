#include "metal_transform.h"
#include <algorithm>
#include <iostream>
#include <memory>
#include <random>
#include <stdexcept>
#include <vector>

[[maybe_unused]] static void require(bool condition, const char *message)
{
    if (!condition) throw std::runtime_error(message);
}
template <typename Word>
static size_t control(uint32_t x, uint32_t slices, std::mt19937_64 &rng, bool fused)
{
    const uint32_t n = 1u << x;
    std::unique_ptr<void, decltype(&independent_metal_destroy)> ctx(
        independent_metal_create(x, slices, sizeof(Word) * 8, fused), independent_metal_destroy);
    size_t cases = 0;
    for (unsigned pattern = 0; pattern < 4; ++pattern) {
        std::vector<Word> input(size_t(n) * slices), expected(input.size());
        for (size_t i = 0; i < input.size(); ++i)
            input[i] = pattern == 0   ? 0
                       : pattern == 1 ? Word(~Word(0))
                       : pattern == 2 ? Word(rng())
                                      : (i % 97 == 0 ? Word(1) << (i % (8 * sizeof(Word))) : 0);
        if (x <= 8) {
            // Independent definition: evaluate ANF by enumerating every subset.
            for (uint32_t s = 0; s < slices; ++s)
                for (uint32_t m = 0; m < n; ++m) {
                    uint32_t subset = m;
                    for (;;) {
                        expected[size_t(s) * n + m] ^= input[size_t(s) * n + subset];
                        if (!subset) break;
                        subset = (subset - 1) & m;
                    }
                }
        } else {
            expected = input;
            // Ascending CPU order differs from the descending GPU order.
            for (uint32_t s = 0; s < slices; ++s)
                for (uint32_t bit = 1; bit < n; bit <<= 1)
                    for (uint32_t m = 0; m < n; ++m)
                        if (m & bit)
                            expected[size_t(s) * n + m] ^= expected[size_t(s) * n + (m ^ bit)];
        }
        auto actual = input;
        DeviceTransformStats stats;
        independent_metal_transform(ctx.get(), actual.data(), actual.size() * sizeof(Word), stats);
        require(actual == expected, "coefficient mismatch");
        require(stats.executed == 1 &&
                    stats.dispatches ==
                        (fused ? x - std::min(x, uint32_t(sizeof(Word) == 4 ? 5 : 4)) + 1 : x),
                "dispatch metadata");
        require(stats.input_bytes == input.size() * sizeof(Word) &&
                    stats.output_bytes == stats.input_bytes,
                "transfer metadata");
        // The transform is an involution in characteristic two; the same scratch
        // is overwritten on every call, including after different input patterns.
        independent_metal_transform(ctx.get(), actual.data(), actual.size() * sizeof(Word), stats);
        require(actual == input, "involution mismatch");
        ++cases;
    }
    std::cout << "EXACT " << x << ' ' << slices << ' ' << sizeof(Word) * 8 << ' '
              << independent_metal_device(ctx.get()) << '\n';
    return cases;
}
int main()
{
    try {
        std::mt19937_64 rng(0x65d13a);
#ifdef EXPECT_UNAVAILABLE
        try {
            void *p = independent_metal_create(1, 1, 32);
            independent_metal_destroy(p);
        } catch (const std::runtime_error &) {
            std::cout << "EXPLICIT_UNAVAILABLE_PASS\n";
            return 0;
        }
        throw std::runtime_error("stub unexpectedly enabled");
#else
        size_t cases = 0;
        for (bool fused : {false, true}) {
            for (uint32_t x : {1u, 2u, 3u, 4u, 5u, 6u, 7u, 8u, 12u}) {
                cases += control<uint32_t>(x, 3, rng, fused);
                cases += control<uint64_t>(x, 5, rng, fused);
            }
            cases += control<uint32_t>(18, 46, rng, fused);
            cases += control<uint64_t>(16, 56, rng, fused);
            cases += control<uint32_t>(20, 1, rng, fused);
        }
        for (auto shape : {std::vector<uint32_t>{0, 1, 32},
                           {21, 1, 32},
                           {1, 0, 32},
                           {1, 113, 32},
                           {1, 1, 16},
                           {20, 112, 64}}) {
            bool rejected = false;
            try {
                void *p = independent_metal_create(shape[0], shape[1], shape[2]);
                independent_metal_destroy(p);
            } catch (const std::exception &) {
                rejected = true;
            }
            require(rejected, "invalid dimensions accepted");
        }
        std::cout << "EXACT_KERNEL_PASS " << cases << " controls, twice each; 6 invalid shapes\n";
#endif
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
