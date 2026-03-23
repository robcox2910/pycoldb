"""Tests for the Tombstone marker."""

from pycoldb.tombstone import Tombstone

DELETED_AT_1000 = 1000.0
DELETED_AT_2000 = 2000.0


class TestTombstoneCreation:
    """Test creating tombstone markers."""

    def test_create_tombstone(self) -> None:
        """Create a tombstone with explicit timestamp."""
        ts = Tombstone(column_name="old_grade", deleted_at=DELETED_AT_1000)
        assert ts.column_name == "old_grade"
        assert ts.deleted_at == DELETED_AT_1000

    def test_default_deleted_at(self) -> None:
        """Verify default deleted_at uses current time."""
        ts = Tombstone(column_name="test")
        assert ts.deleted_at > 0


class TestTombstoneSerialization:
    """Test converting tombstones to/from dictionaries."""

    def test_to_dict(self) -> None:
        """Convert a tombstone to a dictionary."""
        ts = Tombstone(column_name="grade", deleted_at=DELETED_AT_1000)
        result = ts.to_dict()
        assert result["column_name"] == "grade"
        assert result["deleted_at"] == DELETED_AT_1000

    def test_from_dict(self) -> None:
        """Create a tombstone from a dictionary."""
        data: dict[str, str | float] = {
            "column_name": "grade",
            "deleted_at": DELETED_AT_2000,
        }
        ts = Tombstone.from_dict(data)
        assert ts.column_name == "grade"
        assert ts.deleted_at == DELETED_AT_2000

    def test_roundtrip(self) -> None:
        """Verify to_dict and from_dict produce identical tombstones."""
        original = Tombstone(column_name="test", deleted_at=DELETED_AT_1000)
        restored = Tombstone.from_dict(original.to_dict())
        assert restored.column_name == original.column_name
        assert restored.deleted_at == original.deleted_at
