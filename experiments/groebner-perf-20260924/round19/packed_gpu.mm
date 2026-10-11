#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include "build/shader_source.inc"
using Clock = std::chrono::steady_clock;
static double elapsed(Clock::time_point begin)
{
    return std::chrono::duration<double>(Clock::now() - begin).count();
}
static thread_local std::string last_error;
struct GPUStats {
    double prepare = 0, encode = 0, execute = 0, device = 0;
    double extract = 0, basis_check = 0, total = 0, spin = 0;
    uint64_t zeta_words = 0, high_gather_words = 0, shared_buffer_bytes = 0, polls = 0;
    uint32_t calls = 0, dispatches = 0, blocking_fallback = 0, threads = 0;
};
struct Params { uint32_t equations, blocks, mask_lo, mask_hi; };

static id<MTLDevice> make_device()
{
    uint32_t endian = 1;
    if (*reinterpret_cast<uint8_t *>(&endian) != 1)
        throw std::runtime_error("little-endian host required");
    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    if (!device) throw std::runtime_error("Metal device unavailable");
    return device;
}

// This small vector interface lets the unchanged packed decoder write straight
// into shared Metal storage, and the frozen proof read the root buffer in place.
struct SharedWords {
    id<MTLBuffer> buffer;
    size_t count;
    SharedWords(id<MTLDevice> device, size_t words) : count(words)
    {
        buffer = [device newBufferWithLength:words * sizeof(uint64_t)
                                    options:MTLResourceStorageModeShared];
        if (!buffer || !buffer.contents) throw std::runtime_error("shared buffer allocation failed");
    }
    uint64_t *data() { return static_cast<uint64_t *>(buffer.contents); }
    const uint64_t *data() const { return static_cast<const uint64_t *>(buffer.contents); }
    uint64_t *begin() { return data(); }
    uint64_t *end() { return data() + count; }
    size_t size() const { return count; }
    uint64_t &operator[](size_t i) { return data()[i]; }
    const uint64_t &operator[](size_t i) const { return data()[i]; }
};

struct Workspace {
    uint32_t n, equations, limbs, universe, blocks;
    id<MTLDevice> device;
    SharedWords values, roots;
    std::vector<uint8_t> present;
    std::array<uint64_t, 64> low{};
    id<MTLCommandQueue> queue;
    id<MTLComputePipelineState> transform, intersect;
    id<MTLBuffer> transformed, params;
    uint32_t spin_us = 0, threads = 256;
    Clock::time_point start;
    GPUStats stats;

    Workspace(uint32_t variables, uint32_t count)
        : n(variables), equations(count), limbs((count + 63) / 64),
          universe(1u << variables), blocks((universe + 63) / 64), device(make_device()),
          values(device, size_t(count) * blocks), roots(device, blocks), present(count)
    {
        @autoreleasepool {
            for (uint32_t mask = 0; mask < 64; ++mask)
                for (uint32_t point = 0; point < 64; ++point)
                    if ((point & mask) == mask) low[mask] |= uint64_t(1) << point;
            NSError *error = nil;
            id<MTLLibrary> library = [device newLibraryWithSource:@(shader_source) options:nil error:&error];
            if (!library) throw std::runtime_error(error.description.UTF8String);
            auto pipeline = [&](NSString *name) {
                id<MTLFunction> fn = [library newFunctionWithName:name];
                if (!fn) throw std::runtime_error("shader function missing");
                id<MTLComputePipelineState> p = [device newComputePipelineStateWithFunction:fn error:&error];
                if (!p) throw std::runtime_error(error.description.UTF8String);
                return p;
            };
            transform = pipeline(@"zeta_tiles");
            intersect = pipeline(@"tiled_intersect");
            if (transform.staticThreadgroupMemoryLength > device.maxThreadgroupMemoryLength)
                throw std::runtime_error("tile exceeds shared-memory capacity");
            threads = uint32_t(std::min(NSUInteger(threads), transform.maxTotalThreadsPerThreadgroup));
            queue = [device newCommandQueue];
            if (!queue) throw std::runtime_error("command queue allocation failed");
            transformed = [device newBufferWithLength:values.buffer.length options:MTLResourceStorageModeShared];
            params = [device newBufferWithLength:sizeof(Params) options:MTLResourceStorageModeShared];
            if (!transformed || !params) throw std::runtime_error("Metal buffer allocation failed");
            const uint64_t mask = n < 6 ? (uint64_t(1) << universe) - 1 : ~uint64_t(0);
            const Params p = {equations, blocks, uint32_t(mask), uint32_t(mask >> 32)};
            memcpy(params.contents, &p, sizeof(p));
        }
    }

