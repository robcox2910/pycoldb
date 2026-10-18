"""Tests for TTL (time-to-live) functionality."""

import time

import pytest

from pycoldb.column import Column
from pycoldb.column_family import ColumnFamily
from pycoldb.errors import ColumnNotFoundError, InvalidTTLError
from pycoldb.query import column_filter, query_with_filter, range_query
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

    def test_invalid_ttl_raises_invalidttlerror(self) -> None:
        """set_ttl raises the dedicated InvalidTTLError, not a bare ValueError."""
        manager = TTLManager()
        with pytest.raises(InvalidTTLError, match="positive"):
            manager.set_ttl("row1", "col1", 0.0)

    def test_colon_keys_do_not_collide(self) -> None:
        """Row/column names containing a colon must not share a TTL entry."""
        manager = TTLManager()
        # With a naive "row:col" string key these two pairs would map to
        # the same "a:b:c" key and clobber each other.
        manager.set_ttl("a:b", "c", TTL_60_SECONDS)
        manager.set_ttl("a", "b:c", TINY_TTL)
        expected_count = 2
        assert manager.entry_count == expected_count
        time.sleep(TINY_TTL)
        assert not manager.is_expired("a:b", "c")
        assert manager.is_expired("a", "b:c")
        # get_expired_columns must report the real column name, not a fragment.
        assert manager.get_expired_columns("a") == ["b:c"]
        assert manager.get_expired_columns("a:b") == []

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
        now = [CREATED_AT_1000]
        cf = ColumnFamily(name="cache", ttl_manager=TTLManager(clock=lambda: now[0]))
        cf.put(
            "key1",
            Column(name="data", value="temp", timestamp=TIMESTAMP_1000),
            ttl_seconds=TTL_60_SECONDS,
        )
        cf.put("key1", Column(name="keep", value="permanent", timestamp=TIMESTAMP_1000))
        now[0] += TTL_60_SECONDS
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


class TestTTLReadVisibility:
    """Expired columns must be hidden from every read path, not just get_column."""

    def _expired_cf(self) -> ColumnFamily:
        """Build a column family with one fully-expired row and one live row."""
        cf = ColumnFamily(name="cache")
        cf.put(
            "gone",
            Column(name="data", value="temp", timestamp=TIMESTAMP_1000),
            ttl_seconds=TINY_TTL,
        )
        cf.put(
            "alive",
            Column(name="data", value="keep", timestamp=TIMESTAMP_1000),
        )
        time.sleep(TINY_TTL)
        return cf

    def test_row_column_names_hide_expired(self) -> None:
        """Row.column_names skips expired columns when given the manager."""
        cf = self._expired_cf()
        row = cf.rows["gone"]
        assert row.column_names(cf.ttl_manager) == []

    def test_row_get_columns_hide_expired(self) -> None:
        """Row.get_columns skips expired columns when given the manager."""
        cf = self._expired_cf()
        row = cf.rows["gone"]
        assert row.get_columns(ttl_manager=cf.ttl_manager) == []
        assert row.get_columns(["data"], cf.ttl_manager) == []

    def test_row_has_column_hides_expired(self) -> None:
        """Row.has_column reports expired columns as absent."""
        cf = self._expired_cf()
        row = cf.rows["gone"]
        assert row.has_column("data") is True  # physically present
        assert row.has_column("data", cf.ttl_manager) is False

    def test_has_row_hides_fully_expired_row(self) -> None:
        """A row whose only column expired is no longer 'present'."""
        cf = self._expired_cf()
        assert cf.has_row("gone") is False
        assert cf.has_row("alive") is True

    def test_row_keys_and_count_exclude_expired(self) -> None:
        """row_keys / row_count only include rows with live columns."""
        cf = self._expired_cf()
        assert cf.row_keys() == ["alive"]
        assert cf.row_count == 1

    def test_range_query_excludes_expired_row(self) -> None:
        """range_query must not return a fully-expired row."""
        cf = self._expired_cf()
        rows = range_query(cf)
        assert [r.key for r in rows] == ["alive"]

    def test_column_filter_hides_expired(self) -> None:
        """column_filter hides expired columns when given the manager."""
        cf = self._expired_cf()
        row = cf.rows["gone"]
        assert column_filter(row, ["data"]) != []  # without manager, still visible
        assert column_filter(row, ["data"], cf.ttl_manager) == []

    def test_query_with_filter_hides_expired(self) -> None:
        """query_with_filter drops rows whose matching columns all expired."""
        cf = self._expired_cf()
        results = query_with_filter(cf, ["data"])
        assert [key for key, _ in results] == ["alive"]


class TestPretendClock:
    """A TTLManager can read a pretend clock instead of the real one."""

    def test_columns_expire_when_the_pretend_clock_moves(self) -> None:
        """Moving a pretend clock past the TTL expires the column, with no waiting."""
        now = [CREATED_AT_1000]
        manager = TTLManager(clock=lambda: now[0])
        manager.set_ttl("row1", "col1", TTL_60_SECONDS)
        now[0] = CREATED_AT_1000 + TTL_60_SECONDS - 1
        assert not manager.is_expired("row1", "col1")
        assert manager.get_expired_columns("row1") == []
        now[0] = CREATED_AT_1000 + TTL_60_SECONDS
        assert manager.is_expired("row1", "col1")
        assert manager.get_expired_columns("row1") == ["col1"]

    def test_from_dict_keeps_the_pretend_clock(self) -> None:
        """A manager rebuilt from records reads the clock it was given."""
        records = TTLManager(clock=lambda: CREATED_AT_100).to_dict()
        restored = TTLManager.from_dict(records, clock=lambda: CREATED_AT_1000)
        assert restored.entry_count == 0
        restored.set_ttl("row1", "col1", TTL_60_SECONDS)
        assert restored.to_dict()[0]["created_at"] == CREATED_AT_1000
