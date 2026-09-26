"""Bounded public fixtures using exact odd-degree half-trace lifting."""
import random


def generate(curve,count,seed):
    field=curve.base_ring()
    degree=int(field.degree())
    if degree%2!=1 or field.characteristic()!=2:
        raise ValueError('fixture generator requires an odd-degree binary field')
    if tuple(curve.ainvs())[0]!=1 or curve.a3() or curve.a4():
        raise ValueError('unsupported binary curve model')
    choose=random.Random(seed)
    points=[];attempts=0
    while len(points)<count:
        attempts+=1
        if attempts>max(128,16*count):
            raise RuntimeError('public point generation cap reached')
        x=field.random_element()
        if not x:continue
        beta=x+curve.a2()+curve.a6()/(x*x)
        if beta.trace():continue
        z=beta
        for _ in range((degree-1)//2):
            z=z*z
            z=z*z+beta
        # An independent check of the half-trace equation precedes ordinary
        # Sage curve-membership validation in the constructor.
        if z*z+z!=beta:raise AssertionError('half-trace equation failed')
        if choose.getrandbits(1):z+=1
        points.append(curve(x,x*z))
    return points,attempts
