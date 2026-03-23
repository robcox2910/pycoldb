"""PyColDB -- An educational column-family store built from scratch in Python.

A column-family store (also called a wide-column store) is a type of NoSQL
database where each row can have different columns. Think of it like a
spreadsheet where every row is allowed to have different column headers!

Real-world column-family stores include Apache Cassandra and HBase. This
library teaches the core concepts in a simple, understandable way.

Quick Start:
    >>> from pycoldb import Keyspace, Column
    >>> school = Keyspace(name="school")
    >>> school.create_column_family("grades")
    ColumnFamily(name='grades', ...)
    >>> school.put("grades", "alice", Column(name="math", value="A+"))
    >>> school.get_column("grades", "alice", "math").value
    'A+'
"""

from pycoldb.column import Column
from pycoldb.column_family import ColumnFamily
from pycoldb.compaction import compact_all, compact_column_family
from pycoldb.errors import (
    ColumnFamilyAlreadyExistsError,
    ColumnFamilyNotFoundError,
    ColumnNotFoundError,
    InvalidTTLError,
    KeyspaceAlreadyExistsError,
    KeyspaceNotFoundError,
    PersistenceError,
    PyColDBError,
    RowNotFoundError,
)
from pycoldb.keyspace import Keyspace
from pycoldb.persistence import load_keyspace, save_keyspace
from pycoldb.query import column_filter, query_with_filter, range_query
from pycoldb.row import Row
from pycoldb.tombstone import Tombstone
from pycoldb.ttl import TTLEntry, TTLManager

__all__ = [
    "Column",
    "ColumnFamily",
    "ColumnFamilyAlreadyExistsError",
    "ColumnFamilyNotFoundError",
    "ColumnNotFoundError",
    "InvalidTTLError",
    "Keyspace",
    "KeyspaceAlreadyExistsError",
    "KeyspaceNotFoundError",
    "PersistenceError",
    "PyColDBError",
    "Row",
    "RowNotFoundError",
    "TTLEntry",
    "TTLManager",
    "Tombstone",
    "column_filter",
    "compact_all",
    "compact_column_family",
    "load_keyspace",
    "query_with_filter",
    "range_query",
    "save_keyspace",
]
