
__kernel void bh_map(__global const uint *table, __global const uint *input,
                     __global uint *output, uint bytes, uint words, uint count) {
    uint i = (uint)get_global_id(0);

    if (i >= count * words) return;
    uint e = i / words, w = i % words;
    uint value = 0;
    for (uint b = 0; b < bytes; ++b) {
        uint digit = (input[e*words + b/4] >> (8*(b%4))) & 255u;
        value ^= table[(b*256u + digit)*words + w];
    }
    output[i] = value;

}
