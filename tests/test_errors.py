"""Tests for custom exceptions."""

import pytest

from pycoldb.errors import (
    ColumnFamilyAlreadyExistsError,
    ColumnFamilyNotFoundError,
    ColumnNotFoundError,
    InvalidTTLError,
    KeyspaceAlreadyExistsError,
    KeyspaceNotFoundError,
    PersistenceError,
    PyColDBError,
    RowNotFoundError,
)


class TestExceptionHierarchy:
    """Test that all exceptions inherit from PyColDBError."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            KeyspaceNotFoundError,
            KeyspaceAlreadyExistsError,
            ColumnFamilyNotFoundError,
            ColumnFamilyAlreadyExistsError,
            RowNotFoundError,
            ColumnNotFoundError,
            InvalidTTLError,
            PersistenceError,
        ],
    )
    def test_inherits_from_base(self, exc_class: type[PyColDBError]) -> None:
        """Verify each exception is a subclass of PyColDBError."""
        assert issubclass(exc_class, PyColDBError)

    @pytest.mark.parametrize(
        "exc_class",
        [
            KeyspaceNotFoundError,
            KeyspaceAlreadyExistsError,
            ColumnFamilyNotFoundError,
            ColumnFamilyAlreadyExistsError,
            RowNotFoundError,
            ColumnNotFoundError,
            InvalidTTLError,
            PersistenceError,
        ],
    )
    def test_exception_message(self, exc_class: type[PyColDBError]) -> None:
        """Verify exceptions store their message."""
        msg = "test error message"
        exc = exc_class(msg)
        assert str(exc) == msg

    def test_base_is_exception(self) -> None:
        """Verify PyColDBError inherits from Exception."""
        assert issubclass(PyColDBError, Exception)
