"""Explicit Metal independent checker for the unchanged packed query producer."""
import ctypes as ct
from pathlib import Path
import sys
import threading

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'round15'))
from ordered_query import query as cpu_query, NativeDescent


class GPUStats(ct.Structure):
    _fields_=[(name,ct.c_double) for name in ('prepare','encode','execute','device','extract','total','spin')]+[
        ('gather_words',ct.c_uint64),('polls',ct.c_uint64),('calls',ct.c_uint32),('blocking_fallback',ct.c_uint32)]


class GPUVerifier:
    def __init__(self,n,e,prototype,sanitizer=False,spin_us=0):
        self.path=HERE/'build'/('gpu-certificate'+('-ubsan' if sanitizer else '')+'.dylib')
        self.lib=ct.CDLL(str(self.path))
        self.lib.gpu_certificate_stats_size.restype=ct.c_uint32
        if self.lib.gpu_certificate_stats_size()!=ct.sizeof(GPUStats):
            raise RuntimeError('GPU statistics ABI mismatch; rebuild the library')
        self.lib.gpu_certificate_error.restype=ct.c_char_p
        self.lib.gpu_certificate_create.argtypes=[ct.c_uint32,ct.c_uint32,ct.c_char_p,ct.c_uint32]
        self.lib.gpu_certificate_create.restype=ct.c_void_p
        self.lib.gpu_certificate_destroy.argtypes=[ct.c_void_p]
        self.lib.gpu_certificate_destroy.restype=None
        self.lib.gpu_certificate_device_name.argtypes=[ct.c_void_p]
        self.lib.gpu_certificate_device_name.restype=ct.c_char_p
        self.lib.gpu_certificate_compute.argtypes=[ct.c_void_p,*prototype.argtypes,ct.POINTER(GPUStats)]
        self.lib.gpu_certificate_compute.restype=ct.c_int
        self.lock=threading.Lock();self.local=threading.local()
        self.spin_us=spin_us
        self.handle=self.lib.gpu_certificate_create(n,e,str(HERE/'direct_truth.metal').encode(),spin_us)
        if not self.handle:
            raise RuntimeError(self.lib.gpu_certificate_error().decode())
        self.device_name=self.lib.gpu_certificate_device_name(self.handle).decode()

    def close(self):
        with self.lock:
            if self.handle:
                self.lib.gpu_certificate_destroy(self.handle)
                self.handle=None

    def packed_boolean_certificate(self,*args):
        with self.lock:
            if not self.handle: raise RuntimeError('GPU checker is closed')
            stats=GPUStats()
            code=self.lib.gpu_certificate_compute(self.handle,*args,ct.byref(stats))
            self.local.stats={name:getattr(stats,name) for name,_ in GPUStats._fields_}
            if code==7:
                raise RuntimeError(self.lib.gpu_certificate_error().decode() or 'GPU certificate failure')
            return code


def query(n,e,arm='gpu',*,sanitizer=False):
    if arm not in ('gpu','gpu-spin'): return cpu_query(n,e,arm,sanitizer=sanitizer)
    if not isinstance(n,int) or not 1<=n<=20 or not isinstance(e,int) or not 1<=e<=4096:
        raise ValueError('GPU certificate ring bounds')
    if ((1<<n)+63)//64*e*8>128*1024*1024:
        raise ValueError('GPU coefficient capacity exceeds 128 MiB')
    result=cpu_query(n,e,'ordered')
    try:
        verifier=GPUVerifier(n,e,result._verifier.packed_boolean_certificate,sanitizer,5000 if arm=='gpu-spin' else 0)
    except Exception:
        result.close();raise
    original_certify,original_close=result._certify,result.close
    result._verifier=verifier;result.verifier_path=verifier.path
    def certify(masks,coefficients,basis):
        answer=original_certify(masks,coefficients,basis)
        answer['backend']='independent-packed-decoder+metal-direct-anf'
        answer['evaluation_counts']={'gather_words':verifier.local.stats['gather_words']}
        answer['gpu_timing']=dict(verifier.local.stats)
        return answer
    def close():
        original_close();verifier.close()
    result._certify=certify;result.close=close
    return result
