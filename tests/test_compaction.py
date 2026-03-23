"""Tests for the compaction process."""

import time

from pycoldb.column import Column
from pycoldb.column_family import ColumnFamily
from pycoldb.compaction import compact_all, compact_column_family

TIMESTAMP_1000 = 1000.0
TINY_TTL = 0.01


class TestCompactColumnFamily:
    """Test compacting a single column family."""

    def test_compact_removes_tombstones(self) -> None:
        """Verify compaction removes tombstoned columns."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf.put("alice", Column(name="science", value="A", timestamp=TIMESTAMP_1000))
        cf.delete_column("alice", "math")
        removed = compact_column_family(cf)
        assert removed == 1
        assert "math" not in cf.rows["alice"].columns
        assert len(cf.rows["alice"].tombstones) == 0

    def test_compact_removes_expired_columns(self) -> None:
        """Verify compaction removes TTL-expired columns."""
        cf = ColumnFamily(name="cache")
        cf.put(
            "key1",
            Column(name="temp", value="data", timestamp=TIMESTAMP_1000),
            ttl_seconds=TINY_TTL,
        )
        cf.put("key1", Column(name="perm", value="keep", timestamp=TIMESTAMP_1000))
        time.sleep(TINY_TTL)
        removed = compact_column_family(cf)
        assert removed == 1
        assert "temp" not in cf.rows["key1"].columns
        assert "perm" in cf.rows["key1"].columns

    def test_compact_removes_empty_rows(self) -> None:
        """Verify compaction removes rows with no live columns."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf.delete_column("alice", "math")
        compact_column_family(cf)
        assert "alice" not in cf.rows

    def test_compact_no_op_on_clean_data(self) -> None:
        """Verify compaction returns 0 when nothing needs cleanup."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        removed = compact_column_family(cf)
        assert removed == 0

    def test_compact_multiple_tombstones(self) -> None:
        """Compact multiple tombstones in one row."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf.put("alice", Column(name="science", value="A", timestamp=TIMESTAMP_1000))
        cf.put("alice", Column(name="art", value="B", timestamp=TIMESTAMP_1000))
        cf.delete_column("alice", "math")
        cf.delete_column("alice", "science")
        expected_removed = 2
        removed = compact_column_family(cf)
        assert removed == expected_removed
        assert cf.has_row("alice")
        assert cf.rows["alice"].has_column("art")


class TestCompactAll:
    """Test compacting multiple column families."""

    def test_compact_multiple_families(self) -> None:
        """Compact multiple column families at once."""
        cf1 = ColumnFamily(name="grades")
        cf1.put("alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf1.delete_column("alice", "math")

        cf2 = ColumnFamily(name="attendance")
        cf2.put("bob", Column(name="monday", value="present", timestamp=TIMESTAMP_1000))
        cf2.delete_column("bob", "monday")

        expected_total = 2
        total = compact_all([cf1, cf2])
        assert total == expected_total
