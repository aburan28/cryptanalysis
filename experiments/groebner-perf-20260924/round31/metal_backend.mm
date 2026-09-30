#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "metal_backend.h"
#include "build/kernel.inc"
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>

struct Parameters { uint32_t branches, features, equations; };
struct MetalBranches {
    id<MTLDevice> device;
    id<MTLCommandQueue> queue;
    id<MTLComputePipelineState> pipeline;
    id<MTLBuffer> input, output, parameters;
    uint32_t branches;
    std::string name;
};
static std::runtime_error failure(NSString* message) {
    return std::runtime_error(message ? message.UTF8String : "Metal operation failed");
}
void* quadratic_metal_create(uint32_t branches, uint32_t features, uint32_t equations) {
    @autoreleasepool {
        if (!branches || !features || features>31 || !equations || equations>32)
            throw std::invalid_argument("Metal requires 1..31 features and 1..32 equations");
        auto c=std::make_unique<MetalBranches>();
        c->branches=branches;
        c->device=MTLCreateSystemDefaultDevice();
        if (!c->device) throw std::runtime_error("requested Metal device unavailable");
        c->name=std::string(c->device.name.UTF8String)+"; registry="+std::to_string(c->device.registryID);
        c->queue=[c->device newCommandQueue];
        NSError* error=nil;
        MTLCompileOptions* options=[MTLCompileOptions new];
        options.languageVersion=MTLLanguageVersion2_4;
        id<MTLLibrary> library=[c->device newLibraryWithSource:@(quadratic_kernel) options:options error:&error];
        if (!library) throw failure(error.localizedDescription);
        id<MTLFunction> function=[library newFunctionWithName:@"quadratic_branches"];
        if (!function) throw std::runtime_error("quadratic_branches kernel missing");
        c->pipeline=[c->device newComputePipelineStateWithFunction:function error:&error];
        if (!c->pipeline) throw failure(error.localizedDescription);
        if (c->pipeline.threadExecutionWidth!=32 || c->pipeline.maxTotalThreadsPerThreadgroup<128)
            throw std::runtime_error("Metal kernel requires SIMD width 32 and 128 threads per group");
        c->input=[c->device newBufferWithLength:size_t(branches)*(features+1)*16 options:MTLResourceStorageModeShared];
        c->output=[c->device newBufferWithLength:size_t(branches)*33*4 options:MTLResourceStorageModeShared];
        c->parameters=[c->device newBufferWithLength:sizeof(Parameters) options:MTLResourceStorageModeShared];
        if (!c->queue || !c->input || !c->output || !c->parameters)
            throw std::runtime_error("Metal queue/buffer allocation failed");
        *static_cast<Parameters*>(c->parameters.contents)={branches,features,equations};
        return c.release();
    }
}
void quadratic_metal_destroy(void* context) { delete static_cast<MetalBranches*>(context); }
const char* quadratic_metal_device(void* context) {
    return static_cast<MetalBranches*>(context)->name.c_str();
}
uint64_t quadratic_metal_bytes(void* context) {
    auto& c=*static_cast<MetalBranches*>(context);
    return c.input.length+c.output.length+c.parameters.length;
}
const uint32_t* quadratic_metal_solve(void* context,const void* input,size_t bytes,double& device_seconds) {
    @autoreleasepool {
        auto& c=*static_cast<MetalBranches*>(context);
        if (!input || bytes!=c.input.length) throw std::invalid_argument("Metal input extent");
        std::memcpy(c.input.contents,input,bytes);
        id<MTLCommandBuffer> command=[c.queue commandBuffer];
        id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
        if (!command || !encoder) throw std::runtime_error("Metal command allocation failed");
        [encoder setComputePipelineState:c.pipeline];
        [encoder setBuffer:c.input offset:0 atIndex:0];
        [encoder setBuffer:c.output offset:0 atIndex:1];
        [encoder setBuffer:c.parameters offset:0 atIndex:2];
        [encoder dispatchThreadgroups:MTLSizeMake((c.branches+3)/4,1,1)
               threadsPerThreadgroup:MTLSizeMake(128,1,1)];
        [encoder endEncoding];
        [command commit];
        [command waitUntilCompleted];
        if (command.status!=MTLCommandBufferStatusCompleted) throw failure(command.error.localizedDescription);
        device_seconds=command.GPUEndTime-command.GPUStartTime;
        return static_cast<const uint32_t*>(c.output.contents);
    }
}
