#include "api.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <iostream>
#include <memory>
#include <random>
#include <thread>

using namespace multiplier_gpu;
static void require(bool value, const char *message)
{
    if (!value) throw std::runtime_error(message);
}
template <typename F> static void rejects(F f)
{
    bool rejected = false;
    try {
        f();
    } catch (const std::invalid_argument &) {
        rejected = true;
    } catch (const std::length_error &) {
        rejected = true;
    }
    require(rejected, "invalid input accepted");
}
struct Data {
    Shape shape;
    std::vector<uint64_t> table, witnesses;
    std::vector<uint32_t> table32;
    std::vector<uint32_t> branches;
    Data(uint32_t x, uint32_t y, uint32_t e, size_t n)
        : shape(x, y, e, n), table(shape.word_bits == 64 ? shape.coefficient_bytes / 8 : 0),
          witnesses(n * (y + 1) * shape.limbs),
          table32(shape.word_bits == 32 ? shape.coefficient_bytes / 4 : 0), branches(n)
    {
        for (size_t i = 0; i < n; ++i) branches[i] = uint32_t(i);
    }
    const void *raw() const
    {
        return shape.word_bits == 32 ? static_cast<const void *>(table32.data()) : table.data();
    }
    Input input() const
    {
        return {raw(),           shape.coefficient_bytes, branches.data(),
                branches.size(), witnesses.data(),        witnesses.size()};
    }
    void set(uint32_t f, uint32_t branch, uint32_t equation, bool value)
    {
        const uint32_t l = equation / 64, bit = equation % 64;
        const size_t i = (size_t(f) * shape.limbs + l) * shape.branches + branch;
        if (shape.word_bits == 32) {
            auto *p = table32.data();
            p[i] = (p[i] & ~(1u << bit)) | (uint32_t(value) << bit);
        } else
            table[i] = (table[i] & ~(uint64_t(1) << bit)) | (uint64_t(value) << bit);
    }
    void witness(size_t r, uint32_t slot, uint32_t equation)
    {
        witnesses[(r * (shape.y + 1) + slot) * shape.limbs + equation / 64] ^= uint64_t(1)
                                                                               << (equation % 64);
    }
    uint32_t feature(uint32_t mask) const
    {
        return uint32_t(std::find(shape.masks.begin(), shape.masks.end(), mask) -
                        shape.masks.begin());
    }
    void fill(uint32_t pattern, uint64_t seed)
    {
        std::mt19937_64 rng(seed);
        std::fill(table.begin(), table.end(), 0);
        std::fill(table32.begin(), table32.end(), 0);
        std::fill(witnesses.begin(), witnesses.end(), 0);
        if (pattern == 0) {
            for (auto &v : table) v = rng();
            for (auto &v : table32) v = uint32_t(rng());
            for (size_t r = 0; r < branches.size(); ++r)
                for (uint32_t slot = 0; slot <= shape.y; ++slot)
                    for (uint32_t e = 0; e < shape.equations; ++e)
                        if (rng() & 1) witness(r, slot, e);
            return;
        }
        for (size_t r = 0; r < branches.size(); ++r) {
            const auto branch = branches[r];
            if (pattern == 1 || shape.equations == 1) {
                set(0, branch, 0, true);
                witness(r, 0, 0);
            } else if (pattern == 2 || (pattern == 3 && shape.equations == 2)) {
                // L*L + (L+1)*(L+1) = 1 for a dense Boolean linear L.
                set(0, branch, 1, true);
                witness(r, 0, 1);
                for (uint32_t bit = 0; bit < shape.y; ++bit) {
                    set(feature(1u << bit), branch, 0, true);
                    set(feature(1u << bit), branch, 1, true);
                    witness(r, bit + 1, 0);
                    witness(r, bit + 1, 1);
                }
            } else if (pattern == 3 && shape.equations >= 3) {
                // Dense quadratic coefficients cancel across distant equations.
                const uint32_t other = shape.equations - 1;
                for (uint32_t f = 0; f < shape.features; ++f) {
                    const bool value = rng() & 1;
                    set(f, branch, 0, value);
                    set(f, branch, other, value);
                }
                for (uint32_t slot = 0; slot <= shape.y; ++slot) {
                    witness(r, slot, 0);
                    witness(r, slot, other);
                }
                set(0, branch, 1, true);
                witness(r, 0, 1);
            } else if (pattern == 4 && shape.y >= 3) {
                // Identity 1 + z0*z1*z2: only the cubic coefficient is wrong.
                set(0, branch, 1, true);
                witness(r, 0, 1);
                set(feature(3), branch, 0, true);
                witness(r, 3, 0);
            } else {
                set(0, branch, 0, true);
                witness(r, 0, 0);
                if (r == branches.size() / 2) witness(r, 0, 0);
            }
        }
    }
};
struct Answer {
    std::vector<uint32_t> first;
    std::vector<uint8_t> values;
    Stats stats;
    Answer(size_t n, uint32_t groups, bool materialized)
        : first(n, 0x12345678), values(materialized ? n * groups : 0, 0xee)
    {
    }
    Output output()
    {
        return {first.data(), first.size(), values.empty() ? nullptr : values.data(),
                values.size()};
    }
};
static void equal(const Answer &a, const Answer &b)
{
    require(a.first == b.first, "first bad coefficient mismatch");
    if (!a.values.empty() && !b.values.empty())
        require(a.values == b.values, "polynomial identity mismatch");
    require(a.stats.records == b.stats.records &&
                a.stats.coefficient_checks == b.stats.coefficient_checks &&
                a.stats.first_invalid_record == b.stats.first_invalid_record &&
                a.stats.records_after_first_invalid == b.stats.records_after_first_invalid,
            "work/first-failure accounting mismatch");
}
using Handle = std::unique_ptr<void, decltype(&destroy)>;

