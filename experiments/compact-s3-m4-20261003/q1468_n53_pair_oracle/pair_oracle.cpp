// Exact four-point pair-sum oracle for Q1467's N53 factor base.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "../q1420_root_theory/root_field.hpp"

namespace {

using q1420::Field;
using q1420::U128;
using q1420::hex;
using q1420::parse_hex;
using q1420::require;
using Clock = std::chrono::steady_clock;

struct Point {
    U128 x = 0, y = 0;
    bool infinity = true;
};

bool equal(const Point &a, const Point &b) {
    return a.infinity == b.infinity &&
           (a.infinity || (a.x == b.x && a.y == b.y));
}

Point neg(const Point &point) {
    return point.infinity ? point : Point{point.x, point.x ^ point.y, false};
}

bool on_curve(Field &field, const Point &point) {
    if (point.infinity) return true;
    return (field.sqr(point.y) ^ field.mul(point.x, point.y)) ==
           (field.mul(field.sqr(point.x), point.x) ^ 1);
}

Point add(Field &field, const Point &a, const Point &b) {
    if (a.infinity) return b;
    if (b.infinity) return a;
    if (a.x == b.x) {
        if (a.y != b.y) {
            require(b.y == (a.x ^ a.y), "same x with noninverse y");
            return {};
        }
        if (a.x == 0) return {};
        U128 slope = a.x ^ field.mul(a.y, field.inv(a.x));
        U128 x = field.sqr(slope) ^ slope;
        U128 y = field.sqr(a.x) ^ field.mul(slope ^ 1, x);
        return {x, y, false};
    }
    U128 slope = field.mul(a.y ^ b.y, field.inv(a.x ^ b.x));
    U128 x = field.sqr(slope) ^ slope ^ a.x ^ b.x;
    U128 y = field.mul(slope, a.x ^ x) ^ x ^ a.y;
    return {x, y, false};
}

std::vector<Point> batch_add_fixed(Field &field, const Point &fixed,
                                   const std::vector<Point> &other) {
    require(!fixed.infinity, "batch fixed point is infinity");
    std::vector<Point> result(other.size());
    std::vector<U128> denominator, prefix, inverse;
    std::vector<size_t> position;
    denominator.reserve(other.size());
    position.reserve(other.size());
    for (size_t index = 0; index < other.size(); ++index) {
        const Point &point = other[index];
        if (point.infinity || point.x == fixed.x) {
            result[index] = add(field, fixed, point);
        } else {
            position.push_back(index);
            denominator.push_back(fixed.x ^ point.x);
        }
    }
    if (!denominator.empty()) {
        prefix.reserve(denominator.size() + 1);
        prefix.push_back(1);
        for (U128 value : denominator)
            prefix.push_back(field.mul(prefix.back(), value));
        U128 running = field.inv(prefix.back());
        inverse.resize(denominator.size());
        for (size_t k = denominator.size(); k-- > 0;) {
            inverse[k] = field.mul(running, prefix[k]);
            running = field.mul(running, denominator[k]);
        }
        require(running == 1, "batch inversion did not unwind");
        for (size_t k = 0; k < position.size(); ++k) {
            const Point &point = other[position[k]];
            U128 slope = field.mul(fixed.y ^ point.y, inverse[k]);
            U128 x = field.sqr(slope) ^ slope ^ fixed.x ^ point.x;
            U128 y = field.mul(slope, fixed.x ^ x) ^ x ^ fixed.y;
            result[position[k]] = {x, y, false};
        }
    }
    return result;
}

struct Base {
    std::vector<Point> points;
    std::vector<unsigned> columns;
};

Base read_base(Field &field, const std::string &path) {
    std::ifstream input(path);
    require(bool(input), "base file missing");
    std::string magic, x, y;
    int n = 0, size = 0, column_count = 0;
    input >> magic >> n >> size >> column_count;
    require(magic == "Q1468BASE1" && n == 53 && size == 2756 &&
            column_count == 26, "bad base header");
    Base base;
    base.points.reserve(size);
    base.columns.reserve(size);
    std::vector<unsigned> per_column(column_count);
    for (int i = 0; i < size; ++i) {
        int column = -1;
        input >> column >> x >> y;
        require(bool(input) && column >= 0 && column < column_count,
                "short base or invalid column");
        U128 coord_x = parse_hex(x), coord_y = parse_hex(y);
        require((coord_x & ~field.mask) == 0 &&
                (coord_y & ~field.mask) == 0, "base element overflow");
        Point point{field.to_poly(coord_x), field.to_poly(coord_y), false};
        require(on_curve(field, point), "base point is off curve");
        base.points.push_back(point);
        base.columns.push_back(unsigned(column));
        ++per_column[column];
    }
    require(!(input >> magic), "extra base rows");
    require(std::all_of(per_column.begin(), per_column.end(),
                        [](unsigned count) { return count == 106; }),
            "base columns are not complete signed Frobenius orbits");
    return base;
}

Point read_target(Field &field, const std::string &path) {
    std::ifstream input(path);
    require(bool(input), "target file missing");
    std::string magic, x, y;
    int n = 0;
    input >> magic >> n >> x >> y;
    require(bool(input) && magic == "Q1468TARGET1" && n == 53,
            "bad target header");
    require(!(input >> magic), "extra target rows");
    U128 coord_x = parse_hex(x), coord_y = parse_hex(y);
    require((coord_x & ~field.mask) == 0 &&
            (coord_y & ~field.mask) == 0, "target overflow");
    Point target{field.to_poly(coord_x), field.to_poly(coord_y), false};
    require(on_curve(field, target), "target is off curve");
    return target;
}

struct Entry {
    uint64_t low = 0, high = 0;
    uint32_t pair = 0;
};

Entry encode(const Point &point, uint32_t pair = 0) {
    require(!point.infinity, "cannot encode group identity");
    U128 packed = point.x | (point.y << 53);
    return {uint64_t(packed), uint64_t(packed >> 64), pair};
}

Point decode(const Entry &entry) {
    U128 packed = U128(entry.low) | (U128(entry.high) << 64);
    U128 mask = (U128(1) << 53) - 1;
    return {packed & mask, (packed >> 53) & mask, false};
}

bool less_key(const Entry &a, const Entry &b) {
    return a.high < b.high || (a.high == b.high && a.low < b.low);
}

bool same_key(const Entry &a, const Entry &b) {
    return a.high == b.high && a.low == b.low;
}

uint32_t pair_code(unsigned i, unsigned j) {
    require(i < 65536 && j < 65536, "pair index overflow");
    return (i << 16) | j;
}

unsigned first(uint32_t pair) { return pair >> 16; }
unsigned second(uint32_t pair) { return pair & 65535; }

uint64_t elapsed_ns(Clock::time_point start) {
    return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
        Clock::now() - start).count());
}

