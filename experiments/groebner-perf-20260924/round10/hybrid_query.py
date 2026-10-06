"""Bounded hybrid query experiment; CPU remains the default backend.

Packed ANF, ring-only reusable layouts, fresh coefficients and mutable state,
and the independent packed truth/staircase certificate from round four.
"""
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'round4'))
from packed_query import PackedQuery, Certificate, _views


class QueryStats(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ('basis_rows','matrix_rows','rank','f5_rows')] + [
        (name, ctypes.c_double) for name in ('decode','signature','generation','population','elimination',
            'extraction','total','gpu_prepare','gpu_encode','gpu_execute','gpu_device','gpu_extract')]


class HybridQuery(PackedQuery):
    def __init__(self, nvars, equations, *, degree=None, capacity=8192, backend='cpu'):
        degree = min(nvars, 8) if degree is None else degree
        if not all(isinstance(x, int) for x in (nvars,equations,degree,capacity)) or not (
                1 <= nvars <= 12 and 1 <= equations <= 64 and 0 <= degree <= nvars and 1 <= capacity <= 8192):
            raise ValueError('invalid hybrid configuration')
        if backend not in ('cpu','gpu-direct','gpu-indirect'):
            raise ValueError('invalid hybrid backend')
        self.nvars, self.equations, self.backend = nvars, equations, backend
        self._lock, self._handle = threading.Lock(), None
        suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        self.solver_path = HERE/'build'/('hybrid_query'+suffix)
        self.verifier_path = HERE.parent/'round4/build'/('packed_certificate'+suffix)
        self._solver = ctypes.CDLL(str(self.solver_path))
        self._verifier = ctypes.CDLL(str(self.verifier_path))
        u32, u64 = ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64)
        for name, restype, args in [
            ('hybrid_create',ctypes.c_void_p,[ctypes.c_uint32]*5+[ctypes.c_char_p]),
            ('hybrid_close',None,[ctypes.c_void_p]),
            ('hybrid_compute',ctypes.c_void_p,[ctypes.c_void_p,u32,u64,ctypes.c_uint32,ctypes.POINTER(QueryStats)]),
            ('hybrid_error',ctypes.c_char_p,[]),
            ('hybrid_row_size',ctypes.c_uint32,[ctypes.c_void_p,ctypes.c_uint32]),
            ('hybrid_row_data',u32,[ctypes.c_void_p,ctypes.c_uint32]),
            ('hybrid_destroy',None,[ctypes.c_void_p])]:
            fn = getattr(self._solver,name)
            fn.restype, fn.argtypes = restype, args
        self._verifier.packed_boolean_certificate.argtypes = [ctypes.c_uint32,ctypes.c_uint32,
            u32,u64,ctypes.c_uint32,u32,ctypes.c_uint32,u32,ctypes.c_uint32,ctypes.POINTER(Certificate)]
        self._verifier.packed_boolean_certificate.restype = ctypes.c_int
        self._binary_sha256 = hashlib.sha256(self.solver_path.read_bytes()).hexdigest()
        self._verifier_sha256 = hashlib.sha256(self.verifier_path.read_bytes()).hexdigest()
        self._handle = self._solver.hybrid_create(nvars,equations,degree,capacity,
            ('cpu','gpu-direct','gpu-indirect').index(backend),str(HERE.parent/'round7/local_panel.metal').encode())
        if not self._handle:
            raise RuntimeError(self._solver.hybrid_error().decode())

    def close(self):
        with self._lock:
            if self._handle:
                self._solver.hybrid_close(self._handle)
                self._handle = None

    def compute(self, anf):
        with self._lock:
            if not self._handle:
                raise RuntimeError('hybrid workspace is closed')
            start = time.perf_counter()
            masks, coefficients = _views(self.nvars,self.equations,anf)
            packing = time.perf_counter()-start
            stats = QueryStats()
            handle = self._solver.hybrid_compute(self._handle,masks,coefficients,len(masks),ctypes.byref(stats))
            if not handle:
                error = self._solver.hybrid_error().decode()
                if 'invalid' in error:
                    raise ValueError(error)
                return {'status':'inconclusive','complete':False,'verified':False,
                        'wall_seconds':time.perf_counter()-start,'detail':error}
            try:
                basis = [list(self._solver.hybrid_row_data(handle,i)[:self._solver.hybrid_row_size(handle,i)])
                         for i in range(stats.basis_rows)]
            finally:
                self._solver.hybrid_destroy(handle)
            wall = time.perf_counter()-start
            start = time.perf_counter()
            certificate = self._certify(masks,coefficients,basis)
            verification = time.perf_counter()-start
            return {'status':'gb' if certificate['verified'] else 'verification-failed',
                'complete':certificate['verified'],'basis_terms':basis,
                'basis_sha256':hashlib.sha256(json.dumps([sorted(g) for g in basis],sort_keys=True).encode()).hexdigest(),
                'basis_seconds':stats.total,'wall_seconds':wall,'packing_seconds':packing,
                'verification_seconds':verification,'basis_certificate':certificate,
                'groebner_verified':certificate['verified'],'generators_reduce_to_zero':certificate['verified'],
                'transport':'packed-library','hard_subprocess_timeout':False,
                'verifier':'independent-native-packed','algorithm':'bounded-signature-seed+macaulay+scalar-completion',
                'backend':self.backend,'metrics':{name:getattr(stats,name) for name,_ in stats._fields_},
                'binary_sha256':self._binary_sha256,'verifier_binary_sha256':self._verifier_sha256}
