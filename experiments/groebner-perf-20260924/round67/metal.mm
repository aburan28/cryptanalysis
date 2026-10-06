#include "transform.h"
#include "build/kernel.inc"
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <memory>
#include <string>

namespace producer_transform
{
namespace
{
using Clock = std::chrono::steady_clock;
double seconds(Clock::time_point start)
{
    return std::chrono::duration<double>(Clock::now() - start).count();
}
struct Context {
    id<MTLDevice> gpu;
    id<MTLCommandQueue> queue;
    id<MTLBuffer> buffer;
    id<MTLComputePipelineState> stage, tile;
    uint32_t variables, stride;
    Mode mode;
    std::string name;
};
struct Parameters {
    uint32_t branches, bit;
};
std::runtime_error failure(NSString *text)
{
    return std::runtime_error(text ? text.UTF8String : "producer Metal failure");
}
} // namespace

void *create(uint32_t variables, uint32_t stride, Mode mode)
{
    @autoreleasepool {
        const size_t bytes = extent(variables, stride);
        if (mode != Mode::staged && mode != Mode::tiled)
            throw std::invalid_argument("producer transform mode");
        auto c = std::make_unique<Context>();
        c->variables = variables;
        c->stride = stride;
        c->mode = mode;
        c->gpu = MTLCreateSystemDefaultDevice();
        if (!c->gpu) throw Unavailable("requested Metal device unavailable");
        if (bytes > c->gpu.maxBufferLength) throw std::length_error("Metal buffer limit");
        c->name =
            std::string(c->gpu.name.UTF8String) + "; registry=" + std::to_string(c->gpu.registryID);
        c->queue = [c->gpu newCommandQueue];
        c->buffer = [c->gpu newBufferWithLength:bytes
                                        options:MTLResourceStorageModeShared |
                                                MTLResourceHazardTrackingModeTracked];
        if (!c->queue || !c->buffer) throw std::runtime_error("Metal allocation failed");
        NSError *error = nil;
        MTLCompileOptions *options = [MTLCompileOptions new];
        options.languageVersion = MTLLanguageVersion2_4;
        id<MTLLibrary> library = [c->gpu newLibraryWithSource:@(producer_transform_kernel)
                                                      options:options
                                                        error:&error];
        if (!library) throw failure(error.localizedDescription);
        MTLFunctionConstantValues *constants = [MTLFunctionConstantValues new];
        [constants setConstantValue:&stride type:MTLDataTypeUInt atIndex:0];
        auto pipeline = [&](NSString *name) -> id<MTLComputePipelineState> {
            NSError *local_error = nil;
            id<MTLFunction> function = [library newFunctionWithName:name
                                                     constantValues:constants
                                                              error:&local_error];
            if (!function) throw failure(local_error.localizedDescription);
            id<MTLComputePipelineState> result =
                [c->gpu newComputePipelineStateWithFunction:function error:&local_error];
            if (!result) throw failure(local_error.localizedDescription);
            if (result.maxTotalThreadsPerThreadgroup < 256)
                throw Unavailable("producer transform requires 256 threads per group");
            return result;
        };
        c->stage = pipeline(@"producer_stage");
        if (mode == Mode::tiled) c->tile = pipeline(@"producer_low_tile");
        return c.release();
    }
}
void destroy(void *p) { delete static_cast<Context *>(p); }
const char *device(void *p) { return p ? static_cast<Context *>(p)->name.c_str() : "unavailable"; }
void apply(void *p, void *values, size_t bytes, Stats &stats)
{
    stats = {};
    const auto start = Clock::now();
    struct Wall {
        Clock::time_point start;
        Stats &stats;
        ~Wall() { stats.wall = seconds(start); }
    } wall{start, stats};
    @autoreleasepool {
        if (!p || !values) throw std::invalid_argument("producer transform null input");
        auto &c = *static_cast<Context *>(p);
        if (bytes != c.buffer.length) throw std::invalid_argument("producer transform extent");
        stats.scratch_bytes = bytes;
        const uint32_t branches = 1u << c.variables;
        stats.logical_xors = uint64_t(c.variables) * (branches / 2) * c.stride;
        auto phase = Clock::now();
        std::memcpy(c.buffer.contents, values, bytes);
        stats.input_bytes = bytes;
        stats.copy_in = seconds(phase);
        phase = Clock::now();
        id<MTLCommandBuffer> command = [c.queue commandBuffer];
        if (!command) throw std::runtime_error("Metal command allocation failed");
        auto encode = [&](id<MTLComputePipelineState> pipeline, uint32_t bit, MTLSize groups) {
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            if (!encoder) throw std::runtime_error("Metal encoder allocation failed");
            const Parameters parameters{branches, bit};
            [encoder setComputePipelineState:pipeline];
            [encoder setBuffer:c.buffer offset:0 atIndex:0];
            [encoder setBytes:&parameters length:sizeof(parameters) atIndex:1];
            [encoder dispatchThreadgroups:groups threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
            [encoder endEncoding];
            ++stats.encoded_dispatches;
            stats.dispatched_threads += groups.width * groups.height * 256;
        };
        uint32_t bit = 1;
        if (c.mode == Mode::tiled) {
            encode(c.tile, 0, MTLSizeMake((branches + 15) / 16, (c.stride + 15) / 16, 1));
            bit = std::min(branches, 16u);
        }
        const uint32_t threads = (branches / 2) * c.stride;
        for (; bit < branches; bit <<= 1)
            encode(c.stage, bit, MTLSizeMake((threads + 255) / 256, 1, 1));
        stats.encode = seconds(phase);
        phase = Clock::now();
        [command commit];
        stats.submitted_dispatches = stats.encoded_dispatches;
        [command waitUntilCompleted];
        stats.wait = seconds(phase);
        if (command.status != MTLCommandBufferStatusCompleted)
            throw failure(command.error.localizedDescription);
        stats.completed_dispatches = stats.submitted_dispatches;
        stats.device = command.GPUEndTime - command.GPUStartTime;
        phase = Clock::now();
        std::memcpy(values, c.buffer.contents, bytes);
        stats.output_bytes = bytes;
        stats.copy_out = seconds(phase);
    }
}
} // namespace producer_transform
