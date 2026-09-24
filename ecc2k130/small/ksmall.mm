// ksmall - native Metal driver for ksmall.metal.  run.py prepares a work
// directory (shader.metal with the curve prelude, config.json) and calls
//
//   ksmall selftest DIR   field/step/start-point vectors -> selftest-out.bin
//   ksmall run DIR        walk until the requested number of collisions
//
// In run mode the host keeps every distinguished point in a table keyed by
// the smallest rotation of its normal-basis x, which names its class
// {+-sigma^i R}.  Two reports from different seeds with one key are a
// collision; both records go to collisions.jsonl for run.py to solve.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

struct Args { uint32_t lanes, steps, dpCap, seedStride, maxTrail, pad[3]; };
struct DpRec { uint64_t seed; uint32_t steps, lane, counts[8], x[4], y[4], nb[4]; };
static_assert(sizeof(Args) == 32 && sizeof(DpRec) == 96, "host/shader layout differs");

static volatile sig_atomic_t stopRequested = 0;
static void onSignal(int) { stopRequested = 1; }

static void need(bool ok, const std::string &text) { if (!ok) throw std::runtime_error(text); }
static NSString *path(NSString *dir, NSString *name) { return [dir stringByAppendingPathComponent:name]; }
static NSData *readFile(NSString *dir, NSString *name)
{
    NSData *d = [NSData dataWithContentsOfFile:path(dir, name)];
    need(d != nil, std::string("missing ") + name.UTF8String);
    return d;
}
static id<MTLComputePipelineState> pipeline(id<MTLDevice> dev, id<MTLLibrary> lib, NSString *name)
{
    NSError *err = nil;
    id<MTLFunction> f = [lib newFunctionWithName:name];
    need(f != nil, "missing kernel");
    id<MTLComputePipelineState> p = [dev newComputePipelineStateWithFunction:f error:&err];
    need(p != nil, err ? err.localizedDescription.UTF8String : "pipeline");
    return p;
}
static double finish(id<MTLCommandBuffer> cb)
{
    [cb commit];
    [cb waitUntilCompleted];
    need(cb.status == MTLCommandBufferStatusCompleted,
         cb.error ? cb.error.localizedDescription.UTF8String : "GPU command failed");
    return cb.GPUEndTime - cb.GPUStartTime;
}
static id<MTLBuffer> buffer(id<MTLDevice> dev, size_t bytes)
{
    id<MTLBuffer> b = [dev newBufferWithLength:std::max<size_t>(bytes, 16) options:MTLResourceStorageModeShared];
    need(b != nil, "buffer allocation failed");
    memset(b.contents, 0, b.length);
    return b;
}

typedef unsigned __int128 u128;
struct KeyHash { size_t operator()(u128 k) const { return size_t(uint64_t(k) ^ uint64_t(k >> 64) * 0x9E3779B97F4A7C15ull); } };

static u128 nbValue(const DpRec &r)
{
    return u128(r.nb[0]) | (u128(r.nb[1]) << 32) | (u128(r.nb[2]) << 64) | (u128(r.nb[3]) << 96);
}
static u128 classKey(const DpRec &r, int m)
{
    u128 mask = (m == 128) ? ~u128(0) : ((u128(1) << m) - 1);
    u128 v = nbValue(r), best = v;
    for (int s = 1; s < m; ++s) {
        v = ((v << 1) | (v >> (m - 1))) & mask;
        if (v < best) best = v;
    }
    return best;
}
// Two seeds whose start points coincide walk one trail: same point, same
// length, same j counts.  That is not a collision, and it cannot be solved.
static bool sameTrail(const DpRec &a, const DpRec &b)
{
    return a.steps == b.steps && !memcmp(a.counts, b.counts, sizeof a.counts) && !memcmp(a.x, b.x, sizeof a.x) &&
           !memcmp(a.y, b.y, sizeof a.y);
}
static std::string hexWords(const uint32_t *w, int n)
{
    std::string s = "0x";
    char buf[16];
    bool lead = true;
    for (int i = n - 1; i >= 0; --i) {
        snprintf(buf, sizeof buf, lead ? "%x" : "%08x", w[i]);
        if (lead && w[i] == 0 && i > 0) continue;
        s += buf;
        lead = false;
    }
    return s;
}
static std::string recJson(const DpRec &r)
{
    std::string s = "{\"seed\":" + std::to_string(r.seed) + ",\"steps\":" + std::to_string(r.steps) +
                    ",\"lane\":" + std::to_string(r.lane) + ",\"counts\":[";
    for (int j = 0; j < 8; ++j) s += std::to_string(r.counts[j]) + (j < 7 ? "," : "]");
    s += ",\"x\":\"" + hexWords(r.x, 4) + "\",\"y\":\"" + hexWords(r.y, 4) + "\",\"nb\":\"" + hexWords(r.nb, 4) + "\"}";
    return s;
}

