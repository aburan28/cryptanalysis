#include "api.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>

using namespace multiplier_gpu;
using Clock = std::chrono::steady_clock;
static double elapsed(Clock::time_point t)
{
    return std::chrono::duration<double>(Clock::now() - t).count();
}
static void require(bool value, const char *message)
{
    if (!value) throw std::runtime_error(message);
}
static void read(std::ifstream &file, void *p, size_t bytes)
{
    if (bytes) file.read(static_cast<char *>(p), std::streamsize(bytes));
    require(bool(file), "truncated fixture");
}

int main(int argc, char **argv)
{
    try {
        require(argc == 2, "usage: bench /absolute/input.bin");
        const uint32_t endian = 1;
        require(*reinterpret_cast<const uint8_t *>(&endian) == 1,
                "fixture requires little endian host");
        std::ifstream input(argv[1], std::ios::binary);
        char magic[8];
        read(input, magic, 8);
        require(std::string(magic, 8) == std::string("MUL69V1\0", 8), "fixture schema");
        uint32_t h[4];
        read(input, h, sizeof(h));
        const auto setup_started = Clock::now();
        Shape s(h[0], h[1], h[2], h[3]);
        std::vector<uint32_t> table32(s.word_bits == 32 ? s.coefficient_bytes / 4 : 0),
            branches(h[3]);
        std::vector<uint64_t> table64(s.word_bits == 64 ? s.coefficient_bytes / 8 : 0),
            witnesses(size_t(h[3]) * (s.y + 1) * s.limbs);
        void *table = s.word_bits == 32 ? static_cast<void *>(table32.data()) : table64.data();
        read(input, table, s.coefficient_bytes);
        read(input, branches.data(), branches.size() * 4);
        read(input, witnesses.data(), witnesses.size() * 8);
        require(input.peek() == std::char_traits<char>::eof(), "trailing fixture data");
        Input in{table,           s.coefficient_bytes, branches.data(),
                 branches.size(), witnesses.data(),    witnesses.size()};
        std::vector<uint32_t> expected(h[3]), actual(h[3]);
        std::vector<uint8_t> coefficients(size_t(h[3]) * s.groups), replay(coefficients.size());
        Stats stats;
        Output full_expected{expected.data(), expected.size(), coefficients.data(),
                             coefficients.size()};
        Output full_actual{actual.data(), actual.size(), replay.data(), replay.size()};
        oracle(s, in, full_expected, stats);
        require(std::all_of(expected.begin(), expected.end(),
                            [](uint32_t v) { return v == valid_identity; }),
                "frozen proof invalid");
        cpu(s, in, full_actual, stats);
        require(actual == expected && replay == coefficients, "CPU full coefficient mismatch");
        std::unique_ptr<void, decltype(&destroy)> context(nullptr, destroy);
        try {
            context.reset(create(s.x, s.y, s.equations, in.records));
        } catch (const Unavailable &error) {
            std::cerr << "METAL_UNAVAILABLE " << error.what() << '\n';
        }
        if (context) {
            std::cerr << "METAL_AVAILABLE " << device(context.get()) << '\n';
            for (uint32_t mode : {1u, 2u}) {
                check(context.get(), mode, in, full_actual, stats);
                require(actual == expected && replay == coefficients,
                        "GPU full coefficient mismatch");
            }
        }
        const double setup = elapsed(setup_started);
        std::cerr << std::setprecision(17) << "SETUP_AND_EXACT_ORACLE_SECONDS " << setup << '\n';
        Output out{actual.data(), actual.size()};
        const std::array<std::array<uint32_t, 3>, 6> orders{
            {{0, 1, 2}, {0, 2, 1}, {1, 0, 2}, {1, 2, 0}, {2, 0, 1}, {2, 1, 0}}};
        std::cout
            << "trial,position,arm,warmup,records,coefficient_checks,outer_seconds,wall_seconds,"
               "validation_seconds,copy_in_seconds,encode_seconds,wait_seconds,copy_out_seconds,"
               "device_seconds,check_seconds,input_bytes,output_bytes,initialized_bytes,dispatched_"
               "threads,submitted_dispatches,completed_dispatches,workspace_bytes,first_invalid_"
               "record,records_after_first_invalid,load_start,load_end,status\n"
            << std::setprecision(17);
        for (int trial = -1; trial < 18; ++trial) {
            const auto order = trial < 0 ? orders[0] : orders[size_t(trial) % 6];
            for (size_t position = 0; position < 3; ++position) {
                const uint32_t arm = order[position];
                if (arm && !context) continue;
                double load_start = 0, load_end = 0;
                getloadavg(&load_start, 1);
                auto started = Clock::now();
                if (arm)
                    check(context.get(), arm, in, out, stats);
                else
                    cpu(s, in, out, stats);
                const double outer = elapsed(started);
                getloadavg(&load_end, 1);
                started = Clock::now();
                require(actual == expected, "timed output mismatch");
                require(stats.records == in.records &&
                            stats.coefficient_checks == in.records * s.groups,
                        "timed work mismatch");
                require(stats.first_invalid_record == UINT64_MAX &&
                            stats.records_after_first_invalid == 0,
                        "valid proof failure accounting");
                const double checked = elapsed(started);
                std::cout << trial << ',' << position << ',' << arm << ',' << (trial < 0) << ','
                          << stats.records << ',' << stats.coefficient_checks << ',' << outer << ','
                          << stats.wall << ',' << stats.validation << ',' << stats.copy_in << ','
                          << stats.encode << ',' << stats.wait << ',' << stats.copy_out << ','
                          << stats.device << ',' << checked << ',' << stats.input_bytes << ','
                          << stats.output_bytes << ',' << stats.initialized_bytes << ','
                          << stats.dispatched_threads << ',' << stats.submitted_dispatches << ','
                          << stats.completed_dispatches << ',' << stats.workspace_bytes << ','
                          << stats.first_invalid_record << ',' << stats.records_after_first_invalid
                          << ',' << load_start << ',' << load_end << ",PASS\n";
            }
        }
    } catch (const std::exception &error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
