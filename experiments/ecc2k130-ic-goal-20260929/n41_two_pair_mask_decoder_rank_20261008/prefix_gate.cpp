// Evaluate the quadratic relation on every admissible fixed-target prefix residual.
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

struct IndexedPairForCheck {
    Point sum;
    uint16_t first_column, second_column;
};

static std::vector<IndexedPairForCheck> indexed_pairs(
        const std::vector<SeedForCheck>& seeds) {
    std::vector<IndexedPairForCheck> result;
    for (int i = 0; i < 64; ++i)
        for (int j = i + 1; j < 64; ++j)
            if (seeds[i].column != seeds[j].column) {
                Point total = add(seeds[i].point, seeds[j].point);
                if (total.infinity) throw std::runtime_error("identity pair");
                result.push_back({total, seeds[i].column, seeds[j].column});
            }
    if (result.size() != 1956) throw std::runtime_error("pair domain size mismatch");
    return result;
}

int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::runtime_error("usage: prefix_gate native_input relation result");
        auto setup_start = std::chrono::steady_clock::now();
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("missing native input");
        uint64_t qx, qy, subgroup_order;
        int summands;
        input >> qx >> qy >> subgroup_order >> summands;
        if (!input || qx != 1458168294740ULL || qy != 1672312028033ULL ||
            subgroup_order != 549756390943ULL || summands != 8)
            throw std::runtime_error("wrong frozen N41 input header");
        Point target = finite(qx, qy);
        if (!on_curve(target)) throw std::runtime_error("off-curve target");
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
        auto first = indexed_pairs(seeds[0]);
        auto second = indexed_pairs(seeds[1]);
        uint64_t setup_ns = elapsed_ns(setup_start);

        auto query_start = std::chrono::steady_clock::now();
        uint64_t visited = 0, admissible = 0, column_rejected = 0;
        uint64_t identity = 0, odd_x = 0, equation_rejected = 0, equation_passed = 0;
        bool time_cap = false, memory_cap = false;
        size_t first_fail_i = 0, first_fail_j = 0;
        Point first_fail;
        for (size_t i = 0; i < first.size(); ++i) {
            Point after_first = add(target, neg(first[i].sum));
            for (size_t j = 0; j < second.size(); ++j) {
                ++visited;
                const auto& a = first[i];
                const auto& b = second[j];
                if (a.first_column == b.first_column ||
                    a.first_column == b.second_column ||
                    a.second_column == b.first_column ||
                    a.second_column == b.second_column) {
                    ++column_rejected;
                    continue;
                }
                ++admissible;
                Point residual = add(after_first, neg(b.sum));
                if (residual.infinity) ++identity;
                else if (residual.x & 1) ++odd_x;
                else if (equation.evaluate(residual)) {
                    ++equation_rejected;
                    if (equation_rejected == 1) {
                        first_fail_i = i;
                        first_fail_j = j;
                        first_fail = residual;
                    }
                } else ++equation_passed;
                if ((admissible & 16383) == 0) {
                    time_cap = elapsed_ns(query_start) >= 180000000000ULL;
                    memory_cap = peak_rss_bytes() >= 4ULL * 1024 * 1024 * 1024;
                    if (time_cap || memory_cap) break;
                }
            }
            if (time_cap || memory_cap) break;
        }
        uint64_t query_ns = elapsed_ns(query_start);
        const char* status = time_cap ? "TIME_CAP" : memory_cap ?
                             "MEMORY_CAP" : "COMPLETE_PREFIX_SCAN";
        std::ofstream out(argv[3]);
        if (!out) throw std::runtime_error("cannot open result");
        out << "{\"kind\":\"n41_target_prefix_quadratic_gate_scan\","
            << "\"status\":\"" << status << "\","
            << "\"candidate_id\":null,\"run_id\":null,"
            << "\"target\":[" << qx << "," << qy << "],"
            << "\"pair_sizes\":[" << first.size() << "," << second.size() << "],"
            << "\"visited_prefixes\":" << visited << ","
            << "\"admissible_prefixes\":" << admissible << ","
            << "\"column_rejected_prefixes\":" << column_rejected << ","
            << "\"identity_residuals\":" << identity << ","
            << "\"odd_x_residuals\":" << odd_x << ","
            << "\"equation_rejected_prefixes\":" << equation_rejected << ","
            << "\"equation_passed_prefixes\":" << equation_passed << ","
            << "\"first_equation_rejection\":";
        if (equation_rejected)
            out << "{\"indices\":[" << first_fail_i << "," << first_fail_j << "],"
                << "\"residual\":[" << first_fail.x << "," << first_fail.y << "]}";
        else out << "null";
        out << ",\"setup_ns\":" << setup_ns
            << ",\"query_ns\":" << query_ns
            << ",\"peak_rss_bytes\":" << peak_rss_bytes() << "}\n";
        std::cout << status << " admissible=" << admissible
                  << " equation_rejected=" << equation_rejected << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