    uint64_t shared_bytes() const
    {
        return values.buffer.length + roots.buffer.length + transformed.length + params.length;
    }

    void begin_call()
    {
        last_error.clear();
        stats = {};
        start = Clock::now();
    }

    uint32_t evaluate()
    {
        @autoreleasepool {
            stats.prepare = elapsed(start);
            auto phase = Clock::now();
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            if (!command || !encoder) throw std::runtime_error("command allocation failed");
            [encoder setBuffer:values.buffer offset:0 atIndex:0];
            [encoder setBuffer:transformed offset:0 atIndex:1];
            [encoder setBuffer:roots.buffer offset:0 atIndex:2];
            [encoder setBuffer:params offset:0 atIndex:3];
            [encoder setComputePipelineState:transform];
            [encoder dispatchThreadgroups:MTLSizeMake(equations * ((blocks + 4095) / 4096), 1, 1)
                    threadsPerThreadgroup:MTLSizeMake(threads, 1, 1)];
            [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
            [encoder setComputePipelineState:intersect];
            [encoder dispatchThreads:MTLSizeMake(blocks, 1, 1)
                    threadsPerThreadgroup:MTLSizeMake(std::min(NSUInteger(256), intersect.maxTotalThreadsPerThreadgroup), 1, 1)];
            [encoder endEncoding];
            stats.encode = elapsed(phase);
            phase = Clock::now();
            [command commit];
            if (spin_us) {
                const auto spin_start = Clock::now();
                const auto deadline = spin_start + std::chrono::microseconds(spin_us);
                while (command.status < MTLCommandBufferStatusCompleted && Clock::now() < deadline)
                    ++stats.polls;
                stats.spin = elapsed(spin_start);
            }
            if (command.status < MTLCommandBufferStatusCompleted) {
                stats.blocking_fallback = 1;
                [command waitUntilCompleted];
            }
            if (command.status != MTLCommandBufferStatusCompleted)
                throw std::runtime_error(command.error ? command.error.description.UTF8String : "GPU execution failed");
            stats.execute = elapsed(phase);
            stats.device = command.GPUEndTime - command.GPUStartTime;
            phase = Clock::now();
            uint32_t alive = 0;
            const auto *data = roots.data();
            for (uint32_t i = 0; i < blocks; ++i) alive += uint32_t(__builtin_popcountll(data[i]));
            stats.extract = elapsed(phase);
            stats.calls = 1;
            stats.dispatches = 2;
            stats.threads = threads;
            stats.shared_buffer_bytes = shared_bytes();
            const uint32_t width = std::min(blocks, uint32_t(4096));
            for (uint32_t stride = 1; stride < width; stride <<= 1)
                stats.zeta_words += uint64_t(equations) * blocks / 2;
            stats.high_gather_words = uint64_t(equations) * width;
            for (uint32_t tiles = blocks / width; tiles > 1; tiles >>= 1)
                stats.high_gather_words *= 3;
            return alive;
        }
    }
};

// Generated from the frozen round18 decoder/direct replay and the same frozen
// exact basis proof. Only workspace storage and truth evaluation are replaced.
#include "build/packed_gpu_core.inc"

extern "C" uint64_t truth_gpu_stats_size() { return sizeof(GPUStats); }
extern "C" const char *truth_gpu_error() { return last_error.c_str(); }
extern "C" const char *truth_gpu_device(void *handle)
{
    return handle ? static_cast<Workspace *>(handle)->device.name.UTF8String : "";
}
extern "C" int truth_gpu_configure(void *handle, uint32_t polling, uint32_t threads)
{
    if (!handle || polling > 5000 || !threads) return 6;
    auto &w = *static_cast<Workspace *>(handle);
    if (threads > w.transform.maxTotalThreadsPerThreadgroup) return 6;
    w.spin_us = polling;
    w.threads = threads;
    return 0;
}
extern "C" int truth_gpu_stats(void *handle, GPUStats *out)
{
    if (!out) return 6;
    *out = {};
    if (!handle) return 6;
    *out = static_cast<Workspace *>(handle)->stats;
    return 0;
}