static id<MTLLibrary> compile(id<MTLDevice> dev, NSString *dir)
{
    NSString *src = [[NSString alloc] initWithData:readFile(dir, @"shader.metal") encoding:NSUTF8StringEncoding];
    MTLCompileOptions *opt = [MTLCompileOptions new];
    opt.mathMode = MTLMathModeSafe;
    NSError *err = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opt error:&err];
    need(lib != nil, err ? err.localizedDescription.UTF8String : "compile failed");
    return lib;
}

static int selftest(id<MTLDevice> dev, NSString *dir, NSDictionary *cfg)
{
    id<MTLLibrary> lib = compile(dev, dir);
    id<MTLComputePipelineState> p = pipeline(dev, lib, @"selftest");
    uint32_t cases = [cfg[@"cases"] unsignedIntValue], nw = [cfg[@"NW"] unsignedIntValue];
    NSData *in = readFile(dir, @"selftest-in.bin"), *seeds = readFile(dir, @"selftest-seeds.bin");
    id<MTLBuffer> bin = [dev newBufferWithBytes:in.bytes length:in.length options:MTLResourceStorageModeShared];
    id<MTLBuffer> bseed = [dev newBufferWithBytes:seeds.bytes length:seeds.length options:MTLResourceStorageModeShared];
    size_t outBytes = (size_t(cases) * 7 * nw + size_t(cases) * 3) * 4;
    id<MTLBuffer> bout = buffer(dev, outBytes);
    id<MTLCommandBuffer> cb = [[dev newCommandQueue] commandBuffer];
    id<MTLComputeCommandEncoder> e = [cb computeCommandEncoder];
    [e setComputePipelineState:p];
    [e setBuffer:bin offset:0 atIndex:0];
    [e setBuffer:bout offset:0 atIndex:1];
    [e setBuffer:bseed offset:0 atIndex:2];
    [e setBytes:&cases length:4 atIndex:3];
    [e dispatchThreads:MTLSizeMake(cases, 1, 1) threadsPerThreadgroup:MTLSizeMake(std::min<uint32_t>(cases, 64), 1, 1)];
    [e endEncoding];
    finish(cb);
    need([[NSData dataWithBytes:bout.contents length:outBytes] writeToFile:path(dir, @"selftest-out.bin") atomically:YES],
         "cannot write selftest-out.bin");
    printf("{\"device\":\"%s\",\"cases\":%u}\n", dev.name.UTF8String, cases);
    return 0;
}

