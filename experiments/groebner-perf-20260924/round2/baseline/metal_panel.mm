// clang++ -O3 -std=c++17 -fobjc-arc -framework Foundation -framework Metal
//   metal_panel.mm -o build/metal-panel
// Kernel experiment only: no symbolic preprocessing, pivots, or F5 scheduling.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>

using Clock = std::chrono::steady_clock;
static double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

int main(int argc, char** argv) {
  @autoreleasepool {
    if (argc < 2 || argc > 3) { std::cerr << "usage: metal-panel path/to/panel.metal [vector]\n"; return 2; }
    bool vector = argc == 3 && std::string(argv[2]) == "vector";
    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    if (!device) { std::cerr << "Metal unavailable\n"; return 3; }
    NSError* error = nil;
    NSString* source = [NSString stringWithContentsOfFile:@(argv[1])
                                                encoding:NSUTF8StringEncoding error:&error];
    if (!source) { std::cerr << error.localizedDescription.UTF8String << '\n'; return 4; }
    id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
    if (!library) { std::cerr << error.localizedDescription.UTF8String << '\n'; return 5; }
    id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:
                                          [library newFunctionWithName:vector ? @"reduce_panel_vec" : @"reduce_panel"] error:&error];
    if (!pipeline) { std::cerr << error.localizedDescription.UTF8String << '\n'; return 6; }
    id<MTLCommandQueue> queue = [device newCommandQueue];
    NSMutableArray* reports = [NSMutableArray array];
    std::mt19937 rng(20260924);
    for (auto shape: std::vector<std::pair<uint32_t,uint32_t>>{
            {1024, 140}, {8192, 512}, {32768, 1024}, {65536, 1024}}) {
        uint32_t rows = shape.first, words = shape.second, count = rows * words;
        size_t bytes = size_t(count) * sizeof(uint32_t);
        id<MTLBuffer> input = [device newBufferWithLength:bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer> output = [device newBufferWithLength:bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer> table = [device newBufferWithLength:size_t(64) * words * sizeof(uint32_t)
                                               options:MTLResourceStorageModeShared];
        if (!input || !output || !table) return 7;
        auto* src = static_cast<uint32_t*>(input.contents);
        auto* tab = static_cast<uint32_t*>(table.contents);
        auto* dst = static_cast<uint32_t*>(output.contents);
        for (uint32_t i=0; i<count; ++i) src[i] = rng();
        std::vector<uint32_t> pivots(size_t(6) * words);
        for (auto& x: pivots) x = rng();
        for (uint32_t bit=0; bit<6; ++bit)
            pivots[size_t(bit) * words] = (pivots[size_t(bit) * words] & ~63u) | (1u << bit);
        std::fill(tab, tab + words, 0);
        for (uint32_t mask=1; mask<64; ++mask) {
            uint32_t bit = __builtin_ctz(mask), previous = mask & (mask-1);
            for (uint32_t word=0; word<words; ++word)
                tab[size_t(mask)*words+word] = tab[size_t(previous)*words+word] ^ pivots[size_t(bit)*words+word];
        }
        std::vector<uint32_t> reference(count);
        std::vector<double> cpu_ms, gpu_ms, dispatch_ms;
        NSMutableArray* samples = [NSMutableArray array];
        for (int repeat=0; repeat<16; ++repeat) {
            double cpu = 0, gpu = 0, wall = 0;
            auto run_cpu = [&] {
                auto started = Clock::now();
                for (uint32_t row=0; row<rows; ++row) {
                    size_t offset = size_t(row)*words;
                    const uint32_t* lookup = tab + size_t(src[offset] & 63u)*words;
                    for (uint32_t word=0; word<words; ++word)
                        reference[offset+word] = src[offset+word] ^ lookup[word];
                }
                cpu = std::chrono::duration<double,std::milli>(Clock::now()-started).count();
            };
            auto run_gpu = [&] {
                auto started = Clock::now();
                id<MTLCommandBuffer> command = [queue commandBuffer];
                id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
                [encoder setComputePipelineState:pipeline];
                [encoder setBuffer:input offset:0 atIndex:0];
                [encoder setBuffer:table offset:0 atIndex:1];
                [encoder setBuffer:output offset:0 atIndex:2];
                [encoder setBytes:&words length:sizeof(words) atIndex:3];
                [encoder setBytes:&count length:sizeof(count) atIndex:4];
                NSUInteger group = std::min(NSUInteger(256), pipeline.maxTotalThreadsPerThreadgroup);
                if (vector) {
                    [encoder dispatchThreads:MTLSizeMake(words/4,rows,1)
                       threadsPerThreadgroup:MTLSizeMake(std::min(NSUInteger(words/4),group),1,1)];
                } else {
                    [encoder dispatchThreads:MTLSizeMake(count,1,1)
                       threadsPerThreadgroup:MTLSizeMake(group,1,1)];
                }
                [encoder endEncoding];
                [command commit];
                [command waitUntilCompleted];
                if (command.status != MTLCommandBufferStatusCompleted) {
                    std::cerr << command.error.localizedDescription.UTF8String << '\n'; exit(8);
                }
                wall = std::chrono::duration<double,std::milli>(Clock::now()-started).count();
                gpu = (command.GPUEndTime - command.GPUStartTime) * 1000;
            };
            if (repeat % 2) { run_gpu(); run_cpu(); } else { run_cpu(); run_gpu(); }
            if (!std::equal(reference.begin(), reference.end(), dst)) {
                std::cerr << "GPU differs from scalar CPU\n"; return 9;
            }
            for (uint32_t row=0; row<rows; ++row)
                if (dst[size_t(row)*words] & 63u) return 10;
            if (repeat) {
                cpu_ms.push_back(cpu); gpu_ms.push_back(gpu); dispatch_ms.push_back(wall);
                [samples addObject:@{@"cpu_ms":@(cpu), @"gpu_ms":@(gpu), @"dispatch_wall_ms":@(wall)}];
            }
        }
        [reports addObject:@{@"rows":@(rows), @"columns":@(words*32), @"bytes":@(bytes),
                             @"block_width":@6, @"repeats":@15, @"verified_every_word":@YES,
                             @"cpu_median_ms":@(median(cpu_ms)), @"gpu_median_ms":@(median(gpu_ms)),
                             @"dispatch_median_ms":@(median(dispatch_ms)),
                             @"speedup_including_dispatch":@(median(cpu_ms)/median(dispatch_ms)),
                             @"samples":samples}];
    }
    NSDictionary* result = @{@"device":device.name, @"seed":@20260924, @"cells":reports,
                            @"kernel":vector ? @"uint4_2d" : @"scalar_1d",
                            @"scope":@"One exact GF(2) Four Russians panel update; not a complete F4 or F5 solver",
                            @"memory":@"Preallocated shared buffers; compilation, table construction and allocation excluded",
                            @"cpu_baseline":@"Single CPU thread, clang -O3 auto-vectorized"};
    NSData* json = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&error];
    if (!json) return 11;
    std::cout.write(static_cast<const char*>(json.bytes), json.length);
    std::cout << '\n';
  }
}
