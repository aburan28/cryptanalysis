"""Generate the scheduled polynomial-basis GF(2^131) multiplier.

This reconstructs the native 128-bit product (nine clmul32 leaves, sixteen
widening products per leaf), adds the top-three-bit terms, and composes the
existing direct polynomial reducer before scheduling word operations. The
integer-mask carryless construction preserves parity after each residue mask.
The final field polynomial is 0xd1d0d000d0000000d000000000000000d.

Graph construction, local Boolean fusion, and deferred scheduling are fixed
and deterministic. This is not an optimizer/search or a CUDA performance
model. Each widening event produces its low/high words together; all ten
input words remain available until their last uses. No archived graph or
external package is needed. C++ emission uses only unsigned arithmetic.
"""
from pathlib import Path
from collections import defaultdict
import argparse
import sys

from collections import Counter
MASK=(1<<32)-1
ZERO=-1
class Graph:
    def __init__(self):
        self.nodes=[];self.producer={};self.memo={};self.next_cell=10;self.products=[];self.outputs=[];self.corrections=[];self.phase='low'
    def add(self,op,args=(),imm=None,wide=False):
        args=tuple(args);key=(op,args,imm)
        if not wide and key in self.memo:return self.memo[key]
        out=list(range(self.next_cell,self.next_cell+(2 if wide else 1)));self.next_cell+=len(out)
        node=dict(id=len(self.nodes),op=op,args=list(args),imm=imm,out=out,phase=self.phase)
        self.nodes.append(node)
        for cell in out:self.producer[cell]=node['id']
        if wide:self.products.append(node['id']);return out
        self.memo[key]=out[0];return out[0]
    def xor(self,*args):
        counts=Counter(x for x in args if x!=ZERO);args=sorted(x for x,n in counts.items() if n%2)
        if not args:return ZERO
        if len(args)==1:return args[0]
        while len(args)>3:args=sorted([self.add('xor',args[:3])]+args[3:])
        return self.add('xor',args)
    def or_(self,*args):
        args=sorted(set(x for x in args if x!=ZERO))
        if not args:return ZERO
        if len(args)==1:return args[0]
        while len(args)>3:args=sorted([self.add('or',args[:3])]+args[3:])
        return self.add('or',args)
    def and_(self,a,mask):
        mask&=MASK
        if a==ZERO or not mask:return ZERO
        if mask==MASK:return a
        parent=self.nodes[self.producer[a]] if a in self.producer else None
        if parent and parent['op']=='xor' and len(parent['args'])==2:return self.add('xor_mask',parent['args'],mask)
        return self.add('and',(a,),mask)
    def and_var(self,a,b):
        if ZERO in (a,b):return ZERO
        if a==b:return a
        return self.add('and_var',sorted((a,b)))
    def shl(self,a,k):return ZERO if a==ZERO or k>=32 else (a if k==0 else self.add('shl',(a,),k))
    def shr(self,a,k):return ZERO if a==ZERO or k>=32 else (a if k==0 else self.add('shr',(a,),k))
    def sar(self,a,k):return ZERO if a==ZERO else self.add('sar',(a,),k)
    def funnel_l(self,previous,current,k):
        if previous==ZERO:return self.shl(current,k)
        if current==ZERO:return self.shr(previous,32-k)
        return self.add('funnel_l',(previous,current),k)
    def funnel_r(self,current,following,k):
        if following==ZERO:return self.shr(current,k)
        if current==ZERO:return self.shl(following,32-k)
        return self.add('funnel_r',(current,following),k)
    def wide(self,a,b):return self.add('wide',(a,b),wide=True)
    def active(self):
        seen=set()
        def visit(n):
            if n in seen:return
            seen.add(n)
            for c in self.nodes[n]['args']:
                if c in self.producer:visit(self.producer[c])
        for n in self.products:visit(n)
        for c in self.outputs:
            if c in self.producer:visit(self.producer[c])
        return seen
    def fuse(self):
        # Shared, conservative one-LOP3 local rules. No free multi-input masks.
        changed=True
        while changed:
            changed=False;active=self.active();uses=Counter(c for n in active for c in self.nodes[n]['args']);uses.update(self.outputs)
            for nid in sorted(active):
                n=self.nodes[nid]
                if n['op'] not in ('xor','or'):continue
                for c in n['args']:
                    if c not in self.producer or uses[c]!=1:continue
                    child=self.nodes[self.producer[c]];other=[a for a in n['args'] if a!=c]
                    if child['op']==n['op'] and len(other)+len(child['args'])<=3:
                        merged=other+child['args']
                        if len(set(merged))!=len(merged):continue
                        n['args']=sorted(merged);changed=True;break
                    if n['op']=='xor' and len(n['args'])==2:
                        if child['op']=='and_var':n['op']='and_xor';n['args']=other+child['args'];n['imm']=None
                        elif child['op']=='and':n['op']='and_const_xor';n['args']=other+child['args'];n['imm']=child['imm']
                        elif child['op']=='or' and len(child['args'])==2:n['op']='or_xor';n['args']=other+child['args'];n['imm']=None
                        else:continue
                        changed=True;break
    def evaluate(self,inputs,raw_override=None):
        assert len(inputs)==10
        values={i:x&MASK for i,x in enumerate(inputs)};values[ZERO]=0
        active=self.active();wide_index={n:i for i,n in enumerate(self.products)}
        overrides={}
        if raw_override is not None:
            assert len(raw_override)==293
            for n,i in wide_index.items():overrides.update(zip(self.nodes[n]['out'],raw_override[2*i:2*i+2]))
            overrides.update(zip(self.corrections,raw_override[288:]))
        for n in self.nodes:
            if n['id'] not in active:continue
            if all(c in overrides for c in n['out']):out=[overrides[c]&MASK for c in n['out']]
            else:
                a=[values[c] for c in n['args']];k=n['imm'];op=n['op']
                if op=='wide':v=a[0]*a[1];out=[v&MASK,(v>>32)&MASK]
                else:
                    if op in ('xor','xor_mask'):
                        v=0
                        for x in a:v^=x
                        if op=='xor_mask':v&=k
                    elif op=='or':
                        v=0
                        for x in a:v|=x
                    elif op=='and':v=a[0]&k
                    elif op=='and_var':v=a[0]&a[1]
                    elif op=='and_xor':v=a[0]^(a[1]&a[2])
                    elif op=='and_const_xor':v=a[0]^(a[1]&k)
                    elif op=='or_xor':v=a[0]^(a[1]|a[2])
                    elif op=='shl':v=a[0]<<k
                    elif op=='shr':v=a[0]>>k
                    elif op=='sar':v=(a[0] if a[0]<(1<<31) else a[0]-(1<<32))>>k
                    elif op=='funnel_l':v=(a[1]<<k)|(a[0]>>(32-k))
                    elif op=='funnel_r':v=(a[0]>>k)|(a[1]<<(32-k))
                    else:raise AssertionError(op)
                    out=[v&MASK]
            values.update(zip(n['out'],out))
        return [values[c] for c in self.outputs]

