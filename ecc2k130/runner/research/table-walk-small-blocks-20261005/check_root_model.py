"""Check actual GF(2^131) inverses under the proposed warp permutations."""
from pathlib import Path
import hashlib,json,random,shutil,subprocess
ROOT=Path(__file__).resolve().parent
POLICY=ROOT.parents[1]/"include/collective_root_policy.h"
import os,tempfile
WORK=Path(tempfile.mkdtemp(prefix="root-policy-check-",dir=os.environ.get("TMPDIR","/tmp")))
TERMS=(0,2,3,64,66,67,96,98,99,112,114,115,120,122,123,124,128,130,131)
MOD=sum(1<<i for i in TERMS)
def reduce(x):
    while x.bit_length()>131:x^=MOD<<(x.bit_length()-132)
    return x
def mul(a,b):
    out=0
    while b:
        if b&1:out^=a
        b>>=1;a<<=1
    return reduce(out)
def inv(a):
    if not a:return 0
    u,v,g,h=a,MOD,1,0
    while u!=1:
        if not u:raise RuntimeError('Noninvertible field input')
        j=u.bit_length()-v.bit_length()
        if j<0:u,v,g,h=v,u,h,g;j=-j
        u^=v<<j;g^=h<<j
    return reduce(g)
def tree(values,rotation):
    n=len(values);shared=[0]*n;acc=[0]*n;right={}
    for physical,value in enumerate(values):
        logical=(physical+rotation)%n
        shared[logical]=acc[logical]=value or 1
    levels=n.bit_length()-1
    for level in range(levels):
        width=1<<(level+1);offset=1<<level
        for k in range(width-1,n,width):
            right[level,k]=acc[k];acc[k]=mul(shared[k-offset],acc[k]);shared[k]=acc[k]
    shared[n-1]=inv(acc[n-1])
    for level in reversed(range(levels)):
        width=1<<(level+1);offset=1<<level
        for k in range(width-1,n,width):
            parent,left=shared[k],shared[k-offset]
            shared[k-offset],shared[k]=mul(parent,right[level,k]),mul(parent,left)
    return [shared[(physical+rotation)%n] if value else 0 for physical,value in enumerate(values)]
fixture=WORK/'root_policy_probe.cpp'
fixture.write_text('''#include <cstdio>
#include "collective_root_policy.h"
int main(){for(unsigned b: {0u,1u,169u,170u,339u,340u,510u,679u})
for(int g=0;g<ECC_THREADS/128;++g)std::printf("%u %d %d\\n",b,g,eccPacked131::collectiveRootRotation<4>(g,b));}
'''.replace('#include <cstdio>','#include <cstdio>\n#include <initializer_list>'))
rng=random.Random(13120261005);rows=[]
for label,threads,wave in (('control512',512,0),('hybrid256',256,0),('hybrid256wave',256,1),('hybrid128wave',128,1)):
    binary=WORK/('probe-'+label)
    cmd=['clang++','-O2','-std=c++17','-I',str(POLICY.parent),'-DECC_THREADS='+str(threads),'-DECC_COLLECTIVE_CTA_WAVE='+str(wave),str(fixture),'-o',str(binary)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=60);assert p.returncode==0,p.stderr
    p=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10);assert p.returncode==0
    checks=0
    for line in p.stdout.splitlines():
        block,group,rotation=map(int,line.split());want=(group+(block//170)*(threads//128))%4 if wave else group
        assert rotation==want
        for lane in range(32):
            values=[rng.getrandbits(131) for _ in range(4)]
            if lane%7==0:values[lane%4]=0
            if lane==1:values=[0,0,0,0]
            if lane==2:values=[1,1<<130,(1<<131)-1,0]
            got=tree(values,rotation);expected=[inv(v) for v in values]
            assert got==expected,(label,block,group,lane)
            assert all(mul(v,out)==1 for v,out in zip(values,got) if v)
            checks+=4
    rows.append(dict(profile=label,coordinate_inverses_checked=checks,rotation_probe_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),passed=True))
out=dict(passed=True,field_degree=131,field_modulus_terms=list(TERMS),rows=rows,
    total_coordinate_inverses_checked=sum(r['coordinate_inverses_checked'] for r in rows),
    scope='Portable policy and product-tree permutation correctness; no CUDA scheduling, point-update, or throughput claim',
    gpu_correctness=None,performance_b=None)
shutil.rmtree(WORK)
print(json.dumps(out,indent=2))
