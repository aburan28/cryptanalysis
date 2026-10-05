// Matched exact-selector A/B kernels appended to artifact_walk.metal.
// Inputs exclude DP/reseed/exceptional cases; Python prepares and checks every
// expected endpoint, history word and direction index independently.
struct FusedBenchResult {
    uint xy[10], history[3], first, second, pad;
};

static ArtifactPoint pairPoint(const device uint *pairs, uint a, uint b) {
    ulong u=min(a,b),v=max(a,b);
    ulong index=v*(v+1ul)/2ul+u;
    const device uint *p=pairs+9ul*index;
    return ArtifactPoint{P131{{p[0],p[1],p[2],p[3],p[8]&7}},
                         P131{{p[4],p[5],p[6],p[7],(p[8]>>3)&7}},p[8]>>31};
}

kernel void fused_bench_baseline(const device ArtifactState *input [[buffer(0)]],
                                 const device uint *directions [[buffer(1)]],
                                 const device uint *constants [[buffer(2)]],
                                 device FusedBenchResult *output [[buffer(3)]],
                                 constant uint &count [[buffer(4)]],
                                 uint tid [[thread_position_in_grid]]) {
    if(tid>=count)return;
    const device ArtifactState &s=input[tid];
    ArtifactPoint p=statePoint(s);
    uint h0=s.history[0],h1=s.history[1],h2=s.history[2];
    P131 cx=cyclic(p.x,constants);uint w=aweight(cx);
    uint first=atag(cx,p.y,w,128,h0,h1,h2,constants);
    p=aadd(p,direction(directions,first));
    cx=cyclic(p.x,constants);w=aweight(cx);
    uint second=atag(cx,p.y,w,128,first,h0,h1,constants);
    p=aadd(p,direction(directions,second));
    FusedBenchResult r;
    for(uint i=0;i<5;++i){r.xy[i]=p.x.v[i];r.xy[i+5]=p.y.v[i];}
    r.history[0]=second;r.history[1]=first;r.history[2]=h0;
    r.first=first;r.second=second;r.pad=p.inf;
    output[tid]=r;
}

kernel void fused_bench_selector(const device ArtifactState *input [[buffer(0)]],
                                 const device uint *directions [[buffer(1)]],
                                 const device uint *constants [[buffer(2)]],
                                 device FusedBenchResult *output [[buffer(3)]],
                                 constant uint &count [[buffer(4)]],
                                 uint tid [[thread_position_in_grid]]) {
    if(tid>=count)return;
    const device ArtifactState &s=input[tid];
    ArtifactPoint p=statePoint(s);
    uint h0=s.history[0],h1=s.history[1],h2=s.history[2];
    P131 cx=cyclic(p.x,constants);uint w=aweight(cx);
    uint first=atag(cx,p.y,w,128,h0,h1,h2,constants);
    p=aadd(p,direction(directions,first));
    cx=cyclic(p.x,constants);w=aweight(cx);
    uint second=atag(cx,p.y,w,128,first,h0,h1,constants);
    FusedBenchResult r;
    for(uint i=0;i<5;++i){r.xy[i]=p.x.v[i];r.xy[i+5]=p.y.v[i];}
    r.history[0]=second;r.history[1]=first;r.history[2]=h0;
    r.first=first;r.second=second;r.pad=p.inf;
    output[tid]=r;
}

kernel void fused_bench_pair_finish(const device ArtifactState *input [[buffer(0)]],
                                    const device uint *pairs [[buffer(1)]],
                                    const device FusedBenchResult *selected [[buffer(2)]],
                                    device FusedBenchResult *output [[buffer(3)]],
                                    constant uint &count [[buffer(4)]],
                                    uint tid [[thread_position_in_grid]]) {
    if(tid>=count)return;
    FusedBenchResult r=selected[tid];
    ArtifactPoint p=aadd(statePoint(input[tid]),pairPoint(pairs,r.first,r.second));
    for(uint i=0;i<5;++i){r.xy[i]=p.x.v[i];r.xy[i+5]=p.y.v[i];}
    r.pad=p.inf;
    output[tid]=r;
}
