// Exact target-conditioned N41 row search from compact seed-bin filters.
// Only pair states and a one-pair hash index are materialized.
#include "filter16_core.hpp"

#include <unordered_map>

namespace {
struct IndexedPair {
    Point point;
    uint32_t columns;
    uint8_t seed;
    uint16_t left, right;
};

std::vector<IndexedPair> indexed_pairs(const std::vector<SeedPoint>& source) {
    std::vector<IndexedPair> pairs;
    for (int i = 0; i < 64; ++i)
        for (int j = i + 1; j < 64; ++j) {
            if (source[i].column == source[j].column) continue;
            Point point = add(source[i].point, source[j].point);
            uint8_t seed = source[i].mask ^ source[j].mask;
            if (point.infinity || seed < 1 || seed > 63)
                throw std::runtime_error("invalid pair point or seed sum");
            pairs.push_back({point,
                             (uint32_t(1) << source[i].column) |
                             (uint32_t(1) << source[j].column),
                             seed, uint16_t(i), uint16_t(j)});
        }
    if (pairs.size() != 1956) throw std::runtime_error("pair domain size changed");
    return pairs;
}

struct Witness {
    int first = -1, second = -1, third = -1, fourth = -1;
    uint64_t residual_x = 0;
};
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 6)
            throw std::runtime_error("usage: resolve16 public_input.txt filters16.bin valid_prefix_cap result.json trace.txt");
        const uint64_t cap = std::stoull(argv[3]);
        if (cap < 1 || cap > 3167136)
            throw std::runtime_error("invalid frozen valid-prefix cap");
        const auto setup_start = std::chrono::steady_clock::now();
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("missing public input");
        uint64_t qx, qy, order;
        int windows;
        input >> qx >> qy >> order >> windows;
        if (!input || qx != 1458168294740ULL || qy != 1672312028033ULL ||
            order != 549756390943ULL || windows != 4)
            throw std::runtime_error("frozen public instance changed");
        Point target = finite(qx, qy);
        if (!on_curve(target)) throw std::runtime_error("public target off curve");
        std::array<std::vector<SeedPoint>, 4> source;
        for (int w = 0; w < 4; ++w) {
            int count;
            input >> count;
            if (!input || count != 64) throw std::runtime_error("source count changed");
            for (int k = 0; k < 64; ++k) {
                uint64_t x, y;
                int column, seed;
                input >> x >> y >> column >> seed;
                if (!input || column < 0 || column >= 26 || seed < 0 || seed >= 64 ||
                    !on_curve(finite(x, y)))
                    throw std::runtime_error("invalid source point");
                source[w].push_back({finite(x, y), uint8_t(column), uint8_t(seed)});
            }
        }
        std::string extra;
        if (input >> extra) throw std::runtime_error("trailing public input");
        std::array<std::vector<IndexedPair>, 4> pairs;
        for (int w = 0; w < 4; ++w) pairs[w] = indexed_pairs(source[w]);
        std::unordered_map<Point, std::vector<uint16_t>, PointHash> left_index;
        left_index.reserve(4096);
        for (size_t k = 0; k < pairs[2].size(); ++k)
            left_index[pairs[2][k].point].push_back(uint16_t(k));
        std::array<std::vector<uint16_t>, 64> right_by_seed;
        for (size_t k = 0; k < pairs[3].size(); ++k)
            right_by_seed[pairs[3][k].seed].push_back(uint16_t(k));
        std::ifstream filters(argv[2], std::ios::binary);
        if (!filters) throw std::runtime_error("missing frozen filter table");
        std::vector<uint64_t> transpose(size_t(FEATURES) * FILTERS * BLOCKS, 0);
        int unfiltered_bins = 0;
        for (int bin = 0; bin < BINS; ++bin) {
            int lo = filters.get(), hi = filters.get(), count = filters.get();
            int reserved = filters.get();
            if (reserved != 0 || count < 0 || count > FILTERS ||
                lo < 0 || hi < 0 || ((hi << 8) | lo) > FEATURES)
                throw std::runtime_error("invalid filter header");
            if (count == 0) ++unfiltered_bins;
            for (int eq = 0; eq < FILTERS; ++eq)
                for (int word = 0; word < WORDS; ++word) {
                    uint64_t value = read_u64(filters);
                    if (eq >= count && value)
                        throw std::runtime_error("nonzero inactive equation");
                    while (value) {
                        const int feature = word * 64 + __builtin_ctzll(value);
                        if (feature >= FEATURES)
                            throw std::runtime_error("filter feature outside family");
                        transpose[(size_t(feature) * FILTERS + eq) * BLOCKS + bin / 64] |=
                            uint64_t(1) << (bin & 63);
                        value &= value - 1;
                    }
                }
        }
        if (filters.get() != EOF || unfiltered_bins != 1)
            throw std::runtime_error("filter table length or full-rank bin changed");
        const uint64_t setup_ns = elapsed(setup_start);
        const auto online_start = std::chrono::steady_clock::now();
        uint64_t visited = 0, column_rejects = 0, valid = 0;
        uint64_t identities = 0, passed_bins = 0, buckets_scanned = 0;
        uint64_t right_candidates = 0, left_hits = 0, rows_verified = 0;
        Witness witness;
        bool time_cap = false, memory_cap = false;
        for (size_t i = 0; i < pairs[0].size() && valid < cap && witness.first < 0; ++i) {
            Point after_first = add(target, neg(pairs[0][i].point));
            for (size_t j = 0; j < pairs[1].size() && valid < cap && witness.first < 0; ++j) {
                ++visited;
                const uint32_t prefix_columns = pairs[0][i].columns | pairs[1][j].columns;
                if (pairs[0][i].columns & pairs[1][j].columns) {
                    ++column_rejects;
                    continue;
                }
                Point residual = add(after_first, neg(pairs[1][j].point));
                ++valid;
                if (residual.infinity) {
                    ++identities;
                    continue;
                }
                const std::vector<int> active = feature_list(residual.x);
                Accumulator parities{};
                for (int feature : active) {
                    const uint64_t* row = transpose.data() + size_t(feature) * FILTERS * BLOCKS;
                    for (size_t offset = 0; offset < parities.size(); ++offset)
                        parities[offset] ^= row[offset];
                }
                std::array<uint64_t, 64> allowed_left_seed_by_right_seed{};
                for (int block = 0; block < BLOCKS; ++block) {
                    uint64_t failed = 0;
                    for (int eq = 0; eq < FILTERS; ++eq)
                        failed |= parities[eq * BLOCKS + block];
                    uint64_t passed = ~failed;
                    if (block == BLOCKS - 1)
                        passed &= (uint64_t(1) << (BINS % 64)) - 1;
                    while (passed) {
                        int bin = block * 64 + __builtin_ctzll(passed);
                        int left_seed = bin / 63 + 1;
                        int right_seed = bin % 63 + 1;
                        allowed_left_seed_by_right_seed[right_seed] |= uint64_t(1) << left_seed;
                        ++passed_bins;
                        passed &= passed - 1;
                    }
                }
                for (int seed = 1; seed <= 63 && witness.first < 0; ++seed) {
                    const uint64_t allowed = allowed_left_seed_by_right_seed[seed];
                    if (!allowed) continue;
                    ++buckets_scanned;
                    for (uint16_t right_id : right_by_seed[seed]) {
                        const IndexedPair& right = pairs[3][right_id];
                        if (prefix_columns & right.columns) continue;
                        ++right_candidates;
                        Point needed = add(residual, neg(right.point));
                        auto found = left_index.find(needed);
                        if (found == left_index.end()) continue;
                        ++left_hits;
                        for (uint16_t left_id : found->second) {
                            const IndexedPair& left = pairs[2][left_id];
                            if (!(allowed & (uint64_t(1) << left.seed)) ||
                                ((prefix_columns | right.columns) & left.columns))
                                continue;
                            if (!(add(left.point, right.point) == residual))
                                throw std::runtime_error("hash hit fails exact group relation");
                            Point replay = add(add(pairs[0][i].point, pairs[1][j].point),
                                               add(left.point, right.point));
                            if (!(replay == target))
                                throw std::runtime_error("row fails target replay");
                            witness = {int(i), int(j), int(left_id), int(right_id), residual.x};
                            ++rows_verified;
                            break;
                        }
                        if (witness.first >= 0) break;
                    }
                }
                if (valid % 64 == 0) {
                    time_cap = elapsed(online_start) >= 120000000000ULL;
                    memory_cap = peak_rss() >= 4ULL * 1024 * 1024 * 1024;
                    if (time_cap || memory_cap) break;
                }
            }
            if (time_cap || memory_cap) break;
        }
        const uint64_t online_ns = elapsed(online_start);
        const char* status = witness.first >= 0 ? "FOUND_VERIFIED_RELATION" :
                             time_cap ? "TIME_CAP" : memory_cap ? "MEMORY_CAP" :
                             valid == cap ? "PREFIX_CAP" : "PREFIX_EXHAUSTED";
        std::ofstream result(argv[4]);
        if (!result) throw std::runtime_error("cannot write result");
        result << "{\n\"status\":\"" << status << "\","
               << "\n\"curve_id\":\"EC1N41Ckb1h7d5e80d3c4d0\","
               << "\n\"public_target_q\":[" << qx << ',' << qy << "],"
               << "\n\"proposal_id\":\"Q20261009232800\",\"candidate_id\":null,"
               << "\n\"valid_prefix_cap\":" << cap
               << ",\"visited_prefixes\":" << visited
               << ",\"column_rejects\":" << column_rejects
               << ",\"valid_prefixes\":" << valid
               << ",\"identity_residuals\":" << identities
               << ",\"passed_seed_bins\":" << passed_bins
               << ",\"right_seed_buckets_scanned\":" << buckets_scanned
               << ",\"right_pair_candidates\":" << right_candidates
               << ",\"left_index_hits\":" << left_hits
               << ",\"rows_verified\":" << rows_verified
               << ",\"witness_pair_state_indices\":["
               << witness.first << ',' << witness.second << ','
               << witness.third << ',' << witness.fourth << ']'
               << ",\"witness_residual_x\":" << witness.residual_x
               << ",\"setup_wall_ns\":" << setup_ns
               << ",\"online_wall_ns\":" << online_ns
               << ",\"peak_rss_bytes\":" << peak_rss() << "\n}\n";
        result.close();
        if (!result) throw std::runtime_error("result write failed");
        std::ofstream trace(argv[5]);
        if (!trace) throw std::runtime_error("cannot write trace");
        trace << status << " valid_prefixes=" << valid
              << " passed_seed_bins=" << passed_bins
              << " right_pair_candidates=" << right_candidates
              << " online_s=" << online_ns / 1e9 << '\n';
        std::cout << status << " prefixes=" << valid << " online_s=" << online_ns / 1e9 << '\n';
    } catch (const std::exception& error) {
        std::cerr << "resolve16 error: " << error.what() << '\n';
        return 1;
    }
}
