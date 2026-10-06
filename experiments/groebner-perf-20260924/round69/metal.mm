#include "api.h"
#include "build/kernel.inc"
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>

namespace multiplier_gpu
{
namespace
{
using Clock = std::chrono::steady_clock;
double elapsed(Clock::time_point start)
{
    return std::chrono::duration<double>(Clock::now() - start).count();
}
struct Timer {
    Stats &stats;
    Clock::time_point start = Clock::now();
    ~Timer() { stats.wall = elapsed(start); }
};
struct Context {
    Shape shape;
    std::mutex mutex;
    id<MTLDevice> device;
    id<MTLCommandQueue> queue;
    id<MTLComputePipelineState> record_pipeline, coefficient_pipeline;
    id<MTLBuffer> table, witnesses, indices, groups, first, materialized;
    std::string name;
    Context(uint32_t x, uint32_t y, uint32_t e, size_t capacity) : shape(x, y, e, capacity) {}
};
struct Parameters {
    uint32_t branches, records, materialize;
};
std::runtime_error failure(NSString *message)
{
    return std::runtime_error(message ? message.UTF8String
                                      : "independent multiplier Metal failure");
}
id<MTLBuffer> buffer(Context &c, size_t bytes)
{
    bytes = std::max<size_t>(bytes, 1);
    if (bytes > c.device.maxBufferLength) throw std::length_error("Metal buffer extent");
    id<MTLBuffer> value = [c.device
        newBufferWithLength:bytes
                    options:MTLResourceStorageModeShared | MTLResourceHazardTrackingModeTracked];
    if (!value) throw std::runtime_error("multiplier buffer allocation failed");
    return value;
}
} // namespace

void *create(uint32_t x, uint32_t y, uint32_t e, size_t capacity)
{
    @autoreleasepool {
        auto c = std::make_unique<Context>(x, y, e, capacity);
        c->device = MTLCreateSystemDefaultDevice();
        if (!c->device) throw Unavailable("independent multiplier Metal unavailable");
        c->name = std::string(c->device.name.UTF8String) +
                  "; registry=" + std::to_string(c->device.registryID);
        c->queue = [c->device newCommandQueue];
        if (!c->queue) throw std::runtime_error("multiplier command queue allocation failed");
        const auto &s = c->shape;
        c->table = buffer(*c, s.coefficient_bytes);
        c->witnesses = buffer(*c, capacity * (s.y + 1) * s.limbs * 8);
        c->indices = buffer(*c, capacity * 4);
        c->first = buffer(*c, capacity * 4);
        c->groups = buffer(*c, s.layout.size() * sizeof(Group));
        std::memcpy(c->groups.contents, s.layout.data(), s.layout.size() * sizeof(Group));
        MTLCompileOptions *options = [MTLCompileOptions new];
        options.languageVersion = MTLLanguageVersion2_4;
        NSError *error = nil;
        id<MTLLibrary> library = [c->device newLibraryWithSource:@(multiplier_identity_kernel)
                                                         options:options
                                                           error:&error];
        if (!library) throw failure(error.localizedDescription);
        MTLFunctionConstantValues *constants = [MTLFunctionConstantValues new];
        uint32_t values[] = {s.y, s.limbs, s.word_bits, s.groups};
        for (NSUInteger i = 0; i < 4; ++i)
            [constants setConstantValue:values + i type:MTLDataTypeUInt atIndex:i];
        auto pipeline = [&](NSString *name) {
            id<MTLFunction> function = [library newFunctionWithName:name
                                                     constantValues:constants
                                                              error:&error];
            if (!function) throw failure(error.localizedDescription);
            id<MTLComputePipelineState> result =
                [c->device newComputePipelineStateWithFunction:function error:&error];
            if (!result || !result.maxTotalThreadsPerThreadgroup)
                throw failure(error.localizedDescription);
            return result;
        };
        c->record_pipeline = pipeline(@"check_records");
        c->coefficient_pipeline = pipeline(@"check_coefficients");
        return c.release();
    }
}

void destroy(void *p) { delete static_cast<Context *>(p); }
const char *device(void *p) { return p ? static_cast<Context *>(p)->name.c_str() : "cpu"; }

void check(void *p, uint32_t mode, const Input &in, const Output &out, Stats &stats)
{
    stats = {};
    Timer timer{stats};
    @autoreleasepool {
        if (!p || mode < 1 || mode > 2) throw std::invalid_argument("multiplier context/mode");
        auto &c = *static_cast<Context *>(p);
        std::lock_guard<std::mutex> lock(c.mutex);
        const auto &s = c.shape;
        auto phase = Clock::now();
        try {
            validate(s, in, out);
        } catch (...) {
            stats.validation = elapsed(phase);
            throw;
        }
        stats.validation = elapsed(phase);
        if (!in.records) return;
        if (out.coefficients && (!c.materialized || c.materialized.length < out.coefficient_bytes))
            c.materialized = buffer(c, out.coefficient_bytes);
        stats.coefficient_table_bytes = s.coefficient_bytes;
        stats.witness_bytes = in.witness_words * 8;
        stats.index_bytes = in.records * 4;
        stats.result_bytes = out.records * 4;
        stats.materialized_bytes = out.coefficient_bytes;
        stats.workspace_bytes = c.table.length + c.witnesses.length + c.indices.length +
                                c.first.length + c.groups.length + c.materialized.length;
        phase = Clock::now();
        std::memcpy(c.table.contents, in.coefficients, s.coefficient_bytes);
        std::memcpy(c.witnesses.contents, in.witnesses, stats.witness_bytes);
        std::memcpy(c.indices.contents, in.branches, stats.index_bytes);
        std::fill_n(static_cast<uint32_t *>(c.first.contents), in.records, valid_identity);
        stats.input_bytes = s.coefficient_bytes + stats.witness_bytes + stats.index_bytes;
        stats.initialized_bytes = stats.result_bytes;
        stats.copy_in = elapsed(phase);
        phase = Clock::now();
        id<MTLCommandBuffer> command = [c.queue commandBuffer];
        if (!command) throw std::runtime_error("multiplier command allocation failed");
        id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        if (!encoder) throw std::runtime_error("multiplier encoder allocation failed");
        id<MTLComputePipelineState> pipeline =
            mode == 1 ? c.record_pipeline : c.coefficient_pipeline;
        [encoder setComputePipelineState:pipeline];
        [encoder setBuffer:c.table offset:0 atIndex:0];
        [encoder setBuffer:c.witnesses offset:0 atIndex:1];
        [encoder setBuffer:c.indices offset:0 atIndex:2];
        [encoder setBuffer:c.groups offset:0 atIndex:3];
        [encoder setBuffer:c.first offset:0 atIndex:4];
        // With materialize=0 no shader accesses this argument.
        [encoder setBuffer:out.coefficients ? c.materialized : c.first offset:0 atIndex:5];
        const Parameters params{s.branches, uint32_t(in.records), out.coefficients ? 1u : 0u};
        [encoder setBytes:&params length:sizeof(params) atIndex:6];
        const size_t logical_threads = in.records * (mode == 1 ? 1 : s.groups);
        const NSUInteger group = std::min<NSUInteger>(256, pipeline.maxTotalThreadsPerThreadgroup);
        stats.dispatched_threads = (logical_threads + group - 1) / group * group;
        [encoder dispatchThreadgroups:MTLSizeMake(stats.dispatched_threads / group, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(group, 1, 1)];
        [encoder endEncoding];
        stats.encode = elapsed(phase);
        phase = Clock::now();
        [command commit];
        stats.submitted_dispatches = 1;
        [command waitUntilCompleted];
        stats.wait = elapsed(phase);
        if (command.status != MTLCommandBufferStatusCompleted)
            throw failure(command.error.localizedDescription);
        stats.completed_dispatches = 1;
        stats.records = in.records;
        stats.coefficient_checks = in.records * s.groups;
        stats.device = command.GPUEndTime - command.GPUStartTime;
        phase = Clock::now();
        std::memcpy(out.first_bad, c.first.contents, stats.result_bytes);
        if (out.coefficients)
            std::memcpy(out.coefficients, c.materialized.contents, out.coefficient_bytes);
        stats.output_bytes = stats.result_bytes + out.coefficient_bytes;
        stats.copy_out = elapsed(phase);
        finish_stats(s, in, out, stats);
    }
}
} // namespace multiplier_gpu
