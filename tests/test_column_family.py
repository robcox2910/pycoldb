"""Tests for the ColumnFamily data structure."""

import pytest

from pycoldb.column import Column
from pycoldb.column_family import ColumnFamily
from pycoldb.errors import ColumnNotFoundError, InvalidTTLError, RowNotFoundError
from pycoldb.ttl import TTLManager

TIMESTAMP_1000 = 1000.0
TIMESTAMP_2000 = 2000.0
VALUE_95 = 95
VALUE_88 = 88
VALUE_92 = 92


class TestColumnFamilyCRUD:
    """Test create, read, update, delete operations."""

    def test_put_and_get(self) -> None:
        """Insert a column and retrieve it."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        result = cf.get_column("alice", "math")
        assert result.value == "A+"

    def test_put_creates_row(self) -> None:
        """Verify put auto-creates a row if it doesn't exist."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        assert cf.has_row("alice")

    def test_update_column(self) -> None:
        """Update an existing column value."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="B", timestamp=TIMESTAMP_1000))
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_2000))
        assert cf.get_column("alice", "math").value == "A+"

    def test_get_missing_row_raises(self) -> None:
        """Raise RowNotFoundError for a missing row."""
        cf = ColumnFamily(name="grades")
        with pytest.raises(RowNotFoundError):
            cf.get_column("alice", "math")

    def test_get_missing_column_raises(self) -> None:
        """Raise ColumnNotFoundError for a missing column."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        with pytest.raises(ColumnNotFoundError):
            cf.get_column("alice", "science")

    def test_multiple_rows(self) -> None:
        """Store data in multiple rows."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value=VALUE_95, timestamp=TIMESTAMP_1000))
        cf.put("bob", Column(name="math", value=VALUE_88, timestamp=TIMESTAMP_1000))
        assert cf.get_column("alice", "math").value == VALUE_95
        assert cf.get_column("bob", "math").value == VALUE_88

    def test_different_columns_per_row(self) -> None:
        """Verify each row can have different columns."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf.put("alice", Column(name="art", value="A", timestamp=TIMESTAMP_1000))
        cf.put("bob", Column(name="math", value="B", timestamp=TIMESTAMP_1000))
        cf.put("bob", Column(name="music", value="A", timestamp=TIMESTAMP_1000))

        alice = cf.get_row("alice")
        bob = cf.get_row("bob")
        assert alice.column_names() == ["art", "math"]
        assert bob.column_names() == ["math", "music"]


class TestColumnFamilyDeletion:
    """Test deletion operations on column families."""

    def test_delete_column(self) -> None:
        """Delete a single column from a row."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf.put("alice", Column(name="art", value="B", timestamp=TIMESTAMP_1000))
        cf.delete_column("alice", "math")
        with pytest.raises(ColumnNotFoundError):
            cf.get_column("alice", "math")

    def test_delete_row(self) -> None:
        """Delete an entire row by tombstoning all columns."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf.put("alice", Column(name="science", value="A", timestamp=TIMESTAMP_1000))
        cf.delete_row("alice")
        assert not cf.has_row("alice")

    def test_delete_missing_row_raises(self) -> None:
        """Raise RowNotFoundError when deleting a nonexistent row."""
        cf = ColumnFamily(name="grades")
        with pytest.raises(RowNotFoundError):
            cf.delete_row("alice")

    def test_tombstones_collected(self) -> None:
        """Verify tombstones are accessible after deletion."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf.delete_column("alice", "math")
        tombstones = cf.get_tombstones()
        assert len(tombstones) == 1
        assert tombstones[0].column_name == "math"


class TestColumnFamilyMetadata:
    """Test metadata and listing operations."""

    def test_row_keys_sorted(self) -> None:
        """Verify row keys are returned sorted."""
        cf = ColumnFamily(name="grades")
        cf.put("charlie", Column(name="math", value="A", timestamp=TIMESTAMP_1000))
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf.put("bob", Column(name="math", value="B", timestamp=TIMESTAMP_1000))
        assert cf.row_keys() == ["alice", "bob", "charlie"]

    def test_row_count(self) -> None:
        """Count active rows."""
        cf = ColumnFamily(name="grades")
        expected_count = 3
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf.put("bob", Column(name="math", value="B", timestamp=TIMESTAMP_1000))
        cf.put("charlie", Column(name="math", value="A", timestamp=TIMESTAMP_1000))
        assert cf.row_count == expected_count

    def test_has_row_false_after_delete(self) -> None:
        """Verify has_row returns False for fully deleted rows."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf.delete_row("alice")
        assert not cf.has_row("alice")


