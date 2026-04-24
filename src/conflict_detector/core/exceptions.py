from __future__ import annotations


class ConflictDetectorError(Exception):
    """Base exception for conflict detector."""


class ParserError(ConflictDetectorError):
    """Raised when DDL parsing fails."""


class UnsupportedDDLError(ParserError):
    """Raised when parser meets unsupported DDL construction."""


class GraphValidationError(ConflictDetectorError):
    """Raised when schema graph is structurally invalid."""


class OperationApplicationError(ConflictDetectorError):
    """Raised when operation cannot be applied to schema graph."""


class MergeError(ConflictDetectorError):
    """Raised when merge candidate cannot be constructed."""


class InvariantValidationError(ConflictDetectorError):
    """Raised when schema invariant validation fails unexpectedly."""
    