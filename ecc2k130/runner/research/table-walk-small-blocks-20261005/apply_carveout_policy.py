"""Patch only host launch policy in the frozen snapshot; default stays 16%."""
from pathlib import Path
import argparse,hashlib,json
EXPECTED_ENGINE_SHA256='5ff6296b9d0373582166167c75753dc8c8a3c1c57f2d612d341c0753d5d970b7'
def transform(text):
    assert hashlib.sha256(text.encode()).hexdigest()==EXPECTED_ENGINE_SHA256
    assert text.count('#pragma once\n')==1
    text=text.replace('#pragma once\n', '''#pragma once
#ifndef ECC_PACKED_SHARED_CARVEOUT
#define ECC_PACKED_SHARED_CARVEOUT 16
#endif
#if ECC_PACKED_SHARED_CARVEOUT < -1 || ECC_PACKED_SHARED_CARVEOUT > 100
#error "ECC_PACKED_SHARED_CARVEOUT must be -1 or an integer percentage from 0 to 100"
#endif
''',1)
    before='cudaFuncAttributePreferredSharedMemoryCarveout,16));'
    assert text.count(before)==1
    text=text.replace(before,'cudaFuncAttributePreferredSharedMemoryCarveout,ECC_PACKED_SHARED_CARVEOUT));',1)
    before='&activeCollectiveBlocks,eccPacked131::walk,ECC_THREADS,0));'
    assert text.count(before)==1
    text=text.replace(before,'&activeCollectiveBlocks,eccPacked131::walk,ECC_THREADS,dynamicSharedBytes()));',1)
    before='''printf("fused collective residency: warps/group=%d, shared-carveout=16 percent, active-blocks/SM=%d, active-warps/SM=%d\\n",
               ECC_COLLECTIVE_WARPS,activeCollectiveBlocks,activeCollectiveBlocks*ECC_THREADS/32);'''
    assert text.count(before)==1
    after='''printf("fused collective residency prediction: warps/group=%d, requested-carveout=%d percent, dynamic-shared=%zu bytes/block, active-blocks/SM=%d, active-warps/SM=%d\\n",
               ECC_COLLECTIVE_WARPS,ECC_PACKED_SHARED_CARVEOUT,dynamicSharedBytes(),activeCollectiveBlocks,activeCollectiveBlocks*ECC_THREADS/32);'''
    return text.replace(before,after,1)
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    path=args.root/'include/packedengine.cuh';updated=transform(path.read_text())
    path.write_text(updated)
    record=dict(baseline_sha256=EXPECTED_ENGINE_SHA256,patched_sha256=hashlib.sha256(updated.encode()).hexdigest(),
        default_requested_carveout=16,host_only=True,gpu_walk_instructions_must_match_before_execution=True,
        occupancy_query_dynamic_bytes='dynamicSharedBytes()',performance_b=None)
    (args.root/'CARVEOUT_POLICY_PATCH.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
if __name__=='__main__':main()
