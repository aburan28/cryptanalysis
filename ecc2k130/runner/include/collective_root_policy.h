#pragma once
#ifndef ECC_COLLECTIVE_CTA_WAVE
#define ECC_COLLECTIVE_CTA_WAVE 0
#endif
#ifndef ECC_COLLECTIVE_WAVE_SMS
#define ECC_COLLECTIVE_WAVE_SMS 170
#endif
#if ECC_COLLECTIVE_CTA_WAVE != 0 && ECC_COLLECTIVE_CTA_WAVE != 1
#error "ECC_COLLECTIVE_CTA_WAVE must be 0 or 1"
#endif
#if ECC_COLLECTIVE_WAVE_SMS < 1
#error "ECC_COLLECTIVE_WAVE_SMS must be positive"
#endif
#ifdef __CUDACC__
#define ECC_ROOT_HD __host__ __device__ __forceinline__
#else
#define ECC_ROOT_HD inline
#endif
namespace eccPacked131 {
template<int WARPS> ECC_ROOT_HD int collectiveRootRotation(int group,unsigned block) {
    const int base=group/(WARPS<4 ? 4/WARPS : 1);
#if ECC_COLLECTIVE_CTA_WAVE
    // This affects only which complete warp becomes a tree root. The wave
    // model is a performance hypothesis, not a hardware scheduling guarantee.
    constexpr int groups=ECC_THREADS/(32*WARPS);
    return (base+int((block/ECC_COLLECTIVE_WAVE_SMS)%WARPS)*groups)%WARPS;
#else
    (void)block;return base;
#endif
}
}
#undef ECC_ROOT_HD
