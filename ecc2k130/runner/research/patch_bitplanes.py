"""Pack 3-bit field tails per warp, retaining 128-byte tile alignment."""
from patch_metadata import replace_once


def patch(content):
    content = dict(content)
    path = 'include/packedcompactstate.cuh'
    s = content[path].replace('4352', '4224')
    s = replace_once(s, '#if ECC_PACKED_COMPACT_STATE\n', '''#if ECC_PACKED_COMPACT_STATE
#if !ECC_TABLE_TAG_DENOM
#error "3-bit field tails require tag-rebuilt denominators"
#endif
''')
    s = replace_once(s, 'return tileSlot * size_t(4224) + size_t(4096) + size_t(tid) % 256;',
        'return tileSlot * size_t(4224) + size_t(4096) + (size_t(tid) % 256 / 32) * 16;')
    s = replace_once(s, '    value.v[4] = bytes[compactTopByteOffset(slot, tid)];', '''
    uint32_t top[4];
#if defined(__CUDA_ARCH__)
    const uint4 packed = *reinterpret_cast<const uint4 *>(bytes + compactTopByteOffset(slot, tid));
    top[0]=packed.x; top[1]=packed.y; top[2]=packed.z;
#else
    std::memcpy(top, bytes + compactTopByteOffset(slot, tid), 16);
#endif
    const unsigned lane=unsigned(tid)&31u;
    value.v[4]=((top[0]>>lane)&1u)|(((top[1]>>lane)&1u)<<1)|(((top[2]>>lane)&1u)<<2);''')
    old = '''    // Byte ownership avoids a read-modify-write race with neighboring tails.
    bytes[compactTopByteOffset(slot, tid)] = static_cast<unsigned char>(value.v[4]);'''
    s = replace_once(s, old, '''
#if defined(__CUDA_ARCH__)
    // The launch and logical worker counts are multiples of a warp, so the
    // physical tail lane agrees with the lane in these ballots, including init.
    const unsigned active=__activemask();
    const unsigned b0=__ballot_sync(active,(value.v[4]&1u)!=0);
    const unsigned b1=__ballot_sync(active,(value.v[4]&2u)!=0);
    const unsigned b2=__ballot_sync(active,(value.v[4]&4u)!=0);
    if((unsigned(threadIdx.x)&31u)==unsigned(__ffs(active)-1)) {
        unsigned *target=reinterpret_cast<unsigned *>(bytes+compactTopByteOffset(slot,tid));
        if(active==0xffffffffu) {
            *reinterpret_cast<uint4 *>(target)=uint4{b0,b1,b2,0u};
        } else {
            // Reseeding may select only part of a warp. Preserve every inactive
            // point. CAS also handles independently scheduled disjoint subsets.
            const unsigned selected[3]={b0,b1,b2};
#pragma unroll
            for(int plane=0;plane<3;++plane) {
                unsigned old=atomicCAS(target+plane,0u,0u), observed;
                do { observed=old; old=atomicCAS(target+plane,observed,
                    (observed&~active)|(selected[plane]&active)); } while(old!=observed);
            }
        }
    }
    __syncwarp(active); // Make the leader's tail stores visible to its peers.
#else
    uint32_t top[4];
    std::memcpy(top,bytes+compactTopByteOffset(slot,tid),16);
    const unsigned mask=1u<<(unsigned(tid)&31u);
    for(int plane=0;plane<3;++plane)
        top[plane]=(top[plane]&~mask)|((value.v[4]&(1u<<plane))?mask:0u);
    std::memcpy(bytes+compactTopByteOffset(slot,tid),top,16);
#endif''')
    content[path] = s
    path = 'include/packedengine.cuh'
    content[path] = replace_once(content[path], '        P.threads = o.threads; P.steps = o.steps;', '''        if(o.threads % 32) {
            std::fprintf(stderr,"bitplane field storage requires a worker count divisible by 32\\n");
            std::exit(2);
        }
        P.threads = o.threads; P.steps = o.steps;''')
    return content
