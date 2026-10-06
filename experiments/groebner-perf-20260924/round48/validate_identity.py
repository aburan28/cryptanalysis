"""Every native coefficient versus equation-by-equation Boolean multiplication."""
import argparse
import ctypes as ct
import hashlib
import json
from pathlib import Path
import platform
import random
import sys

from identity_accounting import IDENTITY_MODES,per_record
from identity_reference import multiply_by_equation

HERE=Path(__file__).resolve().parent
U64=ct.c_uint64;U32=ct.c_uint32;U8=ct.c_ubyte


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    seed=202610014802;rng=random.Random(seed);cases=[]
    for y,e in ((1,1),(2,1),(3,1),(1,2),(2,2)):
        features=1+y+y*(y-1)//2;extent=features+y+1;mask=(1<<e)-1
        for encoded in range(1<<(e*extent)):
            values=[(encoded>>(j*e))&mask for j in range(extent)]
            cases.append((y,e,values[:features],values[features:],'exhaustive'))
    for y in range(1,11):
        features=1+y+y*(y-1)//2
        for e in (31,32,33,63,64,65,127,128):
            for _ in range(16):cases.append((y,e,[rng.getrandbits(e) for _ in range(features)],[rng.getrandbits(e) for _ in range(y+1)],'seeded-wide'))
            if e>64:cases.append((y,e,[(1|(1<<64))]*features,[(1|(1<<64))]*(y+1),'cross-limb-cancellation'))
            # Valid, invalid, valid on each reused native context.
            constant=[rng.getrandbits(e)&~1 for _ in range(features)];constant[0]|=1
            for bit in (1,0,1):
                coefficients=constant[:];coefficients[0]=(coefficients[0]&~1)|bit
                cases.append((y,e,coefficients,[1]+[0]*y,'fresh-constant'))
    prepared=[];case_digest=hashlib.sha256()
    for y,e,coefficients,witness,kind in cases:
        features=[m for m in range(1<<y) if m.bit_count()<=2]
        truth=multiply_by_equation(y,e,features,coefficients,witness)
        expected=bytes((truth>>m)&1 for m in range(1<<y))
        limbs=(e+63)//64
        def words(values):return [((v>>(64*l))&((1<<64)-1)) for v in values for l in range(limbs)]
        prepared.append((y,e,words(coefficients),words(witness),expected,truth==1,kind))
        case_digest.update(json.dumps([y,e,coefficients,witness,truth,kind],separators=(',',':')).encode())
    sources={str(HERE/name):sha(HERE/name) for name in ('multiplier.h','identity_test.cpp','identity_reference.py','identity_accounting.py','validate_identity.py')}
    rows=[];calls=comparisons=0;binaries={}
    for tag in ('','-ubsan'):
        path=HERE/'build'/('identity-test'+tag+('.dylib' if sys.platform=='darwin' else '.so'));binaries[str(path)]=sha(path)
        lib=ct.CDLL(str(path));lib.identity_create.argtypes=[U32,U32];lib.identity_create.restype=ct.c_void_p
        lib.identity_destroy.argtypes=[ct.c_void_p];lib.identity_destroy.restype=None
        lib.identity_replay.argtypes=[ct.c_void_p,U32,ct.POINTER(U64),U32,ct.POINTER(U64),U32,ct.POINTER(U8),U32,ct.POINTER(U64),U32];lib.identity_replay.restype=ct.c_int
        contexts={};histogram={}
        try:
            for index,(y,e,coefficients,witness,expected,valid,kind) in enumerate(prepared):
                key=y,e
                if key not in contexts:contexts[key]=lib.identity_create(y,e);assert contexts[key]
                a=(U64*len(coefficients))(*coefficients);u=(U64*len(witness))(*witness);out=(U8*(1<<y))();stats=(U64*13)()
                for mode,code in IDENTITY_MODES.items():
                    assert lib.identity_replay(contexts[key],code,a,len(a),u,len(u),out,len(out),stats,len(stats))==0
                    assert bytes(out)==expected,(tag,index,mode,y,e)
                    count=per_record(y,e,code)
                    for j,name in enumerate(('ands','accumulator_xors','witness_xors','identity_xors','parities','table_loads','cached_loads','copy_words')):assert stats[j]==count[name],(mode,name,stats[j],count[name])
                    assert stats[8]==valid and stats[9]==stats[10]==count['table_loads']
                    assert 0<stats[11]<=16384 and stats[12]==1+y+y*(y-1)//2+y*(y-1)*(y-2)//6
                    calls+=1;comparisons+=len(out);histogram[kind]=histogram.get(kind,0)+1
                if (index+1)%5000==0:print('IDENTITY_CASES_PASS',tag or 'optimized',index+1,flush=True)
            # Exact input extents, missing pointers, invalid modes and padding.
            a=(U64*8)();u=(U64*6)();out=(U8*4)();stats=(U64*13)();context=lib.identity_create(2,65);assert context
            try:
                assert lib.identity_replay(context,8,a,8,u,6,out,4,stats,13)==-1
                assert lib.identity_replay(context,0,a,7,u,6,out,4,stats,13)==-1
                assert lib.identity_replay(context,0,a,8,u,5,out,4,stats,13)==-1
                assert lib.identity_replay(context,0,a,8,u,6,out,3,stats,13)==-1
                assert lib.identity_replay(context,0,None,8,u,6,out,4,stats,13)==-1
                u[1]=2;assert lib.identity_replay(context,0,a,8,u,6,out,4,stats,13)==-1
                u[1]=0;a[1]=2;assert lib.identity_replay(context,0,a,8,u,6,out,4,stats,13)==-1
            finally:lib.identity_destroy(context)
            assert not lib.identity_create(0,31) and not lib.identity_create(11,31) and not lib.identity_create(2,129)
            rows.append({'build':tag or 'optimized','cases':len(prepared),'modes':list(IDENTITY_MODES),'calls':len(prepared)*len(IDENTITY_MODES),'histogram':histogram})
        finally:
            for context in contexts.values():lib.identity_destroy(context)
    for name,digest in {**sources,**binaries}.items():assert sha(Path(name))==digest,name
    result={'status':'PASS','schema':'independent-multiplier-coefficients/1','platform':platform.platform(),'architecture':platform.machine(),'seed':seed,'case_result_sha256':case_digest.hexdigest(),'cases_per_build':len(prepared),'native_calls':calls,'coefficient_comparisons':comparisons,'records':rows,'sources':sources,'binaries':binaries,'timing_eligible':False,'candidate_id':None,'online_speedup':None}
    args.output.write_text(json.dumps(result,indent=2)+'\n');print('NATIVE_IDENTITY_PASS',calls,comparisons,flush=True)


if __name__=='__main__':main()
