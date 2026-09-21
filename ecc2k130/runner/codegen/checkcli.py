"""Every Modal entry-point parameter has to survive the round trip to the CLI.

Modal builds the flag as "--" + name.replace("_", "-"), and click derives the
keyword it hands back by lowercasing that and turning "-" into "_".  So a
capital letter never comes back: --minBlocksList arrives as minblockslist and
the call dies with "unexpected keyword argument".  The invariant is therefore
simply that an entry-point parameter is lowercase, and it is worth checking
because the failure is invisible until someone runs that entry point -- bench,
autotune, search and fanout were all unrunnable this way while validate and
merge, which happen to have only lowercase parameters, worked fine.

The repository is otherwise camelCase; this is the one boundary where an
outside tool dictates the spelling.

It also checks that every module-level name an entry point calls actually
exists.  Modal entry points are only executed by `modal run`, so a call to a
function that a refactor deleted is a NameError nobody sees until they try to
use it -- which is how ::autolab shipped calling a runAutolab that had been
removed from the file.
"""

import ast
import builtins
import sys


def entryPointParams(path):
    tree = ast.parse(open(path).read())
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and getattr(dec.func, 'attr', '') == 'local_entrypoint':
                # Every kind of named parameter, not just positional-or-keyword:
                # a keyword-only one is exactly where somebody would add the
                # next flag, and missing it would make this check useless in
                # the one case it exists for.
                a = node.args
                for arg in list(getattr(a, 'posonlyargs', [])) + list(a.args) + list(a.kwonlyargs):
                    yield node.name, arg.arg


def moduleNames(tree):
    """Every name bound at module level: defs, imports and assignments."""
    out = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                out.add((a.asname or a.name).split('.')[0])
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.add(node.target.id)
    return out


def localNames(fn):
    """Names the function binds itself: parameters, assignments, loop and with
    targets, comprehension variables."""
    a = fn.args
    out = {arg.arg for arg in
           list(getattr(a, 'posonlyargs', [])) + list(a.args) + list(a.kwonlyargs)}
    for arg in (a.vararg, a.kwarg):
        if arg is not None:
            out.add(arg.arg)
    for sub in ast.walk(fn):
        targets = []
        if isinstance(sub, ast.Assign):
            targets = sub.targets
        elif isinstance(sub, (ast.For, ast.AsyncFor, ast.comprehension)):
            targets = [sub.target]
        elif isinstance(sub, ast.withitem) and sub.optional_vars is not None:
            targets = [sub.optional_vars]
        elif isinstance(sub, ast.AnnAssign):
            targets = [sub.target]
        for t in targets:
            for nm in ast.walk(t):
                if isinstance(nm, ast.Name):
                    out.add(nm.id)
    return out


def entryPointCalls(tree):
    """(entry point, name) for every unresolved name an entry point calls.

    Only bare names count: a call through an attribute (`fn.remote`,
    `json.dumps`) resolves at run time against an object this cannot see, so
    what gets checked is the base of the chain.  Decorators are skipped -- the
    `app` in `@app.local_entrypoint()` is not a call the body makes."""
    module = moduleNames(tree)
    builtin = set(dir(builtins))
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not any(isinstance(d, ast.Call) and getattr(d.func, 'attr', '') == 'local_entrypoint'
                   for d in node.decorator_list):
            continue
        known = module | builtin | localNames(node)
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            f = sub.func
            while isinstance(f, ast.Attribute):
                f = f.value
            if isinstance(f, ast.Name) and f.id not in known:
                yield node.name, f.id


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'modal_app.py'
    bad = [(fn, p) for fn, p in entryPointParams(path) if p != p.lower()]
    for fn, p in bad:
        flag = '--' + p.replace('_', '-')
        print('%s: parameter %r becomes %s, which click hands back as %r'
              % (fn, p, flag, flag.lstrip('-').replace('-', '_').lower()))
    if bad:
        print('%d entry-point parameter(s) cannot be passed on the command line' % len(bad))
        return 1

    tree = ast.parse(open(path).read())
    missing = list(entryPointCalls(tree))
    for fn, name in missing:
        print('%s calls %s(), which is not defined in %s' % (fn, name, path))
    if missing:
        print('%d entry-point call(s) would raise NameError' % len(missing))
        return 1

    print('modal entry points: %d parameters all round-trip, every call resolves'
          % sum(1 for _ in entryPointParams(path)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
