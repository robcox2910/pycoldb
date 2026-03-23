"""Tombstone markers for soft deletion in the column-family store.

Imagine you're writing in a notebook with pen (not pencil!). When you
make a mistake, you can't erase it -- instead, you draw a line through
it and write the correct answer next to it. That crossed-out text is
still there, but everyone knows to ignore it.

That's exactly what a **tombstone** is! Instead of truly deleting data
(which could cause problems in a distributed database), we mark it as
"deleted" with a special marker called a tombstone. Later, during
compaction (cleaning up), we actually remove the tombstoned data.

Real databases like Apache Cassandra use tombstones for the same reason:
when you have copies of data on multiple computers, you need a way to
tell all the computers "this data was deleted" without the data just
magically reappearing from another copy.

Example:
    >>> from pycoldb.tombstone import Tombstone
    >>> marker = Tombstone(column_name="old_grade", deleted_at=1000.0)
    >>> marker.column_name
    'old_grade'

"""

import time
from dataclasses import dataclass, field


@dataclass
class Tombstone:
    """A marker indicating that a column has been soft-deleted.

    Think of this as drawing a line through something in pen.
    The original data is gone, but the marker stays until compaction
    cleans it up.

    Attributes:
        column_name: The name of the deleted column.
        deleted_at: When the deletion happened (epoch seconds).

    """

    column_name: str
    deleted_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, str | float]:
        """Convert this tombstone to a dictionary for serialization.

        Returns:
            A dictionary with column_name and deleted_at keys.

        """
        return {
            "column_name": self.column_name,
            "deleted_at": self.deleted_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | float]) -> Tombstone:
        """Create a Tombstone from a dictionary.

        Args:
            data: Dictionary with column_name and deleted_at keys.

        Returns:
            A new Tombstone instance.

        """
        return cls(
            column_name=str(data["column_name"]),
            deleted_at=float(data["deleted_at"]),
        )
