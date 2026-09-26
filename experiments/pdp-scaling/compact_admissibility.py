"""Compact admissibility controls for E0 on the bounded toy PDP benchmark.

For odd n, x!=0 lies over the odd-order subgroup iff there exists t with
xt=1, Tr(x)=Tr(t)=Tr(x H(t^2))=0. H is the half trace. See COMPACT.md.
No factor-base payloads are enumerated by construction.
"""
from fixed_phase import Template


def admissible(F, x):
    if not x:
        return False
    t=F.inv(x)
    return (F.trace(x)==0 and F.trace(t)==0
            and F.trace(F.mul(x,F.half_trace(F.sqr(t))))==0)


class CompactTemplate(Template):
    def __init__(self,F,l,phases,encoding):
        if not (3<=F.n<=19 and F.n%2 and 1<=l<=min(8,F.n)):
            raise ValueError('compact control supports odd 3<=n<=19 and l<=8')
        super().__init__(F,l,phases,encoding)
        c,fc=self.c,self.fc
        trace_mask=[F.trace(1<<j) for j in range(F.n)]
        ht_basis=[F.half_trace(F.sqr(1<<j)) for j in range(F.n)]
        self.inverse=[]
        self.admissibility_outputs=[]
        def trace(w):
            return c.xor(*(v for v,b in zip(w,trace_mask) if b))
        for x in self.xs:
            t=fc.inputs();self.inverse.append(t)
            for wire in fc.add(fc.mul(x,t),fc.one):
                c.zero(wire)
            h=fc.linear(t,ht_basis)
            outputs=(trace(x),trace(t),trace(fc.mul(x,h)))
            self.admissibility_outputs.append(outputs)
            for wire in outputs:
                c.zero(wire)


class PowerCompactTemplate(Template):
    """Same trace predicate, with an inverse circuit instead of guessed bits."""
    def __init__(self,F,l,phases,encoding):
        if not (3<=F.n<=19 and F.n%2 and 1<=l<=min(8,F.n)):
            raise ValueError('compact control supports odd 3<=n<=19 and l<=8')
        super().__init__(F,l,phases,encoding)
        c,fc=self.c,self.fc
        trace_mask=[F.trace(1<<j) for j in range(F.n)]
        ht_basis=[F.half_trace(F.sqr(1<<j)) for j in range(F.n)]
        def trace(w):
            return c.xor(*(v for v,b in zip(w,trace_mask) if b))
        def frob(w,k):
            return fc.linear(w,[F.frob(1<<j,k) for j in range(F.n)])
        self.admissibility_outputs=[]
        self.inverse=[]
        for x in self.xs:
            powers={1:x}
            # Addition chain for A_k=x^(2^k-1), then inverse=A_(n-1)^2.
            def ak(k):
                if k not in powers:
                    if k%2:
                        powers[k]=fc.mul(fc.square(ak(k-1)),x)
                    else:
                        a=ak(k//2)
                        powers[k]=fc.mul(frob(a,k//2),a)
                return powers[k]
            t=fc.square(ak(F.n-1))
            self.inverse.append(t)
            outputs=(trace(x),trace(t),trace(fc.mul(x,fc.linear(t,ht_basis))))
            self.admissibility_outputs.append(outputs)
            for wire in outputs:
                c.zero(wire)
