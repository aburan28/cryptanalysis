"""Opt-in ordering of exact checker obligations over unchanged packed producers."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('macaulay92_for93',HERE.parent/'round92/query.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
previous.HERE=HERE
previous.abi.HERE=HERE
abi=previous.abi
DenseInput=previous.DenseInput

class Query(previous.Query):
    def __init__(self,*,sanitizer=False,checker_order='legacy'):
        if checker_order not in ('legacy','proof-first','completion-first'):
            raise ValueError('unknown checker schedule')
        super().__init__(sanitizer=sanitizer)
        self.checker_order=checker_order
        suffix=('-ubsan' if sanitizer else '')+('.dylib' if sys.platform=='darwin' else '.so')
        path=HERE/'build'/('scheduled_checker'+suffix)
        self.ordered=C.CDLL(str(path))
        self.ordered.check_packed_ordered.argtypes=[C.POINTER(abi.PackedInput),C.POINTER(abi.ProofView),abi.U64,abi.U64,abi.U32,C.POINTER(abi.CheckStats)]
        self.ordered.check_packed_ordered.restype=C.c_int
        self.ordered.checker_error.argtypes=[];self.ordered.checker_error.restype=C.c_char_p
        self.binary_sha256[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        self.legacy_check=self.base._check
        self.base._check=self._check

    def compute(self,*args,**kwargs):
        result=super().compute(*args,**kwargs)
        result['checker_order']=self.checker_order
        return result

    def _check(self,input_view,proof_view,max_work,max_retained_terms):
        if self.checker_order=='legacy':
            result=self.legacy_check(input_view,proof_view,max_work,max_retained_terms)
        else:
            abi.integer(max_work,0,1<<64);abi.integer(max_retained_terms,0,1<<64)
            stats=abi.CheckStats()
            code=self.ordered.check_packed_ordered(C.byref(input_view),C.byref(proof_view),max_work,max_retained_terms,
                int(self.checker_order=='completion-first'),C.byref(stats))
            result=dict(verified=code==0,status=('verified','rejected','inconclusive','checker-failure')[code],
                method='independent-native-derivation-DAG+Boolean-Buchberger',stats=abi.fields(stats),root_count=None,solutions=None)
            if code: result['reason']=self.ordered.checker_error().decode()
            else: result.update(ideal_equality=True,reduced_groebner_basis=True)
        result['schedule']=self.checker_order
        return result

LayoutStats=previous.LayoutStats
MatrixStats=previous.MatrixStats
