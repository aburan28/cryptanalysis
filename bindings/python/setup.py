"""Build libcryptanalysis from the C sources and ship it inside the package.

The pure-Python bindings load the shared library through ctypes; this file
only exists to compile ``../../src/*.c`` into
``cryptanalysis/libcryptanalysis.so`` (``.dylib`` on macOS) at install time.

Environment overrides:
    CC                  C compiler (default: ``cc``)
    CFLAGS              extra compiler flags appended to the defaults
    LDFLAGS             extra linker flags appended to the defaults
    CRYPTANALYSIS_SRC   repository root holding ``include/`` and ``src/``
                        (default: two directories above this file)
"""

from __future__ import annotations

import glob
import os
import shlex
import subprocess
import sys

from setuptools import Distribution, setup
from setuptools.command.build_ext import build_ext as _build_ext

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = "cryptanalysis"


def _repo_root() -> str:
    root = os.environ.get("CRYPTANALYSIS_SRC") or os.path.normpath(os.path.join(HERE, "..", ".."))
    if not os.path.isdir(os.path.join(root, "src")) or not os.path.isdir(
        os.path.join(root, "include")
    ):
        raise SystemExit(
            f"setup.py: C sources not found under {root!r} (expected src/ and include/).\n"
            "Install from a checkout of the cryptanalysis repository, or set "
            "CRYPTANALYSIS_SRC to the repository root."
        )
    return root


def _lib_filename() -> str:
    if sys.platform == "darwin":
        return "libcryptanalysis.dylib"
    if sys.platform == "win32":
        return "libcryptanalysis.dll"
    return "libcryptanalysis.so"


class build_ext(_build_ext):
    """Compile the C library with the system compiler instead of a Python extension."""

    def initialize_options(self) -> None:
        super().initialize_options()
        self.extensions = []

    def finalize_options(self) -> None:
        super().finalize_options()
        self.extensions = []

    def _output_dir(self) -> str:
        if self.inplace:
            return os.path.join(HERE, PACKAGE)
        return os.path.join(self.build_lib, PACKAGE)

    def _c_sources(self) -> list:
        return sorted(glob.glob(os.path.join(_repo_root(), "src", "*.c")))

    def get_source_files(self):
        # Deliberately empty.  The C sources live outside this project
        # directory (../../src), so they cannot be expressed as setup.py
        # relative paths; returning the absolute names here puts them into
        # egg-info's SOURCES.txt, and setuptools' build_py then aborts with
        # "setup script specifies an absolute path".  Use _c_sources()
        # internally instead.
        return []

    def get_outputs(self):
        return [os.path.join(self._output_dir(), _lib_filename())]

    def run(self) -> None:
        root = _repo_root()
        sources = self._c_sources()
        if not sources:
            raise SystemExit(f"setup.py: no C sources in {os.path.join(root, 'src')}")
        out_dir = self._output_dir()
        os.makedirs(out_dir, exist_ok=True)
        output = os.path.join(out_dir, _lib_filename())

        cc = shlex.split(os.environ.get("CC", "cc"))
        cflags = [
            "-O3",
            "-std=gnu11",
            "-fPIC",
            "-fvisibility=hidden",
            "-D_GNU_SOURCE",
            "-DCA_BUILDING",
            "-DCA_SHARED",
            "-I" + os.path.join(root, "include"),
            "-I" + os.path.join(root, "src"),
            *shlex.split(os.environ.get("CFLAGS", "")),
        ]
        if sys.platform == "darwin":
            link = ["-dynamiclib", "-install_name", "@rpath/" + _lib_filename()]
        else:
            link = ["-shared"]
        ldflags = ["-lpthread", "-lm", *shlex.split(os.environ.get("LDFLAGS", ""))]

        cmd = cc + cflags + link + ["-o", output] + sources + ldflags
        self.announce("building " + output, level=2)
        self.announce(" ".join(shlex.quote(c) for c in cmd), level=1)
        if not self.dry_run:
            subprocess.check_call(cmd)


class BinaryDistribution(Distribution):
    """Mark the wheel as platform-specific and make ``build`` run ``build_ext``."""

    def has_ext_modules(self) -> bool:
        return True


setup(
    distclass=BinaryDistribution,
    cmdclass={"build_ext": build_ext},
)
