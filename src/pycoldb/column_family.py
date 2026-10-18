"""Column family -- a named collection of rows.

Imagine a teacher's gradebook. The gradebook has a name (like "Science Class"),
and inside it are rows for each student. Each student (row) can have different
grades and notes (columns).

A **column family** is exactly like that gradebook:
- It has a name (like "grades" or "attendance")
- It contains rows, each identified by a unique key
- Each row can have completely different columns

In real databases like Apache Cassandra, column families are the main way
data is organized. You create a column family for each type of data, and
then add rows with whatever columns make sense.

Example:
    >>> from pycoldb.column_family import ColumnFamily
    >>> from pycoldb.column import Column
    >>> grades = ColumnFamily(name="grades")
    >>> grades.put("alice", Column(name="math", value="A+", timestamp=1000))
    >>> grades.get_column("alice", "math").value
    'A+'

"""

from dataclasses import dataclass, field

from pycoldb.column import Column
from pycoldb.errors import ColumnNotFoundError, RowNotFoundError
from pycoldb.row import Row
from pycoldb.tombstone import Tombstone
from pycoldb.ttl import TTLManager, check_ttl


@dataclass
class ColumnFamily:
    """A named group of rows, each with its own set of columns.

    Think of this as a teacher's gradebook. The gradebook has a name,
    and each student (row) has their own grades (columns). Different
    students can have different grades recorded.

    Attributes:
        name: The name of this column family.
        rows: Dictionary mapping row keys to Row objects.
        ttl_manager: Manages time-to-live for columns.

    """

    name: str
    rows: dict[str, Row] = field(default_factory=lambda: {})
    ttl_manager: TTLManager = field(default_factory=TTLManager)

    def put(
        self,
        row_key: str,
        column: Column,
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        """Insert or update a column in a row.

        If the row doesn't exist yet, it's created automatically.
        Think of it as a student walking into class for the first time --
        they get a new record card and their first grade is recorded.

        The TTL belongs to this write: a write that lands sets the
        column's TTL (or clears it, if ``ttl_seconds`` is None). A write
        too old to count (see :meth:`Row.put_column`) changes nothing at
        all, TTL included.

        Args:
            row_key: The unique key for the row.
            column: The column to insert or update.
            ttl_seconds: Optional time-to-live in seconds. If set,
                the column will expire after this many seconds.

        Raises:
            InvalidTTLError: If ttl_seconds is not positive. Nothing is
                written: the check happens before the write.

        """
        if ttl_seconds is not None:
            check_ttl(ttl_seconds)
        if row_key not in self.rows:
            self.rows[row_key] = Row(key=row_key)
        if not self.rows[row_key].put_column(column):
            return  # too old to count: the column, and its TTL, stay as they were
        if ttl_seconds is not None:
            self.ttl_manager.set_ttl(row_key, column.name, ttl_seconds)
        else:
            self.ttl_manager.remove_ttl(row_key, column.name)

    def get_column(self, row_key: str, column_name: str) -> Column:
        """Get a specific column from a row.

        Args:
            row_key: The row to look in.
            column_name: The column to get.

        Returns:
            The requested Column.

        Raises:
            RowNotFoundError: If the row doesn't exist.
            ColumnNotFoundError: If the column doesn't exist or is
                expired/tombstoned.

        """
        row = self._get_row(row_key)
        if self.ttl_manager.is_expired(row_key, column_name):
            msg = f"Column '{column_name}' has expired in row '{row_key}'"
            raise ColumnNotFoundError(msg)
        return row.get_column(column_name)

    def get_row(self, row_key: str) -> Row:
        """Get a full row by its key.

        Args:
            row_key: The row key to look up.

        Returns:
            The Row object.

        Raises:
            RowNotFoundError: If the row doesn't exist.

        """
        return self._get_row(row_key)

    def delete_column(
        self, row_key: str, column_name: str, *, timestamp: float | None = None
    ) -> None:
        """Soft-delete a column by placing a tombstone.

        Args:
            row_key: The row containing the column.
            column_name: The column to delete.
            timestamp: When the delete happened (defaults to the deleted
                column's own timestamp). Older writes can't undo it.

        Raises:
            RowNotFoundError: If the row doesn't exist.
            ColumnNotFoundError: If the column doesn't exist.

        """
        row = self._get_row(row_key)
        row.delete_column(column_name, timestamp=timestamp)
        self.ttl_manager.remove_ttl(row_key, column_name)

    def delete_row(self, row_key: str, *, timestamp: float | None = None) -> None:
        """Soft-delete an entire row by tombstoning all its columns.

        Args:
            row_key: The row to delete.
            timestamp: When the delete happened (defaults to each column's
                own timestamp).

        Raises:
            RowNotFoundError: If the row doesn't exist.

        """
        row = self._get_row(row_key)
        for col_name in list(row.columns.keys()):
            row.delete_column(col_name, timestamp=timestamp)
            self.ttl_manager.remove_ttl(row_key, col_name)

    def has_row(self, row_key: str) -> bool:
        """Check whether a row exists and has live columns.

        Args:
            row_key: The row key to check.

        Returns:
            True if the row exists and has at least one live column
            (not tombstoned and not expired).

        """
        if row_key not in self.rows:
            return False
        return bool(self.rows[row_key].column_names(self.ttl_manager))

    def row_keys(self) -> list[str]:
        """Get all row keys that have live columns.

        A row counts as live only if it still has at least one column
        that is neither tombstoned nor TTL-expired.

        Returns:
            A sorted list of row keys.

        """
        return sorted(key for key, row in self.rows.items() if row.column_names(self.ttl_manager))

    @property
    def row_count(self) -> int:
        """Count the number of rows with live columns.

        Returns:
            The number of active rows.

        """
        return len(self.row_keys())

    def get_tombstones(self) -> list[Tombstone]:
        """Get all tombstones across all rows.

        Returns:
            A list of all tombstone markers.

        """
        result: list[Tombstone] = []
        for row in self.rows.values():
            result.extend(row.tombstones.values())
        return result

    def _get_row(self, row_key: str) -> Row:
        """Look up a row by key, raising an error if not found.

        Args:
            row_key: The row key to look up.

        Returns:
            The Row object.

        Raises:
            RowNotFoundError: If the row doesn't exist.

        """
        if row_key not in self.rows:
            msg = f"Row '{row_key}' not found in column family '{self.name}'"
            raise RowNotFoundError(msg)
        return self.rows[row_key]

    def to_dict(self) -> dict[str, object]:
        """Convert this column family to a dictionary.

        Returns:
            A dictionary with name, rows, and ttl data.

        """
        return {
            "name": self.name,
            "rows": {key: row.to_dict() for key, row in self.rows.items()},
            "ttl": self.ttl_manager.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ColumnFamily:
        """Create a ColumnFamily from a dictionary.

        Args:
            data: Dictionary with name, rows, and ttl data.

        Returns:
            A new ColumnFamily instance.

        """
        name = str(data["name"])
        rows_data = data.get("rows", {})
        ttl_data = data.get("ttl", [])

        rows: dict[str, Row] = {}
        if isinstance(rows_data, dict):
            for key, row_data in rows_data.items():  # pyright: ignore[reportUnknownVariableType]
                if isinstance(row_data, dict):
                    row_dict: dict[str, object] = {str(k): v for k, v in row_data.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
                    rows[str(key)] = Row.from_dict(row_dict)  # pyright: ignore[reportUnknownArgumentType]

        ttl_manager = TTLManager()
        if isinstance(ttl_data, list):
            ttl_manager = TTLManager.from_dict(ttl_data)  # type: ignore[arg-type]

        return cls(name=name, rows=rows, ttl_manager=ttl_manager)