class TestColumnFamilySerialization:
    """Test serialization of column families."""

    def test_roundtrip(self) -> None:
        """Verify roundtrip serialization preserves data."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value=VALUE_95, timestamp=TIMESTAMP_1000))
        cf.put("bob", Column(name="science", value=VALUE_88, timestamp=TIMESTAMP_2000))

        data = cf.to_dict()
        restored = ColumnFamily.from_dict(data)

        assert restored.name == "grades"
        assert restored.get_column("alice", "math").value == VALUE_95
        assert restored.get_column("bob", "science").value == VALUE_88


def test_column_family_delete_is_last_write_wins() -> None:
    """Through the column family too, a stale write can't resurrect a deleted column."""
    cf = ColumnFamily(name="grades")
    cf.put("alice", Column(name="math", value="A", timestamp=2000))
    cf.put("alice", Column(name="art", value="B", timestamp=2000))
    cf.delete_column("alice", "math", timestamp=2500)
    cf.put("alice", Column(name="math", value="old", timestamp=2400))
    assert not cf.get_row("alice").has_column("math")


class TestPutWithTTL:
    """A TTL belongs to the write it came with, and only to a write that lands."""

    def test_a_bad_ttl_refuses_the_whole_write(self) -> None:
        """Regression (found by the model check): a TTL of 0 used to raise *after* writing."""
        cf = ColumnFamily(name="grades")
        with pytest.raises(InvalidTTLError):
            cf.put("alice", Column(name="alice", value="x", timestamp=3.0), ttl_seconds=0.0)
        assert not cf.has_row("alice")
        assert cf.ttl_manager.entry_count == 0

    def test_a_write_too_old_to_count_keeps_the_ttl(self) -> None:
        """Regression: an ignored, older write used to wipe the newer column's TTL."""
        now = [1000.0]
        cf = ColumnFamily(name="grades", ttl_manager=TTLManager(clock=lambda: now[0]))
        cf.put("alice", Column(name="art", value="B", timestamp=2.0))
        cf.put("alice", Column(name="math", value="new", timestamp=2.0), ttl_seconds=1.0)
        cf.put("alice", Column(name="math", value="old", timestamp=1.0))  # too old: ignored
        now[0] += 1.0
        with pytest.raises(ColumnNotFoundError):
            cf.get_column("alice", "math")

    def test_a_write_too_old_to_undo_a_delete_adds_no_ttl(self) -> None:
        """Regression (found by a property): an ignored write put a TTL on a deleted column."""
        cf = ColumnFamily(name="grades")
        cf.put("bob", Column(name="alice", value="", timestamp=0.0))
        cf.delete_column("bob", "alice")
        cf.put("bob", Column(name="alice", value="", timestamp=0.0), ttl_seconds=1.0)
        assert cf.ttl_manager.entry_count == 0


class TestNothingLiveIsMissing:
    """A row or column with nothing live left reads as missing, before compaction and after."""

    def test_a_row_whose_columns_were_all_deleted_is_not_found(self) -> None:
        """Regression (found by a property): get_row returned it until compaction, then raised."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="alice", value=None, timestamp=0.0))
        cf.delete_column("alice", "alice")
        with pytest.raises(RowNotFoundError):
            cf.get_row("alice")
        with pytest.raises(RowNotFoundError):
            cf.get_column("alice", "alice")
        with pytest.raises(RowNotFoundError):
            cf.delete_row("alice")

    def test_a_row_whose_columns_all_expired_is_not_found(self) -> None:
        """Regression (found by the model check): it said "column not found" until compaction."""
        now = [1000.0]
        cf = ColumnFamily(name="grades", ttl_manager=TTLManager(clock=lambda: now[0]))
        cf.put("alice", Column(name="alice", value="", timestamp=0.0), ttl_seconds=1.0)
        now[0] += 1.0
        with pytest.raises(RowNotFoundError):
            cf.get_column("alice", "bob")
        with pytest.raises(RowNotFoundError):
            cf.get_row("alice")

    def test_an_expired_column_cannot_be_deleted(self) -> None:
        """Deleting an expired column is refused, just like reading it."""
        now = [1000.0]
        cf = ColumnFamily(name="grades", ttl_manager=TTLManager(clock=lambda: now[0]))
        cf.put("alice", Column(name="math", value="A", timestamp=0.0), ttl_seconds=1.0)
        cf.put("alice", Column(name="art", value="B", timestamp=0.0))
        now[0] += 1.0
        with pytest.raises(ColumnNotFoundError):
            cf.delete_column("alice", "math")
        cf.delete_row("alice")
        assert [t.column_name for t in cf.get_tombstones()] == ["art"]
