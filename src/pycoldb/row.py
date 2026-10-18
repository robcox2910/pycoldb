"""Row data structure for the column-family store.

Think of a row like a student's record card. Each student has a unique
ID (the row key), and the card can hold different pieces of information
(columns). The cool thing is that each student's card can have DIFFERENT
columns!

For example:
- Student "alice" might have columns: math_grade, science_grade, art_grade
- Student "bob" might have columns: math_grade, music_grade, gym_grade

In a regular spreadsheet, every row must have the same columns. But in
a column-family store, each row picks and chooses which columns it has.
This is called a "sparse" layout, and it's super efficient when different
rows need different kinds of data.

Example:
    >>> from pycoldb.row import Row
    >>> from pycoldb.column import Column
    >>> student = Row(key="alice")
    >>> student.put_column(Column(name="math", value="A+", timestamp=1000))
    >>> student.get_column("math").value
    'A+'

"""

from dataclasses import dataclass, field

from pycoldb.column import Column
from pycoldb.errors import ColumnNotFoundError
from pycoldb.tombstone import Tombstone
from pycoldb.ttl import TTLManager


@dataclass
class Row:
    """A row containing a set of named columns.

    Each row has a unique key and can hold any number of columns.
    Different rows in the same column family can have completely
    different sets of columns -- that's the "wide column" magic!

    Attributes:
        key: The unique identifier for this row.
        columns: Dictionary mapping column names to Column objects.
        tombstones: Dictionary mapping column names to Tombstone markers
            for soft-deleted columns.

    """

    key: str
    columns: dict[str, Column] = field(default_factory=lambda: {})
    tombstones: dict[str, Tombstone] = field(default_factory=lambda: {})

    def put_column(self, column: Column) -> bool:
        """Insert or update a column in this row.

        This is "last write wins" by timestamp, just like the concept
        docs describe: if a column with this name already exists and it
        has a *newer* timestamp than the one you're writing, the older
        write is ignored so the newest data always survives. Writing
        with an equal-or-newer timestamp replaces the existing value.

        Deletes play by the same rule. If the column was deleted, a write
        only brings it back when it is *newer* than the delete -- an old,
        late-arriving write can't undo it. On a tie, the delete wins.

        Args:
            column: The column to insert or update.

        Returns:
            True if the write landed, False if it was too old and ignored.

        """
        tombstone = self.tombstones.get(column.name)
        if tombstone is not None and column.timestamp <= tombstone.deleted_at:
            return False
        existing = self.columns.get(column.name)
        if existing is not None and column.timestamp < existing.timestamp:
            return False
        self.columns[column.name] = column
        self.tombstones.pop(column.name, None)
        return True

    def get_column(self, name: str) -> Column:
        """Get a column by name.

        Args:
            name: The column name to look up.

        Returns:
            The Column with the given name.

        Raises:
            ColumnNotFoundError: If no column with that name exists
                or if it has been tombstoned.

        """
        if name in self.tombstones:
            msg = f"Column '{name}' has been deleted in row '{self.key}'"
            raise ColumnNotFoundError(msg)
        if name not in self.columns:
            msg = f"Column '{name}' not found in row '{self.key}'"
            raise ColumnNotFoundError(msg)
        return self.columns[name]

    def delete_column(self, name: str, *, timestamp: float | None = None) -> None:
        """Soft-delete a column by placing a tombstone.

        The column data is removed but a tombstone marker is left
        behind. This is like crossing something out with a pen
        instead of erasing it.

        The tombstone is stamped with *when* the delete happened, on the
        same clock as the writes: by default the deleted column's own
        timestamp, or ``timestamp`` if you give one. Any later write that
        is not newer than that stamp is ignored.

        Args:
            name: The column name to delete.
            timestamp: When the delete happened (defaults to the deleted
                column's timestamp).

        Raises:
            ColumnNotFoundError: If the column doesn't exist.

        """
        if name not in self.columns:
            msg = f"Column '{name}' not found in row '{self.key}'"
            raise ColumnNotFoundError(msg)
        deleted = self.columns.pop(name)
        deleted_at = deleted.timestamp if timestamp is None else timestamp
        self.tombstones[name] = Tombstone(column_name=name, deleted_at=deleted_at)

    def has_column(self, name: str, ttl_manager: TTLManager | None = None) -> bool:
        """Check whether a column exists and is still visible.

        Args:
            name: The column name to check.
            ttl_manager: If provided, an expired column is treated as
                gone, just like a tombstoned one.

        Returns:
            True if the column exists, has no tombstone, and (when a
            ttl_manager is given) has not expired.

        """
        if name not in self.columns or name in self.tombstones:
            return False
        return ttl_manager is None or not ttl_manager.is_expired(self.key, name)

    def column_names(self, ttl_manager: TTLManager | None = None) -> list[str]:
        """Get the names of all live (visible) columns.

        A column is "live" if it has not been tombstoned and, when a
        ttl_manager is provided, has not expired.

        Args:
            ttl_manager: If provided, expired columns are hidden too.

        Returns:
            A sorted list of column names.

        """
        names = (name for name in self.columns if name not in self.tombstones)
        if ttl_manager is not None:
            names = (name for name in names if not ttl_manager.is_expired(self.key, name))
        return sorted(names)

    def get_columns(
        self,
        names: list[str] | None = None,
        ttl_manager: TTLManager | None = None,
    ) -> list[Column]:
        """Get multiple columns, optionally filtered by name.

        Args:
            names: If provided, only return columns with these names.
                If None, return all live columns.
            ttl_manager: If provided, expired columns are hidden.

        Returns:
            A list of Column objects, sorted by name.

        """
        if names is None:
            live_names = self.column_names(ttl_manager)
        else:
            candidates = (n for n in names if n in self.columns and n not in self.tombstones)
            if ttl_manager is not None:
                candidates = (n for n in candidates if not ttl_manager.is_expired(self.key, n))
            live_names = sorted(candidates)
        return [self.columns[n] for n in live_names]

    @property
    def is_empty(self) -> bool:
        """Check whether this row has no live columns.

        Returns:
            True if the row has no live (non-tombstoned) columns.

        """
        return len(self.column_names()) == 0

    def to_dict(self) -> dict[str, object]:
        """Convert this row to a dictionary for serialization.

        Returns:
            A dictionary with key, columns, and tombstones.

        """
        return {
            "key": self.key,
            "columns": {name: col.to_dict() for name, col in self.columns.items()},
            "tombstones": {name: ts.to_dict() for name, ts in self.tombstones.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Row:
        """Create a Row from a dictionary.

        Args:
            data: Dictionary with key, columns, and tombstones.

        Returns:
            A new Row instance.

        """
        key = str(data["key"])
        columns_data = data.get("columns", {})
        tombstones_data = data.get("tombstones", {})

        columns: dict[str, Column] = {}
        if isinstance(columns_data, dict):
            for name, col_data in columns_data.items():  # pyright: ignore[reportUnknownVariableType]
                if isinstance(col_data, dict):
                    col_dict: dict[str, object] = {str(k): v for k, v in col_data.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
                    columns[str(name)] = Column.from_dict(col_dict)  # pyright: ignore[reportUnknownArgumentType, reportArgumentType]

        tombstones: dict[str, Tombstone] = {}
        if isinstance(tombstones_data, dict):
            for name, ts_data in tombstones_data.items():  # pyright: ignore[reportUnknownVariableType]
                if isinstance(ts_data, dict):
                    ts_dict: dict[str, object] = {str(k): v for k, v in ts_data.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
                    tombstones[str(name)] = Tombstone.from_dict(ts_dict)  # pyright: ignore[reportUnknownArgumentType, reportArgumentType]

        return cls(key=key, columns=columns, tombstones=tombstones)
