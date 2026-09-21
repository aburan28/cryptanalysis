// Point-dependent synthetic walk over the public tables' sparse polynomial.
// mslgen.py supplies P131 and the shared unreduced carryless product.
using namespace eccPacked131;
#ifndef ARTIFACT_BATCH
#define ARTIFACT_BATCH 16
#endif

struct ArtifactPoint { P131 x, y; uint inf; };
struct ArtifactState {
    uint xy[10], history[3], mode; // 0 walking, 1 needs seed, 2 halted, 3 exhausted
    ulong seed, trailSteps, walkSteps, reseeds, trace, dpHash, dpCount;
};
struct ArtifactDp { ulong seed, steps, lane; uint xy[10], history[3], pad; };
struct ArtifactArgs { uint lanes, cycles, branches, dpCap; int dpWeight; uint pad; };

static P131 azero() { P131 r = {}; return r; }
static P131 aone() { P131 r = {}; r.v[0] = 1; return r; }
static bool az(P131 a) { return !(a.v[0]|a.v[1]|a.v[2]|a.v[3]|a.v[4]); }
static bool ae(P131 a, P131 b) { return az(add131(a,b)); }
static ulong amix(ulong x) {
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ul;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebul;
    return x ^ (x >> 31);
}
static P131 areduce(thread const uint *h) {
    ulong h0=ulong(h[0])|(ulong(h[1])<<32), h1=ulong(h[2])|(ulong(h[3])<<32);
    ulong h2=ulong(h[4])|(ulong(h[5])<<32), h3=ulong(h[6])|(ulong(h[7])<<32), h4=h[8];
    ulong q0=(h2>>3)|(h3<<61), q1=(h3>>3)|(h4<<61), q2=h4>>3;
    ulong r0=h0^q0, r1=h1^q1, r2=(h2&7)^q2;
    for (uint i=0;i<3;++i) {
        uint s=i==0?1:i==1?2:13;
        r0 ^= q0<<s; r1 ^= (q1<<s)|(q0>>(64-s)); r2 ^= (q2<<s)|(q1>>(64-s));
    }
    ulong t=r2>>3; r2&=7; r0^=t^(t<<1)^(t<<2)^(t<<13);
    return P131{{uint(r0),uint(r0>>32),uint(r1),uint(r1>>32),uint(r2)}};
}
static P131 amul(P131 a,P131 b) { uint h[9]; product131(a,b,h); return areduce(h); }
static P131 asquare(P131 a) {
    uint h[9];
    for (uint i=0;i<4;++i) { ulong v=spread32p(a.v[i]); h[2*i]=uint(v); h[2*i+1]=uint(v>>32); }
    h[8]=(a.v[4]&1)|((a.v[4]&2)<<1)|((a.v[4]&4)<<2);
    return areduce(h);
}
static P131 ainverse(P131 a) {
    P131 r=a; uint k=1;
    for (int bit=6;bit>=0;--bit) {
        P131 t=r; for (uint j=0;j<k;++j) t=asquare(t);
        r=amul(r,t); k*=2;
        if ((130>>bit)&1) { r=amul(asquare(r),a); ++k; }
    }
    return asquare(r);
}
static ArtifactPoint aadd(ArtifactPoint p,ArtifactPoint q) {
    if (p.inf) return q;
    if (q.inf) return p;
    if (ae(p.x,q.x)) {
        if (!ae(p.y,q.y)||az(p.x)) return ArtifactPoint{azero(),azero(),1};
        P131 lam=add131(p.x,amul(p.y,ainverse(p.x)));
        P131 x=add131(asquare(lam),lam);
        return ArtifactPoint{x,add131(asquare(p.x),amul(add131(lam,aone()),x)),0};
    }
    P131 d=add131(p.x,q.x), lam=amul(add131(p.y,q.y),ainverse(d));
    P131 x=add131(add131(asquare(lam),lam),d);
    return ArtifactPoint{x,add131(add131(amul(lam,add131(p.x,x)),x),p.y),0};
}
static ArtifactPoint direction(const device uint *table,uint d) {
    const device uint *p=table+ulong(d)*9;
    return ArtifactPoint{P131{{p[0],p[1],p[2],p[3],p[8]&7}},
                         P131{{p[4],p[5],p[6],p[7],(p[8]>>3)&7}},p[8]>>31};
}
static ArtifactPoint statePoint(const device ArtifactState &s) {
    ArtifactPoint p; p.inf=0;
    for (uint i=0;i<5;++i) { p.x.v[i]=s.xy[i]; p.y.v[i]=s.xy[i+5]; }
    return p;
}
static P131 cyclic(P131 x,const device uint *constants) {
    P131 out=azero();
    for (uint nibble=0;nibble<33;++nibble) {
        uint value=(x.v[nibble/8]>>(4*(nibble&7)))&15;
        const device uint *row=constants+(nibble*16+value)*5;
        for (uint w=0;w<5;++w) out.v[w]^=row[w];
    }
    return out;
}
static uint aweight(P131 x) { return popcount(x.v[0])+popcount(x.v[1])+popcount(x.v[2])+popcount(x.v[3])+popcount(x.v[4]&7); }
static bool opposite(uint a,uint b) { return (a^b)==1u; }
static bool fruitless(uint d,uint h0,uint h1,uint h2) {
    return opposite(d,h0)||(opposite(d,h1)&&opposite(h0,h2));
}
static uint atag(P131 cx,P131 y,uint weight,uint branches,
                 uint h0,uint h1,uint h2,const device uint *constants) {
    uint sum=0;
    for (uint w=0;w<5;++w) {
        uint bits=cx.v[w];
        while (bits) { sum+=32*w+ctz(bits); bits&=bits-1; }
    }
    uint phase=(sum*constants[2640+655+weight])%131;
    P131 normalized=azero(); int highest=-1;
    for (uint t=0;t<131;++t) if ((cx.v[t/32]>>(t&31))&1) {
        uint n=(t+131-phase)%131; normalized.v[n/32]|=1u<<(n&31); highest=max(highest,int(n));
    }
    uint pivot=(uint(highest)+phase)%131;
    const device uint *row=constants+2640+pivot*5;
    uint parity=0; for (uint w=0;w<5;++w) parity^=y.v[w]&row[w];
    uint eps=popcount(parity)&1;
    ulong fingerprint=20260921ul;
    fingerprint=amix(fingerprint^(ulong(normalized.v[0])|(ulong(normalized.v[1])<<32)));
    fingerprint=amix(fingerprint^(ulong(normalized.v[2])|(ulong(normalized.v[3])<<32)));
    fingerprint=amix(fingerprint^normalized.v[4]);
    uint h=uint(fingerprint)&(branches-1), d=2*(phase*branches+h)+eps;
    for (uint i=0;i<branches&&fruitless(d,h0,h1,h2);++i) {
        h=(h+1)&(branches-1); d=2*(phase*branches+h)+eps;
    }
    return d;
}

