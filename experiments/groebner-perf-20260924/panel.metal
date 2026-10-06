#include <metal_stdlib>
using namespace metal;

// Exact GF(2) Four Russians trailing-panel update. The first six columns of
// table pivot rows form I_6. Input and output must not alias: every lane reads
// its row's original pivot pattern while another lane writes column zero.
kernel void reduce_panel(device const uint* input [[buffer(0)]],
                         device const uint* table [[buffer(1)]],
                         device uint* output [[buffer(2)]],
                         constant uint& words [[buffer(3)]],
                         constant uint& count [[buffer(4)]],
                         uint index [[thread_position_in_grid]]) {
    if (index >= count) return;
    uint row = index / words;
    uint column = index % words;
    uint pattern = input[row * words] & 63u;
    output[index] = input[index] ^ table[pattern * words + column];
}

// A two-dimensional grid removes per-word integer division/modulo. uint4
// loads amortize pattern lookup and address arithmetic over 128 coefficient
// bits. The caller pads the matrix stride to a multiple of four uint words.
kernel void reduce_panel_vec(device const uint4* input [[buffer(0)]],
                             device const uint4* table [[buffer(1)]],
                             device uint4* output [[buffer(2)]],
                             constant uint& words [[buffer(3)]],
                             constant uint& count [[buffer(4)]],
                             uint2 position [[thread_position_in_grid]]) {
    uint stride = words / 4;
    uint index = position.y * stride + position.x;
    if (position.x >= stride || index >= count / 4) return;
    uint pattern = input[position.y * stride].x & 63u;
    output[index] = input[index] ^ table[pattern * stride + position.x];
}
