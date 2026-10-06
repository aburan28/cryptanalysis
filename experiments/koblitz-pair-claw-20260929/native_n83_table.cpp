// Bounded lossless n=83 quotient table and target lookup.
// Exact 83-bit x keys are stored without witnesses. A verified hit rescans
// the deterministic table schedule once to recover the pair descriptor.
#define main native_pair_stage_main
#include "native_n83_pairs.cpp"
#undef main

#include <sys/resource.h>

struct __attribute__((packed)) Entry {
    U lo = 0;
    uint32_t hi = 0xffffffffu;
};
static_assert(sizeof(Entry) == 12, "packed key entry must be 12 bytes");

U hash_key(V key) {
    U z = U(key) ^ (U(key >> 64) * 0x9e3779b97f4a7c15ull);
    z ^= z >> 30;
    z *= 0xbf58476d1ce4e5b9ull;
    z ^= z >> 27;
    z *= 0x94d049bb133111ebull;
    return z ^ (z >> 31);
}
struct ExactTable {
    std::vector<Entry> slots;
    U distinct = 0, duplicate = 0, insert_probes = 0, lookup_probes = 0;
    explicit ExactTable(U entries) {
        U capacity = entries * 10 / 7 + 1024;
        need(capacity > entries && capacity <= SIZE_MAX / sizeof(Entry),
             "table capacity out of range");
        slots.assign(size_t(capacity), Entry{});
    }
    bool insert(V key) {
        U position = hash_key(key) % slots.size();
        U lo = U(key);
        uint32_t hi = uint32_t(key >> 64);
        for (U probes = 0; probes < slots.size(); ++probes) {
            ++insert_probes;
            Entry &entry = slots[position];
            if (entry.hi == 0xffffffffu) {
                entry.lo = lo; entry.hi = hi; ++distinct;
                return true;
            }
            if (entry.lo == lo && entry.hi == hi) {
                ++duplicate;
                return false;
            }
            if (++position == slots.size()) position = 0;
        }
        throw std::runtime_error("exact table full");
    }
    bool contains(V key) {
        U position = hash_key(key) % slots.size();
        U lo = U(key);
        uint32_t hi = uint32_t(key >> 64);
        for (U probes = 0; probes < slots.size(); ++probes) {
            ++lookup_probes;
            const Entry &entry = slots[position];
            if (entry.hi == 0xffffffffu) return false;
            if (entry.lo == lo && entry.hi == hi) return true;
            if (++position == slots.size()) position = 0;
        }
        throw std::runtime_error("exact table lookup exhausted");
    }
};

struct Hit { U query_position, table_position = U(-1); V key; };

