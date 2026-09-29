// Bounded, memory-conscious n=83 quotient-key filter and exact replay.
// The Bloom filter is only a candidate screen. Every positive query key is
// checked against a second, exact pass over the deterministic table schedule.
#define main native_pair_stage_main
#include "native_n83_pairs.cpp"
#undef main

#include <sys/resource.h>
#include <thread>

struct alignas(64) BloomBlock { std::array<U, 8> word{}; };
static_assert(sizeof(BloomBlock) == 64, "Bloom block must be one cache line");

U mix64(U x) {
    x ^= x >> 30;
    x *= 0xbf58476d1ce4e5b9ull;
    x ^= x >> 27;
    x *= 0x94d049bb133111ebull;
    return x ^ (x >> 31);
}
U hash83(V key) {
    return mix64(U(key) ^ mix64(U(key >> 64) +
                              0x9e3779b97f4a7c15ull));
}

struct Bloom {
    std::vector<BloomBlock> blocks;
    unsigned hashes;
    Bloom(U entries, unsigned bits_per_key, unsigned hash_count)
        : hashes(hash_count) {
        need(bits_per_key >= 8 && bits_per_key <= 64 &&
             hash_count >= 1 && hash_count <= 32,
             "invalid Bloom parameters");
        U count = (entries * bits_per_key + 511) / 512 + 1024;
        need(count > 0 && count <= SIZE_MAX / sizeof(BloomBlock),
             "Bloom size overflow");
        blocks.resize(size_t(count));
    }
    template <typename F> void positions(V key, F action) const {
        U h = hash83(key);
        size_t block0 = size_t(h % blocks.size());
        size_t block1 = size_t(mix64(h ^ 0xbb67ae8584caa73bull) %
                               blocks.size());
        U stream = h ^ 0x6a09e667f3bcc909ull;
        for (unsigned j = 0; j < hashes; ++j) {
            stream += 0x9e3779b97f4a7c15ull;
            action((j & 1) ? block1 : block0,
                   unsigned(mix64(stream) & 511));
        }
    }
    void insert(V key) {
        positions(key, [&](size_t b, unsigned bit) {
            blocks[b].word[bit >> 6] |= U(1) << (bit & 63);
        });
    }
    bool contains(V key) const {
        bool found = true;
        positions(key, [&](size_t b, unsigned bit) {
            found &= bool(blocks[b].word[bit >> 6] &
                          (U(1) << (bit & 63)));
        });
        return found;
    }
    U bytes() const { return U(blocks.size()) * sizeof(BloomBlock); }
    void release() { std::vector<BloomBlock>().swap(blocks); }
};

struct __attribute__((packed)) Candidate { V key; U query_position; };
static_assert(sizeof(Candidate) == 24, "candidate record layout changed");
struct __attribute__((packed)) CandidateSlot {
    U lo = 0;
    uint32_t hi = 0xffffffffu;
    U query_position = 0;
    U table_position = U(-1);
};
static_assert(sizeof(CandidateSlot) == 28, "candidate slot layout changed");

struct CandidateTable {
    std::vector<CandidateSlot> slots;
    U duplicate_keys = 0;
    explicit CandidateTable(size_t count) {
        size_t capacity = count * 10 / 7 + 1024;
        need(capacity > count, "candidate table capacity overflow");
        slots.assign(capacity, CandidateSlot{});
    }
    CandidateSlot &slot(V key) {
        size_t position = size_t(hash83(key) % slots.size());
        U lo = U(key);
        uint32_t hi = uint32_t(key >> 64);
        for (size_t probes = 0; probes < slots.size(); ++probes) {
            CandidateSlot &entry = slots[position];
            if (entry.hi == 0xffffffffu ||
                (entry.lo == lo && entry.hi == hi))
                return entry;
            if (++position == slots.size()) position = 0;
        }
        throw std::runtime_error("candidate table full");
    }
    void insert(Candidate candidate) {
        CandidateSlot &entry = slot(candidate.key);
        if (entry.hi != 0xffffffffu) { ++duplicate_keys; return; }
        entry.lo = U(candidate.key);
        entry.hi = uint32_t(candidate.key >> 64);
        entry.query_position = candidate.query_position;
    }
    CandidateSlot *find(V key) {
        CandidateSlot &entry = slot(key);
        return entry.hi == 0xffffffffu ? nullptr : &entry;
    }
};

