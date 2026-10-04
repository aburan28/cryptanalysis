#include "metal_transform.h"
#include "build/kernel.inc"
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>

namespace
{
using Clock = std::chrono::steady_clock;
double elapsed(Clock::time_point start)
{
    return std::chrono::duration<double>(Clock::now() - start).count();
}
struct Context {
    id<MTLDevice> device;
    id<MTLCommandQueue> queue;
    id<MTLComputePipelineState> pipeline, low_pipeline;
    id<MTLBuffer> buffer;
    uint32_t branches, slices, lanes, variables, lane_shift, low_bits;
    std::string name;
};
struct Parameters {
    uint32_t branches, slices, lanes, bit, variables, lane_shift, low_bits;
};
std::runtime_error failure(NSString *text)
{
    return std::runtime_error(text ? text.UTF8String : "independent Metal transform failed");
}
} // namespace

void *independent_metal_create(uint32_t variables, uint32_t slices, uint32_t word_bits, bool fused)
{
    @autoreleasepool {
        if (!variables || variables > 20 || !slices || slices > 112 ||
            (word_bits != 32 && word_bits != 64))
            throw std::invalid_argument("independent transform dimensions");
        const size_t bytes = size_t(1u << variables) * slices * (word_bits / 8);
        if (bytes > (64u << 20)) throw std::length_error("independent transform exceeds 64 MiB");
        auto c = std::make_unique<Context>();
        c->branches = 1u << variables;
        c->slices = slices;
        c->lanes = word_bits / 32;
        c->variables = variables;
        c->lane_shift = word_bits == 64 ? 1 : 0;
        c->low_bits = fused ? std::min(variables, 5 - c->lane_shift) : 0;
        c->device = MTLCreateSystemDefaultDevice();
        if (!c->device) throw IndependentMetalUnavailable("requested Metal device unavailable");
        if (bytes > c->device.maxBufferLength) throw std::length_error("Metal buffer limit");
        c->name = std::string(c->device.name.UTF8String) +
                  "; registry=" + std::to_string(c->device.registryID);
        c->queue = [c->device newCommandQueue];
        // Explicit tracked storage, ordinary Metal queue, one encoder per stage.
        // This is not an MTL4 command queue or an untracked heap resource.
        c->buffer = [c->device newBufferWithLength:bytes
                                           options:MTLResourceStorageModeShared |
                                                   MTLResourceHazardTrackingModeTracked];
        if (!c->queue || !c->buffer)
            throw std::runtime_error("Metal queue/buffer allocation failed");
        NSError *error = nil;
        MTLCompileOptions *options = [MTLCompileOptions new];
        options.languageVersion = MTLLanguageVersion2_4;
        id<MTLLibrary> library = [c->device newLibraryWithSource:@(independent_transform_kernel)
                                                         options:options
                                                           error:&error];
        if (!library) throw failure(error.localizedDescription);
        id<MTLFunction> function =
            [library newFunctionWithName:fused ? @"independent_subset_stage_bits"
                                               : @"independent_subset_stage"];
        if (!function) throw std::runtime_error("independent transform kernel missing");
        c->pipeline = [c->device newComputePipelineStateWithFunction:function error:&error];
        if (!c->pipeline) throw failure(error.localizedDescription);
        if (!c->pipeline.maxTotalThreadsPerThreadgroup)
            throw std::runtime_error("Metal threadgroup capacity unavailable");
        if (fused) {
            id<MTLFunction> low = [library newFunctionWithName:@"independent_subset_low"];
            if (!low) throw std::runtime_error("independent SIMD transform kernel missing");
            c->low_pipeline = [c->device newComputePipelineStateWithFunction:low error:&error];
            if (!c->low_pipeline) throw failure(error.localizedDescription);
            if (c->low_pipeline.threadExecutionWidth != 32 ||
                c->low_pipeline.maxTotalThreadsPerThreadgroup < 32)
                throw std::runtime_error("independent SIMD transform requires width 32");
        }
        return c.release();
    }
}

void independent_metal_destroy(void *p) { delete static_cast<Context *>(p); }
const char *independent_metal_device(void *p)
{
    return p ? static_cast<Context *>(p)->name.c_str() : "cpu";
}
void independent_metal_transform(void *p, void *values, size_t bytes, DeviceTransformStats &stats)
{
    @autoreleasepool {
        if (!p || !values) throw std::invalid_argument("independent transform null input");
        auto &c = *static_cast<Context *>(p);
        if (bytes != c.buffer.length) throw std::invalid_argument("independent transform extent");
        stats = {};
        stats.requested = 1;
        stats.scratch_bytes = bytes;
        stats.kernel_mode = c.low_bits ? 2 : 1;
        stats.fused_stages = c.low_bits;
        const auto started = Clock::now();
        auto phase = Clock::now();
        std::memcpy(c.buffer.contents, values, bytes);
        stats.copy_in = elapsed(phase);
        stats.input_bytes = bytes;
        phase = Clock::now();
        id<MTLCommandBuffer> command = [c.queue commandBuffer];
        if (!command) throw std::runtime_error("Metal command allocation failed");
        const uint32_t threads = c.slices * (c.branches / 2) * c.lanes;
        const NSUInteger group =
            std::min<NSUInteger>(256, c.pipeline.maxTotalThreadsPerThreadgroup);
        for (uint32_t bit = c.branches / 2; bit >= (1u << c.low_bits); bit >>= 1) {
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            if (!encoder) throw std::runtime_error("Metal encoder allocation failed");
            const Parameters params{c.branches,  c.slices,     c.lanes,   bit,
                                    c.variables, c.lane_shift, c.low_bits};
            [encoder setComputePipelineState:c.pipeline];
            [encoder setBuffer:c.buffer offset:0 atIndex:0];
            [encoder setBytes:&params length:sizeof(params) atIndex:1];
            [encoder dispatchThreadgroups:MTLSizeMake((threads + group - 1) / group, 1, 1)
                    threadsPerThreadgroup:MTLSizeMake(group, 1, 1)];
            [encoder endEncoding];
            ++stats.dispatches;
        }
        if (c.low_bits) {
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            if (!encoder) throw std::runtime_error("Metal SIMD encoder allocation failed");
            const Parameters params{c.branches,  c.slices,     c.lanes,   0,
                                    c.variables, c.lane_shift, c.low_bits};
            const NSUInteger low_group =
                std::min<NSUInteger>(256, c.low_pipeline.maxTotalThreadsPerThreadgroup / 32 * 32);
            const uint32_t words = c.slices * c.branches * c.lanes;
            [encoder setComputePipelineState:c.low_pipeline];
            [encoder setBuffer:c.buffer offset:0 atIndex:0];
            [encoder setBytes:&params length:sizeof(params) atIndex:1];
            [encoder dispatchThreadgroups:MTLSizeMake((words + low_group - 1) / low_group, 1, 1)
                    threadsPerThreadgroup:MTLSizeMake(low_group, 1, 1)];
            [encoder endEncoding];
            ++stats.dispatches;
        }
        stats.encode = elapsed(phase);
        phase = Clock::now();
        [command commit];
        [command waitUntilCompleted];
        stats.wait = elapsed(phase);
        stats.device = command.GPUEndTime - command.GPUStartTime;
        if (command.status != MTLCommandBufferStatusCompleted)
            throw failure(command.error.localizedDescription);
        phase = Clock::now();
        std::memcpy(values, c.buffer.contents, bytes);
        stats.output_bytes = bytes;
        stats.copy_out = elapsed(phase);
        stats.executed = 1;
        stats.seconds = elapsed(started);
    }
}
