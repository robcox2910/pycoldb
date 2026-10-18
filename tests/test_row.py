"""Tests for the Row data structure."""

import pytest

from pycoldb.column import Column
from pycoldb.errors import ColumnNotFoundError
from pycoldb.row import Row

TIMESTAMP_1000 = 1000.0
TIMESTAMP_2000 = 2000.0
VALUE_95 = 95
VALUE_88 = 88


class TestRowBasics:
    """Test basic row operations."""

    def test_create_empty_row(self) -> None:
        """Create an empty row with a key."""
        row = Row(key="alice")
        assert row.key == "alice"
        assert row.is_empty

    def test_put_column(self) -> None:
        """Insert a column into a row."""
        row = Row(key="alice")
        col = Column(name="math", value="A+", timestamp=TIMESTAMP_1000)
        row.put_column(col)
        assert row.has_column("math")
        assert not row.is_empty

    def test_get_column(self) -> None:
        """Retrieve a column from a row."""
        row = Row(key="alice")
        col = Column(name="math", value="A+", timestamp=TIMESTAMP_1000)
        row.put_column(col)
        result = row.get_column("math")
        assert result.value == "A+"

    def test_get_missing_column_raises(self) -> None:
        """Raise ColumnNotFoundError for a missing column."""
        row = Row(key="alice")
        with pytest.raises(ColumnNotFoundError):
            row.get_column("math")

    def test_update_column(self) -> None:
        """Update an existing column with a new value."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value="B", timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="math", value="A+", timestamp=TIMESTAMP_2000))
        assert row.get_column("math").value == "A+"
        assert row.get_column("math").timestamp == TIMESTAMP_2000

    def test_older_timestamp_write_is_ignored(self) -> None:
        """Last-write-wins: an older-timestamped write must not clobber newer data."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value="A+", timestamp=TIMESTAMP_2000))
        # A late-arriving, older write should be ignored.
        row.put_column(Column(name="math", value="B", timestamp=TIMESTAMP_1000))
        assert row.get_column("math").value == "A+"
        assert row.get_column("math").timestamp == TIMESTAMP_2000

    def test_equal_timestamp_write_overwrites(self) -> None:
        """A write with an equal timestamp replaces the existing value."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value="B", timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        assert row.get_column("math").value == "A+"

    def test_column_names_sorted(self) -> None:
        """Verify column_names returns sorted names."""
        row = Row(key="alice")
        row.put_column(Column(name="science", value="A", timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="art", value="B+", timestamp=TIMESTAMP_1000))
        assert row.column_names() == ["art", "math", "science"]


class TestRowDeletion:
    """Test soft-deleting columns from rows."""

    def test_delete_column(self) -> None:
        """Delete a column and verify tombstone is created."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        row.delete_column("math")
        assert not row.has_column("math")
        assert "math" in row.tombstones

    def test_delete_missing_column_raises(self) -> None:
        """Raise ColumnNotFoundError when deleting a missing column."""
        row = Row(key="alice")
        with pytest.raises(ColumnNotFoundError):
            row.delete_column("math")

    def test_get_deleted_column_raises(self) -> None:
        """Raise ColumnNotFoundError for a tombstoned column."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        row.delete_column("math")
        with pytest.raises(ColumnNotFoundError, match="deleted"):
            row.get_column("math")

    def test_reinsert_after_delete(self) -> None:
        """Re-insert a column after deletion clears the tombstone."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        row.delete_column("math")
        row.put_column(Column(name="math", value="A", timestamp=TIMESTAMP_2000))
        assert row.has_column("math")
        assert "math" not in row.tombstones


