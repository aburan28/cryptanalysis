// Exhaustive W_d rationality and [4]-projection classes on ECC2K-130.
// The native arithmetic is checked independently by verify_sage.py.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <vector>

#if defined(__aarch64__) && defined(__ARM_FEATURE_CRYPTO)
#include <arm_neon.h>
#define FIELD_BACKEND "arm_pmull"
#else
#define FIELD_BACKEND "portable_bitwise"
#endif

struct Fe {
    uint64_t lo, mid, hi;
};

static bool operator==(Fe a, Fe b) {
    return a.lo == b.lo && a.mid == b.mid && a.hi == b.hi;
}

static Fe xored(Fe a, Fe b) {
    return {a.lo ^ b.lo, a.mid ^ b.mid, a.hi ^ b.hi};
}

static Fe shifted(Fe a, unsigned k) {
    return {a.lo << k, (a.mid << k) | (a.lo >> (64 - k)),
            (a.hi << k) | (a.mid >> (64 - k))};
}

static std::array<uint64_t, 2> clmul64(uint64_t a, uint64_t b) {
#if defined(__aarch64__) && defined(__ARM_FEATURE_CRYPTO)
    const poly128_t p = vmull_p64(poly64_t(a), poly64_t(b));
    const uint64x2_t words = vreinterpretq_u64_p128(p);
    return {vgetq_lane_u64(words, 0), vgetq_lane_u64(words, 1)};
#else
    std::array<uint64_t, 2> out{0, 0};
    while (b != 0) {
        const unsigned k = static_cast<unsigned>(__builtin_ctzll(b));
        out[0] ^= a << k;
        if (k != 0) out[1] ^= a >> (64 - k);
        b &= b - 1;
    }
    return out;
#endif
}

// Reduce modulo X^131+X^13+X^2+X+1. Inputs have degree at most 260.
static Fe reduce_product(const std::array<uint64_t, 6>& p) {
    Fe rem{p[0], p[1], p[2] & 7};
    const Fe upper{(p[2] >> 3) | (p[3] << 61),
                   (p[3] >> 3) | (p[4] << 61),
                   (p[4] >> 3) | (p[5] << 61)};
    rem = xored(rem, upper);
    rem = xored(rem, shifted(upper, 1));
    rem = xored(rem, shifted(upper, 2));
    rem = xored(rem, shifted(upper, 13));
    const uint64_t spill = rem.hi >> 3;
    rem.hi &= 7;
    rem.lo ^= spill ^ (spill << 1) ^ (spill << 2) ^ (spill << 13);
    return rem;
}

static Fe mul(Fe a, Fe b) {
    const std::array<uint64_t, 3> aa{a.lo, a.mid, a.hi};
    const std::array<uint64_t, 3> bb{b.lo, b.mid, b.hi};
    std::array<uint64_t, 6> p{};
    for (size_t i = 0; i < 3; ++i) {
        for (size_t j = 0; j < 3; ++j) {
            const auto q = clmul64(aa[i], bb[j]);
            p[i + j] ^= q[0];
            p[i + j + 1] ^= q[1];
        }
    }
    return reduce_product(p);
}

static Fe square(Fe a) {
    const auto x = clmul64(a.lo, a.lo);
    const auto y = clmul64(a.mid, a.mid);
    const auto z = clmul64(a.hi, a.hi);
    return reduce_product({x[0], x[1], y[0], y[1], z[0], z[1]});
}

static Fe square_n(Fe a, int count) {
    while (count-- > 0) a = square(a);
    return a;
}

// Itoh-Tsujii chain for a^(2^131-2).
static Fe inverse(Fe a) {
    if (a == Fe{0, 0, 0}) throw std::runtime_error("inverse of zero");
    const Fe t2 = mul(square(a), a);
    Fe t = t2;
    for (int k = 2; k <= 64; k *= 2) t = mul(square_n(t, k), t);
    return square(mul(square_n(t, 2), t2));
}

