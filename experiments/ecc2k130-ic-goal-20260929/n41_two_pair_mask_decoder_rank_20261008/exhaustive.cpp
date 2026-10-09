// Evaluate the extracted quadratic relation on every exact N41 D2 x D3 pair sum.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <algorithm>
#include <array>
#include <chrono>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

struct SeedForCheck {
    Point point;
    uint16_t column;
};

static uint64_t elapsed_ns(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
}

static uint64_t peak_rss_bytes() {
    rusage usage{};
    getrusage(RUSAGE_SELF, &usage);
#ifdef __APPLE__
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss) * 1024;
#endif
}

static std::vector<int> parse_terms(const std::string& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("missing relation");
    std::string raw((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    const std::string marker = "\"term_indices\":[";
    size_t cursor = raw.find(marker);
    if (cursor == std::string::npos) throw std::runtime_error("missing term list");
    cursor += marker.size();
    std::vector<int> terms;
    while (cursor < raw.size() && raw[cursor] != ']') {
        if (raw[cursor] == ',') { ++cursor; continue; }
        size_t count = 0;
        int index = std::stoi(raw.substr(cursor), &count);
        if (count == 0 || index < 0 || index >= 3322 ||
            (!terms.empty() && index <= terms.back()))
            throw std::runtime_error("bad term index");
        terms.push_back(index);
        cursor += count;
    }
    if (cursor == raw.size() || terms.empty()) throw std::runtime_error("unterminated term list");
    return terms;
}

struct Equation {
    bool constant = false;
    U128 linear = 0;
    std::array<U128, 81> quadratic{};

    explicit Equation(const std::vector<int>& terms) {
        size_t at = 0;
        if (terms[at] == 0) { constant = true; ++at; }
        while (at < terms.size() && terms[at] <= 81) {
            linear ^= U128(1) << (terms[at] - 1);
            ++at;
        }
        int feature = 82;
        for (int i = 0; i < 81; ++i)
            for (int j = i + 1; j < 81; ++j, ++feature)
                if (at < terms.size() && terms[at] == feature) {
                    quadratic[i] ^= U128(1) << j;
                    ++at;
                }
        if (feature != 3322 || at != terms.size())
            throw std::runtime_error("unparsed feature index");
    }

    static bool parity(U128 value) {
        return (__builtin_popcountll(uint64_t(value)) ^
                __builtin_popcountll(uint64_t(value >> 64))) & 1;
    }

    bool evaluate(Point point) const {
        if (point.infinity || (point.x & 1)) throw std::runtime_error("point outside feature domain");
        U128 variables = U128(point.x >> 1) | (U128(point.y) << 40);
        bool value = constant ^ parity(linear & variables);
        for (int i = 0; i < 81; ++i)
            if ((variables >> i) & 1)
                value ^= parity(quadratic[i] & variables);
        return value;
    }
};

static std::vector<Point> pair_sums(const std::vector<SeedForCheck>& seeds) {
    std::vector<Point> sums;
    for (int i = 0; i < 64; ++i)
        for (int j = i + 1; j < 64; ++j)
            if (seeds[i].column != seeds[j].column) {
                Point total = add(seeds[i].point, seeds[j].point);
                if (total.infinity) throw std::runtime_error("identity pair");
                sums.push_back(total);
            }
    if (sums.size() != 1956) throw std::runtime_error("pair domain size mismatch");
    return sums;
}

int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::runtime_error("usage: exhaustive native_input relation result");
        auto start = std::chrono::steady_clock::now();
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("missing native input");
        uint64_t qx, qy, subgroup_order;
        int summands;
        input >> qx >> qy >> subgroup_order >> summands;
        if (!input || qx != 1458168294740ULL || qy != 1672312028033ULL ||
            subgroup_order != 549756390943ULL || summands != 8)
            throw std::runtime_error("wrong frozen N41 input header");
        std::array<std::vector<SeedForCheck>, 4> seeds;
        for (int slot = 0; slot < 8; ++slot) {
            int count;
            input >> count;
            if (!input || count != 64) throw std::runtime_error("wrong slot size");
            for (int index = 0; index < count; ++index) {
                uint64_t x, y;
                int column, mask, branch, sign;
                input >> x >> y >> column >> mask >> branch >> sign;
                if (!input || !on_curve(finite(x, y)) || column < 0 || column >= 26 ||
                    mask <= 0 || mask >= 64 || branch != 0 || sign < 0 || sign > 1)
                    throw std::runtime_error("bad input seed");
                SeedForCheck seed{finite(x, y), uint16_t(column)};
                if (slot % 2 == 0) seeds[slot/2].push_back(seed);
                else {
                    const auto& prior = seeds[slot/2][index];
                    if (!(prior.point == seed.point) || prior.column != seed.column)
                        throw std::runtime_error("duplicated slots differ");
                }
            }
        }
        std::string extra;
        if (input >> extra) throw std::runtime_error("trailing native input");
        Equation equation(parse_terms(argv[2]));
        auto a = pair_sums(seeds[2]);
        auto b = pair_sums(seeds[3]);
        uint64_t setup_ns = elapsed_ns(start);

        start = std::chrono::steady_clock::now();
        uint64_t checked = 0, failed = 0, identity = 0, odd_x = 0;
        size_t first_i = 0, first_j = 0;
        Point first_point;
        bool time_cap = false, memory_cap = false;
        for (size_t i = 0; i < a.size(); ++i) {
            for (size_t j = 0; j < b.size(); ++j) {
                Point point = add(a[i], b[j]);
                ++checked;
                if (point.infinity) { ++identity; continue; }
                if (point.x & 1) { ++odd_x; continue; }
                if (equation.evaluate(point)) {
                    ++failed;
                    if (failed == 1) {
                        first_i = i;
                        first_j = j;
                        first_point = point;
                    }
                }
                if ((checked & 16383) == 0) {
                    time_cap = elapsed_ns(start) >= 180000000000ULL;
                    memory_cap = peak_rss_bytes() >= 4ULL * 1024 * 1024 * 1024;
                    if (time_cap || memory_cap) break;
                }
            }
            if (time_cap || memory_cap) break;
        }
        uint64_t check_ns = elapsed_ns(start);
        const char* status = time_cap ? "TIME_CAP" : memory_cap ? "MEMORY_CAP" :
                             failed ? "RELATION_COUNTEREXAMPLE" : "COMPLETE_SUPPORT_EQUATION";
        std::ofstream out(argv[3]);
        if (!out) throw std::runtime_error("cannot open result");
        out << "{\"kind\":\"n41_two_pair_quadratic_exhaustive_check\","
            << "\"status\":\"" << status << "\","
            << "\"candidate_id\":null,\"run_id\":null,"
            << "\"pair_sizes\":[" << a.size() << "," << b.size() << "],"
            << "\"checked_combinations\":" << checked << ","
            << "\"violations\":" << failed << ","
            << "\"identity_combinations\":" << identity << ","
            << "\"odd_x_combinations\":" << odd_x << ","
            << "\"first_violation\":";
        if (failed)
            out << "{\"indices\":[" << first_i << "," << first_j << "],"
                << "\"point\":[" << first_point.x << "," << first_point.y << "]}";
        else out << "null";
        out << ",\"setup_ns\":" << setup_ns
            << ",\"check_ns\":" << check_ns
            << ",\"peak_rss_bytes\":" << peak_rss_bytes() << "}\n";
        std::cout << status << " checked=" << checked << " violations=" << failed << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
