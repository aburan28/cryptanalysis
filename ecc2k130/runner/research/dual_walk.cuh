// Included inside eccPacked131, after tableSelectSlot and the field helpers.
// Two 16-point chains occupy the 32 slots of one CUDA thread.
static_assert(ECC_BATCH==32,"dual walk needs exactly two 16-point chains");
static_assert(ECC_WALK_TABLE && ECC_TABLE_TAG_DENOM && ECC_PACKED_POLY_STATE,
              "dual walk uses the existing polynomial table walk");
static __global__ void ECC_BOUNDS walk(WalkParams<unsigned> p, unsigned *denominators) {
    (void)denominators;
    extern __shared__ uint32_t table[];
    twLoadShared(table,p.twConsts);
    const int tid=blockIdx.x*blockDim.x+threadIdx.x;
    if(tid>=p.threads)return;
#pragma unroll 1
    for(int step=0;step<p.steps;++step){
        const unsigned long long now=p.iterBase+step;
        const bool guard=p.maxIters && now%ECC_GUARD_PERIOD==0;
        P131 prod0{},prod1{};
#pragma unroll 1
        for(int slot=0;slot<16;++slot){
            P131 d0,e0,d1,e1;
            tableSelectSlot(p,slot,tid,now,guard,table,table,&d0,&e0);
            tableSelectSlot(p,slot+16,tid,now,guard,table,table,&d1,&e1);
            if(slot){
                uint32_t c0[9],c1[9],w0[9],w1[9];
                product131(prod0,d0,c0); product131(prod1,d1,c1);
                product131(prod0,e0,w0); product131(prod1,e1,w1);
                prod0=reducePolynomial131(c0);prod1=reducePolynomial131(c1);
                store(p.pchain,slot,tid,p.threads,reducePolynomial131(w0));
                store(p.pchain,slot+16,tid,p.threads,reducePolynomial131(w1));
            } else {
                prod0=d0;prod1=d1;
                store(p.pchain,slot,tid,p.threads,e0);store(p.pchain,slot+16,tid,p.threads,e1);
            }
        }
        const auto inverse=goal22PairedInverse({fromPolynomial131(prod0),fromPolynomial131(prod1)});
        P131 inv0=toPolynomial131(inverse.first),inv1=toPolynomial131(inverse.second);
#pragma unroll 1
        for(int slot=15;slot>=0;--slot){
            const P131 x0=load(p.x,slot,tid,p.threads),y0=load(p.y,slot,tid,p.threads);
            const P131 x1=load(p.x,slot+16,tid,p.threads),y1=load(p.y,slot+16,tid,p.threads);
            P131 d0,d1;
            const unsigned tag0=unsigned(goal22ReadHist(p.hist,size_t(slot)*p.threads+tid,size_t(p.threads)*ECC_BATCH)&0xffffu);
            const unsigned tag1=unsigned(goal22ReadHist(p.hist,size_t(slot+16)*p.threads+tid,size_t(p.threads)*ECC_BATCH)&0xffffu);
            twDenominator(tag0,x0,table,&d0);twDenominator(tag1,x1,table,&d1);
            const P131 w0=load(p.pchain,slot,tid,p.threads),w1=load(p.pchain,slot+16,tid,p.threads);
            P131 lambda0,lambda1;
            if(slot){
                uint32_t c0[9],c1[9],l0[9],l1[9];
                product131(inv0,d0,c0);product131(inv1,d1,c1);
                product131(inv0,w0,l0);product131(inv1,w1,l1);
                inv0=reducePolynomial131(c0);inv1=reducePolynomial131(c1);
                lambda0=reducePolynomial131(l0);lambda1=reducePolynomial131(l1);
            } else {
                uint32_t l0[9],l1[9];product131(inv0,w0,l0);product131(inv1,w1,l1);
                lambda0=reducePolynomial131(l0);lambda1=reducePolynomial131(l1);
            }
            const P131 nx0=add131(add131(squarePolynomial131(lambda0),lambda0),d0);
            const P131 nx1=add131(add131(squarePolynomial131(lambda1),lambda1),d1);
            uint32_t h0[9],h1[9];
            product131(lambda0,add131(x0,nx0),h0);product131(lambda1,add131(x1,nx1),h1);
            const P131 ny0=add131(add131(reducePolynomial131(h0),nx0),y0);
            const P131 ny1=add131(add131(reducePolynomial131(h1),nx1),y1);
            store(p.x,slot,tid,p.threads,nx0);store(p.y,slot,tid,p.threads,ny0);
            store(p.x,slot+16,tid,p.threads,nx1);store(p.y,slot+16,tid,p.threads,ny1);
        }
    }
}
