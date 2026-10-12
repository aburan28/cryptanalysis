"""Opt-in reusable matrix layouts; only independently checked results escape."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys
import threading
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('packed92',HERE.parent/'round11/packed_proof.py')
abi=importlib.util.module_from_spec(spec)
spec.loader.exec_module(abi)
abi.HERE=HERE

class LayoutStats(C.Structure):
    _fields_=[(n,abi.U64) for n in ('support','columns','multipliers','rows','payload_bytes')]+[
        ('total_seconds',C.c_double),('status',abi.U32)]

class MatrixStats(C.Structure):
    _fields_=[(n,abi.U64) for n in ('work','rows','forward_xors','backward_xors','word_xors',
        'pivots','kept_rows','nodes','output_nodes','peak_payload_words')]+[
        (n,C.c_double) for n in ('decode_seconds','elimination_seconds','extraction_seconds','total_seconds')]+[('status',abi.U32)]

class Layout:
    def __init__(self,query,nvars,equations,degree,multiplier_degree,*,max_bytes=64*1024*1024):
        for v,maximum in ((nvars,65),(equations,4097),(degree,65),(multiplier_degree,65),(max_bytes,1<<64)):
            abi.integer(v,0,maximum)
        self.query=query
        self._lock=threading.RLock()
        self._handle=None
        self.shape=(nvars,equations,degree,multiplier_degree)
        stats=LayoutStats()
        self._handle=query.lib.macaulay_layout_create(*self.shape,max_bytes,C.byref(stats))
        self.stats=abi.fields(stats)
        if not self._handle:
            self.reason=query.lib.macaulay_error().decode()
            self.support=()
        else:
            self.reason=None
            self.support=tuple(query.lib.macaulay_layout_support(self._handle)[:stats.support])

    def close(self):
        with self._lock:
            if self._handle:
                self.query.lib.macaulay_layout_destroy(self._handle)
                self._handle=None

    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def __del__(self):
        if getattr(self,'_handle',None): self.close()

class DenseInput:
    """Immutable fixture transport. Construction stays outside the algebra query."""
    def __init__(self,nvars,rows,support):
        self.originals=[list(row) for row in rows]
        self.nvars=nvars
        self.count=len(rows)
        # The fixture adapter is not used on the native compute path.
        packed=abi.anf_from_equations(rows)
        if set(packed)-set(support): raise ValueError('input outside declared support envelope')
        self.masks=(abi.U64*(len(support) if rows else 0))(*(support if rows else ()))
        limbs=(len(rows)+63)//64
        coefficients=[(packed.get(m,0)>>(64*k))&((1<<64)-1) for m in support for k in range(limbs)]
        self.coefficients=(abi.U64*len(coefficients))(*coefficients)
        self.view=abi.PackedInput(nvars,len(rows),len(self.masks),self.masks,self.coefficients)

    def equations(self):
        # Comparator conversion is charged inside its call.
        rows=[[] for _ in range(self.count)]
        limbs=(self.count+63)//64
        for i,m in enumerate(self.masks):
            for k in range(limbs):
                bits=int(self.coefficients[i*limbs+k])
                while bits:
                    bit=bits&-bits
                    rows[k*64+bit.bit_length()-1].append(m)
                    bits^=bit
        return rows

class Query:
    def __init__(self,*,sanitizer=False):
        self.base=abi.PackedProof(sanitizer=sanitizer)
        suffix=('-ubsan' if sanitizer else '')+('.dylib' if sys.platform=='darwin' else '.so')
        path=HERE/'build'/('macaulay'+suffix)
        self.lib=C.CDLL(str(path))
        self.lib.macaulay_layout_create.argtypes=[abi.U32,abi.U32,abi.U32,abi.U32,abi.U64,C.POINTER(LayoutStats)]
        self.lib.macaulay_layout_create.restype=C.c_void_p
        self.lib.macaulay_layout_destroy.argtypes=[C.c_void_p]
        self.lib.macaulay_layout_destroy.restype=None
        self.lib.macaulay_layout_support.argtypes=[C.c_void_p]
        self.lib.macaulay_layout_support.restype=abi.P64
        self.lib.macaulay_apply.argtypes=[C.c_void_p,C.POINTER(abi.PackedInput),abi.U64,abi.U32,abi.U32,C.POINTER(MatrixStats)]
        self.lib.macaulay_apply.restype=C.c_void_p
        self.lib.macaulay_view.argtypes=[C.c_void_p]
        self.lib.macaulay_view.restype=C.POINTER(abi.ProofView)
        self.lib.macaulay_result_destroy.argtypes=[C.c_void_p]
        self.lib.macaulay_result_destroy.restype=None
        self.lib.macaulay_error.argtypes=[]
        self.lib.macaulay_error.restype=C.c_char_p
        self.lib.macaulay_stats_size.restype=abi.U64
        self.lib.macaulay_layout_stats_size.restype=abi.U64
        assert self.lib.macaulay_stats_size()==C.sizeof(MatrixStats)
        assert self.lib.macaulay_layout_stats_size()==C.sizeof(LayoutStats)
        self.binary_sha256={**self.base.binary_sha256,path.name:hashlib.sha256(path.read_bytes()).hexdigest()}

    def layout(self,*args,**kwargs): return Layout(self,*args,**kwargs)

    def compute(self,original,*,layout=None,fresh_shape=None,fallback=True,max_work=2_000_000,
                matrix_cap=1_000_000,max_check_work=20_000_000,max_terms=2_000_000,
                max_nodes=1_000_000,max_rows=10000,batch=64,export_proof=False):
        start=time.perf_counter()
        for v in (max_work,matrix_cap,max_check_work,max_terms): abi.integer(v,0,1<<64)
        abi.integer(max_nodes,1,10_000_001);abi.integer(max_rows,1,1_000_001);abi.integer(batch,1,max_rows+1)
        if fresh_shape is not None and layout is not None: raise ValueError('choose one layout policy')
        temporary=None
        if fresh_shape is not None:
            temporary=layout=self.layout(*fresh_shape)
        attempts=[]
        remaining,check_remaining=max_work,max_check_work
        answer=dict(status='inconclusive',verified=False,complete=False)
        try:
            if layout is not None:
                if layout.query is not self: raise ValueError('layout belongs to another query')
                with layout._lock:
                    if not layout._handle:
                        if layout.reason is None: raise RuntimeError('layout is closed')
                        attempts.append(dict(kind='matrix-layout',verified=False,stats=dict(work=0,status=layout.stats['status']),reason=layout.reason,layout_stats=layout.stats))
                    else:
                        stats=MatrixStats()
                        handle=self.lib.macaulay_apply(layout._handle,C.byref(original.view),min(remaining,matrix_cap),max_nodes,max_rows,C.byref(stats))
                        remaining-=stats.work
                        attempt=dict(kind='macaulay',verified=False,stats=abi.fields(stats),layout_stats=layout.stats)
                        if handle:
                            try:
                                view=self.lib.macaulay_view(handle).contents
                                cert=self.base._check(original.view,view,check_remaining,max_terms)
                                check_remaining-=cert['stats']['work']
                                attempt.update(verified=cert['verified'],certificate=cert)
                                if cert['verified']: answer=self._answer(view,cert,export_proof)
                            finally:
                                self.lib.macaulay_result_destroy(handle)
                        else: attempt['reason']=self.lib.macaulay_error().decode()
                        attempts.append(attempt)
            if not answer['verified'] and (layout is None or fallback):
                stats=abi.ProducerStats()
                handle=self.base.producer.produce_packed(C.byref(original.view),remaining,max_nodes,max_rows,batch,C.byref(stats))
                remaining-=stats.work
                attempt=dict(kind='fresh-f4',verified=False,stats=abi.fields(stats))
                if handle:
                    try:
                        view=self.base.producer.producer_view(handle).contents
                        cert=self.base._check(original.view,view,check_remaining,max_terms)
                        check_remaining-=cert['stats']['work']
                        attempt.update(verified=cert['verified'],certificate=cert)
                        if cert['verified']: answer=self._answer(view,cert,export_proof)
                    finally: self.base.producer.producer_destroy(handle)
                else: attempt['reason']=self.base.producer.producer_error().decode()
                attempts.append(attempt)
        finally:
            if temporary: temporary.close()
        if not answer['verified'] and attempts:
            last=attempts[-1]
            answer['status']={1:'invalid-input',2:'inconclusive',3:'producer-failure'}.get(last['stats']['status'],last.get('certificate',{}).get('status','inconclusive'))
        answer.update(attempts=attempts,work=max_work-remaining,check_work=max_check_work-check_remaining,
            total_seconds=time.perf_counter()-start,timing_eligible=False,qualified_speedup=None,
            layout_policy='fresh' if fresh_shape else ('reused' if layout else 'none'))
        return answer

    @staticmethod
    def _answer(view,cert,export_proof):
        basis=[list(view.basis_terms[view.offsets[i]:view.offsets[i+1]]) for i in range(view.rows)]
        answer=dict(status='gb',verified=True,complete=True,basis=basis,certificate=cert)
        if export_proof: _,answer['proof']=abi.export(view)
        return answer