kernel void artifact_arithmetic(const device uint *input [[buffer(0)]],device uint *output [[buffer(1)]],
                                constant uint &count [[buffer(2)]],uint tid [[thread_position_in_grid]]) {
    if (tid>=count) return;
    const device uint *in=input+tid*32; device uint *out=output+tid*26;
    P131 a,b; ArtifactPoint p,q;
    for (uint i=0;i<5;++i) { a.v[i]=in[i];b.v[i]=in[i+5];p.x.v[i]=in[i+10];p.y.v[i]=in[i+15];q.x.v[i]=in[i+20];q.y.v[i]=in[i+25]; }
    p.inf=in[30];q.inf=in[31];
    P131 product=amul(a,b),square=asquare(a),inverse=ainverse(a);
    ArtifactPoint sum=aadd(p,q);
    for (uint i=0;i<5;++i) { out[i]=product.v[i];out[i+5]=square.v[i];out[i+10]=inverse.v[i];out[i+15]=sum.x.v[i];out[i+20]=sum.y.v[i]; }
    out[25]=sum.inf;
}

kernel void artifact_walk(device ArtifactState *states [[buffer(0)]],
                          const device uint *directions [[buffer(1)]],const device uint *constants [[buffer(2)]],
                          device ArtifactDp *records [[buffer(3)]],device atomic_uint *counts [[buffer(4)]],
                          constant ArtifactArgs &args [[buffer(5)]],uint tid [[thread_position_in_grid]]) {
    const uint base=tid*ARTIFACT_BATCH;
    if (base>=args.lanes) return;
    for (uint cycle=0;cycle<args.cycles;++cycle) {
        P131 px[ARTIFACT_BATCH],py[ARTIFACT_BATCH],denom[ARTIFACT_BATCH],weighted[ARTIFACT_BATCH];
        uint kind[ARTIFACT_BATCH],seeded[ARTIFACT_BATCH],tags[ARTIFACT_BATCH];
        P131 product=aone(); bool active=false;
        for (uint slot=0;slot<ARTIFACT_BATCH;++slot) {
            uint lane=base+slot; kind[slot]=0;seeded[slot]=0;tags[slot]=0;
            px[slot]=azero();py[slot]=azero();P131 d=aone(),e=azero();
            if (lane<args.lanes&&states[lane].mode<2) {
                device ArtifactState &s=states[lane]; ArtifactPoint p=statePoint(s),q;
                if (s.mode==0) {
                    P131 cx=cyclic(p.x,constants);uint weight=aweight(cx);
                    if (weight==0||weight==131) s.mode=2;
                    else if (args.dpWeight>=0&&weight<=uint(args.dpWeight)) {
                        uint dest=atomic_fetch_add_explicit(counts,1u,memory_order_relaxed);
                        if (dest<args.dpCap) {
                            ArtifactDp rec;rec.seed=s.seed;rec.steps=s.trailSteps;rec.lane=lane;rec.pad=0;
                            for(uint w=0;w<10;++w)rec.xy[w]=s.xy[w];
                            for(uint w=0;w<3;++w)rec.history[w]=s.history[w];
                            records[dest]=rec;
                        } else atomic_fetch_add_explicit(counts+1,1u,memory_order_relaxed);
                        for(uint w=0;w<10;++w)s.dpHash=amix(s.dpHash^s.xy[w]);
                        for(uint w=0;w<3;++w)s.dpHash=amix(s.dpHash^s.history[w]);
                        s.dpHash=amix(s.dpHash^s.trailSteps^s.seed);++s.dpCount;
                        if (s.seed>0xfffffffffffffffful-args.lanes) s.mode=3;
                        else { s.seed+=args.lanes;s.mode=1; }
                    } else {
                        uint tag=atag(cx,p.y,weight,args.branches,s.history[0],s.history[1],s.history[2],constants);
                        s.history[2]=s.history[1];s.history[1]=s.history[0];s.history[0]=tag;
                        tags[slot]=tag;q=direction(directions,tag);
                    }
                }
                if (s.mode==1) {
                    uint n=262*args.branches;
                    uint u=uint(amix(s.seed^0x736565642d616464ul)%n);
                    uint v=uint(amix(s.seed^0x736565642d706169ul)%n);
                    if (v==(u^1))v=(v+2)%n;
                    p=direction(directions,u);q=direction(directions,v);seeded[slot]=1;
                    s.history[0]=s.history[1]=s.history[2]=0xffffffffu;s.trailSteps=0;
                }
                if (s.mode<2) {
                    active=true;px[slot]=p.x;py[slot]=p.y;
                    if (ae(p.x,q.x)) {
                        if (!ae(p.y,q.y)||az(p.x))kind[slot]=3;
                        else {kind[slot]=2;d=p.x;e=p.y;}
                    } else {kind[slot]=1;d=add131(p.x,q.x);e=add131(p.y,q.y);}
                }
            }
            denom[slot]=d;weighted[slot]=amul(product,e);product=amul(product,d);
        }
        if (!active) break;
        P131 inv=ainverse(product);
        for (int slot=ARTIFACT_BATCH-1;slot>=0;--slot) {
            P131 lambda=amul(inv,weighted[slot]);inv=amul(inv,denom[slot]);
            if (!kind[slot])continue;
            device ArtifactState &s=states[base+uint(slot)];
            P131 nx=azero(),ny=azero();
            if (kind[slot]==2) {
                lambda=add131(lambda,px[slot]);nx=add131(asquare(lambda),lambda);
                ny=add131(asquare(px[slot]),amul(add131(lambda,aone()),nx));
            } else if(kind[slot]==1) {
                nx=add131(add131(asquare(lambda),lambda),denom[slot]);
                ny=add131(add131(amul(lambda,add131(px[slot],nx)),nx),py[slot]);
            }
            for(uint w=0;w<5;++w){s.xy[w]=nx.v[w];s.xy[w+5]=ny.v[w];}
            s.mode=kind[slot]==3?2:0;
            if(seeded[slot])++s.reseeds;
            else {++s.walkSteps;++s.trailSteps;s.trace=amix(s.trace^(ulong(tags[slot])<<32)^s.walkSteps);}
        }
    }
}
