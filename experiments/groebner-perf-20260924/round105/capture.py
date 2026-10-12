"""Capture an already certified native proof into pointer-free owned bytes."""
import ctypes as C
from dataclasses import dataclass
import struct
import sys


@dataclass(frozen=True)
class OwnedProof:
    nvars: int
    nodes: int
    outputs: int
    byteorder: str
    graph: bytes
    references: bytes

    @property
    def payload_bytes(self):
        return len(self.graph)+len(self.references)

    def serialized(self):
        # Artifact serialization is separate from the timed ownership transfer.
        if (self.byteorder not in ('little', 'big') or
                type(self.nvars) is not int or not 1 <= self.nvars <= 64 or
                type(self.nodes) is not int or not 0 <= self.nodes <= 10000000 or
                type(self.outputs) is not int or not 0 <= self.outputs <= 1000000 or
                type(self.graph) is not bytes or type(self.references) is not bytes or
                len(self.graph) != 16*self.nodes or len(self.references) != 4*self.outputs):
            raise ValueError('invalid owned proof envelope')
        header = struct.pack('<8sBBBBIQQ', b'GBPROOF1', 1,
            0 if self.byteorder == 'little' else 1, 1, 0,
            self.nvars, self.nodes, self.outputs)
        return header+self.graph+self.references


def capture(view, node_type):
    # Check the precise layout we copy; no native pointers survive this function.
    if C.sizeof(node_type) != 16 or (node_type.op.offset, node_type.a.offset, node_type.b.offset) != (0, 4, 8):
        raise ValueError('unsupported native proof node layout')
    if (view.version, view.order, view.reserved) != (1, 1, 0) or not 1 <= view.nvars <= 64:
        raise ValueError('unsupported proof envelope')
    if view.nodes > 10000000 or view.rows > 1000000:
        raise ValueError('proof copy shape exceeds the checked ABI')
    if (view.nodes and not view.graph) or (view.rows and not view.outputs):
        raise ValueError('missing proof copy buffer')
    graph = C.string_at(view.graph, 16*view.nodes) if view.nodes else b''
    outputs = C.string_at(view.outputs, 4*view.rows) if view.rows else b''
    return OwnedProof(view.nvars, view.nodes, view.rows, sys.byteorder, graph, outputs)
