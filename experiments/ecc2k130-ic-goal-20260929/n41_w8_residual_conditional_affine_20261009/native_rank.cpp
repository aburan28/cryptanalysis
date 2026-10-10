#include <m4ri/m4ri.h>

#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int kN = 41;
constexpr int kLabelBits = 20;
constexpr int kLabelFeatures = 1 + kLabelBits + kLabelBits * (kLabelBits - 1) / 2;
constexpr int kFeatures = kLabelFeatures + kN + kN * kLabelBits;
constexpr int kRecordBytes = 15;

std::vector<unsigned char> read_file(const char* path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error(std::string("cannot read ") + path);
    return {std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
}

uint64_t little(const unsigned char* p, int length) {
    uint64_t value = 0;
    for (int i = 0; i < length; ++i) value |= uint64_t(p[i]) << (8 * i);
    return value;
}

void set_label_features(mzd_t* out, int row, uint32_t labels) {
    mzd_write_bit(out, row, 0, 1);
    int active[kLabelBits], used = 0;
    for (int bit = 0; bit < kLabelBits; ++bit)
        if ((labels >> bit) & 1) {
            active[used++] = bit;
            mzd_write_bit(out, row, 1 + bit, 1);
        }
    int column = 1 + kLabelBits;
    for (int a = 0; a < kLabelBits; ++a)
        for (int b = a + 1; b < kLabelBits; ++b, ++column)
            if (((labels >> a) & 1) && ((labels >> b) & 1))
                mzd_write_bit(out, row, column, 1);
    if (column != kLabelFeatures) throw std::runtime_error("label dimension changed");
}

void set_mixed_features(mzd_t* out, int row, uint64_t coordinate, uint32_t labels) {
    set_label_features(out, row, labels);
    for (int c = 0; c < kN; ++c)
        if ((coordinate >> c) & 1) {
            mzd_write_bit(out, row, kLabelFeatures + c, 1);
            for (int bit = 0; bit < kLabelBits; ++bit)
                if ((labels >> bit) & 1)
                    mzd_write_bit(out, row,
                                  kLabelFeatures + kN + c * kLabelBits + bit, 1);
        }
}
}

int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::runtime_error("expected table.bin phi.bin labels.bin");
        auto table = read_file(argv[1]);
        auto phi = read_file(argv[2]);
        auto labels = read_file(argv[3]);
        if (table.size() % kRecordBytes) throw std::runtime_error("table length invalid");
        const size_t count = table.size() / kRecordBytes;
        if (phi.size() != count * 6 || labels.size() != count * 4)
            throw std::runtime_error("coordinate or label length invalid");
        mzd_t* label_matrix = mzd_init(count, kLabelFeatures);
        mzd_t* x_matrix = mzd_init(count, kFeatures);
        mzd_t* phi_matrix = mzd_init(count, kFeatures);
        if (!label_matrix || !x_matrix || !phi_matrix)
            throw std::runtime_error("matrix allocation failed");
        for (size_t row = 0; row < count; ++row) {
            const auto* record = table.data() + row * kRecordBytes;
            uint64_t x = little(record, 6);
            uint64_t p = little(phi.data() + row * 6, 6);
            uint32_t l = uint32_t(little(labels.data() + row * 4, 4));
            if (x >= (uint64_t(1) << kN) || p >= (uint64_t(1) << kN) ||
                l >= (uint32_t(1) << kLabelBits))
                throw std::runtime_error("feature value out of range");
            set_label_features(label_matrix, row, l);
            set_mixed_features(x_matrix, row, x, l);
            set_mixed_features(phi_matrix, row, p, l);
        }
        const int label_rank = int(mzd_echelonize_m4ri(label_matrix, 0, 5));
        const int x_rank = int(mzd_echelonize_m4ri(x_matrix, 0, 5));
        const int phi_rank = int(mzd_echelonize_m4ri(phi_matrix, 0, 5));
        const int ceiling = kFeatures - kLabelFeatures + label_rank;
        mzd_free(label_matrix);
        mzd_free(x_matrix);
        mzd_free(phi_matrix);
        std::cout << "{\"rows\":" << count
                  << ",\"label_features\":" << kLabelFeatures
                  << ",\"mixed_features\":" << kFeatures
                  << ",\"label_rank\":" << label_rank
                  << ",\"mixed_rank_ceiling\":" << ceiling
                  << ",\"x_rank\":" << x_rank
                  << ",\"phi_rank\":" << phi_rank << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
