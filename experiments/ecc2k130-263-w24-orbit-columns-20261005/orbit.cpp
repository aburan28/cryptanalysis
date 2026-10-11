// Exact sign/Frobenius orbit partition of a frozen polynomial-W mask stream.
// Reuse the already Sage-checked GF(2^131) arithmetic and W encoding from
// the merged W24 census, while compiling native and portable backends.
#define main frozen_w24_census_main
#include "../ecc2k130-263-w24-exact-base-20261005/enumerate.cpp"
#undef main

#include <map>

static uint32_t read_mask(std::ifstream& input) {
    unsigned char bytes[4];
    input.read(reinterpret_cast<char*>(bytes), 4);
    if (!input) throw std::runtime_error("truncated mask stream");
    return uint32_t(bytes[0]) | (uint32_t(bytes[1]) << 8) |
           (uint32_t(bytes[2]) << 16) | (uint32_t(bytes[3]) << 24);
}

static void write_pair(std::ofstream& output, uint32_t first, uint32_t second) {
    write_le32(output, first);
    write_le32(output, second);
}

struct OrbitDsu {
    std::vector<uint32_t> parent;
    std::vector<uint32_t> size;
    uint64_t components;

    OrbitDsu(uint32_t limit, uint64_t count)
        : parent(size_t(limit) + 1), size(size_t(limit) + 1), components(count) {}

    uint32_t find(uint32_t value) {
        uint32_t root = value;
        while (parent[root] != root) root = parent[root];
        while (parent[value] != value) {
            const uint32_t next = parent[value];
            parent[value] = root;
            value = next;
        }
        return root;
    }

    bool join(uint32_t first, uint32_t second) {
        uint32_t a = find(first), b = find(second);
        if (a == b) return false;
        if (size[a] < size[b] || (size[a] == size[b] && a > b)) std::swap(a, b);
        parent[b] = a;
        size[a] += size[b];
        --components;
        return true;
    }
};

static uint64_t peak_rss_bytes() {
    rusage usage{};
    if (getrusage(RUSAGE_SELF, &usage) != 0)
        throw std::runtime_error("getrusage failed");
#if defined(__APPLE__)
    return static_cast<uint64_t>(usage.ru_maxrss);
#else
    return static_cast<uint64_t>(usage.ru_maxrss) * 1024;
#endif
}

