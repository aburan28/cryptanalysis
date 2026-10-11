// The runner generates the unchanged round29 host with only main renamed.
// Its 512-thread/direct/16-pivot path is the frozen previous GPU control.
#include "../round29/active_rref_library.mm"
#ifndef MAP_THREADS
#define MAP_THREADS 512
#endif
#ifndef MAP_SKIP_WORDS
#define MAP_SKIP_WORDS 1
#endif
struct MappedResult { Result result; bool fallback=false; };

static MappedResult mapped_gpu(const std::vector<uint64_t>& input,Params p,
    id<MTLDevice> device,id<MTLCommandQueue> queue,NSArray* pipes,NSArray* fallback_pipe,
    uint32_t width,size_t scratch_limit=32768) {
    auto start=Clock::now();
    if((width!=16&&width!=32)||p.rows>8192||p.cols>8192||p.count>256||
       p.words!=2*((p.cols+63)/64)||input.size()!=size_t(p.rows)*p.count*p.words/2)
        throw std::runtime_error("invalid mapped matrix shape");
    if(p.cols%64)for(size_t row=0;row<size_t(p.rows)*p.count;++row)
        if(input[row*(p.words/2)+p.words/2-1]>>(p.cols%64))throw std::runtime_error("nonzero matrix padding");
    MappedResult out;
    id<MTLComputePipelineState> selector=pipes[0];
    size_t local=(size_t(p.rows)*8+15)/16*16;
    size_t available=std::min(scratch_limit,size_t(device.maxThreadgroupMemoryLength));
    if(p.rows&&p.cols&&p.count&&local+selector.staticThreadgroupMemoryLength>available) {
        out.fallback=true;out.result=active_gpu(input,p,device,queue,fallback_pipe,16).result;
        out.result.ms=baseline::elapsed(start);return out;
    }
    out.result.data.resize(input.size());out.result.ranks.resize(p.count);
    @autoreleasepool {
        if(p.rows&&p.cols&&p.count) {
            id<MTLBuffer> a=[device newBufferWithBytes:input.data() length:input.size()*8 options:MTLResourceStorageModeShared];
            id<MTLBuffer> state=[device newBufferWithLength:p.count*16 options:MTLResourceStorageModeShared];
            id<MTLBuffer> pc=[device newBufferWithLength:p.count*width*4 options:MTLResourceStorageModeShared];
            id<MTLBuffer> table=[device newBufferWithLength:size_t(p.count)*(width/8)*256*p.words*4 options:MTLResourceStorageModeShared];
            id<MTLBuffer> masks=[device newBufferWithLength:size_t(p.count)*p.rows*4 options:MTLResourceStorageModeShared];
            id<MTLBuffer> order=[device newBufferWithLength:size_t(p.count)*p.rows*4 options:MTLResourceStorageModeShared];
            id<MTLBuffer> mixing=[device newBufferWithLength:size_t(p.count)*(width+(width/8)*256)*4 options:MTLResourceStorageModeShared];
            if(!a||!state||!pc||!table||!masks||!order||!mixing)throw std::runtime_error("mapped buffer allocation");
            memset(state.contents,0,p.count*16);
            auto* row_map=static_cast<uint32_t*>(order.contents);
            for(uint32_t b=0;b<p.count;++b)for(uint32_t row=0;row<p.rows;++row)row_map[size_t(b)*p.rows+row]=row;
            id<MTLCommandBuffer> command=[queue commandBuffer];id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
            if(!command||!encoder)throw std::runtime_error("mapped command allocation");
            [encoder setBuffer:a offset:0 atIndex:0];[encoder setBuffer:state offset:0 atIndex:1];
            [encoder setBuffer:pc offset:0 atIndex:2];[encoder setBuffer:table offset:0 atIndex:3];
            [encoder setBuffer:masks offset:0 atIndex:4];[encoder setBytes:&p length:sizeof(p) atIndex:5];
            [encoder setBuffer:order offset:0 atIndex:6];[encoder setBuffer:mixing offset:0 atIndex:7];
            [encoder setThreadgroupMemoryLength:local atIndex:0];
            bool vec=p.words%4==0;
            for(uint32_t panel=0;panel<(std::min(p.rows,p.cols)+width-1)/width;++panel) {
                for(uint32_t stage=0;stage<3;++stage) {
                    [encoder setComputePipelineState:pipes[stage?(vec?stage+2:stage):0]];
                    if(!stage)[encoder dispatchThreadgroups:MTLSizeMake(1,p.count,1) threadsPerThreadgroup:MTLSizeMake(MAP_THREADS,1,1)];
                    else [encoder dispatchThreads:MTLSizeMake((stage==1?(width/8)*256:p.rows)*(p.words/(vec?4:1)),p.count,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];
                    [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
                }
            }
            [encoder endEncoding];[command commit];[command waitUntilCompleted];
            if(command.status!=MTLCommandBufferStatusCompleted)throw std::runtime_error(command.error.description.UTF8String);
            out.result.gpu_ms=1000*(command.GPUEndTime-command.GPUStartTime);
            auto* values=static_cast<const uint64_t*>(a.contents);size_t stride=p.words/2;
            // Ordered output materialization is part of the charged invocation.
            for(uint32_t b=0;b<p.count;++b) {
                out.result.ranks[b]=static_cast<uint32_t*>(state.contents)[4*b];
                for(uint32_t row=0;row<p.rows;++row) {
                    uint32_t physical=row_map[size_t(b)*p.rows+row];
                    if(physical>=p.rows)throw std::runtime_error("invalid GPU row index");
                    memcpy(out.result.data.data()+(size_t(b)*p.rows+row)*stride,
                           values+(size_t(b)*p.rows+physical)*stride,stride*8);
                }
            }
        }
    }
    out.result.ms=baseline::elapsed(start);return out;
}

static NSArray* compile_mapped(id<MTLDevice> device,const char* path,uint32_t width,bool skip=bool(MAP_SKIP_WORDS)) {
    NSError* error=nil;
    NSString* body=[NSString stringWithContentsOfFile:@(path) encoding:NSUTF8StringEncoding error:&error];
    if(!body)throw std::runtime_error(error.description.UTF8String);
    NSString* src=[NSString stringWithFormat:@"#define MAP_WIDTH %u\n#define MAP_THREADS %u\n#define MAP_SKIP_WORDS %u\n%@",width,MAP_THREADS,unsigned(skip),body];
    id<MTLLibrary> library=[device newLibraryWithSource:src options:nil error:&error];
    if(!library)throw std::runtime_error(error.description.UTF8String);
    NSMutableArray* out=[NSMutableArray array];
    for(NSString* name in @[@"select_mapped",@"table_mapped",@"eliminate_mapped",@"table_mapped_vec",@"eliminate_mapped_vec"]) {
        id<MTLComputePipelineState> p=[device newComputePipelineStateWithFunction:[library newFunctionWithName:name] error:&error];
        uint32_t required=[name isEqualToString:@"select_mapped"]?MAP_THREADS:256;
        if(!p||p.maxTotalThreadsPerThreadgroup<required)throw std::runtime_error(error?error.description.UTF8String:"mapped thread capability");
        [out addObject:p];
    }
    return out;
}

int main(int argc,char**argv) {
 @autoreleasepool {try {
    if(argc!=6)throw std::runtime_error("usage: row-map round7.metal round29.metal mapped.metal matrices.json correctness|measure");
    std::string mode=argv[5];if(mode!="correctness"&&mode!="measure")throw std::runtime_error("mode");
    if(pthread_set_qos_class_self_np(QOS_CLASS_USER_INITIATED,0))throw std::runtime_error("CPU QoS");
    auto start=Clock::now();id<MTLDevice> device=MTLCreateSystemDefaultDevice();if(!device)throw std::runtime_error("no Metal device");
    NSArray* previous=compile_pipelines(device,argv[1],argv[2],16);
    NSArray* narrow=compile_mapped(device,argv[3],16);NSArray* wide=compile_mapped(device,argv[3],32);
    NSArray* other_narrow=compile_mapped(device,argv[3],16,!MAP_SKIP_WORDS);
    NSArray* other_wide=compile_mapped(device,argv[3],32,!MAP_SKIP_WORDS);
    id<MTLCommandQueue> queue=[device newCommandQueue];if(!queue)throw std::runtime_error("command queue");
    double setup=baseline::elapsed(start);size_t checked=0,mapped_calls=0,fallback_calls=0;
    auto check=[&](const Case& c,uint32_t count=1) {
        Params p={c.rows,c.cols,2*((c.cols+63)/64),count};auto ref=baseline::cpu(c.data,p);
        for(uint32_t width:{16u,32u})for(bool other:{false,true})for(size_t budget:{size_t(32768),size_t(0)}) {
            NSArray* pipe=width==16?(other?other_narrow:narrow):(other?other_wide:wide);
            auto got=mapped_gpu(c.data,p,device,queue,pipe,previous,width,budget);
            baseline::same(ref,got.result);checked+=count;(got.fallback?fallback_calls:mapped_calls)++;
        }
    };
    auto cases=load_cases(argv[4]);
    if(mode=="correctness") {
        std::mt19937_64 rng(2026092930);
        for(auto shape:std::vector<std::pair<uint32_t,uint32_t>>{{0,0},{0,65},{3,0},{1,1},{2,2},{2,3},{3,3}})
            for(uint64_t bits=0;bits<(UINT64_C(1)<<(shape.first*shape.second));++bits) {
                Case c={"exhaustive",shape.first,shape.second,{}};
                if(c.cols)for(uint32_t r=0;r<c.rows;++r)c.data.push_back((bits>>(r*c.cols))&((UINT64_C(1)<<c.cols)-1));
                check(c);
            }
        for(uint32_t cols:{7u,15u,16u,17u,31u,32u,33u,63u,64u,65u,127u,128u,129u,255u,256u,257u}) {
            for(uint32_t rows:{1u,15u,16u,17u,31u,32u,33u,65u})check(baseline::random_case(rows,cols,rng));
            Case zero={"zero",67,cols,std::vector<uint64_t>(67*((cols+63)/64),0)};check(zero);
            for(uint32_t row=0;row<zero.rows;++row)zero.data[row*((cols+63)/64)+(cols-1)/64]=UINT64_C(1)<<((cols-1)%64);
            check(zero);
        }
        for(auto shape:std::vector<std::pair<uint32_t,uint32_t>>{{4096,4096},{4097,65},{8192,33},{65,8192}})
            check(baseline::random_case(shape.first,shape.second,rng));
        Case gaps={"gapped-panels",79,4097,std::vector<uint64_t>(79*65,0)};
        for(uint32_t row=0;row<79;++row){uint32_t col=(row%71)*53;gaps.data[row*65+col/64]=UINT64_C(1)<<(col%64);gaps.data[row*65+64]=1;}
        check(gaps);
        for(uint32_t cols:{33u,65u,129u,4096u}) {
            Case batch={"unequal-ranks",65,cols,{}};
            for(uint32_t b=0;b<7;++b) {
                auto c=baseline::random_case(65,cols,rng);uint32_t stride=(cols+63)/64;
                if(b%3==0)std::fill(c.data.begin(),c.data.end(),0);
                else if(b%3==1)for(uint32_t r=0;r<65;++r)c.data[r*stride]&=~UINT64_C(0xffffffff);
                batch.data.insert(batch.data.end(),c.data.begin(),c.data.end());
            }
            check(batch,7);
        }
        for(const auto& c:cases)check(c);
        size_t rejected=0;
        for(auto p:std::vector<Params>{{1,1,2,1},{8193,1,2,1},{1,1,4,1}}) {
            try{mapped_gpu({2},p,device,queue,wide,previous,32);}
            catch(const std::runtime_error&){++rejected;}
        }
        if(rejected!=3||!mapped_calls||!fallback_calls)throw std::runtime_error("coverage incomplete");
        output(@{@"schema":@"row-map-correctness/2",@"device":device.name,@"m4ri_library":m4ri_path(),@"tested_word_skip":@[@YES,@NO],
            @"checked_matrices":@(checked),@"exact_rank_and_rref":@YES,@"mapped_calls":@(mapped_calls),@"fallback_calls":@(fallback_calls),
            @"invalid_inputs_rejected":@(rejected),@"timing_eligible":@NO,@"pivot_threads":@MAP_THREADS,@"word_skip":@(bool(MAP_SKIP_WORDS)),@"seed":@2026092930});return 0;
    }
    std::mt19937_64 rng(2026092507);
    for(auto shape:std::vector<std::pair<uint32_t,uint32_t>>{{256,1024},{1536,3072},{2048,4096}})
        cases.push_back(baseline::random_case(shape.first,shape.second,rng));
    Case low=cases[0];low.name="captured-seed1-duplicate-row-control";uint32_t stride=(low.cols+63)/64;
    for(uint32_t row=low.rows/2;row<low.rows;++row)std::copy_n(low.data.data()+(row%(low.rows/2))*stride,stride,low.data.data()+row*stride);
    cases.push_back(std::move(low));
    long cpus=sysconf(_SC_NPROCESSORS_ONLN);double initial=load();
    if(cpus<=0||initial>cpus)throw std::runtime_error("initial load admission rejected");
    NSMutableArray* cells=[NSMutableArray array];
    for(const auto& c:cases) {
        Params p={c.rows,c.cols,2*((c.cols+63)/64),1};NSMutableArray* samples=[NSMutableArray array];
        for(int rep=0;rep<32;++rep) {
            double group_load=load();if(group_load>cpus)throw std::runtime_error("group load admission rejected");
            std::array<int,5> order={0,1,2,3,4};std::shuffle(order.begin(),order.end(),rng);
            Result cpu,old;MappedResult a,b,other;double cpu_thread=0;
            for(int arm:order) {
                if(arm==0){double t=thread_ms();cpu=baseline::cpu(c.data,p);cpu_thread=thread_ms()-t;}
                else if(arm==1)old=active_gpu(c.data,p,device,queue,previous,16).result;
                else if(arm==2)a=mapped_gpu(c.data,p,device,queue,narrow,previous,16);
                else if(arm==3)b=mapped_gpu(c.data,p,device,queue,wide,previous,32);
                else other=mapped_gpu(c.data,p,device,queue,other_wide,previous,32);
            }
            baseline::same(cpu,old);baseline::same(cpu,a.result);baseline::same(cpu,b.result);baseline::same(cpu,other.result);checked+=4;
            [samples addObject:@{@"warmup":@(rep==0),@"order":@[@(order[0]),@(order[1]),@(order[2]),@(order[3]),@(order[4])],
                @"load1":@(group_load),@"rank":@(cpu.ranks[0]),@"cpu_wall_ms":@(cpu.ms),@"cpu_thread_ms":@(cpu_thread),
                @"previous_wall_ms":@(old.ms),@"previous_device_ms":@(old.gpu_ms),
                @"mapped16_wall_ms":@(a.result.ms),@"mapped16_device_ms":@(a.result.gpu_ms),
                @"mapped32_wall_ms":@(b.result.ms),@"mapped32_device_ms":@(b.result.gpu_ms),
                @"other32_wall_ms":@(other.result.ms),@"other32_device_ms":@(other.result.gpu_ms),
                @"mapped16_fallback":@(a.fallback),@"mapped32_fallback":@(b.fallback),@"other32_fallback":@(other.fallback)}];
        }
        [cells addObject:@{@"name":@(c.name.c_str()),@"rows":@(c.rows),@"cols":@(c.cols),@"matrix_count":@1,@"samples":samples}];
        std::cerr<<c.name<<" exact comparisons passed\n";
    }
    double last=load();if(last>cpus)throw std::runtime_error("final load admission rejected");
    output(@{@"schema":@"row-map-measurement/2",@"scope":@"single-matrix RREF only; no full polynomial query or IC claim",
        @"device":device.name,@"m4ri_library":m4ri_path(),@"logical_cpus":@(cpus),@"load_initial":@(initial),@"load_final":@(last),
        @"initialization_ms":@(setup),@"checked_matrices":@(checked),@"exact_rank_and_rref":@YES,@"timing_eligible":@YES,
        @"seed":@2026092507,@"cpu_qos":@"USER_INITIATED",@"m4ri_k":@5,@"pivot_threads":@MAP_THREADS,
        @"previous_pivot_threads":@ACTIVE_THREADS,@"previous_indirect":@(bool(ACTIVE_INDIRECT)),@"word_skip":@(bool(MAP_SKIP_WORDS)),@"other32_word_skip":@(!bool(MAP_SKIP_WORDS)),
        @"timing":@"fresh allocations, permutation initialization, transfers, dispatch, synchronization, final ordered gather and buffer destruction included; setup/input loading/exact comparison excluded",
        @"cells":cells});return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
}
