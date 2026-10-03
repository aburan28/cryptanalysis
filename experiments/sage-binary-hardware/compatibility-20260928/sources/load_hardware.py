"""Development loader: installed Sage plus the additive hardware module."""
import importlib.util
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
INSTALLED=os.environ.get('SAGE_BINARY_USE_INSTALLED')=='1'
if INSTALLED:
    if os.environ.get('SAGE_BINARY_NATIVE') or os.environ.get('SAGE_BINARY_CODEC'):
        raise RuntimeError('installed validation forbids development binary overrides')
    import sage.all
    from sage.schemes.elliptic_curves import binary_hardware as candidate
    SOURCE=Path(candidate.__file__)
else:
    SOURCE=ROOT/'third_party/sage-binary/src/sage/schemes/elliptic_curves/binary_hardware.py'
    os.environ.setdefault('SAGE_BINARY_NATIVE',str(HERE/('_binary_hardware_native.dylib' if sys.platform=='darwin'
                                                      else '_binary_hardware_native.so')))
    import sage.all
    spec=importlib.util.spec_from_file_location('sage_binary_hardware_candidate',SOURCE)
    candidate=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    if os.environ.get('SAGE_BINARY_CODEC'):
        codec_path=Path(os.environ['SAGE_BINARY_CODEC'])
        codec_spec=importlib.util.spec_from_file_location('binary_hardware_codec',codec_path)
        codec=importlib.util.module_from_spec(codec_spec)
        codec_spec.loader.exec_module(codec)
        candidate._codec=codec
FrobeniusPlan=candidate.FrobeniusPlan


def artifacts():
    import hashlib
    paths={'module':SOURCE,'native':Path(candidate._library()._name)}
    if candidate._codec is not None:
        paths['codec']=Path(candidate._codec.__file__)
    return {'installed':INSTALLED,'files':{k:{'path':str(p),
        'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in paths.items()}}
