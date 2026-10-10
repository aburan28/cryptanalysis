// Independently enumerate every unordered W15 support pair by mask values.
#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

struct Entry {
    std::uint32_t mask;
    std::uint32_t column;
};

int main(int argc, char **argv) {
    try {
        if (argc != 2) throw std::runtime_error("expected support TSV path");
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("cannot open support TSV");
        std::vector<Entry> entries;
        std::array<bool, 1u << 15> seen{};
        Entry entry{};
        while (input >> entry.mask >> entry.column) {
            if (entry.mask == 0 || entry.mask >= seen.size() || seen[entry.mask])
                throw std::runtime_error("invalid or repeated support mask");
            seen[entry.mask] = true;
            entries.push_back(entry);
        }
        if (!input.eof() || entries.size() != 16441)
            throw std::runtime_error("incomplete W15 support TSV");

        std::array<std::uint64_t, 1u << 15> signed_by_seed{};
        std::uint64_t distinct_column_pairs = 0;
        for (std::size_t i = 0; i < entries.size(); ++i) {
            for (std::size_t j = i + 1; j < entries.size(); ++j) {
                if (entries[i].column == entries[j].column) continue;
                const auto seed = entries[i].mask ^ entries[j].mask;
                if (seed == 0) throw std::runtime_error("zero seed on distinct masks");
                signed_by_seed[seed] += 4; // independent signs on both atoms
                ++distinct_column_pairs;
            }
        }

        std::uint64_t signed_pairs = 0, same_seed_blocks = 0;
        std::uint64_t minimum = UINT64_MAX, maximum = 0;
        for (std::size_t seed = 1; seed < signed_by_seed.size(); ++seed) {
            const auto count = signed_by_seed[seed];
            signed_pairs += count;
            same_seed_blocks += count * count;
            minimum = std::min(minimum, count);
            maximum = std::max(maximum, count);
        }
        std::cout << distinct_column_pairs << ' ' << signed_pairs << ' '
                  << same_seed_blocks << ' ' << minimum << ' ' << maximum << '\n';
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
