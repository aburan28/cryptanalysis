"""Packed sparse F4 plus an independent native algebraic certificate checker.

Only libraries and fixed configuration persist. Every call owns fresh input,
producer state and proof values. No truth table or 2**n monomial array is used.
"""
from array import array
import ctypes as C
import hashlib
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'round5'))
from algebraic_certificate import verify as python_verify

U32,U64=C.c_uint32,C.c_uint64
P32,P64=C.POINTER(U32),C.POINTER(U64)


class PackedInput(C.Structure):
    _fields_=[('nvars',U32),('equations',U32),('terms',U64),('masks',P64),('coefficients',P64)]


class Node(C.Structure):
    _fields_=[('op',U32),('a',U32),('b',U64)]


class ProofView(C.Structure):
    _fields_=[(name,U32) for name in ('version','nvars','order','reserved')]+[
        (name,U64) for name in ('rows','terms','nodes')]+[
        ('basis_terms',P64),('offsets',P64),('graph',C.POINTER(Node)),('outputs',P32)]


class ProducerStats(C.Structure):
    _fields_=[(name,U64) for name in ('work','matrices','matrix_rows','peak_rows','pairs','nodes')]+[
        (name,C.c_double) for name in ('decode_seconds','produce_seconds','export_seconds','total_seconds')]+[('status',U32)]


class CheckStats(C.Structure):
    _fields_=[(name,U64) for name in ('work','retained_terms','proof_nodes','generator_checks',
        'basis_pairs','product_pairs_skipped','field_pairs','reduction_steps')]+[
        (name,C.c_double) for name in ('decode_seconds','derivation_seconds','membership_seconds',
            'reducedness_seconds','completion_seconds','total_seconds')]


def integer(value,lower,upper):
    if type(value) is not int or not lower<=value<upper:
        raise ValueError('integer outside its declared range')
    return value


def anf_from_equations(equations):
    """Fixture/legacy adapter. The native query itself takes packed ANF directly."""
    if not isinstance(equations,(tuple,list)) or len(equations)>4096:
        raise ValueError('equations must be a finite sequence with at most 4096 rows')
    anf={}
    for i,row in enumerate(equations):
        if not isinstance(row,(tuple,list,set,frozenset)):
            raise ValueError('equation must be a finite term collection')
        for mask in row:
            integer(mask,0,1<<64)
            anf[mask]=anf.get(mask,0)^(1<<i)
    return {m:c for m,c in anf.items() if c}


class InputOwner:
    def __init__(self,nvars,equations,anf):
        integer(nvars,1,65);integer(equations,0,4097)
        if not isinstance(anf,dict) or (not equations and anf):
            raise ValueError('packed ANF must be a coefficient dictionary')
        self.anf=dict(anf)
        integer(len(self.anf),0,1<<32)
        masks=array('Q');coefficients=array('Q');limbs=(equations+63)//64
        for mask,value in self.anf.items():
            masks.append(integer(mask,0,1<<nvars))
            integer(value,0,1<<equations)
            if limbs==1:
                coefficients.append(value)
            else:
                coefficients.extend((value>>(64*i))&((1<<64)-1) for i in range(limbs))
        self.masks=(U64*len(masks)).from_buffer(masks)
        self.coefficients=(U64*len(coefficients)).from_buffer(coefficients)
        self.view=PackedInput(nvars,equations,len(masks),self.masks,self.coefficients)

    def equations(self):
        rows=[[] for _ in range(self.view.equations)]
        for mask,bits in self.anf.items():
            while bits:
                low=bits&-bits;bits^=low;rows[low.bit_length()-1].append(mask)
        return rows


class ProofOwner:
    """Strict Python-to-C proof adapter for external/corrupted certificate tests."""
    def __init__(self,nvars,basis,proof):
        integer(nvars,1,65)
        if not isinstance(proof,dict) or type(proof.get('version')) is not int or proof['version']!=1 or \
                type(proof.get('nvars')) is not int or proof['nvars']!=nvars or proof.get('order')!='grevlex-x0-first':
            raise ValueError('proof ring/version/order mismatch')
        if not isinstance(basis,(tuple,list)) or len(basis)>1_000_000:
            raise ValueError('invalid basis shape')
        terms=[];offsets=[0]
        for row in basis:
            if not isinstance(row,(tuple,list,set,frozenset)):
                raise ValueError('invalid basis row')
            terms.extend(integer(m,0,1<<nvars) for m in row);offsets.append(len(terms))
        integer(len(terms),0,1<<32)
        nodes,outputs=proof.get('nodes'),proof.get('outputs')
        if not isinstance(nodes,list) or len(nodes)>10_000_000 or not isinstance(outputs,list) or len(outputs)!=len(basis):
            raise ValueError('invalid proof graph/output shape')
        graph=[]
        for node in nodes:
            if not isinstance(node,(tuple,list)) or not node:
                raise ValueError('malformed proof node')
            if node[0]=='input' and len(node)==2:
                graph.append(Node(0,integer(node[1],0,1<<32),0))
            elif node[0] in ('mul','xor') and len(node)==3:
                graph.append(Node(1 if node[0]=='mul' else 2,integer(node[1],0,1<<32),integer(node[2],0,1<<64)))
            else:
                raise ValueError('unsupported proof operation')
        self.terms=(U64*len(terms))(*terms);self.offsets=(U64*len(offsets))(*offsets)
        self.nodes=(Node*len(graph))(*graph)
        self.outputs=(U32*len(outputs))(*(integer(i,0,1<<32) for i in outputs))
        self.view=ProofView(1,nvars,1,0,len(basis),len(terms),len(graph),
                            self.terms,self.offsets,self.nodes,self.outputs)


