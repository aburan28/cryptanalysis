"""Opt-in independent decoder selection; native producer and replay unchanged."""
import ctypes as ct
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'round14'))
from native_descent import NativeDescent, PackedANF, packed_query

ARMS = ('baseline','row-check','ordered')


def library_path(arm, sanitizer=False):
    if arm not in ARMS:
        raise ValueError('unknown certificate variant')
    return HERE/'build'/(arm+('-ubsan' if sanitizer else '')+('.dylib' if sys.platform=='darwin' else '.so'))


def query(nvars, equations, arm='ordered', *, sanitizer=False):
    path = library_path(arm,sanitizer)
    result = packed_query(nvars,equations)
    try:
        library = ct.CDLL(str(path))
        method = library.packed_boolean_certificate
        method.argtypes = result._verifier.packed_boolean_certificate.argtypes
        method.restype = result._verifier.packed_boolean_certificate.restype
        result._verifier = library
        result.verifier_path = path
        return result
    except Exception:
        result.close()
        raise
