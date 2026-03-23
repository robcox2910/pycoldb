"""Tests for TTL (time-to-live) functionality."""

import time

import pytest

from pycoldb.column import Column
from pycoldb.column_family import ColumnFamily
from pycoldb.errors import ColumnNotFoundError
from pycoldb.ttl import TTLEntry, TTLManager

TTL_60_SECONDS = 60.0
TTL_30_SECONDS = 30.0
TIMESTAMP_1000 = 1000.0
CREATED_AT_1000 = 1000.0
CREATED_AT_100 = 100.0
TINY_TTL = 0.01


class TestTTLEntry:
    """Test the TTLEntry dataclass."""

    def test_expires_at(self) -> None:
        """Calculate expiration time correctly."""
        entry = TTLEntry(created_at=CREATED_AT_1000, ttl_seconds=TTL_60_SECONDS)
        expected_expiry = 1060.0
        assert entry.expires_at == expected_expiry

    def test_not_expired(self) -> None:
        """Verify entry is not expired before its time."""
        entry = TTLEntry(created_at=time.time(), ttl_seconds=TTL_60_SECONDS)
        assert not entry.is_expired()

    def test_expired(self) -> None:
        """Verify entry is expired after its time."""
        entry = TTLEntry(created_at=CREATED_AT_100, ttl_seconds=TTL_60_SECONDS)
        assert entry.is_expired()

    def test_is_expired_with_explicit_time(self) -> None:
        """Check expiration against an explicit time."""
        entry = TTLEntry(created_at=CREATED_AT_1000, ttl_seconds=TTL_60_SECONDS)
        check_time = 1059.0
        assert not entry.is_expired(current_time=check_time)
        expired_time = 1061.0
        assert entry.is_expired(current_time=expired_time)

    def test_serialization_roundtrip(self) -> None:
        """Verify TTLEntry roundtrip serialization."""
        original = TTLEntry(created_at=CREATED_AT_1000, ttl_seconds=TTL_60_SECONDS)
        restored = TTLEntry.from_dict(original.to_dict())
        assert restored.created_at == original.created_at
        assert restored.ttl_seconds == original.ttl_seconds


class TestTTLManager:
    """Test the TTLManager class."""

    def test_set_and_check_ttl(self) -> None:
        """Set a TTL and verify it's not yet expired."""
        manager = TTLManager()
        manager.set_ttl("row1", "col1", TTL_60_SECONDS)
        assert not manager.is_expired("row1", "col1")

    def test_no_ttl_means_not_expired(self) -> None:
        """Column without TTL should never be expired."""
        manager = TTLManager()
        assert not manager.is_expired("row1", "col1")

    def test_negative_ttl_raises(self) -> None:
        """Raise ValueError for negative TTL."""
        manager = TTLManager()
        with pytest.raises(ValueError, match="positive"):
            manager.set_ttl("row1", "col1", -1.0)

    def test_zero_ttl_raises(self) -> None:
        """Raise ValueError for zero TTL."""
        manager = TTLManager()
        with pytest.raises(ValueError, match="positive"):
            manager.set_ttl("row1", "col1", 0.0)

    def test_remove_ttl(self) -> None:
        """Remove a TTL and verify it no longer expires."""
        manager = TTLManager()
        manager.set_ttl("row1", "col1", TINY_TTL)
        manager.remove_ttl("row1", "col1")
        assert not manager.is_expired("row1", "col1")

    def test_remove_nonexistent_ttl(self) -> None:
        """Removing a nonexistent TTL should not raise."""
        manager = TTLManager()
        manager.remove_ttl("row1", "col1")  # no error

    def test_get_expired_columns(self) -> None:
        """Get all expired columns for a row."""
        manager = TTLManager()
        manager.set_ttl("row1", "col1", TINY_TTL)
        manager.set_ttl("row1", "col2", TTL_60_SECONDS)
        time.sleep(TINY_TTL)
        expired = manager.get_expired_columns("row1")
        assert "col1" in expired
        assert "col2" not in expired

    def test_entry_count(self) -> None:
        """Count tracked TTL entries."""
        manager = TTLManager()
        manager.set_ttl("row1", "col1", TTL_60_SECONDS)
        manager.set_ttl("row1", "col2", TTL_30_SECONDS)
        expected_count = 2
        assert manager.entry_count == expected_count

    def test_serialization_roundtrip(self) -> None:
        """Verify TTLManager roundtrip serialization."""
        manager = TTLManager()
        manager.set_ttl("row1", "col1", TTL_60_SECONDS)
        data = manager.to_dict()
        restored = TTLManager.from_dict(data)
        assert restored.entry_count == 1


class TestTTLWithColumnFamily:
    """Test TTL integration with ColumnFamily."""

    def test_put_with_ttl(self) -> None:
        """Insert a column with TTL."""
        cf = ColumnFamily(name="cache")
        cf.put(
            "key1",
            Column(name="data", value="temp", timestamp=TIMESTAMP_1000),
            ttl_seconds=TTL_60_SECONDS,
        )
        assert cf.get_column("key1", "data").value == "temp"

    def test_expired_column_raises(self) -> None:
        """Raise ColumnNotFoundError for expired columns."""
        cf = ColumnFamily(name="cache")
        cf.put(
            "key1",
            Column(name="data", value="temp", timestamp=TIMESTAMP_1000),
            ttl_seconds=TINY_TTL,
        )
        time.sleep(TINY_TTL)
        with pytest.raises(ColumnNotFoundError, match="expired"):
            cf.get_column("key1", "data")

    def test_put_without_ttl_clears_existing_ttl(self) -> None:
        """Overwriting a column without TTL clears the old TTL."""
        cf = ColumnFamily(name="cache")
        cf.put(
            "key1",
            Column(name="data", value="temp", timestamp=TIMESTAMP_1000),
            ttl_seconds=TINY_TTL,
        )
        cf.put("key1", Column(name="data", value="permanent", timestamp=TIMESTAMP_1000))
        time.sleep(TINY_TTL)
        # Should NOT raise because TTL was cleared
        assert cf.get_column("key1", "data").value == "permanent"
