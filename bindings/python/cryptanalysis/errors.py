"""Exception hierarchy mirroring the ``ca_status`` codes of libcryptanalysis."""

from __future__ import annotations

from enum import IntEnum


class Status(IntEnum):
    """``ca_status`` codes returned by every fallible library call."""

    OK = 0
    INVALID = 1
    NOT_FOUND = 2
    NOMEM = 3
    LIMIT = 4
    UNSUPPORTED = 5
    INTERNAL = 6
    SINGULAR = 7


class CryptanalysisError(Exception):
    """Base class for every error raised by the library.

    ``status`` is the raw ``ca_status`` code; ``message`` is the text taken
    from ``ca_last_error()`` when the library provided one, otherwise the
    generic ``ca_status_string()`` text.
    """

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status: int = int(status)
        self.message: str = message

    def __str__(self) -> str:
        return f"{self.message} (ca_status={self.status})"


class InvalidError(CryptanalysisError):
    """CA_ERR_INVALID: bad modulus, element not in the group, ..."""


class NotFoundError(CryptanalysisError):
    """CA_ERR_NOT_FOUND: the search space was exhausted without a solution."""


class NoMemoryError(CryptanalysisError):
    """CA_ERR_NOMEM: allocation failure inside the library."""


class LimitError(CryptanalysisError):
    """CA_ERR_LIMIT: an explicit work/memory/time limit was reached."""


class UnsupportedError(CryptanalysisError):
    """CA_ERR_UNSUPPORTED: the operation is not supported for this group/params."""


class InternalError(CryptanalysisError):
    """CA_ERR_INTERNAL: internal consistency failure (should not happen)."""


class SingularError(CryptanalysisError):
    """CA_ERR_SINGULAR: a linear system had no usable solution."""


_STATUS_TO_EXC: dict[int, type[CryptanalysisError]] = {
    Status.INVALID: InvalidError,
    Status.NOT_FOUND: NotFoundError,
    Status.NOMEM: NoMemoryError,
    Status.LIMIT: LimitError,
    Status.UNSUPPORTED: UnsupportedError,
    Status.INTERNAL: InternalError,
    Status.SINGULAR: SingularError,
}


def exception_for_status(status: int) -> type[CryptanalysisError]:
    """Return the exception class used for a non-zero ``ca_status``."""
    return _STATUS_TO_EXC.get(int(status), CryptanalysisError)
