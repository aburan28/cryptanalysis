#include "transform.h"
#include <algorithm>
#include <iostream>
#include <memory>
#include <random>
#include <string>
#include <utility>
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
// Independent order: feature-major traversal and descending assignment bits.
static std::vector<uint32_t> oracle(const std::vector<uint32_t> &input, uint32_t variables,
                                    uint32_t stride)
{
    auto result = input;
    const uint32_t branches = 1u << variables;
    for (uint32_t feature = 0; feature < stride; ++feature)
        for (uint32_t bit = branches / 2; bit; bit >>= 1)
            for (uint32_t row = 0; row < branches; ++row)
                if (row & bit)
                    result[size_t(row) * stride + feature] ^=
                        result[size_t(row ^ bit) * stride + feature];
    return result;
}
static void direct(const std::vector<uint32_t> &input, const std::vector<uint32_t> &output,
                   uint32_t stride)
{
    for (uint32_t row = 0; row < input.size() / stride; ++row)
        for (uint32_t feature = 0; feature < stride; ++feature) {
            uint32_t sum = 0, subset = row;
            for (;;) {
                sum ^= input[size_t(subset) * stride + feature];
                if (!subset) break;
                subset = (subset - 1) & row;
            }
            require(sum == output[size_t(row) * stride + feature], "subset-definition mismatch");
        }
}
int main(int argc, char **argv)
{
    try {
        if (argc == 2 && std::string(argv[1]) == "--probe") {
            try {
                std::unique_ptr<void, decltype(&pt::destroy)> probe(
                    pt::create(2, 7, pt::Mode::tiled), pt::destroy);
                std::cout << "METAL_AVAILABLE " << pt::device(probe.get()) << '\n';
                return 0;
            } catch (const pt::Unavailable &error) {
                std::cout << "METAL_UNAVAILABLE " << error.what() << '\n';
                return 77;
            }
        }
        if (argc != 1) throw std::invalid_argument("unexpected arguments");
        rejects<std::invalid_argument>([] { pt::extent(0, 2); });
        rejects<std::invalid_argument>([] { pt::extent(21, 2); });
        rejects<std::invalid_argument>([] { pt::extent(1, 1); });
        rejects<std::invalid_argument>([] { pt::extent(1, 57); });
        rejects<std::length_error>([] { pt::extent(20, 17); });
        rejects<std::invalid_argument>([] { pt::create(2, 2, static_cast<pt::Mode>(0)); });
        rejects<std::invalid_argument>([] { pt::cpu(nullptr, 2, 2); });
        pt::destroy(nullptr);
        std::vector<std::pair<uint32_t, uint32_t>> shapes;
        for (uint32_t variables = 1; variables <= 8; ++variables)
            for (uint32_t stride : {2u, 4u, 7u, 16u, 22u, 29u, 37u, 46u, 56u})
                shapes.emplace_back(variables, stride);
        for (auto shape : {std::pair{12u, 7u},
                           {12u, 46u},
                           {18u, 2u},
                           {18u, 46u},
                           {18u, 56u},
                           {20u, 2u},
                           {20u, 16u}})
            shapes.push_back(shape);
        std::mt19937 rng(670051);
        uint64_t controls = 0;
        for (const auto &shape : shapes) {
            const uint32_t variables = shape.first, stride = shape.second;
            const size_t bytes = pt::extent(variables, stride);
            std::vector<uint32_t> input(bytes / 4);
            for (auto mode : {pt::Mode::staged, pt::Mode::tiled}) {
                std::unique_ptr<void, decltype(&pt::destroy)> context(nullptr, pt::destroy);
#ifdef EXPECT_UNAVAILABLE
                rejects<pt::Unavailable>([&] { pt::create(variables, stride, mode); });
#else
                context.reset(pt::create(variables, stride, mode));
                if (!controls) std::cout << "DEVICE " << pt::device(context.get()) << '\n';
#endif
                for (uint32_t pattern = 0; pattern < 3; ++pattern) {
                    for (size_t i = 0; i < input.size(); ++i)
                        input[i] = pattern == 0 ? 0 : (pattern == 1 && i % 127 ? 0 : rng());
                    auto expected = oracle(input, variables, stride);
                    auto host = input;
                    pt::cpu(host.data(), variables, stride);
                    require(host == expected, "CPU/reference mismatch");
                    if (variables <= 8) direct(input, expected, stride);
                    pt::cpu(host.data(), variables, stride);
                    require(host == input, "CPU involution mismatch");
                    auto actual = input;
                    pt::Stats stats;
#ifdef EXPECT_UNAVAILABLE
                    stats.output_bytes = 9;
                    rejects<pt::Unavailable>(
                        [&] { pt::apply(nullptr, actual.data(), bytes, stats); });
                    require(stats.output_bytes == 0 && stats.completed_dispatches == 0,
                            "unavailable stats stale");
#else
                    pt::apply(context.get(), actual.data(), bytes, stats);
                    require(actual == expected, "GPU/reference mismatch");
                    require(stats.logical_xors ==
                                uint64_t(variables) * (1u << (variables - 1)) * stride,
                            "logical XOR count");
                    const uint32_t dispatches = mode == pt::Mode::staged
                                                    ? variables
                                                    : 1 + variables - std::min(variables, 4u);
                    require(stats.encoded_dispatches == dispatches &&
                                stats.submitted_dispatches == dispatches &&
                                stats.completed_dispatches == dispatches &&
                                stats.input_bytes == bytes && stats.output_bytes == bytes &&
                                stats.scratch_bytes == bytes,
                            "GPU accounting");
                    require(stats.wall >=
                                    stats.copy_in + stats.encode + stats.wait + stats.copy_out &&
                                stats.device >= 0,
                            "phase accounting");
                    pt::apply(context.get(), actual.data(), bytes, stats);
                    require(actual == input, "GPU involution mismatch");
                    // Failed requests must not mutate host input or leave stale success stats.
                    rejects<std::invalid_argument>(
                        [&] { pt::apply(context.get(), actual.data(), bytes - 4, stats); });
                    require(actual == input && stats.completed_dispatches == 0 &&
                                stats.output_bytes == 0 && stats.input_bytes == 0,
                            "failed request altered state");
                    rejects<std::invalid_argument>(
                        [&] { pt::apply(context.get(), nullptr, bytes, stats); });
                    rejects<std::invalid_argument>(
                        [&] { pt::apply(nullptr, actual.data(), bytes, stats); });
#endif
                    ++controls;
                }
            }
        }
        std::cout << "PASS " << controls
                  << " exact controls; direct subset oracle, descending oracle, "
                     "involution, fresh reuse, bounds, and failure accounting\n";
    } catch (const std::exception &error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
