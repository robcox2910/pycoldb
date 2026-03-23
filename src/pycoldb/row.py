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

    def put_column(self, column: Column) -> None:
        """Insert or update a column in this row.

        If a tombstone exists for this column name, it is removed
        since we're writing new data.

        Args:
            column: The column to insert or update.

        """
        self.columns[column.name] = column
        self.tombstones.pop(column.name, None)

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

    def delete_column(self, name: str) -> None:
        """Soft-delete a column by placing a tombstone.

        The column data is removed but a tombstone marker is left
        behind. This is like crossing something out with a pen
        instead of erasing it.

        Args:
            name: The column name to delete.

        Raises:
            ColumnNotFoundError: If the column doesn't exist.

        """
        if name not in self.columns:
            msg = f"Column '{name}' not found in row '{self.key}'"
            raise ColumnNotFoundError(msg)
        del self.columns[name]
        self.tombstones[name] = Tombstone(column_name=name)

    def has_column(self, name: str) -> bool:
        """Check whether a column exists and is not tombstoned.

        Args:
            name: The column name to check.

        Returns:
            True if the column exists and has no tombstone.

        """
        return name in self.columns and name not in self.tombstones

    def column_names(self) -> list[str]:
        """Get the names of all live (non-tombstoned) columns.

        Returns:
            A sorted list of column names.

        """
        return sorted(name for name in self.columns if name not in self.tombstones)

    def get_columns(self, names: list[str] | None = None) -> list[Column]:
        """Get multiple columns, optionally filtered by name.

        Args:
            names: If provided, only return columns with these names.
                If None, return all live columns.

        Returns:
            A list of Column objects, sorted by name.

        """
        if names is None:
            live_names = self.column_names()
        else:
            live_names = sorted(n for n in names if n in self.columns and n not in self.tombstones)
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