class TestRowFiltering:
    """Test filtering columns from a row."""

    def test_get_all_columns(self) -> None:
        """Get all columns when no filter is specified."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value=VALUE_95, timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="science", value=VALUE_88, timestamp=TIMESTAMP_1000))
        columns = row.get_columns()
        expected_count = 2
        assert len(columns) == expected_count
        assert columns[0].name == "math"
        assert columns[1].name == "science"

    def test_get_filtered_columns(self) -> None:
        """Get only specific columns by name."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value=VALUE_95, timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="science", value=VALUE_88, timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="art", value="B+", timestamp=TIMESTAMP_1000))
        columns = row.get_columns(["math", "art"])
        expected_count = 2
        assert len(columns) == expected_count
        assert columns[0].name == "art"
        assert columns[1].name == "math"

    def test_get_columns_excludes_tombstoned(self) -> None:
        """Verify tombstoned columns are excluded from results."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value=VALUE_95, timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="science", value=VALUE_88, timestamp=TIMESTAMP_1000))
        row.delete_column("science")
        columns = row.get_columns()
        assert len(columns) == 1
        assert columns[0].name == "math"


class TestRowSerialization:
    """Test row serialization to/from dictionaries."""

    def test_to_dict(self) -> None:
        """Convert a row to a dictionary."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        result = row.to_dict()
        assert result["key"] == "alice"
        assert isinstance(result["columns"], dict)

    def test_roundtrip(self) -> None:
        """Verify to_dict and from_dict produce identical rows."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="science", value=VALUE_95, timestamp=TIMESTAMP_2000))
        row.delete_column("science")

        data = row.to_dict()
        restored = Row.from_dict(data)

        assert restored.key == "alice"
        assert restored.has_column("math")
        assert "science" in restored.tombstones

    def test_from_dict_empty(self) -> None:
        """Create a row from minimal dictionary."""
        data: dict[str, object] = {"key": "test"}
        row = Row.from_dict(data)
        assert row.key == "test"
        assert row.is_empty


class TestDeletesWinOverOlderWrites:
    """Last-write-wins includes deletes: an older write can't undo a newer delete."""

    def test_stale_write_after_delete_stays_deleted(self) -> None:
        """Regression: a write older than the delete used to bring the column back."""
        row = Row(key="alice")
        row.put_column(Column(name="grade", value="fresh", timestamp=2000))
        row.delete_column("grade")
        row.put_column(Column(name="grade", value="stale", timestamp=1000))
        assert not row.has_column("grade")
        with pytest.raises(ColumnNotFoundError):
            row.get_column("grade")

    def test_write_at_the_same_time_as_the_delete_loses(self) -> None:
        """On a tie, the delete wins (like Cassandra)."""
        row = Row(key="alice")
        row.put_column(Column(name="grade", value="A", timestamp=2000))
        row.delete_column("grade")
        row.put_column(Column(name="grade", value="B", timestamp=2000))
        assert not row.has_column("grade")

    def test_newer_write_after_delete_brings_the_column_back(self) -> None:
        """A write that is genuinely newer than the delete is kept."""
        row = Row(key="alice")
        row.put_column(Column(name="grade", value="A", timestamp=2000))
        row.delete_column("grade")
        row.put_column(Column(name="grade", value="B", timestamp=3000))
        assert row.get_column("grade").value == "B"
        assert "grade" not in row.tombstones

    def test_delete_can_be_stamped_with_its_own_time(self) -> None:
        """An explicit delete time hides every write up to that moment."""
        row = Row(key="alice")
        row.put_column(Column(name="grade", value="A", timestamp=1000))
        row.delete_column("grade", timestamp=5000)
        row.put_column(Column(name="grade", value="late but old", timestamp=3000))
        assert not row.has_column("grade")
        row.put_column(Column(name="grade", value="newest", timestamp=6000))
        assert row.get_column("grade").value == "newest"


def test_put_column_says_whether_the_write_landed() -> None:
    """put_column returns True for a write that lands, False for one too old to count."""
    row = Row(key="alice")
    assert row.put_column(Column(name="math", value="A", timestamp=2.0)) is True
    assert row.put_column(Column(name="math", value="old", timestamp=1.0)) is False
    row.delete_column("math")
    assert row.put_column(Column(name="math", value="tie", timestamp=2.0)) is False
    assert row.put_column(Column(name="math", value="new", timestamp=3.0)) is True
