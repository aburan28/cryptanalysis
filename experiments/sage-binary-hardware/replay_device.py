"""Validate CUDA/HIP/OpenCL on supplied hardware without installing Sage.

Requires NumPy plus the appropriate CuPy or PyOpenCL installation. This tool
does not launch cloud resources or perform network operations. Its timings
describe packed coordinates, not the full Sage API.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import time
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--backend',choices=['cuda','hip','opencl'],required=True)
parser.add_argument('--device',type=int,default=0)
parser.add_argument('--fixture',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
if args.device<0:parser.error('device index must be nonnegative')
args.out.mkdir(parents=True,exist_ok=False)
manifest=json.loads((args.fixture/'manifest.json').read_text())
for name,digest in manifest['kernel_sha256'].items():
    assert hashlib.sha256((args.fixture/name).read_bytes()).hexdigest()==digest,name
started=time.perf_counter()
if args.backend in ('cuda','hip'):
    import cupy as cp
    is_hip=bool(cp.cuda.runtime.is_hip)
    if is_hip!=(args.backend=='hip'):
        raise RuntimeError('CuPy runtime does not match the requested CUDA/HIP backend')
    cp.cuda.Device(args.device).use()
    properties=cp.cuda.runtime.getDeviceProperties(args.device)
    name=properties['name']
    name=name.decode() if isinstance(name,bytes) else str(name)
    kernel=cp.RawKernel((args.fixture/'kernel.cuda').read_text(),'bh_map')
    kernel.compile()
    driver=str(cp.cuda.runtime.driverGetVersion())
else:
    import pyopencl as cl
    devices=[d for p in cl.get_platforms() for d in p.get_devices() if d.type & cl.device_type.GPU]
    if args.device>=len(devices):raise RuntimeError('requested OpenCL GPU is unavailable')
    device=devices[args.device]
    if not device.endian_little:raise RuntimeError('device byte order is unsupported')
    name=f'{device.vendor} {device.name}';driver=device.driver_version
    context=cl.Context([device]);queue=cl.CommandQueue(context)
    program=cl.Program(context,(args.fixture/'kernel.opencl').read_text()).build(options=['-cl-std=CL1.2'])
    kernel=cl.Kernel(program,'bh_map')
setup_seconds=time.perf_counter()-started
rows=[]
for case in manifest['cases']:
    path=args.fixture/case['file']
    assert path.stat().st_size<=16*1024*1024
    assert hashlib.sha256(path.read_bytes()).hexdigest()==case['sha256']
    with np.load(path,allow_pickle=False) as archive:
        table,data,expected=(np.ascontiguousarray(archive[k]) for k in ('table','data','expected'))
    words,bytes_=case['words'],case['bytes']
    assert 1<=words<=8 and 1<=bytes_<=32 and (bytes_+3)//4==words
    assert table.dtype==data.dtype==expected.dtype==np.dtype('uint32')
    assert table.shape==(bytes_*256*words,)
    assert data.ndim==2 and data.shape[1]==words and expected.shape==data.shape
    assert len(data)==case['coordinates'] and data.nbytes*2+table.nbytes<=512*1024*1024
    samples=[]
    if args.backend in ('cuda','hip'):
        device_table=cp.asarray(table)
        for _ in range(3):
            start=time.perf_counter()
            device_input=cp.asarray(data);device_output=cp.empty_like(device_input)
            kernel(((data.size+255)//256,),(256,),
                   (device_table,device_input,device_output,np.uint32(bytes_),np.uint32(words),np.uint32(len(data))))
            output=cp.asnumpy(device_output)
            assert np.array_equal(output,expected)
            samples.append(time.perf_counter()-start)
    else:
        device_table=cl.Buffer(context,cl.mem_flags.READ_ONLY|cl.mem_flags.COPY_HOST_PTR,hostbuf=table)
        for _ in range(3):
            start=time.perf_counter()
            device_input=cl.Buffer(context,cl.mem_flags.READ_ONLY|cl.mem_flags.COPY_HOST_PTR,hostbuf=data)
            device_output=cl.Buffer(context,cl.mem_flags.WRITE_ONLY,size=data.nbytes)
            event=kernel(queue,(data.size,),None,device_table,device_input,device_output,
                         np.uint32(bytes_),np.uint32(words),np.uint32(len(data)))
            output=np.empty_like(data)
            cl.enqueue_copy(queue,output,device_output,wait_for=[event]).wait()
            assert np.array_equal(output,expected)
            samples.append(time.perf_counter()-start)
    rows.append({**case,'exact_output_agreement':True,'validated_packed_seconds':samples})
    print(case['file'],'PASS',flush=True)
(args.out/'receipt.json').write_text(json.dumps({'backend':args.backend,'device':name,'driver':driver,
    'platform':platform.platform(),'setup_seconds':setup_seconds,'rows':rows,
    'fixture_manifest_sha256':hashlib.sha256((args.fixture/'manifest.json').read_bytes()).hexdigest(),
    'scope':'packed field-coordinate correctness; no full-Sage or cross-device speedup claim'},indent=2)+'\n')
