// Exact odd-degree F_2^n S3 roots with the archived ONB/poly bridge.
#pragma once

#include <array>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace q1420 {

using U128 = unsigned __int128;

inline void require(bool condition, const char *message) {
    if (!condition) throw std::runtime_error(message);
}

inline U128 parse_hex(const std::string &text) {
    require(!text.empty() && text.size() <= 32, "bad hex field element");
    U128 value = 0;
    for (char c : text) {
        unsigned digit = c >= '0' && c <= '9' ? unsigned(c - '0') :
                         c >= 'a' && c <= 'f' ? unsigned(c - 'a' + 10) :
                         c >= 'A' && c <= 'F' ? unsigned(c - 'A' + 10) : 16;
        require(digit < 16, "bad hex digit");
        value = (value << 4) | digit;
    }
    return value;
}

inline std::string hex(U128 value) {
    if (!value) return "0";
    std::string result;
    while (value) {
        unsigned digit = unsigned(value & 15);
        result.push_back("0123456789abcdef"[digit]);
        value >>= 4;
    }
    for (size_t i = 0, j = result.size() - 1; i < j; ++i, --j) {
        char temporary = result[i]; result[i] = result[j]; result[j] = temporary;
    }
    return result;
}

inline unsigned bit_index(U128 value) {
    require(value != 0, "zero has no bit index");
    uint64_t low = uint64_t(value);
    return low ? unsigned(__builtin_ctzll(low)) :
                 64 + unsigned(__builtin_ctzll(uint64_t(value >> 64)));
}

struct Counts {
    uint64_t mul = 0;
    uint64_t sqr = 0;
    uint64_t inv = 0;
    uint64_t roots = 0;
};

struct Field {
    int n = 0;
    U128 low = 0, mask = 0, one_onb = 0;
    std::array<U128, 128> onb_to_poly{}, poly_to_onb{}, square_basis{};
    Counts counts{};

    explicit Field(const std::string &path) {
        std::ifstream input(path);
        require(bool(input), "field bridge file missing");
        std::string magic, encoded;
        input >> magic >> n >> encoded;
        require(magic == "Q1420FIELD1" && (n == 53 || n == 83),
                "unexpected field bridge header");
        low = parse_hex(encoded);
        mask = (U128(1) << n) - 1;
        require((low & ~mask) == 0 && (low & 1), "bad field modulus");
        for (int i = 0; i < n; ++i) {
            input >> encoded; require(bool(input), "short forward bridge");
            onb_to_poly[i] = parse_hex(encoded);
            require((onb_to_poly[i] & ~mask) == 0, "forward overflow");
        }
        for (int i = 0; i < n; ++i) {
            input >> encoded; require(bool(input), "short inverse bridge");
            poly_to_onb[i] = parse_hex(encoded);
            require((poly_to_onb[i] & ~mask) == 0, "inverse overflow");
        }
        require(!(input >> encoded), "extra field bridge data");
        for (int i = 0; i < n; ++i)
            square_basis[i] = raw_mul(U128(1) << i, U128(1) << i);
        one_onb = to_onb(1);
        for (int i = 0; i < n; ++i)
            require(to_onb(to_poly(U128(1) << i)) == (U128(1) << i),
                    "noninverse basis bridge");
        counts = {};
    }

    U128 map(U128 value, const std::array<U128, 128> &basis) const {
        require((value & ~mask) == 0, "field element overflow");
        U128 result = 0;
        while (value) {
            unsigned bit = bit_index(value);
            result ^= basis[bit];
            value &= value - 1;
        }
        return result;
    }
    U128 to_poly(U128 onb) const { return map(onb, onb_to_poly); }
    U128 to_onb(U128 poly) const { return map(poly, poly_to_onb); }

    U128 raw_mul(U128 a, U128 b) const {
        require((a & ~mask) == 0 && (b & ~mask) == 0, "multiply overflow");
        U128 result = 0;
        for (int i = 0; i < n; ++i) {
            if (b & 1) result ^= a;
            b >>= 1;
            a <<= 1;
            if (a & (U128(1) << n)) a ^= (U128(1) << n) | low;
        }
        return result;
    }
    U128 mul(U128 a, U128 b) { ++counts.mul; return raw_mul(a, b); }
    U128 sqr(U128 a) { ++counts.sqr; return map(a, square_basis); }
    U128 square_power(U128 a, unsigned count) {
        while (count--) a = sqr(a);
        return a;
    }
    U128 inv(U128 a) {
        require(a != 0, "zero inverse");
        ++counts.inv;
        unsigned target = unsigned(n - 1);
        unsigned highest = 31 - unsigned(__builtin_clz(target));
        unsigned length = 1;
        U128 result = a;  // a^(2^length-1)
        for (int bit = int(highest) - 1; bit >= 0; --bit) {
            result = mul(square_power(result, length), result);
            length *= 2;
            if (target >> bit & 1) {
                result = mul(sqr(result), a);
                ++length;
            }
        }
        require(length == target, "inverse exponent length");
        result = sqr(result);
        require(mul(a, result) == 1, "inverse check failed");
        return result;
    }

    U128 half_trace(U128 value) {
        U128 result = 0;
        for (int i = 0; i < (n + 1) / 2; ++i) {
            result ^= value;
            value = sqr(sqr(value));
        }
        return result;
    }
    U128 evaluate_s3(U128 a, U128 b, U128 c) {
        U128 ab = mul(a, b), ac = mul(a, c), bc = mul(b, c);
        return sqr(ab ^ ac ^ bc) ^ mul(ab, c) ^ 1;
    }
    std::vector<U128> roots_onb(U128 left, U128 right) {
        ++counts.roots;
        require(left && right, "zero S3 leaf x");
        U128 a = to_poly(left), b = to_poly(right);
        U128 product = mul(a, b);
        if (a == b) {
            U128 root = mul(sqr(product) ^ 1, inv(product));
            require(evaluate_s3(a, b, root) == 0, "linear S3 root fails");
            return {to_onb(root)};
        }
        U128 total_squared = sqr(a ^ b);
        U128 inverse_product = inv(product);
        U128 rhs = mul(mul(total_squared, sqr(product) ^ 1),
                       sqr(inverse_product));
        U128 z = half_trace(rhs);
        if ((sqr(z) ^ z) != rhs) return {};
        U128 scale = mul(product, inv(total_squared));
        U128 first = mul(scale, z), second = first ^ scale;
        require(first != second, "duplicate quadratic S3 root");
        require(evaluate_s3(a, b, first) == 0 &&
                evaluate_s3(a, b, second) == 0, "quadratic S3 root fails");
        U128 out0 = to_onb(first), out1 = to_onb(second);
        if (out1 < out0) { U128 temporary = out0; out0 = out1; out1 = temporary; }
        return {out0, out1};
    }
};

}  // namespace q1420
