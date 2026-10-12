"""Native-free decoder of the documented owned proof format.

Decoding establishes format and DAG shape only. Independent algebraic verification
against the original equations and claimed basis remains required for acceptance.
"""
import struct


def decode(data):
    if not isinstance(data, bytes) or len(data) < 32:
        raise ValueError('truncated proof header')
    magic, version, endian, order, reserved, nvars, nodes, outputs = struct.unpack_from('<8sBBBBIQQ', data)
    if (magic, version, order, reserved) != (b'GBPROOF1', 1, 1, 0) or endian not in (0, 1):
        raise ValueError('unsupported proof encoding')
    if not 1 <= nvars <= 64 or nodes > 10000000 or outputs > 1000000:
        raise ValueError('invalid proof shape')
    if len(data) != 32+16*nodes+4*outputs:
        raise ValueError('proof payload length mismatch')
    prefix = '<' if endian == 0 else '>'
    graph = []
    view = memoryview(data)
    for i, (op, a, b) in enumerate(struct.iter_unpack(prefix+'IIQ', view[32:32+16*nodes])):
        if op == 0:
            if b:
                raise ValueError('invalid input node padding')
            graph.append(['input', a])
        elif op == 1:
            if a >= i or b >= 1 << nvars:
                raise ValueError('invalid multiplication node')
            graph.append(['mul', a, b])
        elif op == 2:
            if a >= i or b >= i:
                raise ValueError('invalid XOR node')
            graph.append(['xor', a, b])
        else:
            raise ValueError('invalid proof opcode')
    references = [row[0] for row in struct.iter_unpack(prefix+'I', view[32+16*nodes:])]
    if any(i >= nodes for i in references):
        raise ValueError('invalid proof output reference')
    return dict(version=1, nvars=nvars, order='grevlex-x0-first', nodes=graph, outputs=references)
