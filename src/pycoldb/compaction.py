"""Compaction -- cleaning up deleted and expired data.

Imagine your notebook is full of crossed-out words (tombstones) and
expired sticky notes (TTL). Over time, all this clutter makes it harder
to find the real data. **Compaction** is like going through your notebook
with a fresh page and only copying over the stuff that's still valid.

In real databases like Cassandra, compaction happens in the background
to free up disk space and make reads faster. Our version does the same
thing: it removes tombstones and expired columns so the data stays clean.

Example:
    >>> from pycoldb.compaction import compact_column_family
    >>> from pycoldb.column_family import ColumnFamily
    >>> from pycoldb.column import Column
    >>> cf = ColumnFamily(name="test")
    >>> cf.put("row1", Column(name="a", value=1, timestamp=1000))
    >>> cf.delete_column("row1", "a")
    >>> compact_column_family(cf)
    1

"""

from pycoldb.column_family import ColumnFamily


def compact_column_family(cf: ColumnFamily) -> int:
    """Remove tombstones and expired columns from a column family.

    Walk through every row, remove tombstoned and TTL-expired columns,
    and clean up empty rows. Return how many entries were cleaned up.

    Args:
        cf: The column family to compact.

    Returns:
        The total number of entries (tombstones + expired columns)
        that were removed.

    """
    removed_count = 0

    for row_key in list(cf.rows.keys()):
        row = cf.rows[row_key]

        # Remove tombstoned columns
        tombstone_names = list(row.tombstones.keys())
        for col_name in tombstone_names:
            row.columns.pop(col_name, None)
            del row.tombstones[col_name]
            cf.ttl_manager.remove_ttl(row_key, col_name)
            removed_count += 1

        # Remove expired columns
        expired_names = cf.ttl_manager.get_expired_columns(row_key)
        for col_name in expired_names:
            row.columns.pop(col_name, None)
            cf.ttl_manager.remove_ttl(row_key, col_name)
            removed_count += 1

        # Remove entirely empty rows
        if not row.columns and not row.tombstones:
            del cf.rows[row_key]

    return removed_count


def compact_all(column_families: list[ColumnFamily]) -> int:
    """Compact multiple column families at once.

    Args:
        column_families: The list of column families to compact.

    Returns:
        The total number of entries removed across all families.

    """
    total = 0
    for cf in column_families:
        total += compact_column_family(cf)
    return total
