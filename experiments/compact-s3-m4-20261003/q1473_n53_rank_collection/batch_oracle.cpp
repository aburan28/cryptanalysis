// Q1473: reuse Q1468's exact cross-column pair table for frozen N53 queries.
// Include the original implementation so field arithmetic, point addition,
// key encoding and witness checks have exactly the same source definitions.
#define main q1468_unused_main
#include "../q1468_n53_pair_oracle/pair_oracle.cpp"
#undef main

namespace {

struct IndexedTarget {
    unsigned index;
    Point point;
};

std::vector<IndexedTarget> read_targets(Field &field, const char *path) {
    std::ifstream input(path);
    require(bool(input), "target list missing");
    std::string magic, x, y;
    unsigned degree = 0, count = 0;
    input >> magic >> degree >> count;
    require(magic == "Q1473TARGETS1" && degree == 53 && count > 0 &&
                count <= 4096, "bad target list header");
    std::vector<IndexedTarget> answer;
    answer.reserve(count);
    for (unsigned i = 0; i < count; ++i) {
        unsigned index;
        input >> index >> x >> y;
        require(bool(input) && index == i, "short or unordered target list");
        U128 ox = parse_hex(x), oy = parse_hex(y);
        require((ox & ~field.mask) == 0 && (oy & ~field.mask) == 0,
                "target element overflow");
        Point point{field.to_poly(ox), field.to_poly(oy), false};
        require(on_curve(field, point), "target is off curve");
        answer.push_back({i, point});
    }
    require(!(input >> magic), "extra target rows");
    return answer;
}

std::vector<Entry> build_table(Field &field, const Base &base,
                               uint64_t wall_cap_ns) {
    constexpr size_t expected = 3651700;
    Clock::time_point start = Clock::now();
    field.counts = {};
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
        auto sums = batch_add_fixed(field, base.points[i], other);
        for (size_t k = 0; k < sums.size(); ++k) {
            require(!sums[k].infinity, "cross-column pair is identity");
            table.push_back(encode(sums[k], pair_code(i, indices[k])));
        }
        if ((i & 63U) == 0 && elapsed_ns(start) > wall_cap_ns)
            throw std::runtime_error("table wall cap reached");
    }
    require(table.size() == expected, "incomplete pair table");
    std::sort(table.begin(), table.end(), less_key);
    size_t duplicates = 0;
    for (size_t i = 1; i < table.size(); ++i)
        duplicates += same_key(table[i - 1], table[i]);
    std::cout << "{\"mode\":\"setup\",\"pair_table_entries\":"
              << table.size() << ",\"duplicate_pair_sums\":" << duplicates
              << ",\"table_wall_ns\":" << elapsed_ns(start)
              << ",\"table_field_calls\":";
    write_counts(std::cout, field.counts);
    std::cout << "}" << std::endl;
    return table;
}

void query(Field &field, const Base &base, const std::vector<Entry> &table,
           const IndexedTarget &target, uint64_t wall_cap_ns) {
    field.counts = {};
    auto start = Clock::now();
    bool found = false, capped = false;
    unsigned witness[4] = {};
    size_t checked = 0, hits = 0, rejected = 0;
    constexpr size_t batch_size = 4096;
    for (size_t offset = 0; offset < table.size(); offset += batch_size) {
        if (elapsed_ns(start) > wall_cap_ns) { capped = true; break; }
        size_t length = std::min(batch_size, table.size() - offset);
        std::vector<Point> negatives;
        negatives.reserve(length);
        for (size_t k = 0; k < length; ++k)
            negatives.push_back(neg(decode(table[offset + k])));
        auto complements = batch_add_fixed(field, target.point, negatives);
        checked += length;
        for (size_t k = 0; k < length && !found; ++k) {
            if (complements[k].infinity) continue;
            Entry key = encode(complements[k]);
            auto hit = std::lower_bound(table.begin(), table.end(), key,
                                        less_key);
            for (; hit != table.end() && same_key(*hit, key); ++hit) {
                ++hits;
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
                if (!distinct) { ++rejected; continue; }
                Point left = add(field, base.points[a], base.points[b]);
                Point right = add(field, base.points[c], base.points[d]);
                require(equal(add(field, left, right), target.point),
                        "pair-table witness did not replay");
                witness[0] = a; witness[1] = b;
                witness[2] = c; witness[3] = d;
                found = true;
                break;
            }
        }
        if (found) break;
    }
    std::cout << "{\"mode\":\"query\",\"index\":" << target.index
              << ",\"status\":\""
              << (found ? "found" : capped ? "censored" : "absent")
              << "\",\"query_wall_ns\":" << elapsed_ns(start)
              << ",\"query_pair_sums_examined\":" << checked
              << ",\"complement_hits\":" << hits
              << ",\"rejected_shared_columns\":" << rejected
              << ",\"query_field_calls\":";
    write_counts(std::cout, field.counts);
    std::cout << ",\"witness_indices\":";
    if (found)
        std::cout << '[' << witness[0] << ',' << witness[1] << ','
                  << witness[2] << ',' << witness[3] << ']';
    else
        std::cout << "null";
    std::cout << "}" << std::endl;
}

}  // namespace

int main(int argc, char **argv) {
    try {
        require(argc == 6,
                "usage: batch_oracle FIELD BASE TARGETS WALL_CAP_S COUNT");
        Field field(argv[1]);
        require(field.n == 53, "only N53 is admitted");
        Base base = read_base(field, argv[2]);
        auto targets = read_targets(field, argv[3]);
        unsigned long long seconds = std::stoull(argv[4]);
        require(seconds > 0 && seconds <= 3600, "bad wall cap");
        unsigned count = unsigned(std::stoul(argv[5]));
        require(count > 0 && count <= targets.size(), "bad target count");
        auto table = build_table(field, base, seconds * 1000000000ULL);
        for (unsigned i = 0; i < count; ++i)
            query(field, base, table, targets[i], seconds * 1000000000ULL);
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "Q1473 batch oracle error: " << error.what() << '\n';
        return 1;
    }
}