static int run(id<MTLDevice> dev, NSString *dir, NSDictionary *cfg)
{
    const uint32_t threads = [cfg[@"threads"] unsignedIntValue], batch = [cfg[@"batch"] unsignedIntValue];
    const uint32_t nw = [cfg[@"NW"] unsignedIntValue], m = [cfg[@"M"] unsignedIntValue];
    const uint32_t steps = [cfg[@"steps"] unsignedIntValue], dpCap = [cfg[@"dpCap"] unsignedIntValue];
    const uint32_t maxTrail = [cfg[@"maxTrail"] unsignedIntValue], wantCollisions = [cfg[@"collisions"] unsignedIntValue];
    const uint64_t seedBase = [cfg[@"seedBase"] unsignedLongLongValue];
    const double maxSeconds = [cfg[@"maxSeconds"] doubleValue];
    const uint32_t progressEvery = std::max(1u, [cfg[@"progressEvery"] unsignedIntValue]);
    const uint32_t lanes = threads * batch;
    need(m <= 127 && nw * 32 >= m, "degree out of range");

    id<MTLLibrary> lib = compile(dev, dir);
    id<MTLComputePipelineState> p = pipeline(dev, lib, @"walk");
    id<MTLCommandQueue> q = [dev newCommandQueue];

    id<MTLBuffer> X = buffer(dev, size_t(lanes) * nw * 4), Y = buffer(dev, size_t(lanes) * nw * 4);
    id<MTLBuffer> SX = buffer(dev, size_t(lanes) * nw * 4), SY = buffer(dev, size_t(lanes) * nw * 4);
    id<MTLBuffer> seeds = buffer(dev, size_t(lanes) * 8), trail = buffer(dev, size_t(lanes) * 4);
    id<MTLBuffer> counts = buffer(dev, size_t(lanes) * 8 * 4), dps = buffer(dev, size_t(dpCap) * sizeof(DpRec));
    id<MTLBuffer> dpCount = buffer(dev, 4), work = buffer(dev, size_t(threads) * 3 * 8);
    for (uint32_t i = 0; i < lanes; ++i) {
        ((uint64_t *)seeds.contents)[i] = seedBase + i;
        ((uint32_t *)trail.contents)[i] = 0xffffffffu;
    }
    Args args = {lanes, steps, dpCap, lanes, maxTrail, {0, 0, 0}};

    NSUInteger tg = std::min<NSUInteger>(p.maxTotalThreadsPerThreadgroup, [cfg[@"threadgroup"] unsignedIntValue] ?: 64);
    fprintf(stderr, "ksmall: %s, M=%u, %u threads x %u lanes, threadgroup %lu (max %lu, simd %lu)\n",
            dev.name.UTF8String, m, threads, batch, (unsigned long)tg,
            (unsigned long)p.maxTotalThreadsPerThreadgroup, (unsigned long)p.threadExecutionWidth);

    FILE *collFile = fopen(path(dir, @"collisions.jsonl").UTF8String, "a");
    need(collFile != nullptr, "cannot open collisions.jsonl");
    FILE *dpFile = [cfg[@"keepDps"] boolValue] ? fopen(path(dir, @"dps.bin").UTF8String, "ab") : nullptr;

    std::unordered_map<u128, DpRec, KeyHash> table;
    table.reserve(1u << 20);
    uint64_t totalDps = 0, dropped = 0, collisions = 0, sameSeed = 0, sameStart = 0;
    double gpuSeconds = 0;
    auto t0 = std::chrono::steady_clock::now();
    uint64_t launch = 0;
    std::vector<std::string> found;

    while (!stopRequested) {
        *(uint32_t *)dpCount.contents = 0;
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> e = [cb computeCommandEncoder];
        [e setComputePipelineState:p];
        [e setBytes:&args length:sizeof args atIndex:0];
        id<MTLBuffer> bufs[] = {X, Y, SX, SY, seeds, trail, counts, dps, dpCount, work};
        for (int i = 0; i < 10; ++i) [e setBuffer:bufs[i] offset:0 atIndex:i + 1];
        [e dispatchThreads:MTLSizeMake(threads, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [e endEncoding];
        gpuSeconds += finish(cb);
        ++launch;

        uint32_t n = *(uint32_t *)dpCount.contents;
        if (n > dpCap) { dropped += n - dpCap; n = dpCap; }
        const DpRec *recs = (const DpRec *)dps.contents;
        if (dpFile) fwrite(recs, sizeof(DpRec), n, dpFile);
        for (uint32_t i = 0; i < n; ++i) {
            u128 key = classKey(recs[i], int(m));
            auto it = table.find(key);
            if (it == table.end()) { table.emplace(key, recs[i]); continue; }
            if (it->second.seed == recs[i].seed) { ++sameSeed; continue; }
            if (sameTrail(it->second, recs[i])) { ++sameStart; continue; }
            ++collisions;
            std::string line = "{\"a\":" + recJson(it->second) + ",\"b\":" + recJson(recs[i]) + "}";
            fprintf(collFile, "%s\n", line.c_str());
            fflush(collFile);
            found.push_back(line);
            fprintf(stderr, "ksmall: collision %llu after %llu DPs (seeds %llu, %llu)\n",
                    (unsigned long long)collisions, (unsigned long long)(totalDps + i + 1),
                    (unsigned long long)it->second.seed, (unsigned long long)recs[i].seed);
        }
        totalDps += n;

        const uint64_t *w = (const uint64_t *)work.contents;
        uint64_t it = 0, starts = 0, abandoned = 0;
        for (uint32_t t = 0; t < threads; ++t) { it += w[3 * t]; starts += w[3 * t + 1]; abandoned += w[3 * t + 2]; }
        double wall = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        bool done = collisions >= wantCollisions || (maxSeconds > 0 && wall >= maxSeconds);
        if (launch % progressEvery == 0 || done) {
            fprintf(stderr, "progress launch %llu: 2^%.2f iterations, %.1f M it/s (GPU), %.1f M it/s (wall), %llu DPs, %llu starts, %llu abandoned, %.1f s\n",
                    (unsigned long long)launch, it ? std::log2(double(it)) : 0.0, it / gpuSeconds / 1e6, it / wall / 1e6,
                    (unsigned long long)totalDps, (unsigned long long)starts, (unsigned long long)abandoned, wall);
        }
        if (done) {
            printf("{\"device\":\"%s\",\"M\":%u,\"threads\":%u,\"batch\":%u,\"steps\":%u,\"launches\":%llu,"
                   "\"iterations\":%llu,\"starts\":%llu,\"abandoned\":%llu,\"dps\":%llu,\"dpsDropped\":%llu,"
                   "\"sameSeedRepeats\":%llu,\"sameStartTrails\":%llu,\"collisions\":%llu,\"gpuSeconds\":%.6f,\"wallSeconds\":%.6f,"
                   "\"iterationsPerSecondGpu\":%.1f,\"iterationsPerSecondWall\":%.1f}\n",
                   dev.name.UTF8String, m, threads, batch, steps, (unsigned long long)launch, (unsigned long long)it,
                   (unsigned long long)starts, (unsigned long long)abandoned, (unsigned long long)totalDps,
                   (unsigned long long)dropped, (unsigned long long)sameSeed, (unsigned long long)sameStart,
                   (unsigned long long)collisions,
                   gpuSeconds, wall, it / gpuSeconds, it / wall);
            break;
        }
    }
    fclose(collFile);
    if (dpFile) fclose(dpFile);
    return collisions >= wantCollisions ? 0 : 3;
}

int main(int argc, char **argv)
{
    @autoreleasepool {
        try {
            need(argc == 3, "usage: ksmall selftest|run DIR");
            signal(SIGINT, onSignal);
            signal(SIGTERM, onSignal);
            NSString *dir = [NSString stringWithUTF8String:argv[2]];
            NSDictionary *cfg = [NSJSONSerialization JSONObjectWithData:readFile(dir, @"config.json") options:0 error:nil];
            need([cfg isKindOfClass:[NSDictionary class]], "invalid config.json");
            id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
            need(dev != nil, "no Metal device (run outside the sandbox)");
            if (strcmp(argv[1], "selftest") == 0) return selftest(dev, dir, cfg);
            if (strcmp(argv[1], "run") == 0) return run(dev, dir, cfg);
            need(false, "unknown mode");
        } catch (const std::exception &ex) {
            fprintf(stderr, "ksmall: %s\n", ex.what());
            return 1;
        }
    }
    return 0;
}
