"""Reusable input storage, with a lease spanning solving and independent checking."""
from contextlib import contextmanager
import ctypes as C
from pathlib import Path
import sys
import threading

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'round4'))
from descent_plan import DescentPlan

def integer(value,upper):
    if type(value) is not int or not 0<=value<upper:
        raise ValueError('integer outside the declared input range')
    return value

class BorrowedInput:
    """A synchronous, thread-owned view; invalid after its context exits."""
    def __init__(self,workspace,generation):
        self._workspace=workspace
        self._generation=generation
    def validate(self,nvars=None,equations=None,view_type=None):
        w=self._workspace
        if not w._ready or self._generation!=w._generation or w._owner!=threading.get_ident():
            raise RuntimeError('input lease is stale or belongs to another thread')
        if nvars is not None and (type(nvars) is not int or nvars!=w.nvars):
            raise ValueError('prepared input ring mismatch')
        if equations is not None and (type(equations) is not int or equations!=w.equations):
            raise ValueError('prepared input equation-count mismatch')
        if view_type is not None and view_type is not w._view_type:
            raise ValueError('prepared input belongs to a different query instance')
        return self
    @property
    def view(self):
        self.validate()
        return self._workspace._view
    def items(self):
        self.validate();w=self._workspace
        for index in range(w._count):
            self.validate()
            value=0
            for limb in range(w._limbs):
                value|=int(w._coefficients[index*w._limbs+limb])<<(64*limb)
            yield int(w._masks[index]),value
    def equations(self):
        self.validate();rows=[[] for _ in range(self._workspace.equations)]
        for mask,bits in self.items():
            while bits:
                low=bits&-bits;bits^=low;rows[low.bit_length()-1].append(mask)
        return rows
    def matches_mapping(self,mapping):
        self.validate()
        return len(mapping)==self._workspace._count and all(m in mapping and mapping[m]==v for m,v in self.items())

class InputWorkspace:
    """Bounded arrays for one declared support envelope, never cached answers."""
    def __init__(self,nvars,equations,support,*,view_type):
        integer(nvars,65);integer(equations,4097)
        if not nvars:raise ValueError('at least one variable is required')
        if not isinstance(support,(tuple,list)) or len(support)>1_048_576:
            raise ValueError('support exceeds the workspace slot limit')
        masks=tuple(integer(mask,1<<nvars) for mask in support)
        if len(set(masks))!=len(masks) or (not equations and masks):
            raise ValueError('support must be unique and empty for zero equations')
        self.nvars=nvars;self.equations=equations
        self._support=masks;self._allowed=frozenset(masks)
        self._limbs=(equations+63)//64;self._coefficient_limit=1<<equations
        words=len(masks)*self._limbs
        if words>4_194_304:raise ValueError('coefficient workspace exceeds 32 MiB')
        self._masks=(C.c_uint64*len(masks))()
        self._coefficients=(C.c_uint64*words)()
        self._view_type=view_type
        self._view=view_type(nvars,equations,0,self._masks,self._coefficients)
        self._lock=threading.Lock();self._owner=None
        self._generation=0;self._ready=False;self._count=0
    @property
    def buffer_addresses(self):
        return C.addressof(self._masks),C.addressof(self._coefficients)
    def _write(self,index,mask,value):
        self._masks[index]=mask
        if self._limbs==1:self._coefficients[index]=value
        else:
            for limb in range(self._limbs):
                self._coefficients[index*self._limbs+limb]=(value>>(64*limb))&((1<<64)-1)
    def _load_mapping(self,mapping):
        if not isinstance(mapping,dict):raise ValueError('expected a coefficient dictionary')
        if len(mapping)>len(self._support):raise ValueError('input exceeds the declared support envelope')
        for index,(mask,value) in enumerate(mapping.items()):
            integer(mask,1<<self.nvars)
            if mask not in self._allowed:raise ValueError('monomial outside the support envelope')
            integer(value,self._coefficient_limit)
            # Preserve mapping order and explicit zero slots exactly as the
            # original InputOwner does, including its partial decode budgets.
            self._write(index,mask,value)
        self._count=len(mapping)
    def _load_dense(self,values):
        if len(values)!=len(self._support):raise ValueError('dense coefficient shape mismatch')
        count=0
        for mask,value in zip(self._support,values):
            integer(value,self._coefficient_limit)
            if value:
                self._write(count,mask,value);count+=1
        # DescentPlan.descend() omits zero coefficients in this exact order.
        self._count=count
    @contextmanager
    def _borrow(self,loader):
        owner=threading.get_ident()
        if self._owner==owner:raise RuntimeError('nested borrowing would overwrite a live input')
        with self._lock:
            self._owner=owner;self._generation+=1;self._ready=False
            self._count=0;self._view.terms=0
            try:
                loader()
                self._view.terms=self._count;self._ready=True
                yield BorrowedInput(self,self._generation)
            finally:
                # Unused tail storage is never exposed: the next load rewrites
                # every active slot, then publishes its fresh compacted count.
                self._ready=False;self._view.terms=0;self._count=0
                self._generation+=1;self._owner=None
    def borrow_mapping(self,mapping):
        return self._borrow(lambda:self._load_mapping(mapping))
    def borrow_dense(self,values):
        return self._borrow(lambda:self._load_dense(values))

class PackedDescentPlan(DescentPlan):
    """The same ring-only contraction, writing into reusable native buffers."""
    def __init__(self,query,n,mod,b,m,ell):
        super().__init__(n,mod,b,m,ell)
        self.workspace=query.workspace(m*ell,n,self._masks)
    def _fill(self,x_target):
        integer(x_target,1<<self.shape[0])
        with self._lock:
            for buffer in self._buffers:
                for index in range(len(buffer)):buffer[index]=0
            powers={exponent:self._field.pow(x_target,exponent) for exponent in self._exponents}
            for destination,exponent,fixed in self._terms:
                self._buffers[0][destination]^=self._field.mul(powers[exponent],fixed)
            for index,stage in enumerate(self._stages):
                source,destination=self._buffers[index],self._buffers[index+1]
                for offset,edges in stage:
                    value=source[offset]
                    if value:
                        for target,table in edges:destination[target]^=table(value)
            self.workspace._load_dense(self._buffers[-1])
    def borrow(self,x_target):
        return self.workspace._borrow(lambda:self._fill(x_target))