static Fe field_bit(int k) {
    if (k < 64) return {uint64_t(1) << k, 0, 0};
    if (k < 128) return {0, uint64_t(1) << (k - 64), 0};
    return {0, 0, uint64_t(1) << (k - 128)};
}

static Fe trace_mask() {
    Fe mask{0, 0, 0};
    for (int k = 0; k < 131; ++k) {
        const Fe basis = field_bit(k);
        Fe term = basis;
        Fe total{0, 0, 0};
        for (int j = 0; j < 131; ++j) {
            total = xored(total, term);
            term = square(term);
        }
        if (!(term == basis) || !(total == Fe{0, 0, 0} || total == Fe{1, 0, 0}))
            throw std::runtime_error("invalid field trace or Frobenius period");
        if (total.lo & 1) mask = xored(mask, basis);
    }
    return mask;
}

static int trace_bit(Fe a, Fe mask) {
    return __builtin_parityll(a.lo & mask.lo) ^
           __builtin_parityll(a.mid & mask.mid) ^
           __builtin_parityll(a.hi & mask.hi);
}

static uint32_t basis_trace_bits(Fe mask, int dimension) {
    uint32_t bits = 0;
    for (int j = 1; j <= dimension; ++j)
        if (trace_bit(field_bit(j), mask)) bits |= uint32_t(1) << (j - 1);
    return bits;
}

static Fe w_from_mask(uint32_t mask, uint32_t trace_bits) {
    const uint64_t constant = static_cast<uint64_t>(__builtin_parity(mask & trace_bits));
    return {(uint64_t(mask) << 1) | constant, 0, 0};
}

static uint32_t member_mask(Fe a, int dimension, uint32_t trace_bits) {
    if (a.mid != 0 || a.hi != 0 || (a.lo >> (dimension + 1)) != 0)
        return 0;
    const uint32_t mask = static_cast<uint32_t>(a.lo >> 1);
    if (mask == 0 || (a.lo & 1) != __builtin_parity(mask & trace_bits))
        return 0;
    return mask;
}

static void write_le32(std::ofstream& out, uint32_t value) {
    for (int i = 0; i < 4; ++i)
        out.put(static_cast<char>((value >> (8 * i)) & 0xff));
    if (!out) throw std::runtime_error("canonical mask output failed");
}

struct Counts {
    uint64_t rational = 0;
    uint64_t partner_inside = 0;
    uint64_t pairs = 0;
    uint64_t fixed = 0;
    uint64_t columns = 0;
    std::vector<uint32_t> first_representatives;
    std::vector<uint32_t> first_pairs;
};

// Per-curve flag nibble: rational, partner inside W, canonical, fixed.
static uint8_t record(Counts& counts, uint32_t mask, Fe partner, Fe trace,
                      int dimension, uint32_t trace_bits, std::ofstream& out) {
    if (trace_bit(partner, trace) != 0) return 0;
    uint8_t flags = 1;
    ++counts.rational;
    const uint32_t other = member_mask(partner, dimension, trace_bits);
    if (other != 0) {
        flags |= 2;
        ++counts.partner_inside;
        if (other == mask) {
            flags |= 8;
            ++counts.fixed;
        }
        if (other < mask) ++counts.pairs;
        if (other != mask && counts.first_pairs.size() < 16)
            counts.first_pairs.push_back(mask);
    }
    if (other == 0 || mask <= other) {
        flags |= 4;
        ++counts.columns;
        write_le32(out, mask);
        if (counts.first_representatives.size() < 16)
            counts.first_representatives.push_back(mask);
    }
    return flags;
}

static void print_array(std::ofstream& out, const std::vector<uint32_t>& values) {
    out << '[';
    for (size_t i = 0; i < values.size(); ++i) {
        if (i != 0) out << ',';
        out << values[i];
    }
    out << ']';
}

