// SPDX-License-Identifier: GPL-2.0-or-later
#include "binary_hardware_native.h"
#include <algorithm>
#include <exception>
#include <thread>
#include <vector>

static thread_local std::string last_error;
void bh_set_error(const std::string& s) { last_error = s; }
extern "C" const char* bh_last_error() { return last_error.c_str(); }

template<unsigned W>
static void transform(const uint32_t* table, const uint32_t* input,
                      uint32_t* output, uint64_t begin, uint64_t end, unsigned bytes) {
    for (uint64_t e=begin; e<end; ++e) {
        uint32_t acc[W] = {};
        const uint32_t* src = input+e*W;
        for (unsigned b=0; b<bytes; ++b) {
            unsigned value = (src[b/4] >> (8*(b%4))) & 255u;
            const uint32_t* row = table+(b*256+value)*W;
            for (unsigned w=0; w<W; ++w) acc[w] ^= row[w];
        }
        for (unsigned w=0; w<W; ++w) output[e*W+w]=acc[w];
    }
}

static void dispatch(const uint32_t* t, const uint32_t* a, uint32_t* b,
                     uint64_t lo, uint64_t hi, unsigned words, unsigned bytes) {
#define CASE(W) case W: transform<W>(t,a,b,lo,hi,bytes); break
    switch(words) { CASE(1); CASE(2); CASE(3); CASE(4); CASE(5); CASE(6); CASE(7); CASE(8); }
#undef CASE
}

extern "C" int bh_cpu_apply(const uint32_t* t, const uint32_t* a, uint32_t* b,
                            uint64_t count, uint32_t words, uint32_t bytes,
                            uint32_t workers) {
    if (!words || words>8 || !bytes || bytes>32 || (bytes+3)/4!=words ||
        !workers || workers>32 || count>134217728ull/words ||
        !t || (count && (!a || !b))) {
        bh_set_error("invalid native CPU dimensions or pointers"); return -1;
    }
    if (!count) return 0;
    try {
        workers=std::min<uint64_t>(workers,count);
        if (workers==1) dispatch(t,a,b,0,count,words,bytes);
        else {
            std::vector<std::thread> threads;
            // Join already-created threads even if thread creation fails.
            try {
                for (unsigned i=0; i<workers; ++i)
                    threads.emplace_back(dispatch,t,a,b,count*i/workers,
                                         count*(i+1)/workers,words,bytes);
            } catch (...) {
                for (auto& thread:threads) thread.join();
                throw;
            }
            for (auto& thread:threads) thread.join();
        }
        return 0;
    } catch (const std::exception& e) { bh_set_error(e.what()); return -2; }
}

#ifndef BH_WITH_METAL
extern "C" void* bh_metal_create(const char*,const uint32_t*,uint32_t,uint32_t,uint32_t) {
    bh_set_error("Metal is unavailable in this native build"); return nullptr;
}
extern "C" void bh_metal_destroy(void*) {}
extern "C" const char* bh_metal_name(void*) { return "unavailable"; }
extern "C" int bh_metal_apply(void*,const uint32_t*,uint32_t*,uint64_t,double*) {
    bh_set_error("Metal is unavailable in this native build"); return -1;
}
#endif
