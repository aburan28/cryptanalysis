// Experimental compact metadata. Point arithmetic and live history are unchanged.
#pragma once
#ifndef GOAL22_BYTE_DEAD
#define GOAL22_BYTE_DEAD 1
#endif
#ifndef GOAL22_FULL_HIST
#define GOAL22_FULL_HIST 0
#endif
namespace eccPacked131 {
ECC_HD size_t goal22HistoryBytes(size_t count) {
    return count * (GOAL22_FULL_HIST ? sizeof(unsigned long long) : 3 * sizeof(unsigned short));
}
ECC_HD size_t goal22DeadBytes(size_t count) {
    return GOAL22_BYTE_DEAD ? count : ((count + 31) / 32) * sizeof(unsigned);
}
ECC_HD unsigned goal22ReadDead(const unsigned *flags, size_t id) {
#if GOAL22_BYTE_DEAD
    return reinterpret_cast<const unsigned char *>(flags)[id];
#elif defined(__CUDA_ARCH__)
    // Atomic load semantics match neighboring lanes' atomic OR/AND writes.
    unsigned value;
    asm volatile("ld.relaxed.gpu.global.u32 %0, [%1];" : "=r"(value) : "l"(flags + (id >> 5)) : "memory");
    return (value >> (id & 31)) & 1u;
#else
    return (flags[id >> 5] >> (id & 31)) & 1u;
#endif
}
ECC_HD void goal22WriteDead(unsigned *flags, size_t id, unsigned value) {
#if GOAL22_BYTE_DEAD
    reinterpret_cast<unsigned char *>(flags)[id] = static_cast<unsigned char>(value);
#else
    const unsigned mask = 1u << (id & 31);
#ifdef __CUDA_ARCH__
    if(value) atomicOr(flags + (id >> 5), mask);
    else atomicAnd(flags + (id >> 5), ~mask);
#else
    if(value) flags[id >> 5] |= mask;
    else flags[id >> 5] &= ~mask;
#endif
#endif
}
ECC_HD unsigned long long goal22ReadHist(const unsigned long long *base, size_t id, size_t count) {
#if GOAL22_FULL_HIST
    return base[id];
#else
    const auto *p = reinterpret_cast<const unsigned short *>(base);
    // eccTagFruitless uses exactly three tags. Canonicalize the unused fourth.
    return 0xffff000000000000ull | (unsigned long long)p[id]
        | ((unsigned long long)p[count + id] << 16)
        | ((unsigned long long)p[2 * count + id] << 32);
#endif
}
ECC_HD void goal22WriteHist(unsigned long long *base, size_t id, size_t count, unsigned long long hist) {
#if GOAL22_FULL_HIST
    base[id] = hist;
#else
    auto *p = reinterpret_cast<unsigned short *>(base);
    p[id] = (unsigned short)hist;
    p[count + id] = (unsigned short)(hist >> 16);
    p[2 * count + id] = (unsigned short)(hist >> 32);
#endif
}
} // namespace eccPacked131
