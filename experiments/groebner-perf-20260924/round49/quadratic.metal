#include <metal_stdlib>
using namespace metal;

struct Parameters {
    uint branches, features, equations, active_branches, variables, projection_enabled;
};

inline uint2 row_bit(uint bit)
{
    return bit < 32 ? uint2(1u << bit, 0) : uint2(0, 1u << (bit - 32));
}
inline bool has_bit(uint2 row, uint2 bit) { return (row.x & bit.x) != 0 || (row.y & bit.y) != 0; }
inline uint2 shuffle_row(uint2 row, ushort lane)
{
    return uint2(simd_shuffle(row.x, lane), simd_shuffle(row.y, lane));
}

// One complete residual branch per SIMD group. Both words participate in
// every lane exchange. Rank/empty-row control flow stays group-uniform.
kernel void quadratic_branches(device const uint *columns [[buffer(0)]],
                               device uint *result [[buffer(1)]],
                               constant Parameters &p [[buffer(2)]],
                               device const uint *branch_ids [[buffer(3)]],
                               device uint *projection [[buffer(4)]],
                               uint group [[threadgroup_position_in_grid]],
                               ushort simd [[simdgroup_index_in_threadgroup]],
                               ushort lane [[thread_index_in_simdgroup]])
{
    uint item = group * 4 + simd;
    if (item >= p.active_branches) return;
    uint branch = p.active_branches < p.branches ? branch_ids[item] : item;
    uint base = branch * (p.features + 1);
    uint2 row = uint2(0);
    uint combination = lane < p.equations ? 1u << lane : 0;
    if (lane < p.equations) {
        for (uint j = 0; j < p.features; ++j)
            if ((columns[base + j + 1] >> lane) & 1u) row |= row_bit(j);
        if ((columns[base] >> lane) & 1u) row |= row_bit(p.features);
    }
    uint rank = 0;
    for (uint j = 0; j < p.features; ++j) {
        uint2 bit = row_bit(j);
        uint chosen = simd_min(lane >= rank && has_bit(row, bit) ? uint(lane) : 32u);
        if (chosen < 32) {
            uint2 pivot = shuffle_row(row, ushort(chosen));
            uint2 displaced = shuffle_row(row, ushort(rank));
            uint pivot_combination = simd_shuffle(combination, ushort(chosen));
            uint displaced_combination = simd_shuffle(combination, ushort(rank));
            if (lane == rank) {
                row = pivot;
                combination = pivot_combination;
            } else {
                if (lane == chosen) {
                    row = displaced;
                    combination = displaced_combination;
                }
                if (has_bit(row, bit)) {
                    row ^= pivot;
                    combination ^= pivot_combination;
                }
            }
            ++rank;
        }
    }
    uint bad_lane = simd_min(all(row == row_bit(p.features)) ? uint(lane) : 32u);
    bool inconsistent = bad_lane < 32;
    uint witness = simd_shuffle(combination, ushort(min(bad_lane, 31u)));
    // Explicit little-endian pairs:34 uint64 host cells, no native64-bit
    // shuffle requirement. Row storage and output bytes are fully charged.
    result[branch * 68 + 2 + 2 * lane] = row.x;
    result[branch * 68 + 3 + 2 * lane] = row.y;
    if (lane == 0) {
        result[branch * 68] = rank | (inconsistent ? 0x80000000u : 0u);
        result[branch * 68 + 1] = 0;
        result[branch * 68 + 66] = inconsistent ? witness : 0;
        result[branch * 68 + 67] = 0;
    }

    if (!p.projection_enabled) return;
    uint quadratic_rank = 0, row_xors = 0;
    // Continue from the lifted RREF, retaining its original-equation witnesses.
    // Forward elimination of quadratic columns extracts the affine kernel.
    for (uint j = p.variables; j < p.features; ++j) {
        uint2 bit = row_bit(j);
        uint chosen = simd_min(lane >= quadratic_rank && has_bit(row, bit) ? uint(lane) : 32u);
        if (chosen < 32) {
            uint2 pivot = shuffle_row(row, ushort(chosen));
            uint2 displaced = shuffle_row(row, ushort(quadratic_rank));
            uint pivot_combination = simd_shuffle(combination, ushort(chosen));
            uint displaced_combination = simd_shuffle(combination, ushort(quadratic_rank));
            if (lane == quadratic_rank) {
                row = pivot;
                combination = pivot_combination;
            } else {
                if (lane == chosen) {
                    row = displaced;
                    combination = displaced_combination;
                }
                if (lane > quadratic_rank && has_bit(row, bit)) {
                    row ^= pivot;
                    combination ^= pivot_combination;
                    ++row_xors;
                }
            }
            ++quadratic_rank;
        }
    }
    rank = quadratic_rank;
    for (uint j = 0; j < p.variables; ++j) {
        uint2 bit = row_bit(j);
        uint chosen = simd_min(lane >= rank && has_bit(row, bit) ? uint(lane) : 32u);
        if (chosen < 32) {
            uint2 pivot = shuffle_row(row, ushort(chosen));
            uint2 displaced = shuffle_row(row, ushort(rank));
            uint pivot_combination = simd_shuffle(combination, ushort(chosen));
            uint displaced_combination = simd_shuffle(combination, ushort(rank));
            if (lane == rank) {
                row = pivot;
                combination = pivot_combination;
            } else {
                if (lane == chosen) {
                    row = displaced;
                    combination = displaced_combination;
                }
                if (lane >= quadratic_rank && has_bit(row, bit)) {
                    row ^= pivot;
                    combination ^= pivot_combination;
                    ++row_xors;
                }
            }
            ++rank;
        }
    }
    uint affine_rank = rank - quadratic_rank;
    bad_lane = simd_min(lane >= quadratic_rank && all(row == row_bit(p.features)) ? uint(lane) : 32u);
    witness = simd_shuffle(combination, ushort(min(bad_lane, 31u)));
    uint operations = simd_sum(row_xors);
    uint offset = branch * (p.variables + 2) * 2;
    // Each row is [affine polynomial with constant bit zero, original witness].
    // Every output slot is overwritten, including unused rows, on every solve.
    for (uint i = 0; i < p.variables; ++i) {
        uint source = min(quadratic_rank + i, 31u);
        uint2 affine = shuffle_row(row, ushort(source));
        uint coefficients = simd_shuffle(combination, ushort(source));
        if (lane == i) {
            uint polynomial = ((affine.x & ((1u << p.variables) - 1u)) << 1) |
                              uint(has_bit(affine, row_bit(p.features)));
            projection[offset + 2 + 2 * i] = i < affine_rank ? polynomial : 0;
            projection[offset + 3 + 2 * i] = i < affine_rank ? coefficients : 0;
        }
    }
    if (lane == 0) {
        projection[offset] = 0x80000000u | quadratic_rank | (affine_rank << 8) |
                             (bad_lane < 32 ? 0x10000u : 0u);
        projection[offset + 1] = operations;
        projection[offset + 2 * (p.variables + 1)] = bad_lane < 32 ? 1 : 0;
        projection[offset + 2 * (p.variables + 1) + 1] = bad_lane < 32 ? witness : 0;
    }
}
