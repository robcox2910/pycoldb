"""Tests for range queries and column filtering."""

from pycoldb.column import Column
from pycoldb.column_family import ColumnFamily
from pycoldb.query import column_filter, query_with_filter, range_query
from pycoldb.row import Row

TIMESTAMP_1000 = 1000.0
VALUE_95 = 95
VALUE_88 = 88
VALUE_92 = 92
VALUE_90 = 90
VALUE_85 = 85


def _make_test_cf() -> ColumnFamily:
    """Create a column family with test data for queries."""
    cf = ColumnFamily(name="grades")
    cf.put("alice", Column(name="math", value=VALUE_95, timestamp=TIMESTAMP_1000))
    cf.put("alice", Column(name="science", value=VALUE_88, timestamp=TIMESTAMP_1000))
    cf.put("bob", Column(name="math", value=VALUE_92, timestamp=TIMESTAMP_1000))
    cf.put("bob", Column(name="science", value=VALUE_90, timestamp=TIMESTAMP_1000))
    cf.put("charlie", Column(name="math", value=VALUE_85, timestamp=TIMESTAMP_1000))
    cf.put("charlie", Column(name="art", value="A", timestamp=TIMESTAMP_1000))
    return cf


class TestRangeQuery:
    """Test range queries on column families."""

    def test_full_range(self) -> None:
        """Get all rows with no range bounds."""
        cf = _make_test_cf()
        rows = range_query(cf)
        expected_count = 3
        assert len(rows) == expected_count

    def test_start_key_inclusive(self) -> None:
        """Get rows starting from a key (inclusive)."""
        cf = _make_test_cf()
        rows = range_query(cf, start_key="bob")
        expected_count = 2
        assert len(rows) == expected_count
        assert rows[0].key == "bob"
        assert rows[1].key == "charlie"

    def test_start_key_exclusive(self) -> None:
        """Get rows starting after a key (exclusive)."""
        cf = _make_test_cf()
        rows = range_query(cf, start_key="bob", inclusive_start=False)
        assert len(rows) == 1
        assert rows[0].key == "charlie"

    def test_end_key_inclusive(self) -> None:
        """Get rows up to a key (inclusive)."""
        cf = _make_test_cf()
        rows = range_query(cf, end_key="bob")
        expected_count = 2
        assert len(rows) == expected_count
        assert rows[0].key == "alice"
        assert rows[1].key == "bob"

    def test_end_key_exclusive(self) -> None:
        """Get rows up to but not including a key."""
        cf = _make_test_cf()
        rows = range_query(cf, end_key="bob", inclusive_end=False)
        assert len(rows) == 1
        assert rows[0].key == "alice"

    def test_bounded_range(self) -> None:
        """Get rows between two keys."""
        cf = _make_test_cf()
        rows = range_query(cf, start_key="alice", end_key="bob")
        expected_count = 2
        assert len(rows) == expected_count

    def test_empty_range(self) -> None:
        """Get no rows when range matches nothing."""
        cf = _make_test_cf()
        rows = range_query(cf, start_key="zz", end_key="zzz")
        assert len(rows) == 0

    def test_single_key_range(self) -> None:
        """Get exactly one row with start == end."""
        cf = _make_test_cf()
        rows = range_query(cf, start_key="bob", end_key="bob")
        assert len(rows) == 1
        assert rows[0].key == "bob"


class TestColumnFilter:
    """Test column filtering on rows."""

    def test_filter_specific_columns(self) -> None:
        """Get only the requested columns."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value=VALUE_95, timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="science", value=VALUE_88, timestamp=TIMESTAMP_1000))
        row.put_column(Column(name="art", value="A", timestamp=TIMESTAMP_1000))
        columns = column_filter(row, ["math", "art"])
        expected_count = 2
        assert len(columns) == expected_count
        assert columns[0].name == "art"
        assert columns[1].name == "math"

    def test_filter_missing_columns(self) -> None:
        """Return empty list when no requested columns exist."""
        row = Row(key="alice")
        row.put_column(Column(name="math", value=VALUE_95, timestamp=TIMESTAMP_1000))
        columns = column_filter(row, ["missing"])
        assert len(columns) == 0


class TestQueryWithFilter:
    """Test combined range query + column filter."""

    def test_range_with_column_filter(self) -> None:
        """Get specific columns from a range of rows."""
        cf = _make_test_cf()
        results = query_with_filter(cf, ["math"], start_key="alice", end_key="bob")
        expected_count = 2
        assert len(results) == expected_count
        assert results[0][0] == "alice"
        assert results[0][1][0].name == "math"

    def test_filter_excludes_empty_results(self) -> None:
        """Exclude rows that have none of the requested columns."""
        cf = _make_test_cf()
        # Only charlie has "art"
        results = query_with_filter(cf, ["art"])
        assert len(results) == 1
        assert results[0][0] == "charlie"
