"""Command line entry point for the Python binding: ``python -m cryptanalysis``.

The C library has its own front end (``ca``), and this is not a second copy of
it. It exists for two reasons:

* the binding is the surface most people script against, and a CLI is the
  cheapest way to check that the shared library it found actually works — run
  ``python -m cryptanalysis version`` and you have verified loading, symbol
  resolution and the ABI in one step;
* a scripted pipeline that is already in Python should not have to shell out to
  ``ca`` and parse its JSON.

Every subcommand prints one JSON object on stdout. Exit status follows the same
convention as ``ca``: 0 for an answer, 1 for a well-posed question whose answer
is that there is none, 2 for a malformed invocation.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import cryptanalysis as ca


def _elem(text: str) -> Any:
    """Parse an element the way ``ca`` does: ``123``, ``x,y``, or ``inf``."""
    if text in ("inf", "O"):
        return ca.Elem(0, 0, True)
    if "," in text:
        x_str, y_str = text.split(",", 1)
        return ca.Elem(int(x_str, 0), int(y_str, 0))
    return int(text, 0)


def _show(elem: Any, kind: ca.GroupKind | None = None) -> Any:
    """Render an element for JSON, the way ``ca`` prints it.

    The binding represents both kinds of element with the same
    :class:`~cryptanalysis.Elem`, so the group's kind is what decides whether
    the ``y`` coordinate is meaningful. Printing ``"712551,0"`` for a member of
    Z_p^* would be wrong in a way that silently breaks round-tripping through
    ``--elem``.
    """
    if isinstance(elem, ca.Elem):
        if elem.inf:
            return "inf"
        if kind == ca.GroupKind.ZP:
            return str(elem.x)
        return f"{elem.x},{elem.y}"
    return str(elem)


def _group(args: argparse.Namespace) -> ca.Group:
    if args.group == "zp":
        return ca.Group.zp(args.p, args.order)
    return ca.Group.ec(args.p, args.a, args.b, args.order)


def _add_group_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--group", choices=("zp", "ec"), default="zp")
    sub.add_argument("--p", type=lambda s: int(s, 0), required=True)
    sub.add_argument("--a", type=lambda s: int(s, 0), default=0)
    sub.add_argument("--b", type=lambda s: int(s, 0), default=0)
    sub.add_argument("--order", type=lambda s: int(s, 0), default=0)


def _stats(st: ca.Stats) -> dict[str, Any]:
    return {
        "group_ops": st.group_ops,
        "iterations": st.iterations,
        "table_entries": st.table_entries,
        "collisions": st.collisions,
        "bytes_peak": st.bytes_peak,
        "seconds": round(st.seconds, 6),
        "threads": st.threads,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m cryptanalysis",
        description="Command line access to the cryptanalysis shared library.",
    )
    subs = p.add_subparsers(dest="cmd", required=True)

    subs.add_parser("version", help="library version and the path it was loaded from")

    q = subs.add_parser("prime", help="primality test and the next prime")
    q.add_argument("n", type=lambda s: int(s, 0))

    q = subs.add_parser("factor", help="factor a 64-bit integer")
    q.add_argument("n", type=lambda s: int(s, 0))

    q = subs.add_parser("powmod", help="modular exponentiation")
    q.add_argument("--base", type=lambda s: int(s, 0), required=True)
    q.add_argument("--exp", type=lambda s: int(s, 0), required=True)
    q.add_argument("--mod", type=lambda s: int(s, 0), required=True)

    q = subs.add_parser("invmod", help="modular inverse")
    q.add_argument("--a", type=lambda s: int(s, 0), required=True)
    q.add_argument("--mod", type=lambda s: int(s, 0), required=True)

    q = subs.add_parser("primitive-root", help="a generator of Z_p^*")
    q.add_argument("--p", type=lambda s: int(s, 0), required=True)

    q = subs.add_parser("group", help="group operations")
    q.add_argument(
        "op",
        choices=("info", "generator", "exp", "order", "random", "lift-x", "count-points"),
    )
    _add_group_args(q)
    q.add_argument("--elem")
    q.add_argument("--k", type=lambda s: int(s, 0), default=1)
    q.add_argument("--x", type=lambda s: int(s, 0), default=0)
    q.add_argument("--seed", type=lambda s: int(s, 0), default=0)

    q = subs.add_parser("solve", help="discrete logarithm")
    q.add_argument(
        "--alg",
        choices=("bsgs", "rho", "kangaroo", "grumpy", "precomp", "glv", "dlog"),
        default="dlog",
    )
    _add_group_args(q)
    q.add_argument("--g", required=True)
    q.add_argument("--h", required=True)
    q.add_argument("--lo", type=lambda s: int(s, 0), default=0)
    q.add_argument("--hi", type=lambda s: int(s, 0), default=0)
    q.add_argument("--threads", type=int, default=1)
    q.add_argument("--seed", type=lambda s: int(s, 0), default=0)
    q.add_argument("--dp-bits", type=int, default=-1, help="precomp: distinguished-point bits")
    q.add_argument("--table", type=lambda s: int(s, 0), default=0, help="precomp: chains to build")
    q.add_argument("--coverage", type=float, default=0.0, help="precomp: coverage factor")

    q = subs.add_parser("ic", help="index calculus in Z_p^*")
    q.add_argument("--p", type=lambda s: int(s, 0), required=True)
    q.add_argument("--g", type=lambda s: int(s, 0), required=True)
    q.add_argument("--h", type=lambda s: int(s, 0), required=True)
    q.add_argument("--threads", type=int, default=1)
    q.add_argument("--bound", type=int, default=0, help="factor base bound B")

    q = subs.add_parser("cheon", help="Cheon's attack against a planted alpha")
    _add_group_args(q)
    q.add_argument("--g", required=True)
    q.add_argument("--d", type=lambda s: int(s, 0), required=True)
    q.add_argument("--alpha", type=lambda s: int(s, 0), required=True)

    q = subs.add_parser("cheon-divisor", help="the divisor of p-1 Cheon does best with")
    q.add_argument("--p", type=lambda s: int(s, 0), required=True)

    q = subs.add_parser("curve", help="curve endomorphism (GLV) structure and chosen solver")
    q.add_argument("--name")
    q.add_argument("--p", type=lambda s: int(s, 0), default=0)
    q.add_argument("--a", type=lambda s: int(s, 0), default=0)
    q.add_argument("--b", type=lambda s: int(s, 0), default=0)
    q.add_argument("--order", type=lambda s: int(s, 0), default=0)
    q.add_argument("--list", action="store_true", help="list the registry curves")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out: dict[str, Any]

    if args.cmd == "version":
        out = {"version": ca.version(), "library": ca.library_path}

    elif args.cmd == "prime":
        out = {"n": args.n, "is_prime": ca.is_prime(args.n), "next_prime": ca.next_prime(args.n)}

    elif args.cmd == "factor":
        out = {"n": args.n, "factors": [[b, e] for b, e in ca.factorize(args.n)]}

    elif args.cmd == "powmod":
        out = {"result": str(ca.powmod(args.base, args.exp, args.mod))}

    elif args.cmd == "invmod":
        inv = ca.invmod(args.a, args.mod)
        if inv == 0:
            print(json.dumps({"invertible": False}))
            return 1
        out = {"invertible": True, "result": str(inv)}

    elif args.cmd == "primitive-root":
        root = ca.primitive_root(args.p)
        if root == 0:
            print(json.dumps({"found": False}))
            return 1
        out = {"found": True, "generator": str(root)}

    elif args.cmd == "group":
        if args.op == "count-points":
            out = {"order": ca.Group.ec_count_points(args.p, args.a, args.b)}
        else:
            with _group(args) as g:
                if args.op == "info":
                    out = {
                        "kind": g.kind.name.lower(),
                        "p": str(g.p),
                        "order": str(g.order),
                        "cofactor": str(g.cofactor),
                    }
                elif args.op == "generator":
                    gen = g.find_generator(args.seed)
                    out = {
                        "generator": _show(gen, g.kind),
                        "order": str(g.elem_order(gen)),
                    }
                elif args.op == "exp":
                    if args.elem is None:
                        raise SystemExit("group exp needs --elem")
                    out = {"result": _show(g.mul(_elem(args.elem), args.k), g.kind)}
                elif args.op == "order":
                    if args.elem is None:
                        raise SystemExit("group order needs --elem")
                    out = {"order": str(g.elem_order(_elem(args.elem)))}
                elif args.op == "random":
                    out = {"element": _show(g.random_element(args.seed), g.kind)}
                else:  # lift-x
                    try:
                        out = {"on_curve": True, "point": _show(g.lift_x(args.x), g.kind)}
                    except ca.CryptanalysisError:
                        print(json.dumps({"on_curve": False}))
                        return 1

    elif args.cmd == "solve":
        with _group(args) as g:
            opts = ca.Options(threads=args.threads, seed=args.seed)
            base, target = _elem(args.g), _elem(args.h)
            info = None
            try:
                if args.alg == "bsgs":
                    x, st = g.bsgs(base, target, args.lo, args.hi, opts)
                elif args.alg == "kangaroo":
                    x, st = g.kangaroo(base, target, args.lo, args.hi, opts)
                elif args.alg == "grumpy":
                    x, st = g.grumpy(base, target, args.lo, args.hi, opts)
                elif args.alg == "rho":
                    x, st = g.rho(base, target, opts)
                elif args.alg == "precomp":
                    x, st = g.precomp(
                        base,
                        target,
                        dp_bits=args.dp_bits,
                        table_size=args.table,
                        coverage=args.coverage,
                        threads=args.threads,
                        seed=args.seed,
                    )
                elif args.alg == "glv":
                    x, info, st = g.curve_solve(base, target, seed=args.seed)
                else:
                    x, st = g.dlog(base, target, opts)
            except ca.NotFoundError:
                print(json.dumps({"found": False}))
                return 1
            out = {"found": True, "x": str(x), "stats": _stats(st)}
            if info is not None:
                out["endomorphism"] = str(info.endo)
                out["aut_order"] = info.aut_order

    elif args.cmd == "ic":
        params = ca.ICParams(threads=args.threads, factor_base_bound=args.bound)
        # Bound to a distinct name: ic_solve returns ICStats, not the Stats the
        # group solvers return, and reusing `st` makes the two indistinguishable
        # to a reader and to a type checker.
        x, ic_st = ca.ic_solve(args.p, args.g, args.h, params)
        out = {
            "x": str(x),
            "factor_base": ic_st.factor_base_size,
            "relations": ic_st.relations,
            "total_seconds": round(ic_st.total_seconds, 6),
        }

    elif args.cmd == "cheon":
        with _group(args) as g:
            gen = _elem(args.g)
            g_alpha, g_alpha_d = g.cheon_instance(gen, args.alpha, args.d)
            try:
                alpha, st = g.cheon(gen, g_alpha, g_alpha_d, args.d)
            except ca.NotFoundError:
                print(json.dumps({"found": False}))
                return 1
            out = {
                "found": True,
                "alpha": str(alpha),
                "correct": alpha == args.alpha % g.order,
                "stats": _stats(st),
            }

    elif args.cmd == "cheon-divisor":
        d, cost = ca.cheon_best_divisor(args.p)
        out = {"divisor": str(d), "relative_cost": round(cost, 6)}

    else:  # curve
        if args.list:
            out = {"curves": ca.curve_names()}
        else:
            if args.name:
                p_, a_, b_, order_ = ca.curve_by_name(args.name)
            elif args.p:
                p_, a_, b_, order_ = args.p, args.a, args.b, args.order
            else:
                raise SystemExit("curve needs --name, --p, or --list")
            ci = ca.curve_detect(p_, a_, b_, order_)
            out = {
                "p": str(p_),
                "a": str(a_),
                "b": str(b_),
                "order": str(order_),
                "endomorphism": str(ci.endo),
                "aut_order": ci.aut_order,
                "beta": str(ci.beta),
                "lambda": str(ci.lambda_),
                "rho_speedup": round(ci.rho_speedup, 4),
                "solver": "glv-rho" if ci.endo != ca.CurveEndo.NONE else "rho",
            }

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