def raw64(g,a,b,leaf):
    lo=leaf(a[0],b[0]);hi=leaf(a[1],b[1]);mid=leaf(g.xor(*a),g.xor(*b))
    m0=g.xor(mid[0],lo[0],hi[0]);m1=g.xor(mid[1],lo[1],hi[1])
    return [lo[0],g.xor(lo[1],m0),g.xor(hi[0],m1),hi[1]]

def raw128(g,a,b,leaf):
    lo=raw64(g,a[:2],b[:2],leaf);hi=raw64(g,a[2:],b[2:],leaf)
    mid=raw64(g,[g.xor(a[0],a[2]),g.xor(a[1],a[3])],[g.xor(b[0],b[2]),g.xor(b[1],b[3])],leaf)
    mid=[g.xor(x,y,z) for x,y,z in zip(mid,lo,hi)]
    return [lo[0],lo[1],g.xor(lo[2],mid[0]),g.xor(lo[3],mid[1]),g.xor(hi[0],mid[2]),g.xor(hi[1],mid[3]),hi[2],hi[3]]

def native_raw(g):
    groups=[[(0,0),(1,3),(2,2),(3,1)],[(0,1),(1,0),(2,3),(3,2)],[(0,2),(1,1),(2,0),(3,3)],[(0,3),(1,2),(2,1),(3,0)]]
    def leaf(a,b):
        aa=[g.and_(a,0x11111111<<i) for i in range(4)];bb=[g.and_(b,0x11111111<<i) for i in range(4)];parts=[[],[]]
        for cls,group in enumerate(groups):
            products=[g.wide(aa[i],bb[j]) for i,j in group]
            for half in range(2):parts[half].append(g.and_(g.xor(*(p[half] for p in products)),0x11111111<<cls))
        return [g.xor(*part) for part in parts]
    return raw128(g,list(range(4)),list(range(5,9)),leaf)

