"""Explicit proof retention policies over the unchanged packed algebra query."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('scheduled93_for94',HERE.parent/'round93/query.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
previous.HERE=HERE
previous.previous.HERE=HERE
previous.abi.HERE=HERE
abi=previous.abi
DenseInput=previous.DenseInput
LayoutStats=previous.LayoutStats
MatrixStats=previous.MatrixStats

class LiveStats(C.Structure):
    _fields_=[(n,abi.U64) for n in ('planning_work','metadata_bytes','live_terms','peak_terms','released_terms','released_nodes')]

class Query(previous.Query):
    def __init__(self,*,sanitizer=False,checker_order='legacy',retention='baseline'):
        if retention not in ('baseline','keep','release-cumulative','release-live'):
            raise ValueError('unknown proof retention policy')
        self.retention=retention
        super().__init__(sanitizer=sanitizer,checker_order=checker_order)
        suffix=('-ubsan' if sanitizer else '')+('.dylib' if sys.platform=='darwin' else '.so')
        path=HERE/'build'/('live_checker'+suffix)
        self.live=C.CDLL(str(path))
        self.live.check_packed_live.argtypes=[C.POINTER(abi.PackedInput),C.POINTER(abi.ProofView),abi.U64,abi.U64,abi.U32,abi.U32,C.POINTER(abi.CheckStats),C.POINTER(LiveStats)]
        self.live.check_packed_live.restype=C.c_int
        self.live.checker_error.argtypes=[];self.live.checker_error.restype=C.c_char_p
        self.live.liveness_stats_size.restype=abi.U64
        assert self.live.liveness_stats_size()==C.sizeof(LiveStats)
        self.binary_sha256[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()

    def compute(self,*args,**kwargs):
        result=super().compute(*args,**kwargs);result['retention_policy']=self.retention
        return result

    def _check(self,input_view,proof_view,max_work,max_retained_terms):
        if self.retention=='baseline':
            result=super()._check(input_view,proof_view,max_work,max_retained_terms)
        else:
            abi.integer(max_work,0,1<<64);abi.integer(max_retained_terms,0,1<<64)
            stats=abi.CheckStats();live=LiveStats()
            policy={'keep':0,'release-cumulative':1,'release-live':2}[self.retention]
            code=self.live.check_packed_live(C.byref(input_view),C.byref(proof_view),max_work,max_retained_terms,
                int(self.checker_order=='completion-first'),policy,C.byref(stats),C.byref(live))
            result=dict(verified=code==0,status=('verified','rejected','inconclusive','checker-failure')[code],
                method='independent-native-derivation-DAG+Boolean-Buchberger',stats=abi.fields(stats),liveness=abi.fields(live),
                root_count=None,solutions=None,schedule=self.checker_order)
            if code:result['reason']=self.live.checker_error().decode()
            else:result.update(ideal_equality=True,reduced_groebner_basis=True)
        result['retention_policy']=self.retention
        return result
