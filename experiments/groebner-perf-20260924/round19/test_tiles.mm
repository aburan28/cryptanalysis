// Device correctness only. No timings or complete-query performance claims.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>

struct Params { uint32_t equations, blocks, mask_lo, mask_hi; };
static uint64_t state = 2026092706;
static uint64_t random_word()
{
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}
static uint64_t direct(const uint64_t *coefficients, uint32_t assignment)
{
    uint64_t value = 0;
    uint32_t subset = assignment;
    do {
        value ^= coefficients[subset];
        if (!subset) break;
        subset = (subset - 1) & assignment;
    } while (true);
    return value;
}

int main(int argc, const char **argv)
{
    @autoreleasepool {
        try {
            if (argc != 2 && argc != 3) throw std::invalid_argument("usage: test-tiles shader.metal [threads]");
            const unsigned requested = argc == 3 ? unsigned(std::stoul(argv[2])) : 256;
            if (!requested || requested > 1024) throw std::invalid_argument("threads: 1..1024");
            uint32_t endian = 1;
            if (*reinterpret_cast<uint8_t *>(&endian) != 1) throw std::runtime_error("little-endian required");
            id<MTLDevice> device = MTLCreateSystemDefaultDevice();
            if (!device) throw std::runtime_error("Metal device unavailable");
            NSError *error = nil;
            NSString *source = [NSString stringWithContentsOfFile:@(argv[1]) encoding:NSUTF8StringEncoding error:&error];
            if (!source) throw std::runtime_error(error.description.UTF8String);
            id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
            if (!library) throw std::runtime_error(error.description.UTF8String);
            auto pipeline = [&](NSString *name) {
                id<MTLFunction> function = [library newFunctionWithName:name];
                if (!function) throw std::runtime_error("missing shader function");
                id<MTLComputePipelineState> result = [device newComputePipelineStateWithFunction:function error:&error];
                if (!result) throw std::runtime_error(error.description.UTF8String);
                return result;
            };
            auto transform = pipeline(@"zeta_tiles"), intersect = pipeline(@"tiled_intersect");
            if (requested > transform.maxTotalThreadsPerThreadgroup)
                throw std::invalid_argument("requested group exceeds pipeline capacity");
            if (transform.staticThreadgroupMemoryLength > device.maxThreadgroupMemoryLength)
                throw std::runtime_error("tile exceeds device shared memory");
            id<MTLCommandQueue> queue = [device newCommandQueue];
            if (!queue) throw std::runtime_error("queue unavailable");
            uint64_t checked_words = 0, checked_roots = 0;
            uint32_t cases = 0;
            for (auto shape : std::vector<std::pair<uint32_t,uint32_t>>{
                     {1,1}, {6,31}, {7,65}, {12,128}, {18,31}, {20,3}}) {
                const auto n = shape.first, e = shape.second, blocks = ((1u<<n)+63)/64;
                const size_t count = size_t(e)*blocks, bytes = count*sizeof(uint64_t);
                auto allocate = [&](size_t length) {
                    id<MTLBuffer> b = [device newBufferWithLength:length options:MTLResourceStorageModeShared];
                    if (!b) throw std::runtime_error("buffer allocation failed");
                    return b;
                };
                auto coefficients = allocate(bytes), values = allocate(bytes);
                auto roots = allocate(size_t(blocks)*8), params = allocate(sizeof(Params));
                const uint64_t mask = n<6 ? (uint64_t(1)<<(1u<<n))-1 : ~uint64_t(0);
                const Params p = {e, blocks, uint32_t(mask), uint32_t(mask>>32)};
                memcpy(params.contents, &p, sizeof(p));
                const uint32_t planted = uint32_t(random_word()) & ((1u<<n)-1);
                for (uint32_t pattern = 0; pattern < 4; ++pattern) {
                    std::vector<uint64_t> original(count);
                    for (auto &v : original) v = pattern == 0 ? 0 : pattern == 3 ? ~uint64_t(0) : random_word();
                    if (pattern == 2)
                        for (uint32_t row = 0; row < e; ++row) {
                            auto *data = original.data()+size_t(row)*blocks;
                            if ((direct(data, planted>>6)>>(planted&63))&1)
                                data[0] ^= uint64_t(1)<<(planted&63);
                        }
                    memcpy(coefficients.contents, original.data(), bytes);
                    memset(values.contents, 0x7f, bytes);
                    memset(roots.contents, 0x7f, size_t(blocks)*8);
                    auto command = [queue commandBuffer];
                    auto encoder = [command computeCommandEncoder];
                    if (!command || !encoder) throw std::runtime_error("command unavailable");
                    [encoder setBuffer:coefficients offset:0 atIndex:0];
                    [encoder setBuffer:values offset:0 atIndex:1];
                    [encoder setBuffer:roots offset:0 atIndex:2];
                    [encoder setBuffer:params offset:0 atIndex:3];
                    [encoder setComputePipelineState:transform];
                    const auto threads = NSUInteger(requested);
                    [encoder dispatchThreadgroups:MTLSizeMake(e*((blocks+4095)/4096),1,1)
                            threadsPerThreadgroup:MTLSizeMake(threads,1,1)];
                    [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
                    [encoder setComputePipelineState:intersect];
                    [encoder dispatchThreads:MTLSizeMake(blocks,1,1)
                            threadsPerThreadgroup:MTLSizeMake(std::min(NSUInteger(256),intersect.maxTotalThreadsPerThreadgroup),1,1)];
                    [encoder endEncoding];
                    [command commit];
                    [command waitUntilCompleted];
                    if (command.status != MTLCommandBufferStatusCompleted)
                        throw std::runtime_error(command.error ? command.error.description.UTF8String : "GPU command failed");
                    auto *actual = static_cast<const uint64_t *>(values.contents);
                    auto *actual_roots = static_cast<const uint64_t *>(roots.contents);
                    std::vector<uint64_t> expected_roots(blocks, mask);
                    for (uint32_t row = 0; row < e; ++row)
                        for (uint32_t block = 0; block < blocks; ++block) {
                            const auto *full = original.data()+size_t(row)*blocks;
                            const auto *tile = full+(block/4096)*4096;
                            if (actual[size_t(row)*blocks+block] != direct(tile,block%4096))
                                throw std::runtime_error("tile truth word differs from direct subset evaluation");
                            expected_roots[block] &= ~direct(full,block);
                            ++checked_words;
                        }
                    for (uint32_t block = 0; block < blocks; ++block) {
                        if (actual_roots[block] != expected_roots[block])
                            throw std::runtime_error("root word differs from direct subset evaluation");
                        ++checked_roots;
                    }
                    if (pattern == 2 && !((actual_roots[planted>>6]>>(planted&63))&1))
                        throw std::runtime_error("planted root lost");
                    ++cases;
                    std::cout << "checked n=" << n << " e=" << e << " pattern=" << pattern << '\n';
                }
            }
            std::cout << "PASS cases=" << cases << " truth_words=" << checked_words
                      << " root_words=" << checked_roots << " device=" << device.name.UTF8String
                      << " static_shared_bytes=" << transform.staticThreadgroupMemoryLength
                      << " threads=" << requested << '\n';
            return 0;
        } catch (const std::exception &error) {
            std::cerr << "FAIL " << error.what() << '\n';
            return 1;
        }
    }
}