int main(int argc, char **argv) {
    try {
        need(argc == 11, "usage: native_n83_table BASE TARGET_X_ONB_HEX TARGET_Y_ONB_HEX TABLE_DESCRIPTORS QUERY_PAIRS BATCH TABLE_STEP TABLE_OFFSET QUERY_STEP QUERY_OFFSET");
        Keyer keyer;
        auto base = load_base(argv[1], keyer);
        self_test(base);
        Point target{onb_to_pb(parse_hex(argv[2])),
                     onb_to_pb(parse_hex(argv[3])), false};
        need(on_curve(target), "target off curve");
        U table_entries = std::stoull(argv[4]);
        U query_pairs = std::stoull(argv[5]);
        U batch_size = std::stoull(argv[6]);
        U table_step = std::stoull(argv[7]), table_offset = std::stoull(argv[8]);
        U query_step = std::stoull(argv[9]), query_offset = std::stoull(argv[10]);
        const U d_cross = U(K) * (K - 1) / 2 * L;
        const U pair_domain = U(base.size()) * (base.size() + 1) / 2;
        need(table_entries > 0 && table_entries <= d_cross &&
             query_pairs > 0 && query_pairs <= pair_domain &&
             batch_size > 0 && batch_size <= 8192, "invalid bounded work");
        auto before_allocation = std::chrono::steady_clock::now();
        ExactTable table(table_entries);
        double allocation_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - before_allocation).count();
        std::vector<Point> left, right, sums, targets, complements;
        left.reserve(batch_size); right.reserve(batch_size);
        targets.reserve(batch_size);
        auto begun = std::chrono::steady_clock::now();
        for (U position = 0; position < table_entries; position += batch_size) {
            U count = std::min(batch_size, table_entries - position);
            left.clear(); right.clear();
            for (U i = 0; i < count; ++i) {
                U rank = scheduled_rank(position + i, d_cross,
                                        table_step, table_offset);
                auto pair = cross_pair(rank);
                left.push_back(base[pair[0] * L]);
                right.push_back(base[pair[1] * L + pair[2]]);
            }
            batch_add(left, right, sums);
            for (U i = 0; i < count; ++i) {
                need(!sums[i].inf, "cross-orbit zero pair");
                table.insert(keyer.canonical_x(sums[i].x));
            }
        }
        double table_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - begun).count();
        std::vector<Hit> hits;
        U total_hits = 0;
        begun = std::chrono::steady_clock::now();
        for (U position = 0; position < query_pairs; position += batch_size) {
            U count = std::min(batch_size, query_pairs - position);
            left.clear(); right.clear(); targets.clear();
            for (U i = 0; i < count; ++i) {
                U rank = scheduled_rank(position + i, pair_domain,
                                        query_step, query_offset);
                auto pair = unordered_pair(rank);
                left.push_back(base[pair.first]);
                right.push_back(base[pair.second]);
            }
            batch_add(left, right, sums);
            for (U i = 0; i < count; ++i) {
                targets.push_back(target);
                sums[i] = neg(sums[i]);
            }
            batch_add(targets, sums, complements);
            for (U i = 0; i < count; ++i) {
                if (complements[i].inf) continue;
                V key = keyer.canonical_x(complements[i].x);
                if (table.contains(key)) {
                    ++total_hits;
                    if (hits.size() < 16)
                        hits.push_back({position + i, U(-1), key});
                }
            }
        }
        double query_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - begun).count();
        double replay_seconds = 0;
        if (!hits.empty()) {
            begun = std::chrono::steady_clock::now();
            for (U position = 0; position < table_entries; position += batch_size) {
                U count = std::min(batch_size, table_entries - position);
                left.clear(); right.clear();
                for (U i = 0; i < count; ++i) {
                    U rank = scheduled_rank(position + i, d_cross,
                                            table_step, table_offset);
                    auto pair = cross_pair(rank);
                    left.push_back(base[pair[0] * L]);
                    right.push_back(base[pair[1] * L + pair[2]]);
                }
                batch_add(left, right, sums);
                for (U i = 0; i < count; ++i) {
                    if (sums[i].inf) continue;
                    V key = keyer.canonical_x(sums[i].x);
                    for (Hit &hit : hits)
                        if (hit.table_position == U(-1) && key == hit.key)
                            hit.table_position = position + i;
                }
                bool done = true;
                for (const Hit &hit : hits)
                    if (hit.table_position == U(-1)) done = false;
                if (done) break;
            }
            for (const Hit &hit : hits)
                need(hit.table_position != U(-1), "hash hit absent on replay");
            replay_seconds = std::chrono::duration<double>(
                std::chrono::steady_clock::now() - begun).count();
        }
        struct rusage usage{};
        getrusage(RUSAGE_SELF, &usage);
        std::cout << "{\"actual_B\":" << base.size()
                  << ",\"table_descriptors\":" << table_entries
                  << ",\"query_pairs\":" << query_pairs
                  << ",\"batch_size\":" << batch_size
                  << ",\"table_capacity\":" << table.slots.size()
                  << ",\"table_slot_bytes\":" << sizeof(Entry)
                  << ",\"table_bytes\":" << table.slots.size() * sizeof(Entry)
                  << ",\"table_distinct_keys\":" << table.distinct
                  << ",\"table_duplicate_keys\":" << table.duplicate
                  << ",\"table_insert_probes\":" << table.insert_probes
                  << ",\"query_lookup_probes\":" << table.lookup_probes
                  << ",\"key_hits\":" << total_hits
                  << ",\"allocation_seconds\":" << std::setprecision(12)
                  << allocation_seconds
                  << ",\"table_seconds\":" << table_seconds
                  << ",\"query_seconds\":" << query_seconds
                  << ",\"replay_seconds\":" << replay_seconds
                  << ",\"peak_rss_bytes\":" << usage.ru_maxrss
                  << ",\"hits\":[";
        for (size_t i = 0; i < hits.size(); ++i) {
            if (i) std::cout << ',';
            std::cout << "{\"query_position\":" << hits[i].query_position
                      << ",\"table_position\":" << hits[i].table_position
                      << ",\"x_key_hex\":\"" << hex(hits[i].key) << "\"}";
        }
        std::cout << "]}" << std::endl;
    } catch (const std::exception &e) {
        std::cerr << e.what() << std::endl;
        return 1;
    }
}