def high_correction(g):
    g.phase='tail';c=[ZERO]*9
    for k in range(3):
        ma=g.sar(g.shl(4,31-k),31);mb=g.sar(g.shl(9,31-k),31)
        for i in range(4):
            t=g.xor(g.and_var(i,mb),g.and_var(5+i,ma))
            c[4+i]=g.xor(c[4+i],g.shl(t,k))
            if k:c[5+i]=g.xor(c[5+i],g.shr(t,32-k))
        c[8]=g.xor(c[8],g.shl(g.and_var(9,ma),k))
    return c[4:]

def reduce(g,h):
    g.phase='reduce'
    d=[g.funnel_r(h[4+i],h[5+i],3) for i in range(4)]+[g.and_(g.shr(h[8],3),3)]
    def right(v,shift,i):
        off,bits=divmod(shift,32);j=i+off
        if j>4:return ZERO
        if not bits:return v[j]
        if j==4:return g.shr(v[j],bits) if bits<2 else ZERO
        return g.funnel_r(v[j],v[j+1],bits)
    def left(v,shift,i):
        off,bits=divmod(shift,32);j=i-off
        if j<0:return ZERO
        if not bits:return v[j]
        return g.funnel_l(v[j-1] if j else ZERO,v[j],bits)
    r=[g.xor(d[i],right(d,1,i),right(d,3,i)) for i in range(5)]
    q=[g.xor(d[i],*(right(r,k,i) for k in (1,9,25,57,121))) for i in range(5)]
    t=[g.xor(q[i],left(q,2,i),left(q,3,i)) for i in range(5)]
    out=[g.xor(h[i],t[i],*(left(t,k,i) for k in (64,96,112,120,128)),left(q,124,i)) for i in range(5)]
    out[4]=g.and_(out[4],7);return out

def baseline():
    g=Graph();h=native_raw(g)+[ZERO];g.corrections=high_correction(g)
    g.phase='reduce'
    for i,c in enumerate(g.corrections):h[4+i]=g.xor(h[4+i],c)
    g.outputs=reduce(g,h);g.fuse();assert len(g.products)==144;return g

def schedule(g):
    active=g.active();uses=Counter(c for n in active for c in g.nodes[n]['args']);consumers=defaultdict(list)
    for n in active:
        for c in g.nodes[n]['args']:consumers[c].append(n)
    dates={i:0 for i in range(10)};dates[ZERO]=0;wide_index={n:i+1 for i,n in enumerate(g.products)}
    node_dates={};product_dependent={i:False for i in range(10)};product_dependent[ZERO]=False
    for n in g.nodes:
        date=wide_index[n['id']] if n['op']=='wide' else max((dates[a] for a in n['args']),default=0)
        if n['phase']=='tail':date=max(date,len(g.products))
        dep=n['op']=='wide' or any(product_dependent[a] for a in n['args'])
        node_dates[n['id']]=date
        for c in n['out']:dates[c]=date;product_dependent[c]=dep
    live=set(range(10));available=live|{ZERO};pinned=set(g.outputs);done=set();events=[];peak=10;stage=0
    def execute(nid):
        nonlocal peak
        n=g.nodes[nid];assert all(c in live or c==ZERO for c in n['args'])
        live.update(n['out']);available.update(n['out']);peak=max(peak,len(live))
        for c in n['args']:
            uses[c]-=1
            if uses[c]==0 and c not in pinned:live.discard(c)
        for c in n['out']:
            if uses[c]==0 and c not in pinned:live.discard(c)
        events.append(nid);done.add(nid)
    def prep(c):
        if c in available:return
        n=g.nodes[g.producer[c]];assert n['phase']=='low' and not any(product_dependent[a] for a in n['args'])
        for a in n['args']:prep(a)
        execute(n['id'])
    def drain():
        while True:
            ready=[]
            for nid in sorted(active-done):
                n=g.nodes[nid]
                if n['op']=='wide' or node_dates[nid]>stage or not all(c in available for c in n['args']):continue
                if n['phase']=='low' and not any(product_dependent[c] for c in n['out']):continue
                count=Counter(n['args']);release=sum(uses[c]==v and c not in pinned for c,v in count.items())
                future=min((node_dates[user] for c in n['out'] for user in consumers[c] if user not in done),default=len(g.products))
                if stage<len(g.products) and release<=1 and future>stage:continue
                ready.append((-release,nid))
            if not ready:return
            execute(min(ready)[1])
    for stage,nid in enumerate(g.products,1):
        for c in g.nodes[nid]['args']:prep(c)
        execute(nid);drain()
    drain();assert done==active and live==pinned
    return dict(peakLiveWords=peak,wordOperations=len(active),events=events,finalLiveWords=len(live),deferNonShrinkingNodesUntilConsumerReady=True)

