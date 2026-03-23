"""Column data structure for the column-family store.

Think of a column like a single cell in a spreadsheet. Each cell has:
- A **name** (the column header, like "Math Grade")
- A **value** (the actual data, like "A+")
- A **timestamp** (when the data was written, like a date stamp)

Unlike a regular spreadsheet, every cell remembers exactly when it was
last updated. This is super useful for knowing which data is newest!

Example:
    >>> from pycoldb.column import Column
    >>> grade = Column(name="math", value="A+", timestamp=1000)
    >>> grade.name
    'math'
    >>> grade.value
    'A+'

"""

import time
from dataclasses import dataclass, field


@dataclass
class Column:
    """A single named value with a timestamp.

    A column is the smallest unit of data in a column-family store.
    Think of it as one cell in a spreadsheet that also remembers
    when it was last changed.

    Attributes:
        name: The column name (like a spreadsheet header).
        value: The stored data (can be any JSON-serializable value).
        timestamp: When this column was last written (epoch seconds).
            If not provided, uses the current time.

    """

    name: str
    value: str | int | float | bool | None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, str | int | float | bool | None]:
        """Convert this column to a dictionary for serialization.

        Returns:
            A dictionary with name, value, and timestamp keys.

        """
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | int | float | bool | None]) -> Column:
        """Create a Column from a dictionary.

        Args:
            data: Dictionary with name, value, and timestamp keys.

        Returns:
            A new Column instance.

        """
        return cls(
            name=str(data["name"]),
            value=data["value"],
            timestamp=float(data.get("timestamp", 0.0) or 0.0),
        )
