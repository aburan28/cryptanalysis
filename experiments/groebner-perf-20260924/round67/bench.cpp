#include "transform.h"
#include <array>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <vector>

namespace pt = producer_transform;
using Clock = std::chrono::steady_clock;
static double seconds(Clock::time_point start)
{
    return std::chrono::duration<double>(Clock::now() - start).count();
}
static uint64_t read(std::ifstream &input)
{
    unsigned char bytes[8];
    input.read(reinterpret_cast<char *>(bytes), 8);
    if (!input) throw std::runtime_error("truncated input");
    uint64_t value = 0;
    for (unsigned i = 0; i < 8; ++i) value |= uint64_t(bytes[i]) << (8 * i);
    return value;
}
int main(int argc, char **argv)
{
    try {
        if (argc != 2) throw std::invalid_argument("expected frozen input path");
        std::ifstream input(argv[1], std::ios::binary);
        if (read(input) != UINT64_C(0x3736524e52454b)) throw std::invalid_argument("input magic");
        const uint64_t x = read(input), y = read(input), equations = read(input),
                       terms = read(input);
        if (!x || x > 20 || !y || y > 10 || !equations || equations > 32 || terms > (1u << 20))
            throw std::invalid_argument("input dimensions");
        const uint32_t stride = 1 + y * (y + 1) / 2;
        const size_t bytes = pt::extent(x, stride);
        std::vector<uint32_t> scatter(bytes / 4), expected, actual(bytes / 4);
        std::vector<uint32_t> features(1u << y, UINT32_MAX);
        features[0] = 0;
        uint32_t feature = 1;
        for (uint32_t i = 0; i < y; ++i) features[1u << i] = feature++;
        for (uint32_t i = 0; i < y; ++i)
            for (uint32_t j = i + 1; j < y; ++j) features[(1u << i) | (1u << j)] = feature++;
        for (uint64_t i = 0; i < terms; ++i) {
            const uint64_t mask = read(input), coefficient = read(input);
            if (mask >> (x + y) || coefficient >> equations || features[mask >> x] == UINT32_MAX)
                throw std::invalid_argument("input term");
            scatter[(mask & ((1u << x) - 1)) * stride + features[mask >> x]] ^= coefficient;
        }
        if (input.peek() != std::ifstream::traits_type::eof())
            throw std::invalid_argument("trailing input");
        expected = scatter;
        // Descending-bit result outside every arm's timer; controls also use direct subset sums.
        for (uint32_t bit = 1u << (x - 1); bit; bit >>= 1)
            for (uint32_t row = 0; row < (1u << x); ++row)
                if (row & bit)
                    for (uint32_t f = 0; f < stride; ++f)
                        expected[size_t(row) * stride + f] ^=
                            expected[size_t(row ^ bit) * stride + f];
        std::array<std::unique_ptr<void, decltype(&pt::destroy)>, 2> gpu = {
            std::unique_ptr<void, decltype(&pt::destroy)>(nullptr, pt::destroy),
            std::unique_ptr<void, decltype(&pt::destroy)>(nullptr, pt::destroy)};
        for (unsigned arm = 1; arm <= 2; ++arm) {
            const auto start = Clock::now();
            gpu[arm - 1].reset(pt::create(x, stride, static_cast<pt::Mode>(arm)));
            std::cerr << "SETUP arm=" << arm << " seconds=" << std::setprecision(17)
                      << seconds(start) << " device=" << pt::device(gpu[arm - 1].get()) << '\n';
        }
        const std::array<std::array<unsigned, 3>, 6> orders = {
            {{0, 1, 2}, {0, 2, 1}, {1, 0, 2}, {1, 2, 0}, {2, 0, 1}, {2, 1, 0}}};
        std::cout << "trial,position,arm,valid,wall,copy_in,encode,wait,copy_out,device,"
                     "verification,logical_xors,"
                     "encoded_dispatches,submitted_dispatches,completed_dispatches,dispatched_"
                     "threads,input_bytes,output_bytes,scratch_bytes\n";
        std::cout << std::setprecision(17);
        for (int trial = -1; trial < 18; ++trial)
            for (unsigned position = 0; position < 3; ++position) {
                const unsigned arm = orders[trial < 0 ? 0 : trial % 6][position];
                actual = scatter; // Common input preparation outside this transform-only interval.
                pt::Stats stats;
                const auto start = Clock::now();
                if (arm == 0)
                    pt::cpu(actual.data(), x, stride);
                else
                    pt::apply(gpu[arm - 1].get(), actual.data(), bytes, stats);
                const double wall = seconds(start);
                if (arm == 0) stats.logical_xors = x * (1u << (x - 1)) * stride;
                const auto check_start = Clock::now();
                const bool valid = actual == expected;
                const double check = seconds(check_start);
                std::cout << trial << ',' << position << ',' << arm << ',' << valid << ',' << wall
                          << ',' << stats.copy_in << ',' << stats.encode << ',' << stats.wait << ','
                          << stats.copy_out << ',' << stats.device << ',' << check << ','
                          << stats.logical_xors << ',' << stats.encoded_dispatches << ','
                          << stats.submitted_dispatches << ',' << stats.completed_dispatches << ','
                          << stats.dispatched_threads << ',' << stats.input_bytes << ','
                          << stats.output_bytes << ',' << stats.scratch_bytes << std::endl;
                if (!valid) throw std::runtime_error("full output mismatch");
            }
    } catch (const std::exception &error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
