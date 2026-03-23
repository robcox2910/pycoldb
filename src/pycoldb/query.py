"""Query engine for range queries and column filtering.

Imagine you have a huge filing cabinet full of student records, sorted
alphabetically. Sometimes you don't need ALL the records -- you just want:
- Students from "A" to "M" (a **range query**)
- Only the math and science grades, not everything (a **column filter**)

This module lets you slice and dice the data in a column family
efficiently, just like looking through only part of the filing cabinet
and only reading certain fields on each card.

Example:
    >>> from pycoldb.query import range_query, column_filter
    >>> from pycoldb.column_family import ColumnFamily
    >>> from pycoldb.column import Column
    >>> cf = ColumnFamily(name="grades")
    >>> cf.put("alice", Column(name="math", value="A+", timestamp=1000))
    >>> cf.put("bob", Column(name="math", value="B", timestamp=1000))
    >>> cf.put("charlie", Column(name="math", value="A", timestamp=1000))
    >>> results = range_query(cf, start_key="alice", end_key="bob")
    >>> [r.key for r in results]
    ['alice', 'bob']

"""

from pycoldb.column import Column
from pycoldb.column_family import ColumnFamily
from pycoldb.row import Row


def range_query(
    cf: ColumnFamily,
    start_key: str | None = None,
    end_key: str | None = None,
    *,
    inclusive_start: bool = True,
    inclusive_end: bool = True,
) -> list[Row]:
    """Get rows whose keys fall within a range.

    This is like looking through a filing cabinet from one letter to
    another. You pick a start and end, and get back all the records
    in between (sorted alphabetically).

    Args:
        cf: The column family to query.
        start_key: The beginning of the range (or None for the start).
        end_key: The end of the range (or None for the end).
        inclusive_start: Whether to include the start key itself.
        inclusive_end: Whether to include the end key itself.

    Returns:
        A list of Row objects whose keys are within the range,
        sorted by key.

    """
    all_keys = cf.row_keys()
    result: list[Row] = []

    for key in all_keys:
        if start_key is not None:
            if inclusive_start and key < start_key:
                continue
            if not inclusive_start and key <= start_key:
                continue
        if end_key is not None:
            if inclusive_end and key > end_key:
                continue
            if not inclusive_end and key >= end_key:
                continue
        result.append(cf.rows[key])

    return result


def column_filter(row: Row, column_names: list[str]) -> list[Column]:
    """Get only specific columns from a row.

    This is like looking at a student's record but only reading the
    math and science grades, ignoring everything else.

    Args:
        row: The row to filter columns from.
        column_names: The names of the columns to include.

    Returns:
        A list of matching Column objects, sorted by name.

    """
    return row.get_columns(column_names)


def query_with_filter(
    cf: ColumnFamily,
    column_names: list[str],
    start_key: str | None = None,
    end_key: str | None = None,
    *,
    inclusive_start: bool = True,
    inclusive_end: bool = True,
) -> list[tuple[str, list[Column]]]:
    """Combine a range query with column filtering.

    Get rows in a key range but only return specific columns from
    each row. This is the most efficient way to read a subset of
    your data.

    Args:
        cf: The column family to query.
        column_names: The columns to include from each row.
        start_key: Start of the key range (or None).
        end_key: End of the key range (or None).
        inclusive_start: Whether to include the start key.
        inclusive_end: Whether to include the end key.

    Returns:
        A list of (row_key, columns) tuples, sorted by row key.

    """
    rows = range_query(
        cf,
        start_key=start_key,
        end_key=end_key,
        inclusive_start=inclusive_start,
        inclusive_end=inclusive_end,
    )
    result: list[tuple[str, list[Column]]] = []
    for row in rows:
        cols = column_filter(row, column_names)
        if cols:
            result.append((row.key, cols))
    return result
