// Independent accepted-pair enumeration for the W15 seed-offset census.
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

struct Entry {std::uint32_t mask, column;};

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: direct_counts support.tsv output.tsv");
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("missing source support");
        std::vector<Entry> source;
        std::array<bool, 1u << 15> seen{};
        Entry entry{};
        while (input >> entry.mask >> entry.column) {
            if (entry.mask == 0 || entry.mask >= seen.size() || seen[entry.mask])
                throw std::runtime_error("invalid or repeated source mask");
            seen[entry.mask] = true;
            source.push_back(entry);
        }
        if (!input.eof() || source.size() != 16441)
            throw std::runtime_error("incomplete W15 support");
        std::array<std::uint64_t, 1u << 15> counts{};
        for (std::size_t i = 0; i < source.size(); ++i)
            for (std::size_t j = i + 1; j < source.size(); ++j) {
                if (source[i].column == source[j].column) continue;
                counts[source[i].mask ^ source[j].mask] += 4;
            }
        if (counts[0] != 0) throw std::runtime_error("zero seed count");
        std::ofstream output(argv[2]);
        if (!output) throw std::runtime_error("cannot write direct counts");
        for (std::size_t seed = 1; seed < counts.size(); ++seed)
            output << seed << ' ' << counts[seed] << '\n';
        if (!output) throw std::runtime_error("incomplete direct output");
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