int main(int argc, char **argv) {
    try {
        need(argc == 15 || argc == 16, "usage: native_n83_bloom BASE TARGET_X_ONB_HEX TARGET_Y_ONB_HEX TABLE_DESCRIPTORS QUERY_PAIRS BATCH TABLE_STEP TABLE_OFFSET QUERY_STEP QUERY_OFFSET BITS_PER_KEY HASHES QUERY_START QUERY_WORKERS [TABLE_START]");
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
        unsigned bits_per_key = unsigned(std::stoul(argv[11]));
        unsigned hashes = unsigned(std::stoul(argv[12]));
        U query_start = std::stoull(argv[13]);
        unsigned query_workers = unsigned(std::stoul(argv[14]));
        U table_start = argc == 16 ? std::stoull(argv[15]) : 0;
        const U d_cross = U(K) * (K - 1) / 2 * L;
        const U pair_domain = U(base.size()) * (base.size() + 1) / 2;
        need(table_entries > 0 && table_start < d_cross &&
             table_entries <= d_cross - table_start &&
             query_pairs > 0 && query_start < pair_domain &&
             query_pairs <= pair_domain - query_start &&
             batch_size > 0 && batch_size <= 8192 &&
             query_workers > 0 && query_workers <= 64,
             "invalid bounded work");

        auto started = std::chrono::steady_clock::now();
        Bloom bloom(table_entries, bits_per_key, hashes);
        double allocation_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started).count();
        U bloom_bytes = bloom.bytes();
        std::vector<Point> left, right, sums, targets, complements;
        left.reserve(batch_size); right.reserve(batch_size);
        targets.reserve(batch_size);
        started = std::chrono::steady_clock::now();
        for (U position = 0; position < table_entries; position += batch_size) {
            U count = std::min(batch_size, table_entries - position);
            left.clear(); right.clear();
            for (U i = 0; i < count; ++i) {
                U rank = scheduled_rank(table_start + position + i, d_cross,
                                        table_step, table_offset);
                auto pair = cross_pair(rank);
                left.push_back(base[pair[0] * L]);
                right.push_back(base[pair[1] * L + pair[2]]);
            }
            batch_add(left, right, sums);
            for (U i = 0; i < count; ++i) {
                need(!sums[i].inf, "cross-orbit zero pair");
                bloom.insert(keyer.canonical_x(sums[i].x));
            }
        }
        double build_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started).count();

        struct QueryResult {
            std::vector<Candidate> candidates;
            U complement_identity = 0;
        };
        std::vector<QueryResult> query_results(query_workers);
        std::vector<std::exception_ptr> query_errors(query_workers);
        std::vector<std::thread> threads;
        threads.reserve(query_workers);
        U total_batches = (query_pairs + batch_size - 1) / batch_size;
        started = std::chrono::steady_clock::now();
        for (unsigned worker = 0; worker < query_workers; ++worker) {
            threads.emplace_back([&, worker] {
                try {
                    std::vector<Point> qleft, qright, qsums, qtargets,
                        qcomplements;
                    qleft.reserve(batch_size); qright.reserve(batch_size);
                    qtargets.reserve(batch_size);
                    U first_batch = total_batches * worker / query_workers;
                    U end_batch = total_batches * (worker + 1) / query_workers;
                    QueryResult &result = query_results[worker];
                    for (U batch = first_batch; batch < end_batch; ++batch) {
                        U offset = batch * batch_size;
                        U count = std::min(batch_size, query_pairs - offset);
                        qleft.clear(); qright.clear(); qtargets.clear();
                        for (U i = 0; i < count; ++i) {
                            U absolute = query_start + offset + i;
                            U rank = scheduled_rank(absolute, pair_domain,
                                                    query_step, query_offset);
                            auto pair = unordered_pair(rank);
                            qleft.push_back(base[pair.first]);
                            qright.push_back(base[pair.second]);
                        }
                        batch_add(qleft, qright, qsums);
                        for (U i = 0; i < count; ++i) {
                            qtargets.push_back(target);
                            qsums[i] = neg(qsums[i]);
                        }
                        batch_add(qtargets, qsums, qcomplements);
                        for (U i = 0; i < count; ++i) {
                            if (qcomplements[i].inf) {
                                ++result.complement_identity;
                                continue;
                            }
                            V key = keyer.canonical_x(qcomplements[i].x);
                            if (bloom.contains(key))
                                result.candidates.push_back(
                                    {key, query_start + offset + i});
                        }
                    }
                } catch (...) {
                    query_errors[worker] = std::current_exception();
                }
            });
        }
        for (std::thread &thread : threads) thread.join();
        for (const auto &error : query_errors)
            if (error) std::rethrow_exception(error);
        double query_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started).count();
        U bloom_positive_queries = 0;
        U complement_identity = 0;
        U candidate_vector_capacity_bytes = 0;
        for (const QueryResult &result : query_results) {
            bloom_positive_queries += result.candidates.size();
            complement_identity += result.complement_identity;
            candidate_vector_capacity_bytes +=
                U(result.candidates.capacity()) * sizeof(Candidate);
        }

        bloom.release();
        started = std::chrono::steady_clock::now();
        CandidateTable exact{size_t(bloom_positive_queries)};
        for (const QueryResult &result : query_results)
            for (const Candidate &candidate : result.candidates)
                exact.insert(candidate);
        U exact_hit_keys = 0;
        if (bloom_positive_queries) {
            for (U position = 0; position < table_entries; position += batch_size) {
                U count = std::min(batch_size, table_entries - position);
                left.clear(); right.clear();
                for (U i = 0; i < count; ++i) {
                    U rank = scheduled_rank(table_start + position + i, d_cross,
                                            table_step, table_offset);
                    auto pair = cross_pair(rank);
                    left.push_back(base[pair[0] * L]);
                    right.push_back(base[pair[1] * L + pair[2]]);
                }
                batch_add(left, right, sums);
                for (U i = 0; i < count; ++i) {
                    if (sums[i].inf) continue;
                    V key = keyer.canonical_x(sums[i].x);
                    CandidateSlot *entry = exact.find(key);
                    if (entry && entry->table_position == U(-1)) {
                        entry->table_position = table_start + position + i;
                        ++exact_hit_keys;
                    }
                }
            }
        }
        U exact_hit_queries = 0;
        std::vector<Candidate> verified;
        for (const QueryResult &result : query_results)
            for (const Candidate &candidate : result.candidates) {
                CandidateSlot *entry = exact.find(candidate.key);
                need(entry != nullptr, "missing Bloom-positive query");
                if (entry->table_position == U(-1)) continue;
                ++exact_hit_queries;
                if (verified.size() < 16)
                    verified.push_back(candidate);
            }
        double replay_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - started).count();
        struct rusage usage{};
        getrusage(RUSAGE_SELF, &usage);
        std::cout << "{\"actual_B\":" << base.size()
                  << ",\"table_descriptors\":" << table_entries
                  << ",\"table_start\":" << table_start
                  << ",\"query_pairs\":" << query_pairs
                  << ",\"query_start\":" << query_start
                  << ",\"query_workers\":" << query_workers
                  << ",\"batch_size\":" << batch_size
                  << ",\"bloom_bits_per_key\":" << bits_per_key
                  << ",\"bloom_hashes\":" << hashes
                  << ",\"bloom_blocks_per_key\":2"
                  << ",\"bloom_bytes\":" << bloom_bytes
                  << ",\"candidate_record_bytes\":" << sizeof(Candidate)
                  << ",\"candidate_vector_capacity_bytes\":"
                  << candidate_vector_capacity_bytes
                  << ",\"candidate_exact_slot_bytes\":"
                  << sizeof(CandidateSlot)
                  << ",\"bloom_positive_queries\":"
                  << bloom_positive_queries
                  << ",\"duplicate_positive_keys\":" << exact.duplicate_keys
                  << ",\"exact_hit_keys\":" << exact_hit_keys
                  << ",\"exact_hit_queries\":" << exact_hit_queries
                  << ",\"false_positive_queries\":"
                  << bloom_positive_queries - exact_hit_queries
                  << ",\"complement_identity_queries\":" << complement_identity
                  << ",\"allocation_seconds\":" << std::setprecision(12)
                  << allocation_seconds
                  << ",\"build_seconds\":" << build_seconds
                  << ",\"query_seconds\":" << query_seconds
                  << ",\"exact_replay_seconds\":" << replay_seconds
                  << ",\"peak_rss_bytes\":" << usage.ru_maxrss
                  << ",\"hits\":[";
        for (size_t i = 0; i < verified.size(); ++i) {
            if (i) std::cout << ',';
            const Candidate &candidate = verified[i];
            CandidateSlot *entry = exact.find(candidate.key);
            std::cout << "{\"query_position\":" << candidate.query_position
                      << ",\"table_position\":" << entry->table_position
                      << ",\"x_key_hex\":\"" << hex(candidate.key) << "\"}";
        }
        std::cout << "]}" << std::endl;
    } catch (const std::exception &e) {
        std::cerr << e.what() << std::endl;
        return 1;
    }
}
