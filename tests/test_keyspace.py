"""Tests for the Keyspace container."""

import pytest

from pycoldb.column import Column
from pycoldb.errors import (
    ColumnFamilyAlreadyExistsError,
    ColumnFamilyNotFoundError,
    ColumnNotFoundError,
    RowNotFoundError,
)
from pycoldb.keyspace import Keyspace

TIMESTAMP_1000 = 1000.0
VALUE_95 = 95
VALUE_88 = 88


class TestKeyspaceColumnFamilies:
    """Test column family management within a keyspace."""

    def test_create_column_family(self) -> None:
        """Create a new column family."""
        ks = Keyspace(name="school")
        cf = ks.create_column_family("grades")
        assert cf.name == "grades"

    def test_duplicate_column_family_raises(self) -> None:
        """Raise error when creating a duplicate column family."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        with pytest.raises(ColumnFamilyAlreadyExistsError):
            ks.create_column_family("grades")

    def test_drop_column_family(self) -> None:
        """Drop an existing column family."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        ks.drop_column_family("grades")
        assert ks.column_family_count == 0

    def test_drop_missing_column_family_raises(self) -> None:
        """Raise error when dropping a nonexistent column family."""
        ks = Keyspace(name="school")
        with pytest.raises(ColumnFamilyNotFoundError):
            ks.drop_column_family("grades")

    def test_get_column_family(self) -> None:
        """Get an existing column family by name."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        cf = ks.get_column_family("grades")
        assert cf.name == "grades"

    def test_get_missing_column_family_raises(self) -> None:
        """Raise error for a missing column family."""
        ks = Keyspace(name="school")
        with pytest.raises(ColumnFamilyNotFoundError):
            ks.get_column_family("grades")

    def test_column_family_names_sorted(self) -> None:
        """Verify column family names are sorted."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        ks.create_column_family("attendance")
        assert ks.column_family_names() == ["attendance", "grades"]

    def test_column_family_count(self) -> None:
        """Count column families."""
        ks = Keyspace(name="school")
        expected_count = 2
        ks.create_column_family("grades")
        ks.create_column_family("attendance")
        assert ks.column_family_count == expected_count


class TestKeyspaceCRUD:
    """Test CRUD operations through the keyspace convenience methods."""

    def test_put_and_get(self) -> None:
        """Insert and retrieve through keyspace."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        ks.put("grades", "alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        result = ks.get_column("grades", "alice", "math")
        assert result.value == "A+"

    def test_put_to_missing_cf_raises(self) -> None:
        """Raise error when putting to a missing column family."""
        ks = Keyspace(name="school")
        with pytest.raises(ColumnFamilyNotFoundError):
            ks.put("grades", "alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))

    def test_get_from_missing_cf_raises(self) -> None:
        """Raise error when getting from a missing column family."""
        ks = Keyspace(name="school")
        with pytest.raises(ColumnFamilyNotFoundError):
            ks.get_column("grades", "alice", "math")

    def test_get_missing_row_raises(self) -> None:
        """Raise RowNotFoundError through keyspace."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        with pytest.raises(RowNotFoundError):
            ks.get_column("grades", "alice", "math")

    def test_get_missing_column_raises(self) -> None:
        """Raise ColumnNotFoundError through keyspace."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        ks.put("grades", "alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        with pytest.raises(ColumnNotFoundError):
            ks.get_column("grades", "alice", "science")

    def test_put_with_ttl(self) -> None:
        """Insert with TTL through keyspace."""
        ks = Keyspace(name="school")
        ks.create_column_family("cache")
        ttl_value = 60.0
        ks.put(
            "cache",
            "session1",
            Column(name="token", value="abc123", timestamp=TIMESTAMP_1000),
            ttl_seconds=ttl_value,
        )
        result = ks.get_column("cache", "session1", "token")
        assert result.value == "abc123"


class TestKeyspaceSerialization:
    """Test keyspace serialization."""

    def test_roundtrip(self) -> None:
        """Verify roundtrip serialization preserves all data."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        ks.put("grades", "alice", Column(name="math", value=VALUE_95, timestamp=TIMESTAMP_1000))
        ks.put("grades", "bob", Column(name="science", value=VALUE_88, timestamp=TIMESTAMP_1000))

        data = ks.to_dict()
        restored = Keyspace.from_dict(data)

        assert restored.name == "school"
        assert restored.column_family_count == 1
        assert restored.get_column("grades", "alice", "math").value == VALUE_95
        assert restored.get_column("grades", "bob", "science").value == VALUE_88
