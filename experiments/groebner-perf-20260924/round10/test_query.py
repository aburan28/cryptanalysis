"""Exact small-ring cross-checks, malformed inputs, reuse and capacity failures."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
import random

from hybrid_query import HybridQuery
from packed_query import PackedQuery
from boolean_basis import certify_boolean_basis
from descend import make_instance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpu',action='store_true')
    args = parser.parse_args()
    arms = ['cpu','gpu-direct','gpu-indirect'] if args.gpu else ['cpu']
    rng = random.Random(2026092511)
    checks = 0
    for n in range(1,8):
        with ExitStack() as stack:
            queries = [stack.enter_context(HybridQuery(n,5,backend=arm,degree=n)) for arm in arms]
            reference = stack.enter_context(PackedQuery(n,5))
            cases = [{},{0:1},{1:1},{0:1,1:1}]
            cases += [{m:rng.randrange(32) for m in range(1<<n) if rng.random()<0.15} for _ in range(12)]
            for anf in cases:
                expected = reference.compute(anf)
                assert expected['complete'], expected
                equations = [[m for m,c in anf.items() if c>>j&1] for j in range(5)]
                for query in queries:
                    result = query.compute(anf)
                    assert result['complete'], result
                    assert result['basis_sha256'] == expected['basis_sha256'], (n,anf,result,expected)
                    assert certify_boolean_basis(n,equations,result['basis_terms'])['verified']
                    checks += 1
            for query in queries:
                for bad in ({1<<n:1},{0:32},{-1:1},{0:-1}):
                    try:
                        query.compute(bad)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError(('invalid input accepted',bad))
    with HybridQuery(4,1,capacity=1) as query:
        failed = query.compute({1:1})
        assert not failed['complete'] and 'capacity' in failed['detail'], failed
        assert query.compute({})['complete']  # failure does not poison later queries
    query = HybridQuery(2,2)
    query.close()
    query.close()
    try:
        query.compute({})
    except RuntimeError:
        pass
    else:
        raise AssertionError('closed workspace accepted')
    # Shared and separate contexts both protect M4RI's allocation cache.
    with ExitStack() as stack:
        queries = [stack.enter_context(HybridQuery(5,2,backend=arms[i%len(arms)])) for i in range(4)]
        def task(i):
            result = queries[i%4].compute({1:1,2:2,0:i%4})
            assert result['complete']
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(task,range(32)))
    # Full query controls: equation evaluation, certified roots and curve replay.
    for ell in (2,3,4):
        instance = make_instance(31,3,ell,seed=1)
        with PackedQuery(3*ell,31) as query:
            reference = query.solve(instance)
        for arm in arms:
            with HybridQuery(3*ell,31,backend=arm) as query:
                result = query.solve(instance)
                assert result.get('verified'), result
                assert result['basis_sha256']==reference['basis_sha256']
                assert result['assignment']==reference['assignment']
                checks += 1
    print(json.dumps({'status':'PASS','arms':arms,'basis_checks':checks,
                      'concurrent_calls':32,'invalid_inputs_rejected':True,
                      'capacity_failure_retained':True,'closed_workspace_rejected':True}))


if __name__ == '__main__':
    main()