void write_counts(std::ostream &stream, const q1420::Counts &counts) {
    stream << "{\"mul\":" << counts.mul << ",\"sqr\":" << counts.sqr
           << ",\"inv\":" << counts.inv << "}";
}

void self_test(Field &field, const Base &base) {
    constexpr unsigned samples = 64;
    std::vector<Point> other;
    std::vector<unsigned> indices;
    for (unsigned t = 0; t < samples; ++t) {
        unsigned index = 106 + t * 19;
        indices.push_back(index);
        other.push_back(base.points[index]);
    }
    std::vector<Point> batch = batch_add_fixed(field, base.points[0], other);
    std::cout << "{\"mode\":\"selftest\",\"samples\":[";
    for (unsigned t = 0; t < samples; ++t) {
        Point direct = add(field, base.points[0], other[t]);
        require(equal(batch[t], direct) && !direct.infinity,
                "batch point addition mismatch");
        require(on_curve(field, direct), "sample sum is off curve");
        if (t) std::cout << ',';
        std::cout << "{\"i\":0,\"j\":" << indices[t]
                  << ",\"x_onb\":\"" << hex(field.to_onb(direct.x))
                  << "\",\"y_onb\":\"" << hex(field.to_onb(direct.y))
                  << "\"}";
    }
    std::cout << "]}" << std::endl;
}

