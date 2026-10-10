// Enumerate the exact N41 W6 same-seed four-atom output family in blocks 4 and 5.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <array>
#include <fstream>
#include <iostream>
#include <set>
#include <vector>

struct Atom { Point point; uint8_t mask, sign, column; };
struct PairState { Point sum; uint8_t a, b, seed; uint32_t columns; };

int main(int argc, char** argv) {
  try {
    if (argc != 3) throw std::runtime_error("usage: census heldout_input output.tsv");
    std::ifstream in(argv[1]);
    if (!in) throw std::runtime_error("missing input");
    uint64_t qx, qy, order;
    int blocks;
    in >> qx >> qy >> order >> blocks;
    if (!in || qx != 1458168294740ULL || qy != 1672312028033ULL ||
        order != 549756390943ULL || blocks != 6)
      throw std::runtime_error("unexpected frozen target or subgroup");
    std::array<std::vector<Atom>, 6> atoms;
    for (int block = 0; block < 6; ++block) {
      int rotation, size;
      in >> rotation >> size;
      if (!in || rotation != block * 5 || size != 64)
        throw std::runtime_error("unexpected frozen source window");
      for (int i = 0; i < size; ++i) {
        uint64_t x, y;
        int mask, sign, column;
        in >> x >> y >> mask >> sign >> column;
        Point point = finite(x, y);
        if (!in || !on_curve(point) || mask < 1 || mask >= 64 ||
            sign < 0 || sign > 1 || column < 0 || column >= 26)
          throw std::runtime_error("bad source atom");
        atoms[block].push_back({point, uint8_t(mask), uint8_t(sign), uint8_t(column)});
      }
    }
    std::string tail;
    if (in >> tail) throw std::runtime_error("trailing input");
    std::array<std::vector<PairState>, 2> pairs;
    for (int b = 0; b < 2; ++b) {
      const auto& source = atoms[b + 4];
      for (size_t i = 0; i < source.size(); ++i)
        for (size_t j = 0; j < source.size(); ++j) {
          if (source[i].mask >= source[j].mask ||
              source[i].column == source[j].column) continue;
          pairs[b].push_back({add(source[i].point, source[j].point),
                              uint8_t(i), uint8_t(j),
                              uint8_t(source[i].mask ^ source[j].mask),
                              (uint32_t(1) << source[i].column) |
                              (uint32_t(1) << source[j].column)});
        }
    }
    std::array<std::vector<size_t>, 64> by_seed;
    for (size_t j = 0; j < pairs[1].size(); ++j)
      by_seed[pairs[1][j].seed].push_back(j);
    std::ofstream out(argv[2]);
    if (!out) throw std::runtime_error("cannot open output");
    out << "seed\tx\ty\tfirst_pair\tsecond_pair\tcolumns\n";
    std::array<uint64_t, 64> counts{};
    uint64_t infinity = 0;
    for (size_t i = 0; i < pairs[0].size(); ++i)
      for (size_t j : by_seed[pairs[0][i].seed]) {
        if (pairs[0][i].columns & pairs[1][j].columns) continue;
        Point sum = add(pairs[0][i].sum, pairs[1][j].sum);
        if (sum.infinity) { ++infinity; continue; }
        auto seed = pairs[0][i].seed;
        ++counts[seed];
        out << unsigned(seed) << '\t' << sum.x << '\t' << sum.y << '\t'
            << i << '\t' << j << '\t'
            << (pairs[0][i].columns | pairs[1][j].columns) << '\n';
      }
    out.close();
    if (!out) throw std::runtime_error("output write failure");
    uint64_t total = 0;
    for (auto count : counts) total += count;
    std::cout << "pair_states=" << pairs[0].size() << "," << pairs[1].size()
              << " finite_quads=" << total << " infinity=" << infinity << '\n';
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