int main(int argc, char** argv) {
    try {
        if (argc != 10)
            throw std::runtime_error("usage: orbit dimension count batch_size wall_limit_s rss_limit_bytes source-masks.bin forest.bin nontrivial-components.bin receipt.json");
        const int dimension = std::stoi(argv[1]);
        const uint64_t expected_count = std::stoull(argv[2]);
        const size_t batch_size = std::stoull(argv[3]);
        const uint64_t wall_limit_s = std::stoull(argv[4]);
        const uint64_t rss_limit_bytes = std::stoull(argv[5]);
        const std::filesystem::path source_path = argv[6];
        if (dimension < 1 || dimension > 24 || expected_count == 0 ||
            batch_size == 0 || batch_size > 65536 || wall_limit_s == 0 ||
            rss_limit_bytes == 0)
            throw std::runtime_error("invalid argument");
        for (int i = 7; i < argc; ++i)
            if (std::filesystem::exists(argv[i]))
                throw std::runtime_error("output already exists: " + std::string(argv[i]));
        if (std::filesystem::file_size(source_path) != 4 * expected_count)
            throw std::runtime_error("wrong raw mask stream length");
        const uint32_t limit = (uint32_t(1) << dimension) - 1;
        if (expected_count > limit) throw std::runtime_error("too many masks");
        std::ifstream input(source_path, std::ios::binary);
        if (!input) throw std::runtime_error("cannot open mask stream");
        std::vector<uint32_t> masks;
        masks.reserve(size_t(expected_count));
        std::vector<uint8_t> in_base(size_t(limit) + 1);
        uint32_t previous = 0;
        for (uint64_t i = 0; i < expected_count; ++i) {
            const uint32_t value = read_mask(input);
            if (value <= previous || value > limit)
                throw std::runtime_error("mask stream not strictly increasing within W");
            masks.push_back(value);
            in_base[value] = 1;
            previous = value;
        }
        OrbitDsu dsu(limit, expected_count);
        for (uint32_t mask : masks) {
            dsu.parent[mask] = mask;
            dsu.size[mask] = 1;
        }
        std::ofstream forest(argv[7], std::ios::binary);
        std::ofstream components_file(argv[8], std::ios::binary);
        if (!forest || !components_file)
            throw std::runtime_error("cannot create edge outputs");
        const Fe trace = trace_mask();
        const uint32_t trace_bits = basis_trace_bits(trace, dimension);
        std::vector<Fe> words(batch_size), prefixes(batch_size + 1), inverses(batch_size);
        uint64_t direct_hits = 0, reciprocal_hits = 0, forest_edges = 0;
        const auto started = std::chrono::steady_clock::now();
        for (size_t first = 0; first < masks.size(); first += batch_size) {
            const size_t count = std::min(batch_size, masks.size() - first);
            prefixes[0] = Fe{1, 0, 0};
            for (size_t i = 0; i < count; ++i) {
                words[i] = w_from_mask(masks[first + i], trace_bits);
                if (words[i] == Fe{0, 0, 0} || trace_bit(words[i], trace) != 0)
                    throw std::runtime_error("invalid trace-zero W element");
                prefixes[i + 1] = mul(prefixes[i], words[i]);
            }
            Fe backward = inverse(prefixes[count]);
            for (size_t i = count; i-- > 0;) {
                inverses[i] = mul(backward, prefixes[i]);
                backward = mul(backward, words[i]);
            }
            if (!(backward == Fe{1, 0, 0}))
                throw std::runtime_error("batch inversion replay failed");
            for (size_t i = 0; i < count; ++i) {
                const uint32_t mask = masks[first + i];
                if (trace_bit(inverses[i], trace) != 0 ||
                    !(mul(words[i], inverses[i]) == Fe{1, 0, 0}))
                    throw std::runtime_error("nonrational or incorrect inverse");
                Fe direct = words[i], reciprocal = inverses[i];
                for (int k = 1; k <= 65; ++k) {
                    direct = square(direct);
                    reciprocal = square(reciprocal);
                    const uint32_t a = member_mask(direct, dimension, trace_bits);
                    const uint32_t b = member_mask(reciprocal, dimension, trace_bits);
                    if (a && in_base[a]) {
                        ++direct_hits;
                        if (dsu.join(mask, a)) {
                            write_pair(forest, std::min(mask, a), std::max(mask, a));
                            ++forest_edges;
                        }
                    }
                    if (b && in_base[b]) {
                        ++reciprocal_hits;
                        if (dsu.join(mask, b)) {
                            write_pair(forest, std::min(mask, b), std::max(mask, b));
                            ++forest_edges;
                        }
                    }
                }
            }
            if (std::chrono::steady_clock::now() - started >
                std::chrono::seconds(wall_limit_s))
                throw std::runtime_error("wall limit exceeded");
            if (peak_rss_bytes() > rss_limit_bytes)
                throw std::runtime_error("RSS limit exceeded");
            if ((first + count) / 1000000 != first / 1000000)
                std::fprintf(stderr, "masks=%zu/%zu components=%llu\n", first + count,
                             masks.size(), static_cast<unsigned long long>(dsu.components));
        }
        std::vector<uint32_t> smallest(size_t(limit) + 1);
        for (uint32_t mask : masks) {
            const uint32_t root = dsu.find(mask);
            if (smallest[root] == 0 || mask < smallest[root]) smallest[root] = mask;
        }
        std::map<uint32_t, uint64_t> histogram;
        uint64_t nontrivial_masks = 0, components_seen = 0;
        uint32_t largest = 0;
        for (uint32_t mask : masks) {
            const uint32_t root = dsu.find(mask);
            if (smallest[root] == mask) {
                ++histogram[dsu.size[root]];
                ++components_seen;
                largest = std::max(largest, dsu.size[root]);
            }
            if (dsu.size[root] > 1) {
                write_pair(components_file, mask, smallest[root]);
                ++nontrivial_masks;
            }
        }
        if (components_seen != dsu.components || forest_edges != expected_count - dsu.components)
            throw std::runtime_error("component or forest accounting failed");
        forest.close();
        components_file.close();
        if (!forest || !components_file)
            throw std::runtime_error("edge output write failed");
        const auto elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - started).count();
        std::ofstream receipt(argv[9]);
        if (!receipt) throw std::runtime_error("cannot create receipt");
        receipt << "{\"schema\":\"ecc2k130-w24-orbit-columns-native-v1\","
                << "\"status\":\"completed_unverified\",\"candidate_id\":null,"
                << "\"field_backend\":\"" FIELD_BACKEND "\","
                << "\"dimension\":" << dimension
                << ",\"source_signed_columns\":" << expected_count
                << ",\"orbit_representatives\":" << dsu.components
                << ",\"saved_columns\":" << expected_count - dsu.components
                << ",\"direct_hits\":" << direct_hits
                << ",\"reciprocal_hits\":" << reciprocal_hits
                << ",\"forest_edges\":" << forest_edges
                << ",\"nontrivial_masks\":" << nontrivial_masks
                << ",\"largest_component\":" << largest
                << ",\"component_size_histogram\":{";
        bool first_entry = true;
        for (const auto& [size, count] : histogram) {
            if (!first_entry) receipt << ',';
            receipt << '\"' << size << "\":" << count;
            first_entry = false;
        }
        receipt << "},\"elapsed_ns\":" << elapsed_ns
                << ",\"peak_rss_bytes\":" << peak_rss_bytes()
                << ",\"natural_pdp_yield\":null,\"verified_relation_rank\":null,"
                << "\"verified_logarithm\":null,\"online_wall_time\":null,"
                << "\"rho_ratio\":null}\n";
        if (!receipt) throw std::runtime_error("receipt write failed");
        std::printf("dimension=%d C=%llu orbit_representatives=%llu saved=%llu\n",
                    dimension, static_cast<unsigned long long>(expected_count),
                    static_cast<unsigned long long>(dsu.components),
                    static_cast<unsigned long long>(expected_count - dsu.components));
        return 0;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "error: %s\n", error.what());
        return 2;
    }
}
