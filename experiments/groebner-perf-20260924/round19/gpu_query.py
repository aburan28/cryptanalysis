"""Opt-in complete GPU queries against the merged packed CPU implementation."""
import ctypes as ct
import hashlib
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
_path = sys.path[:]
try:
    sys.path.insert(0,str(HERE.parent/'round18'))
    from packed_checker import PackedChecker, PackedANF, Result, U32, U64, Curve, GF2n, Point, query as ordered_query
    from truth_query import TruthQuery
finally:
    sys.path[:] = _path

ARMS = ('cpu','gpu-blocking','gpu-poll')


class GPUStats(ct.Structure):
    _fields_ = [(name,ct.c_double) for name in ('prepare','encode','execute','device',
                 'extract','basis_check','total','spin')] + [
        (name,U64) for name in ('zeta_words','high_gather_words','shared_buffer_bytes','polls')] + [
        (name,U32) for name in ('calls','dispatches','blocking_fallback','threads')]


class GPUChecker(PackedChecker):
    def __init__(self,nvars,equations,*,poll_us=0,threads=256,sanitizer=False):
        if type(poll_us) is not int or not 0 <= poll_us <= 5000:
            raise ValueError('polling bound: 0..5000 microseconds')
        if type(threads) is not int or not 1 <= threads <= 1024:
            raise ValueError('threadgroup size: 1..1024')
        if sys.platform != 'darwin': raise RuntimeError('Metal requires macOS')
        # Reuse the pinned Python ABI and validation. The temporary CPU context
        # is released during setup; it never supplies roots to the GPU checker.
        super().__init__(nvars,equations,sanitizer=sanitizer)
        candidate = None
        try:
            path = HERE/'build'/('packed-gpu'+('-ubsan' if sanitizer else '')+'.dylib')
            lib = ct.CDLL(str(path))
            for name in ('truth_create','truth_destroy','truth_result_size','truth_certify','truth_evaluate'):
                fn, original = getattr(lib,name), getattr(self.lib,name)
                fn.argtypes, fn.restype = original.argtypes, original.restype
            lib.truth_gpu_error.restype = ct.c_char_p
            lib.truth_gpu_device.argtypes = [ct.c_void_p]
            lib.truth_gpu_device.restype = ct.c_char_p
            lib.truth_gpu_stats_size.restype = U64
            lib.truth_gpu_stats.argtypes = [ct.c_void_p,ct.POINTER(GPUStats)]
            lib.truth_gpu_stats.restype = ct.c_int
            lib.truth_gpu_configure.argtypes = [ct.c_void_p,U32,U32]
            lib.truth_gpu_configure.restype = ct.c_int
            if lib.truth_result_size() != ct.sizeof(Result) or lib.truth_gpu_stats_size() != ct.sizeof(GPUStats):
                raise RuntimeError('GPU ABI mismatch')
            candidate = lib.truth_create(nvars,equations)
            if not candidate: raise RuntimeError(lib.truth_gpu_error().decode())
            if lib.truth_gpu_configure(candidate,poll_us,threads):
                raise ValueError('device does not support requested configuration')
            binary_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            device = lib.truth_gpu_device(candidate).decode()
        except Exception:
            if candidate: lib.truth_destroy(candidate)
            super().close()
            raise
        self.lib.truth_destroy(self._handle)
        self.lib,self._handle,self.path = lib,candidate,path
        self.binary_sha256,self.device_name = binary_hash,device
        self.poll_us,self.threads = poll_us,threads
        # Keep the certificate and its statistics atomic across concurrent calls.
        self._lock = threading.RLock()

    def certify_views(self,masks,coefficients,basis):
        with self._lock:
            if not self._handle: raise RuntimeError('checker is closed')
            try:
                answer = super().certify_views(masks,coefficients,basis)
            except RuntimeError as error:
                detail = self.lib.truth_gpu_error().decode()
                raise RuntimeError(detail or str(error)) from error
            stats = GPUStats()
            if self.lib.truth_gpu_stats(self._handle,ct.byref(stats)):
                raise RuntimeError('GPU statistics unavailable')
            answer['backend'] = 'independent-packed-metal-tiled-zeta'
            answer['gpu_timing'] = {name:getattr(stats,name) for name,_ in GPUStats._fields_}
            if stats.device <= 0: answer['gpu_timing']['device'] = None
            answer['evaluation_counts']['high_gather_words'] = stats.high_gather_words
            return answer


class GPUQuery(TruthQuery):
    def __init__(self,n,mod,b,m,ell,arm='cpu',*,sanitizer=False,threads=256):
        if arm not in ARMS: raise ValueError('unknown complete-query arm')
        self.query_backend = arm
        super().__init__(n,mod,b,m,ell,'combined',sanitizer=sanitizer)
        try:
            if arm != 'cpu':
                checker = GPUChecker(m*ell,n,poll_us=5000 if arm=='gpu-poll' else 0,
                                     threads=threads,sanitizer=sanitizer)
                self.checker.close()
                self.checker = checker
                self.basis._certify = checker.certify_views
                self.basis.verifier_path = checker.path
        except Exception:
            self.close()
            raise

    def solve(self,target):
        answer = super().solve(target)
        answer['query_arm'] = self.query_backend
        answer['gpu_device'] = getattr(self.checker,'device_name',None)
        return answer