static void print_counts(std::ofstream& out, const Counts& counts) {
    out << "{\"rational_w\":" << counts.rational
        << ",\"reciprocal_partners_in_w\":" << counts.partner_inside
        << ",\"two_element_reciprocal_pairs\":" << counts.pairs
        << ",\"fixed_reciprocal_points\":" << counts.fixed
        << ",\"sign_folded_columns\":" << counts.columns
        << ",\"actual_usable_points_B\":" << (2 * counts.columns)
        << ",\"first_representative_masks\":";
    print_array(out, counts.first_representatives);
    out << ",\"first_paired_masks\":";
    print_array(out, counts.first_pairs);
    out << '}';
}

int main(int argc, char** argv) {
    try {
        if (argc != 12)
            throw std::runtime_error("usage: enumerate dimension alpha_lo alpha_mid alpha_hi batch_size wall_limit_s rss_limit_bytes source_masks.bin descendant_masks.bin flags.bin receipt.json");
        const int dimension = std::stoi(argv[1]);
        const Fe alpha{std::stoull(argv[2]), std::stoull(argv[3]), std::stoull(argv[4])};
        const size_t batch_size = std::stoull(argv[5]);
        const uint64_t wall_limit_s = std::stoull(argv[6]);
        const uint64_t rss_limit_bytes = std::stoull(argv[7]);
        if (dimension < 1 || dimension > 28 || batch_size < 1 || batch_size > 65536 ||
            (alpha.hi & ~uint64_t(7)) != 0 || alpha == Fe{0, 0, 0})
            throw std::runtime_error("invalid field, dimension, or batch argument");
        for (int i = 8; i < argc; ++i)
            if (std::filesystem::exists(argv[i]))
                throw std::runtime_error("output already exists: " + std::string(argv[i]));
        std::ofstream source_out(argv[8], std::ios::binary);
        std::ofstream descendant_out(argv[9], std::ios::binary);
        std::ofstream flags_out(argv[10], std::ios::binary);
        if (!source_out || !descendant_out || !flags_out)
            throw std::runtime_error("cannot open canonical mask output");
        const Fe trace = trace_mask();
        const uint32_t trace_bits = basis_trace_bits(trace, dimension);
        if (trace_bit(Fe{1, 0, 0}, trace) != 1 || trace_bit(alpha, trace) != 1)
            throw std::runtime_error("expected trace-one alpha on cofactor-four curves");
        const Fe b = square(square(alpha));
        const uint32_t limit = (uint32_t(1) << dimension) - 1;
        std::vector<Fe> words(batch_size), prefixes(batch_size + 1), inverses(batch_size);
        Counts source, descendant;
        const auto start = std::chrono::steady_clock::now();
        for (uint32_t first = 1; first <= limit;) {
            const size_t count = std::min<size_t>(batch_size, size_t(limit - first + 1));
            prefixes[0] = Fe{1, 0, 0};
            for (size_t i = 0; i < count; ++i) {
                words[i] = w_from_mask(first + static_cast<uint32_t>(i), trace_bits);
                if (words[i] == Fe{0, 0, 0} || trace_bit(words[i], trace) != 0)
                    throw std::runtime_error("basis produced zero or non-trace-zero w");
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
                if (!(mul(words[i], inverses[i]) == Fe{1, 0, 0}))
                    throw std::runtime_error("individual inverse replay failed");
                const uint32_t mask = first + static_cast<uint32_t>(i);
                const uint8_t source_flags = record(
                    source, mask, inverses[i], trace, dimension, trace_bits, source_out);
                const uint8_t descendant_flags = record(
                    descendant, mask, mul(alpha, inverses[i]), trace,
                    dimension, trace_bits, descendant_out);
                flags_out.put(static_cast<char>(source_flags | (descendant_flags << 4)));
                if (!flags_out) throw std::runtime_error("per-mask flag output failed");
            }
            const uint32_t completed = first + static_cast<uint32_t>(count) - 1;
            if ((completed >> 20) != ((first - 1) >> 20))
                std::fprintf(stderr, "masks=%u/%u source_C=%llu descendant_C=%llu\n",
                             completed, limit,
                             static_cast<unsigned long long>(source.columns),
                             static_cast<unsigned long long>(descendant.columns));
            first = completed + 1;
            const auto elapsed = std::chrono::steady_clock::now() - start;
            if (elapsed > std::chrono::seconds(wall_limit_s))
                throw std::runtime_error("wall limit exceeded");
            rusage usage{};
            if (getrusage(RUSAGE_SELF, &usage) != 0)
                throw std::runtime_error("getrusage failed");
#if defined(__APPLE__)
            const uint64_t rss_bytes = static_cast<uint64_t>(usage.ru_maxrss);
#else
            const uint64_t rss_bytes = static_cast<uint64_t>(usage.ru_maxrss) * 1024;
#endif
            if (rss_bytes > rss_limit_bytes)
                throw std::runtime_error("RSS limit exceeded");
        }
        source_out.close();
        descendant_out.close();
        flags_out.close();
        if (source.columns != source.rational - source.pairs ||
            descendant.columns != descendant.rational - descendant.pairs ||
            source.partner_inside != 2 * source.pairs + source.fixed ||
            descendant.partner_inside != 2 * descendant.pairs + descendant.fixed ||
            source.fixed != 0 || descendant.fixed != 0)
            throw std::runtime_error("reciprocal class accounting failed");
        // For d<=28, products inside W_d have degree <=56. Source alpha=1
        // cannot be a product of trace-zero nonconstants, while this frozen
        // descendant alpha has degree 130; neither has a reciprocal pair.
        if (alpha.hi & uint64_t(4)) {
            if (source.pairs != 0 || descendant.pairs != 0)
                throw std::runtime_error("degree-bound reciprocal collision");
        }
        const auto elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - start).count();
        rusage usage{};
        if (getrusage(RUSAGE_SELF, &usage) != 0)
            throw std::runtime_error("getrusage failed");
#if defined(__APPLE__)
        const uint64_t rss_bytes = static_cast<uint64_t>(usage.ru_maxrss);
#else
        const uint64_t rss_bytes = static_cast<uint64_t>(usage.ru_maxrss) * 1024;
#endif
        std::ofstream receipt(argv[11]);
        if (!receipt) throw std::runtime_error("cannot open receipt");
        receipt << "{\"kind\":\"ecc2k130_degree263_exact_w_base_native_census\","
                << "\"status\":\"completed\",\"candidate_id\":null,"
                << "\"field_backend\":\"" FIELD_BACKEND "\","
                << "\"dimension\":" << dimension << ",\"batch_size\":" << batch_size
                << ",\"checked_nonzero_masks\":" << limit
                << ",\"basis_trace_bits\":" << trace_bits
                << ",\"alpha_limbs\":[" << alpha.lo << ',' << alpha.mid << ',' << alpha.hi << ']'
                << ",\"normalized_b_limbs\":[" << b.lo << ',' << b.mid << ',' << b.hi << ']'
                << ",\"source\":";
        print_counts(receipt, source);
        receipt << ",\"descendant\":";
        print_counts(receipt, descendant);
        receipt << ",\"elapsed_ns\":" << elapsed_ns
                << ",\"peak_rss_bytes\":" << rss_bytes
                << ",\"natural_pdp_yield\":null,\"verified_relation_rank\":null,"
                << "\"verified_logarithm\":null,\"online_wall_time\":null,"
                << "\"rho_ratio\":null}\n";
        if (!receipt) throw std::runtime_error("receipt write failed");
        std::printf("dimension=%d source_R=%llu source_C=%llu descendant_R=%llu descendant_C=%llu\n",
                    dimension,
                    static_cast<unsigned long long>(source.rational),
                    static_cast<unsigned long long>(source.columns),
                    static_cast<unsigned long long>(descendant.rational),
                    static_cast<unsigned long long>(descendant.columns));
        return 0;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "error: %s\n", error.what());
        return 2;
    }
}