def export(view):
    basis=[list(view.basis_terms[view.offsets[i]:view.offsets[i+1]]) for i in range(view.rows)]
    nodes=[]
    for i in range(view.nodes):
        node=view.graph[i]
        nodes.append(['input',node.a] if node.op==0 else ['mul' if node.op==1 else 'xor',node.a,node.b])
    proof={'version':view.version,'nvars':view.nvars,'order':'grevlex-x0-first',
           'nodes':nodes,'outputs':list(view.outputs[:view.rows])}
    return basis,proof


def fields(stats):
    return {name:getattr(stats,name) for name,_ in stats._fields_}


class PackedProof:
    def __init__(self,*,sanitizer=False):
        suffix=('-ubsan' if sanitizer else '')+('.dylib' if sys.platform=='darwin' else '.so')
        self.producer_path=HERE/'build'/('packed_producer'+suffix)
        self.checker_path=HERE/'build'/('native_checker'+suffix)
        self.producer=C.CDLL(str(self.producer_path));self.checker=C.CDLL(str(self.checker_path))
        self.producer.produce_packed.argtypes=[C.POINTER(PackedInput),U64,U32,U32,U32,C.POINTER(ProducerStats)]
        self.producer.produce_packed.restype=C.c_void_p
        self.producer.producer_view.argtypes=[C.c_void_p];self.producer.producer_view.restype=C.POINTER(ProofView)
        self.producer.producer_destroy.argtypes=[C.c_void_p];self.producer.producer_destroy.restype=None
        self.producer.producer_error.argtypes=[];self.producer.producer_error.restype=C.c_char_p
        self.checker.check_packed.argtypes=[C.POINTER(PackedInput),C.POINTER(ProofView),U64,U64,C.POINTER(CheckStats)]
        self.checker.check_packed.restype=C.c_int
        self.checker.checker_error.argtypes=[];self.checker.checker_error.restype=C.c_char_p
        self.binary_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.producer_path,self.checker_path)}

    def _check(self,input_view,proof_view,max_work,max_retained_terms):
        integer(max_work,0,1<<64);integer(max_retained_terms,0,1<<64)
        stats=CheckStats()
        code=self.checker.check_packed(C.byref(input_view),C.byref(proof_view),max_work,max_retained_terms,C.byref(stats))
        result={'verified':code==0,'status':('verified','rejected','inconclusive','checker-failure')[code],
            'method':'independent-native-derivation-DAG+Boolean-Buchberger','stats':fields(stats),
            'root_count':None,'solutions':None}
        if code:
            result['reason']=self.checker.checker_error().decode()
        else:
            result.update(ideal_equality=True,reduced_groebner_basis=True)
        return result

    def verify(self,nvars,equations,anf,basis,proof,*,max_work=20_000_000,max_retained_terms=2_000_000):
        try:
            original=InputOwner(nvars,equations,anf);certificate=ProofOwner(nvars,basis,proof)
            return self._check(original.view,certificate.view,max_work,max_retained_terms)
        except ValueError as error:
            return {'status':'rejected','verified':False,'reason':str(error)}

    def compute(self,nvars,equations,anf,*,max_work=20_000_000,max_nodes=1_000_000,
                max_rows=10_000,batch=64,max_check_work=20_000_000,max_retained_terms=2_000_000,
                checker='native',export_proof=False):
        start=time.perf_counter()
        integer(max_work,0,1<<64);integer(max_nodes,1,10_000_001);integer(max_rows,1,1_000_001)
        integer(batch,1,max_rows+1);integer(max_check_work,0,1<<64);integer(max_retained_terms,0,1<<64)
        if checker not in ('native','python'):
            raise ValueError('unknown checker')
        original=InputOwner(nvars,equations,anf);packing=time.perf_counter()-start
        stats=ProducerStats()
        handle=self.producer.produce_packed(C.byref(original.view),max_work,max_nodes,max_rows,batch,C.byref(stats))
        if not handle:
            return {'status':{1:'invalid-input',2:'inconclusive',3:'producer-failure'}.get(stats.status,'producer-failure'),
                'verified':False,'complete':False,'reason':self.producer.producer_error().decode(),
                'producer_stats':fields(stats),'packing_seconds':packing,'total_seconds':time.perf_counter()-start,
                'hard_subprocess_timeout':False}
        try:
            view=self.producer.producer_view(handle).contents
            phase=time.perf_counter()
            if checker=='native':
                certificate=self._check(original.view,view,max_check_work,max_retained_terms)
                # No Python graph construction lies on this verification path.
                basis=[list(view.basis_terms[view.offsets[i]:view.offsets[i+1]]) for i in range(view.rows)]
                proof=None
            else:
                basis,proof=export(view)
                certificate=python_verify(nvars,original.equations(),basis,proof,
                    max_work=max_check_work,max_retained_terms=max_retained_terms)
            verification=time.perf_counter()-phase
            if export_proof and proof is None:
                basis,proof=export(view)
            result={'status':'gb' if certificate['verified'] else ('inconclusive' if certificate['status']=='inconclusive' else 'verification-failed'),
                'complete':certificate['verified'],'verified':certificate['verified'],'basis':basis,
                'certificate':certificate,'producer_stats':fields(stats),'packing_seconds':packing,
                'verification_seconds':verification,'proof_nodes':view.nodes,'basis_terms':view.terms,
                'proof_payload_bytes':view.nodes*C.sizeof(Node)+view.rows*4+view.terms*8+(view.rows+1)*8,
                'hard_subprocess_timeout':False,'algorithm':'sparse-Boolean-F4-with-derivations',
                'transport':'packed-library','checker':checker,'binary_sha256':self.binary_sha256}
            if export_proof:result['proof']=proof
        finally:
            self.producer.producer_destroy(handle)
        result['total_seconds']=time.perf_counter()-start
        return result
