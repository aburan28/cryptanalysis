// Q1458: exact S3 roots with shared inversions over a frozen input batch.
#pragma once

#include "../q1420_root_theory/root_field.hpp"

#include <utility>

namespace q1458 {

using q1420::Field;
using q1420::U128;

struct BatchStats {
    uint64_t inverse_batches = 0;
    uint64_t denominators = 0;
    uint64_t root_inputs = 0;
};

// Montgomery's trick: k nonzero inverses need one field inversion and O(k)
// multiplications. The final check also catches any field or ordering error.
inline std::vector<U128> inverses(Field &field,
                                  const std::vector<U128> &values,
                                  BatchStats &stats) {
    if (values.empty()) return {};
    std::vector<U128> prefix(values.size() + 1, 1);
    for (size_t i = 0; i < values.size(); ++i) {
        q1420::require(values[i] != 0, "zero batched denominator");
        prefix[i + 1] = field.mul(prefix[i], values[i]);
    }
    U128 inverse_product = field.inv(prefix.back());
    std::vector<U128> result(values.size());
    for (size_t i = values.size(); i-- > 0;) {
        result[i] = field.mul(inverse_product, prefix[i]);
        inverse_product = field.mul(inverse_product, values[i]);
        q1420::require(field.mul(result[i], values[i]) == 1,
                       "batched inverse fails replay");
    }
    ++stats.inverse_batches;
    stats.denominators += values.size();
    return result;
}

// The returned root list has one entry per input, including empty lists.
// It uses exactly Field::roots_onb's S3 quadratic and root ordering.
inline std::vector<std::vector<U128>> roots_onb(
    Field &field, const std::vector<std::pair<U128, U128>> &inputs,
    BatchStats &stats) {
    struct Work {
        U128 a = 0, b = 0, product = 0, total_squared = 0, z = 0;
        bool quadratic_root = false;
    };
    std::vector<Work> work(inputs.size());
    std::vector<U128> products;
    products.reserve(inputs.size());
    for (size_t i = 0; i < inputs.size(); ++i) {
        auto [left, right] = inputs[i];
        q1420::require(left && right, "zero S3 input x");
        Work &w = work[i];
        w.a = field.to_poly(left);
        w.b = field.to_poly(right);
        w.product = field.mul(w.a, w.b);
        products.push_back(w.product);
        if (w.a != w.b) w.total_squared = field.sqr(w.a ^ w.b);
    }
    std::vector<U128> inverse_products = inverses(field, products, stats);
    std::vector<U128> valid_total_squares;
    std::vector<size_t> valid_indices;
    std::vector<std::vector<U128>> answer(inputs.size());
    for (size_t i = 0; i < inputs.size(); ++i) {
        Work &w = work[i];
        if (w.a == w.b) {
            U128 root = field.mul(field.sqr(w.product) ^ 1,
                                  inverse_products[i]);
            q1420::require(field.evaluate_s3(w.a, w.b, root) == 0,
                           "batched linear S3 root fails");
            answer[i] = {field.to_onb(root)};
            continue;
        }
        U128 rhs = field.mul(
            field.mul(w.total_squared, field.sqr(w.product) ^ 1),
            field.sqr(inverse_products[i]));
        w.z = field.half_trace(rhs);
        if ((field.sqr(w.z) ^ w.z) != rhs) continue;
        w.quadratic_root = true;
        valid_total_squares.push_back(w.total_squared);
        valid_indices.push_back(i);
    }
    std::vector<U128> inverse_total_squares = inverses(
        field, valid_total_squares, stats);
    for (size_t j = 0; j < valid_indices.size(); ++j) {
        size_t i = valid_indices[j];
        Work &w = work[i];
        q1420::require(w.quadratic_root,
                       "batch quadratic root index mismatch");
        U128 scale = field.mul(w.product, inverse_total_squares[j]);
        U128 first = field.mul(scale, w.z);
        U128 second = first ^ scale;
        q1420::require(first != second, "duplicate batched S3 root");
        q1420::require(field.evaluate_s3(w.a, w.b, first) == 0 &&
                       field.evaluate_s3(w.a, w.b, second) == 0,
                       "batched quadratic S3 root fails");
        U128 out0 = field.to_onb(first), out1 = field.to_onb(second);
        if (out1 < out0) std::swap(out0, out1);
        answer[i] = {out0, out1};
    }
    field.counts.roots += inputs.size();
    stats.root_inputs += inputs.size();
    return answer;
}

}  // namespace q1458
