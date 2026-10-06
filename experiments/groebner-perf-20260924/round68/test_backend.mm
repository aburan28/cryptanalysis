#include "transform_api.h"
#include "../round49/metal_backend.h"
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <iostream>
#include <memory>
#include <random>
#include <vector>

namespace pt = producer_transform;
static void require(bool condition, const char *message)
{
    if (!condition) throw std::runtime_error(message);
}
template <typename Error, typename Function> static void rejects(Function f)
{
    bool rejected = false;
    try {
        f();
    } catch (const Error &) {
        rejected = true;
    }
    require(rejected, "expected rejection");
}
using Context = std::unique_ptr<void, decltype(&compact_metal_destroy)>;

int main()
{
    try {
        uint64_t controls = 0;
        std::mt19937 random(680067);
        for (uint32_t x : {2u, 4u, 6u, 8u})
            for (uint32_t y : {3u, 5u})
                for (uint32_t equations : {1u, 31u, 32u}) {
                    const uint32_t branches = 1u << x, features = y * (y + 1) / 2,
                                   stride = features + 1;
                    const size_t bytes = size_t(branches) * stride * 4;
                    Context reference(compact_metal_create(branches, features, equations, y),
                                      compact_metal_destroy);
                    Context actual(compact_metal_create(branches, features, equations, y),
                                   compact_metal_destroy);
                    const uint64_t resident_bytes = compact_metal_bytes(actual.get());
                    for (uint32_t mode : {1u, 2u}) {
#ifdef PRODUCER_TRANSFORM_TEST_FAIL_MODE
                        if (mode == PRODUCER_TRANSFORM_TEST_FAIL_MODE) {
                            rejects<std::runtime_error>(
                                [&] { compact_metal_configure_transform(actual.get(), mode); });
                            mode = 1; // The preceding valid mode must remain usable after
                                      // allocation failure.
                        } else
#endif
                            compact_metal_configure_transform(actual.get(), mode);
                        require(compact_metal_bytes(actual.get()) == resident_bytes,
                                "second table was allocated");
                        for (uint32_t pattern = 0; pattern < 4; ++pattern) {
                            std::vector<uint32_t> values(size_t(branches) * stride);
                            for (size_t i = 0; i < values.size(); ++i)
                                values[i] =
                                    pattern == 0 ? 0 : (pattern == 1 && i % 13 ? 0 : random());
                            if (equations < 32)
                                for (auto &value : values) value &= (1u << equations) - 1;
                            auto expected = values;
                            pt::cpu(expected.data(), x, stride);
                            double seconds = 0;
                            const auto *rows = compact_metal_solve(reference.get(), expected.data(),
                                                                   bytes, false, true, seconds);
                            std::vector<uint64_t> expected_rows(rows, rows + size_t(branches) * 34);
                            const auto *projection = compact_metal_projection(reference.get());
                            std::vector<uint64_t> expected_projection(
                                projection, projection + size_t(branches) * (y + 2));
                            pt::Stats stats;
                            const uint64_t generation = compact_metal_begin(actual.get());
                            compact_metal_transform(actual.get(), values.data(), bytes, generation,
                                                    stats);
                            require(values == expected, "borrowed transform output differs");
                            require(stats.input_bytes == bytes && stats.output_bytes == bytes &&
                                        stats.scratch_bytes == bytes,
                                    "borrowed transform copy accounting");
                            rows = compact_metal_solve_prepared(actual.get(), values.data(), bytes,
                                                                false, true, generation, seconds);
                            require(std::equal(expected_rows.begin(), expected_rows.end(), rows),
                                    "projection rows differ");
                            require(std::equal(expected_projection.begin(),
                                               expected_projection.end(),
                                               compact_metal_projection(actual.get())),
                                    "projection proof data differ");
                            rejects<std::invalid_argument>([&] {
                                compact_metal_solve_prepared(actual.get(), values.data(), bytes,
                                                             false, true, generation, seconds);
                            });
                            require(seconds == 0, "stale device timing after rejected projection");
                            const uint64_t fresh = compact_metal_begin(actual.get());
                            require(fresh > generation, "generation did not advance");
                            rejects<std::invalid_argument>([&] {
                                compact_metal_transform(actual.get(), values.data(), bytes,
                                                        generation, stats);
                            });
                            require(stats.completed_dispatches == 0, "stale transform stats");
                            rejects<std::invalid_argument>([&] {
                                compact_metal_transform(actual.get(), values.data(), bytes, fresh,
                                                        stats);
                            });
                            const uint64_t extent_generation = compact_metal_begin(actual.get());
                            rejects<std::invalid_argument>([&] {
                                compact_metal_transform(actual.get(), values.data(), bytes - 4,
                                                        extent_generation, stats);
                            });
                            rejects<std::invalid_argument>([&] {
                                compact_metal_solve_prepared(actual.get(), values.data(), bytes,
                                                             false, true, extent_generation,
                                                             seconds);
                            });
                            const uint64_t changed = compact_metal_begin(actual.get());
                            compact_metal_transform(actual.get(), values.data(), bytes, changed,
                                                    stats);
                            auto other = values;
                            rejects<std::invalid_argument>([&] {
                                compact_metal_solve_prepared(actual.get(), other.data(), bytes,
                                                             false, true, changed, seconds);
                            });
                            rejects<std::invalid_argument>([&] {
                                compact_metal_solve_prepared(actual.get(), values.data(), bytes,
                                                             false, true, changed, seconds);
                            });
                            const uint64_t configured = compact_metal_begin(actual.get());
                            compact_metal_transform(actual.get(), values.data(), bytes, configured,
                                                    stats);
                            rejects<std::invalid_argument>(
                                [&] { compact_metal_configure_transform(actual.get(), 99); });
                            rejects<std::invalid_argument>([&] {
                                compact_metal_solve_prepared(actual.get(), values.data(), bytes,
                                                             false, true, configured, seconds);
                            });
                            // A legacy upload always supplies its own coefficients and consumes
                            // readiness.
                            compact_metal_solve(actual.get(), expected.data(), bytes, false, true,
                                                seconds);
                            const uint64_t zero = 0;
                            rejects<std::invalid_argument>([&] {
                                compact_metal_solve_prepared(actual.get(), values.data(), bytes,
                                                             false, true, zero, seconds);
                            });
                            ++controls;
                        }
                    }
                    compact_metal_configure_transform(actual.get(), 0);
                    const uint64_t disabled = compact_metal_begin(actual.get());
                    std::vector<uint32_t> values(bytes / 4);
                    pt::Stats stats;
                    rejects<std::invalid_argument>([&] {
                        compact_metal_transform(actual.get(), values.data(), bytes, disabled,
                                                stats);
                    });
                }
        // A borrowed helper must retain its own strong references and reject the
        // wrong extent/storage/hazard policy before it can run a kernel.
        void *borrowed = nullptr;
        @autoreleasepool {
            id<MTLDevice> gpu = MTLCreateSystemDefaultDevice();
            id<MTLCommandQueue> queue = [gpu newCommandQueue];
            auto make = [&](id<MTLBuffer> buffer) {
                return pt::create_borrowed(2, 7, pt::Mode::tiled, (__bridge void *)gpu,
                                           (__bridge void *)queue, (__bridge void *)buffer);
            };
            id<MTLBuffer> short_buffer =
                [gpu newBufferWithLength:4
                                 options:MTLResourceStorageModeShared |
                                         MTLResourceHazardTrackingModeTracked];
            rejects<std::invalid_argument>([&] { make(short_buffer); });
            id<MTLBuffer> private_buffer =
                [gpu newBufferWithLength:112
                                 options:MTLResourceStorageModePrivate |
                                         MTLResourceHazardTrackingModeTracked];
            rejects<std::invalid_argument>([&] { make(private_buffer); });
            id<MTLBuffer> untracked =
                [gpu newBufferWithLength:112
                                 options:MTLResourceStorageModeShared |
                                         MTLResourceHazardTrackingModeUntracked];
            rejects<std::invalid_argument>([&] { make(untracked); });
            id<MTLBuffer> valid = [gpu newBufferWithLength:112
                                                   options:MTLResourceStorageModeShared |
                                                           MTLResourceHazardTrackingModeTracked];
            borrowed = make(valid);
        }
        std::unique_ptr<void, decltype(&pt::destroy)> retained(borrowed, pt::destroy);
        std::vector<uint32_t> values(28, 7), expected = values;
        pt::cpu(expected.data(), 2, 7);
        pt::Stats stats;
        pt::apply(retained.get(), values.data(), 112, stats);
        require(values == expected, "borrowed resources did not survive owner scope");
        std::cout << "PASS " << controls
                  << " shared-buffer controls; freshness, projection equality, bounds, lifetime "
                     "and failure invalidation\n";
    } catch (const std::exception &error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
