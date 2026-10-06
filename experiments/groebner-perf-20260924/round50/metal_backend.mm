#include "../round49/metal_backend.h"
#include "build/kernel.inc"
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>

struct Parameters {
  uint32_t branches, features, equations, active_branches, variables,
      projection_enabled;
};
struct CompactMetalBranches {
  id<MTLDevice> device;
  id<MTLCommandQueue> queue;
  id<MTLComputePipelineState> pipeline;
  id<MTLBuffer> input, output, parameters, branch_ids, projection;
  uint32_t branches, compact_count = 0, active_branches = 0;
  std::string name;
};
static std::runtime_error failure(NSString *message) {
  return std::runtime_error(message ? message.UTF8String
                                    : "Metal operation failed");
}
void *compact_metal_create(uint32_t branches, uint32_t features,
                           uint32_t equations, uint32_t variables) {
  @autoreleasepool {
    if (!branches || (branches & (branches - 1)) || branches > (1u << 20))
      throw std::invalid_argument(
          "Metal requires a power-of-two branch count in 1..2^20");
    if (!features || features > 55 || !equations || equations > 32)
      throw std::invalid_argument(
          "Metal requires 1..55 features and 1..32 equations");
    if (!variables || variables > 10 ||
        features != variables * (variables + 1) / 2)
      throw std::invalid_argument(
          "Metal projection requires triangular features and 1..10 variables");
    if (size_t(branches) * (features + 1) * 4 > (64u << 20))
      throw std::length_error("Metal input table exceeds 64 MiB");
    const uint16_t marker = 1;
    if (*reinterpret_cast<const uint8_t *>(&marker) != 1)
      throw std::runtime_error(
          "Metal uint32-pair output requires little-endian host");
    auto c = std::make_unique<CompactMetalBranches>();
    c->branches = branches;
    const uint32_t bits = __builtin_ctz(branches);
    const uint32_t block = 1u << (bits / 2);
    if (!(bits % 2))
      c->compact_count = block * (block + 1) / 2;
    c->device = MTLCreateSystemDefaultDevice();
    if (!c->device)
      throw std::runtime_error("requested Metal device unavailable");
    c->name = std::string(c->device.name.UTF8String) +
              "; registry=" + std::to_string(c->device.registryID);
    c->queue = [c->device newCommandQueue];
    NSError *error = nil;
    MTLCompileOptions *options = [MTLCompileOptions new];
    options.languageVersion = MTLLanguageVersion2_4;
    id<MTLLibrary> library = [c->device newLibraryWithSource:@(quadratic_kernel)
                                                     options:options
                                                       error:&error];
    if (!library)
      throw failure(error.localizedDescription);
    id<MTLFunction> function =
        [library newFunctionWithName:@"quadratic_branches"];
    if (!function)
      throw std::runtime_error("quadratic_branches kernel missing");
    c->pipeline = [c->device newComputePipelineStateWithFunction:function
                                                           error:&error];
    if (!c->pipeline)
      throw failure(error.localizedDescription);
    if (c->pipeline.threadExecutionWidth != 32 ||
        c->pipeline.maxTotalThreadsPerThreadgroup < 128)
      throw std::runtime_error(
          "Metal kernel requires SIMD width 32 and 128 threads per group");
    c->input =
        [c->device newBufferWithLength:size_t(branches) * (features + 1) * 4
                               options:MTLResourceStorageModeShared];
    c->output = [c->device newBufferWithLength:size_t(branches) * 34 * 8
                                       options:MTLResourceStorageModeShared];
    c->projection =
        [c->device newBufferWithLength:size_t(branches) * (variables + 2) * 8
                               options:MTLResourceStorageModeShared];
    c->parameters =
        [c->device newBufferWithLength:sizeof(Parameters)
                               options:MTLResourceStorageModeShared];
    c->branch_ids = [c->device
        newBufferWithLength:size_t(c->compact_count ? c->compact_count : 1) * 4
                    options:MTLResourceStorageModeShared];
    if (!c->queue || !c->input || !c->output || !c->parameters ||
        !c->branch_ids || !c->projection)
      throw std::runtime_error("Metal queue/buffer allocation failed");
    // Immutable layout only: no specialized coefficients or answers.
    auto *ids = static_cast<uint32_t *>(c->branch_ids.contents);
    if (c->compact_count) {
      uint32_t index = 0;
      for (uint32_t high = 0; high < block; ++high)
        for (uint32_t low = high; low < block; ++low)
          ids[index++] = low | (high << (bits / 2));
      if (index != c->compact_count)
        throw std::logic_error("compact map extent");
    } else
      ids[0] = 0; // Bound placeholder; the odd-dimension path never reads it.
    *static_cast<Parameters *>(c->parameters.contents) = {
        branches, features, equations, branches, variables, 0};
    return c.release();
  }
}
void compact_metal_destroy(void *context) {
  delete static_cast<CompactMetalBranches *>(context);
}
const char *compact_metal_device(void *context) {
  return static_cast<CompactMetalBranches *>(context)->name.c_str();
}
uint64_t compact_metal_bytes(void *context) {
  auto &c = *static_cast<CompactMetalBranches *>(context);
  return c.input.length + c.output.length + c.parameters.length +
         c.branch_ids.length + c.projection.length;
}
const uint64_t *compact_metal_solve(void *context, const void *input,
                                    size_t bytes, bool symmetric,
                                    bool projection, double &device_seconds) {
  @autoreleasepool {
    auto &c = *static_cast<CompactMetalBranches *>(context);
    if (!input || bytes != c.input.length)
      throw std::invalid_argument("Metal input extent");
    if (symmetric && !c.compact_count)
      throw std::invalid_argument(
          "compact dispatch requires an even fixed dimension");
    c.active_branches = symmetric ? c.compact_count : c.branches;
    static_cast<Parameters *>(c.parameters.contents)->active_branches =
        c.active_branches;
    static_cast<Parameters *>(c.parameters.contents)->projection_enabled =
        projection;
    std::memcpy(c.input.contents, input, bytes);
    id<MTLCommandBuffer> command = [c.queue commandBuffer];
    id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
    if (!command || !encoder)
      throw std::runtime_error("Metal command allocation failed");
    [encoder setComputePipelineState:c.pipeline];
    [encoder setBuffer:c.input offset:0 atIndex:0];
    [encoder setBuffer:c.output offset:0 atIndex:1];
    [encoder setBuffer:c.parameters offset:0 atIndex:2];
    [encoder setBuffer:c.branch_ids offset:0 atIndex:3];
    [encoder setBuffer:c.projection offset:0 atIndex:4];
    [encoder dispatchThreadgroups:MTLSizeMake((c.active_branches + 3) / 4, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
    [encoder endEncoding];
    [command commit];
    [command waitUntilCompleted];
    if (command.status != MTLCommandBufferStatusCompleted)
      throw failure(command.error.localizedDescription);
    device_seconds = command.GPUEndTime - command.GPUStartTime;
    return static_cast<const uint64_t *>(c.output.contents);
  }
}
uint64_t compact_metal_dispatched_branches(void *context) {
  return static_cast<CompactMetalBranches *>(context)->active_branches;
}

const uint64_t *compact_metal_projection(void *context) {
  return static_cast<const uint64_t *>(
      static_cast<CompactMetalBranches *>(context)->projection.contents);
}
uint64_t compact_metal_projection_bytes(void *context) {
  return static_cast<CompactMetalBranches *>(context)->projection.length;
}