void run(Field &field, const Base &base, const Point &target,
         uint64_t wall_cap_ns) {
    constexpr size_t expected = 3651700;
    field.counts = {};
    Clock::time_point table_start = Clock::now();
    std::vector<Entry> table;
    table.reserve(expected);
    for (unsigned i = 0; i < base.points.size(); ++i) {
        std::vector<Point> other;
        std::vector<unsigned> indices;
        for (unsigned j = i + 1; j < base.points.size(); ++j) {
            if (base.columns[i] == base.columns[j]) continue;
            other.push_back(base.points[j]);
            indices.push_back(j);
        }
        std::vector<Point> sums = batch_add_fixed(field, base.points[i], other);
        for (size_t k = 0; k < sums.size(); ++k) {
            require(!sums[k].infinity, "cross-column pair summed to identity");
            table.push_back(encode(sums[k], pair_code(i, indices[k])));
        }
        if ((i & 63U) == 0 && elapsed_ns(table_start) > wall_cap_ns)
            throw std::runtime_error("table wall cap reached");
    }
    require(table.size() == expected, "incomplete pair table");
    std::sort(table.begin(), table.end(), less_key);
    size_t duplicate_sums = 0;
    for (size_t i = 1; i < table.size(); ++i)
        duplicate_sums += same_key(table[i - 1], table[i]);
    uint64_t table_ns = elapsed_ns(table_start);
    q1420::Counts table_counts = field.counts;
    field.counts = {};

    Clock::time_point query_start = Clock::now();
    bool found = false, cap = false;
    unsigned witness[4] = {};
    size_t checked = 0, complement_hits = 0, rejected_columns = 0;
    constexpr size_t batch_size = 4096;
    for (size_t offset = 0; offset < table.size(); offset += batch_size) {
        if (elapsed_ns(query_start) > wall_cap_ns) { cap = true; break; }
        size_t length = std::min(batch_size, table.size() - offset);
        std::vector<Point> negatives;
        negatives.reserve(length);
        for (size_t k = 0; k < length; ++k)
            negatives.push_back(neg(decode(table[offset + k])));
        std::vector<Point> complements = batch_add_fixed(field, target,
                                                          negatives);
        checked += length;
        for (size_t k = 0; k < length && !found; ++k) {
            if (complements[k].infinity) continue;
            Entry key = encode(complements[k]);
            auto hit = std::lower_bound(table.begin(), table.end(), key,
                                        less_key);
            for (; hit != table.end() && same_key(*hit, key); ++hit) {
                ++complement_hits;
                unsigned a = first(table[offset + k].pair);
                unsigned b = second(table[offset + k].pair);
                unsigned c = first(hit->pair);
                unsigned d = second(hit->pair);
                unsigned columns[4] = {base.columns[a], base.columns[b],
                                       base.columns[c], base.columns[d]};
                bool distinct = true;
                for (int x = 0; x < 4; ++x)
                    for (int y = x + 1; y < 4; ++y)
                        distinct &= columns[x] != columns[y];
                if (!distinct) { ++rejected_columns; continue; }
                Point left = add(field, base.points[a], base.points[b]);
                Point right = add(field, base.points[c], base.points[d]);
                require(equal(add(field, left, right), target),
                        "pair-table witness did not replay");
                witness[0] = a; witness[1] = b;
                witness[2] = c; witness[3] = d;
                found = true;
                break;
            }
        }
        if (found) break;
    }
    uint64_t query_ns = elapsed_ns(query_start);
    q1420::Counts query_counts = field.counts;
    std::cout << "{\"mode\":\"query\",\"status\":\""
              << (found ? "found" : (cap ? "censored" : "absent"))
              << "\",\"complete_pair_table\":true,\"pair_table_entries\":"
              << table.size() << ",\"duplicate_pair_sums\":"
              << duplicate_sums << ",\"table_wall_ns\":" << table_ns
              << ",\"query_wall_ns\":" << query_ns
              << ",\"query_pair_sums_examined\":" << checked
              << ",\"complement_hits\":" << complement_hits
              << ",\"rejected_shared_columns\":" << rejected_columns
              << ",\"table_field_calls\":";
    write_counts(std::cout, table_counts);
    std::cout << ",\"query_field_calls\":";
    write_counts(std::cout, query_counts);
    std::cout << ",\"witness_indices\":";
    if (found) {
        std::cout << '[' << witness[0] << ',' << witness[1] << ','
                  << witness[2] << ',' << witness[3] << ']';
    } else {
        std::cout << "null";
    }
    std::cout << "}" << std::endl;
}

}  // namespace

int main(int argc, char **argv) {
    try {
        require(argc == 4 || argc == 5, "usage: oracle field base --selftest | field base target wall_cap_seconds");
        Field field(argv[1]);
        require(field.n == 53, "only N53 is admitted");
        Base base = read_base(field, argv[2]);
        if (argc == 4) {
            require(std::string(argv[3]) == "--selftest", "bad mode");
            self_test(field, base);
        } else {
            Point target = read_target(field, argv[3]);
            unsigned long long seconds = std::stoull(argv[4]);
            require(seconds > 0 && seconds <= 3600, "bad wall cap");
            run(field, base, target, seconds * 1000000000ULL);
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "Q1468 pair oracle error: " << error.what() << '\n';
        return 1;
    }
}
