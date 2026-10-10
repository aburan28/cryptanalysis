// Independent M4RI rank check for the saved target-residual witness rows.
#include <m4ri/m4ri.h>

#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

constexpr int N = 41;
constexpr int DIM = 11522;
constexpr int RECORD_BYTES = 15;

std::vector<unsigned char> read_bytes(const char* path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error(std::string("cannot open ") + path);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

uint64_t read_le(const unsigned char* bytes, int count) {
    uint64_t value = 0;
    for (int i = 0; i < count; ++i) value |= uint64_t(bytes[i]) << (8*i);
    return value;
}

int witness_rank(const std::vector<unsigned char>& values, int stride,
                 const std::vector<unsigned char>& witness, int total_rows) {
    if (witness.size() != size_t(DIM)*4)
        throw std::runtime_error("witness index count changed");
    std::array<std::array<int, N>, N> pair_index{};
    std::array<std::array<std::array<int, N>, N>, N> triple_index{};
    int column = 1+N;
    for (int i=0; i<N; ++i)
        for (int j=i+1; j<N; ++j) pair_index[i][j] = column++;
    for (int i=0; i<N; ++i)
        for (int j=i+1; j<N; ++j)
            for (int k=j+1; k<N; ++k) triple_index[i][j][k] = column++;
    if (column != DIM) throw std::runtime_error("monomial dimension changed");
    mzd_t* matrix = mzd_init(DIM, DIM);
    if (!matrix) throw std::runtime_error("M4RI allocation failed");
    for (int row=0; row<DIM; ++row) {
        const uint32_t index = uint32_t(read_le(witness.data()+4*row, 4));
        if (index >= uint32_t(total_rows)) {
            mzd_free(matrix);
            throw std::runtime_error("witness table index out of range");
        }
        const uint64_t value = read_le(values.data()+size_t(index)*stride, 6);
        if (value >= (uint64_t(1)<<N)) {
            mzd_free(matrix);
            throw std::runtime_error("coordinate exceeds field width");
        }
        int active[N], used=0;
        for (int bit=0; bit<N; ++bit)
            if (value & (uint64_t(1)<<bit)) active[used++] = bit;
        mzd_write_bit(matrix, row, 0, 1);
        for (int a=0; a<used; ++a)
            mzd_write_bit(matrix, row, 1+active[a], 1);
        for (int a=0; a<used; ++a)
            for (int b=a+1; b<used; ++b)
                mzd_write_bit(matrix, row, pair_index[active[a]][active[b]], 1);
        for (int a=0; a<used; ++a)
            for (int b=a+1; b<used; ++b)
                for (int c=b+1; c<used; ++c)
                    mzd_write_bit(matrix, row,
                                  triple_index[active[a]][active[b]][active[c]], 1);
    }
    const int rank = int(mzd_echelonize_m4ri(matrix, 0, 5));
    mzd_free(matrix);
    return rank;
}

int main(int argc, char** argv) {
    try {
        if (argc != 5) throw std::runtime_error("expected table phi x-index phi-index");
        auto table = read_bytes(argv[1]);
        auto phi = read_bytes(argv[2]);
        auto x_indices = read_bytes(argv[3]);
        auto phi_indices = read_bytes(argv[4]);
        if (table.size() % RECORD_BYTES ||
            phi.size() != (table.size()/RECORD_BYTES)*6)
            throw std::runtime_error("table or phi byte length changed");
        const int count = int(table.size()/RECORD_BYTES);
        const int x_rank = witness_rank(table, RECORD_BYTES, x_indices, count);
        const int phi_rank = witness_rank(phi, 6, phi_indices, count);
        std::cout << "{\"x_rank\":" << x_rank << ",\"phi_rank\":" << phi_rank
                  << ",\"witness_rows\":" << DIM << "}\n";
        return x_rank == DIM && phi_rank == DIM ? 0 : 2;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
