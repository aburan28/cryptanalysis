// Count exact pair and four-state image cardinalities for the frozen input.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <unordered_set>

struct State { Point point; uint8_t column, mask, sign; };
struct Pair10 { Point sum; uint8_t a, b, col_a, col_b; };

static bool all_distinct(const std::array<uint8_t,10>& columns, int count) {
    uint16_t seen=0;
    for(int i=0;i<count;++i) {
        uint16_t bit=uint16_t(1)<<columns[i];
        if(seen&bit) return false;
        seen|=bit;
    }
    return true;
}

static std::vector<Pair10> pair_states(const std::vector<State>& a,
                                       const std::vector<State>& b) {
    std::vector<Pair10> out;
    for(size_t i=0;i<a.size();++i)for(size_t j=0;j<b.size();++j) {
        if(a[i].column==b[j].column)continue;
        out.push_back({add(a[i].point,b[j].point),uint8_t(i),uint8_t(j),
                       a[i].column,b[j].column});
    }
    return out;
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: analyze_pairs input output");
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("missing input");
        uint64_t header[5];
        int count;
        for (auto& value : header) input >> value;
        input >> count;
        if (!input || count != 10 || header[0] != 1458168294740ULL ||
            header[1] != 1672312028033ULL || header[4] != 549756390943ULL)
            throw std::runtime_error("wrong public target input");
        for (int i = 0; i < 4; ++i) {
            uint64_t x, y; input >> x >> y;
            if (!input || !on_curve(finite(x,y))) throw std::runtime_error("bad target preimage");
        }
        std::array<std::vector<State>,10> blocks;
        for (auto& block : blocks) {
            int size; input >> size;
            if (!input || size != 34) throw std::runtime_error("wrong block size");
            for (int i = 0; i < size; ++i) {
                uint64_t x,y;int col,mask,sign;
                input >> x >> y >> col >> mask >> sign;
                if (!input || !on_curve(finite(x,y)) || col<0 || col>=14)
                    throw std::runtime_error("invalid base state");
                block.push_back({finite(x,y),uint8_t(col),uint8_t(mask),uint8_t(sign)});
            }
        }
        std::array<std::vector<Pair10>,5> pairs;
        std::array<size_t,5> unique_pair;
        std::array<size_t,5> exceptional_pair;
        for (int i=0;i<5;++i) {
            pairs[i]=pair_states(blocks[2*i],blocks[2*i+1]);
            std::unordered_set<Point,PointHash> unique;
            size_t exceptions=0;
            for (const auto& p:pairs[i]) {
                if (p.sum.infinity || p.sum.x==0 || p.sum.x==1) ++exceptions;
                unique.insert(p.sum);
            }
            unique_pair[i]=unique.size();
            exceptional_pair[i]=exceptions;
        }
        uint64_t left_entries=0;
        std::unordered_set<Point,PointHash> left;
        left.reserve(800000);
        for (const auto& a:pairs[0]) for (const auto& b:pairs[1]) {
            std::array<uint8_t,10> cols{a.col_a,a.col_b,b.col_a,b.col_b};
            if (!all_distinct(cols,4)) continue;
            ++left_entries;
            left.insert(add(a.sum,b.sum));
        }
        std::ofstream out(argv[2]);
        if (!out) throw std::runtime_error("cannot write result");
        out << "{\"status\":\"PASS_EXACT_PAIR_IMAGE_COUNTS\","
            << "\"pair_rows_per_block\":[";
        for (int i=0;i<5;++i)out << (i?",":"") << pairs[i].size();
        out << "],\"unique_pair_sums\":[";
        for (int i=0;i<5;++i)out << (i?",":"") << unique_pair[i];
        out << "],\"exceptional_pair_rows\":[";
        for (int i=0;i<5;++i)out << (i?",":"") << exceptional_pair[i];
        out << "],\"left_four_rows\":" << left_entries
            << ",\"unique_left_four_sums\":" << left.size() << "}\n";
        std::cout << "unique pair0=" << unique_pair[0]
                  << " four=" << left.size() << "/" << left_entries << "\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 1;
    }
}