int main(int argc, char **argv)
{
    try {
        require(argc == 1 || (argc == 2 && std::string(argv[1]) == "--probe"),
                "unknown test argument");
        bool available = true;
        try {
            Handle probe(create(1, 1, 1, 1), destroy);
            std::cout << "METAL_AVAILABLE " << device(probe.get()) << '\n';
        } catch (const Unavailable &error) {
            available = false;
            std::cout << "METAL_UNAVAILABLE " << error.what() << '\n';
        }
#ifdef EXPECT_UNAVAILABLE
        require(!available, "portable backend unexpectedly available");
#endif
        if (argc == 2) return available ? 0 : 77;
        uint64_t controls = 0, gpu_calls = 0;
        for (uint32_t y = 1; y <= 10; ++y)
            for (uint32_t equations : {1u, 31u, 32u, 33u, 63u, 64u, 65u, 127u, 128u}) {
                Data d(4, y, equations, 7);
                d.branches = {0, 1, 3, 6, 8, 12, 15};
                Handle context(available ? create(4, y, equations, 7) : nullptr, destroy);
                for (uint32_t pattern = 0; pattern < 6; ++pattern) {
                    d.fill(pattern, 690000 + y * 1000 + equations * 10 + pattern);
                    Answer expected(7, d.shape.groups, true);
                    oracle(d.shape, d.input(), expected.output(), expected.stats);
                    if (pattern >= 1 && pattern <= 3)
                        require(std::all_of(expected.first.begin(), expected.first.end(),
                                            [](uint32_t v) { return v == valid_identity; }),
                                "constructed valid identity rejected");
                    if (pattern == 4 && y >= 3 && equations >= 2)
                        require(std::all_of(expected.first.begin(), expected.first.end(),
                                            [](uint32_t v) { return v == 7; }),
                                "cubic counterexample not retained");
                    for (bool materialized : {false, true}) {
                        Answer actual(7, d.shape.groups, materialized);
                        cpu(d.shape, d.input(), actual.output(), actual.stats);
                        equal(expected, actual);
                        if (available)
                            for (uint32_t mode : {1u, 2u}) {
                                check(context.get(), mode, d.input(), actual.output(),
                                      actual.stats);
                                equal(expected, actual);
                                require(actual.stats.submitted_dispatches == 1 &&
                                            actual.stats.completed_dispatches == 1,
                                        "missing dispatch");
                                require(actual.stats.input_bytes == d.shape.coefficient_bytes +
                                                                        d.witnesses.size() * 8 +
                                                                        7 * 4,
                                        "input byte count");
                                require(actual.stats.output_bytes == 7 * 4 + actual.values.size(),
                                        "output byte count");
                                ++gpu_calls;
                            }
                    }
                    ++controls;
                }
            }
        // Large mixed/invalid batches exercise atomic reduction across groups.
        {
            Data d(12, 10, 128, 4096);
            Handle h(available ? create(12, 10, 128, 4096) : nullptr, destroy);
            for (uint32_t pattern : {0u, 3u, 5u}) {
                d.fill(pattern, 694096 + pattern);
                Answer a(4096, d.shape.groups, true), b(4096, d.shape.groups, true);
                oracle(d.shape, d.input(), a.output(), a.stats);
                cpu(d.shape, d.input(), b.output(), b.stats);
                equal(a, b);
                if (available)
                    for (uint32_t mode : {1u, 2u}) {
                        check(h.get(), mode, d.input(), b.output(), b.stats);
                        equal(a, b);
                        ++gpu_calls;
                    }
                ++controls;
            }
        }
        // Exact 64 MiB table boundary and sparse records including the last branch.
        {
            Data d(20, 5, 32, 3);
            d.branches = {0, 1, (1u << 20) - 1};
            d.fill(2, 1);
            require(d.shape.coefficient_bytes == (64u << 20), "boundary shape");
            Answer a(3, d.shape.groups, true), b(3, d.shape.groups, true);
            oracle(d.shape, d.input(), a.output(), a.stats);
            cpu(d.shape, d.input(), b.output(), b.stats);
            equal(a, b);
            if (available) {
                Handle h(create(20, 5, 32, 3), destroy);
                for (uint32_t mode : {1u, 2u}) {
                    check(h.get(), mode, d.input(), b.output(), b.stats);
                    equal(a, b);
                    ++gpu_calls;
                }
            }
            ++controls;
        }
        for (auto shape : {std::array<uint32_t, 3>{0, 1, 1},
                           {21, 1, 1},
                           {1, 0, 1},
                           {1, 11, 1},
                           {1, 1, 0},
                           {1, 1, 129},
                           {20, 10, 128}})
            rejects([&] { Shape s(shape[0], shape[1], shape[2], 1); });
        rejects([] { Shape s(1, 1, 1, 3); });
        {
            Data d(3, 3, 65, 4);
            d.fill(3, 12);
            Handle h(available ? create(3, 3, 65, 4) : nullptr, destroy);
            Answer a(4, d.shape.groups, true), expected(4, d.shape.groups, true);
            oracle(d.shape, d.input(), expected.output(), expected.stats);
            auto reject_input = [&](Input in, Output out) {
                a.stats.records = 100;
                rejects([&] { cpu(d.shape, in, out, a.stats); });
                require(!a.stats.records, "stale CPU failure stats");
                if (available) {
                    a.stats.records = 100;
                    rejects([&] { check(h.get(), 1, in, out, a.stats); });
                    require(!a.stats.records && !a.stats.completed_dispatches,
                            "stale GPU failure stats");
                    check(h.get(), 2, d.input(), a.output(), a.stats);
                    equal(expected, a);
                }
                ++controls;
            };
            auto in = d.input();
            --in.coefficient_bytes;
            reject_input(in, a.output());
            in = d.input();
            --in.witness_words;
            reject_input(in, a.output());
            in = d.input();
            in.coefficients = nullptr;
            reject_input(in, a.output());
            in = d.input();
            in.branches = nullptr;
            reject_input(in, a.output());
            auto out = a.output();
            --out.records;
            reject_input(d.input(), out);
            out = a.output();
            --out.coefficient_bytes;
            reject_input(d.input(), out);
            out = a.output();
            out.first_bad = reinterpret_cast<uint32_t *>(d.table.data());
            reject_input(d.input(), out);
            out = a.output();
            out.coefficients = reinterpret_cast<uint8_t *>(a.first.data());
            reject_input(d.input(), out);
            // These mutations are restored before checking recovery.
            auto rejects_current = [&] {
                rejects([&] { cpu(d.shape, d.input(), a.output(), a.stats); });
                if (available) rejects([&] { check(h.get(), 1, d.input(), a.output(), a.stats); });
                ++controls;
            };
            d.branches[1] = d.branches[0];
            rejects_current();
            d.branches[1] = 1;
            d.branches[3] = 8;
            rejects_current();
            d.branches[3] = 3;
            d.witnesses[1] |= uint64_t(1) << 1;
            rejects_current();
            d.witnesses[1] &= ~uint64_t(2);
            if (available) {
                rejects([&] { check(h.get(), 0, d.input(), a.output(), a.stats); });
                check(h.get(), 1, d.input(), a.output(), a.stats);
                equal(expected, a);
                rejects([&] { check(nullptr, 1, d.input(), a.output(), a.stats); });
            }
            Input empty{d.table.data(), d.shape.coefficient_bytes, nullptr, 0, nullptr, 0};
            Output no_output{nullptr, 0};
            cpu(d.shape, empty, no_output, a.stats);
            require(a.stats.records == 0, "empty CPU records");
            if (available) {
                check(h.get(), 2, empty, no_output, a.stats);
                require(a.stats.input_bytes == 0 && a.stats.completed_dispatches == 0,
                        "empty GPU work");
            }
            ++controls;
        }
        if (available) {
            Handle h(create(5, 6, 127, 17), destroy);
            std::atomic<bool> good{true};
            std::vector<std::thread> threads;
            for (uint32_t t = 0; t < 3; ++t)
                threads.emplace_back([&, t] {
                    try {
                        Data d(5, 6, 127, 17);
                        Answer a(17, d.shape.groups, true), b(17, d.shape.groups, true);
                        for (uint32_t k = 0; k < 4; ++k) {
                            d.fill((t + k) % 6, 100 + t * 10 + k);
                            oracle(d.shape, d.input(), a.output(), a.stats);
                            check(h.get(), 1 + k % 2, d.input(), b.output(), b.stats);
                            equal(a, b);
                        }
                    } catch (...) {
                        good = false;
                    }
                });
            for (auto &thread : threads) thread.join();
            require(good, "concurrent context control");
            gpu_calls += 12;
            ++controls;
        }
        std::cout << "PASS " << controls << " exact control cells; " << gpu_calls
                  << " GPU output comparisons; every materialized coefficient checked\n";
    } catch (const std::exception &error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