def expression(n,python=False):
    a=[('0' if python else '0u') if c==-1 else f'v{c}' for c in n['args']];op=n['op'];k=n['imm']
    mask=(str(k) if python else hex(k)+'u') if k is not None else None
    if op=='xor':e=' ^ '.join(a)
    elif op=='or':e=' | '.join(a)
    elif op=='xor_mask':e='('+(' ^ '.join(a))+') & '+mask
    elif op=='and':e=a[0]+' & '+mask
    elif op=='and_var':e=' & '.join(a)
    elif op=='and_xor':e=a[0]+' ^ ('+a[1]+' & '+a[2]+')'
    elif op=='and_const_xor':e=a[0]+' ^ ('+a[1]+' & '+mask+')'
    elif op=='or_xor':e=a[0]+' ^ ('+a[1]+' | '+a[2]+')'
    elif op=='shl':e=f'{a[0]} << {k}'
    elif op=='shr':e=f'{a[0]} >> {k}'
    elif op=='sar':
        assert k==31
        e=f'-( {a[0]} >> 31)' if python else f'0u - ({a[0]} >> 31)'
    elif op=='funnel_l':e=f'({a[1]} << {k}) | ({a[0]} >> {32-k})'
    elif op=='funnel_r':e=f'({a[0]} >> {k}) | ({a[1]} << {32-k})'
    else:raise AssertionError(op)
    return e

def emit_cpp(g,schedule):
    lines=['// Generated by codegen/genpackedproduct.py; do not edit.', '// Polynomial product and reduction modulo 0xd1d0d000d0000000d000000000000000d.', '// Included inside eccPacked131. The normal-basis inverse path is separate.','#pragma once','ECC_HD P131 generatedProduct131(P131 a, P131 b) {']
    for i in range(10):lines.append(f'    const uint32_t v{i} = {"a" if i<5 else "b"}.v[{i%5}];')
    event=0
    for nid in schedule:
        n=g.nodes[nid]
        if n['op']=='wide':
            lines.extend([f'    // native wide event {event}, coupled low/high',f'    const uint64_t w{event} = uint64_t(v{n["args"][0]}) * uint64_t(v{n["args"][1]});',f'    const uint32_t v{n["out"][0]} = uint32_t(w{event});',f'    const uint32_t v{n["out"][1]} = uint32_t(w{event} >> 32);']);event+=1
        else:lines.append(f'    const uint32_t v{n["out"][0]} = {expression(n)};')
    lines.extend(['    P131 out;']+[f'    out.v[{i}] = v{c};' for i,c in enumerate(g.outputs)]+['    return out;','}'])
    assert event==144
    return '\n'.join(lines)+'\n'


def generate():
    graph = baseline()
    ordered = schedule(graph)
    assert ordered['wordOperations'] == 562
    assert len(graph.products) == 144 and len(graph.corrections) == 5
    assert [nid for nid in ordered['events'] if graph.nodes[nid]['op'] == 'wide'] == graph.products
    return emit_cpp(graph, ordered['events'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'include' / 'packedgeneratedproduct131.h')
    parser.add_argument('--check', action='store_true', help='fail if the checked-in header differs; do not write it')
    args = parser.parse_args(argv)
    text = generate()
    if args.check:
        if not args.output.is_file() or args.output.read_text() != text:
            print(f'generated product header is stale or missing: {args.output}', file=sys.stderr)
            return 1
        print(f'generated product header is current: {args.output}')
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
