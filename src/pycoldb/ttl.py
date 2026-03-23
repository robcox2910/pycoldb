"""Time-to-live (TTL) support for columns.

Imagine putting a sticky note on your locker that says "Remember: test
on Friday!" After Friday, that note isn't useful anymore. Wouldn't it
be nice if the sticky note could just fall off automatically?

That's what TTL does! You can set a column to expire after a certain
number of seconds. Once the time is up, the column is considered
"expired" and will be cleaned up during compaction.

This is really useful for things like:
- Temporary session data ("you're logged in for 30 minutes")
- Cache entries ("remember this answer for 5 minutes")
- Temporary announcements ("sale ends in 24 hours")

Example:
    >>> from pycoldb.ttl import TTLManager
    >>> manager = TTLManager()
    >>> manager.set_ttl("row1", "temp_note", ttl_seconds=60)
    >>> manager.is_expired("row1", "temp_note")
    False

"""

import time
from dataclasses import dataclass


@dataclass
class TTLEntry:
    """Track the expiration time for a single column.

    Attributes:
        created_at: When the TTL was set (epoch seconds).
        ttl_seconds: How many seconds until expiration.

    """

    created_at: float
    ttl_seconds: float

    @property
    def expires_at(self) -> float:
        """Calculate when this entry expires.

        Returns:
            The epoch timestamp when this entry expires.

        """
        return self.created_at + self.ttl_seconds

    def is_expired(self, current_time: float | None = None) -> bool:
        """Check whether this entry has expired.

        Args:
            current_time: The current time to check against. If None,
                uses the actual current time.

        Returns:
            True if the entry has expired, False otherwise.

        """
        now = current_time if current_time is not None else time.time()
        return now >= self.expires_at

    def to_dict(self) -> dict[str, float]:
        """Convert this TTL entry to a dictionary.

        Returns:
            A dictionary with created_at and ttl_seconds keys.

        """
        return {
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> TTLEntry:
        """Create a TTLEntry from a dictionary.

        Args:
            data: Dictionary with created_at and ttl_seconds keys.

        Returns:
            A new TTLEntry instance.

        """
        return cls(
            created_at=float(data["created_at"]),
            ttl_seconds=float(data["ttl_seconds"]),
        )


class TTLManager:
    """Manage time-to-live settings for columns across rows.

    The TTL manager keeps track of which columns have expiration times
    set. Think of it as a timer system -- you tell it "this sticky note
    should fall off in 60 seconds" and it remembers when each note
    should expire.

    The key format is "(row_key, column_name)" to uniquely identify
    each column that has a TTL set.
    """

    def __init__(self) -> None:
        """Initialize an empty TTL manager."""
        self._entries: dict[str, TTLEntry] = {}

    def _make_key(self, row_key: str, column_name: str) -> str:
        """Create a composite key for the TTL lookup.

        Args:
            row_key: The row key.
            column_name: The column name.

        Returns:
            A composite string key.

        """
        return f"{row_key}:{column_name}"

    def set_ttl(self, row_key: str, column_name: str, ttl_seconds: float) -> None:
        """Set a TTL for a specific column in a specific row.

        Args:
            row_key: The row containing the column.
            column_name: The column to set the TTL on.
            ttl_seconds: How many seconds until the column expires.

        Raises:
            ValueError: If ttl_seconds is not positive.

        """
        if ttl_seconds <= 0:
            msg = f"TTL must be positive, got {ttl_seconds}"
            raise ValueError(msg)
        key = self._make_key(row_key, column_name)
        self._entries[key] = TTLEntry(created_at=time.time(), ttl_seconds=ttl_seconds)

    def is_expired(self, row_key: str, column_name: str) -> bool:
        """Check whether a column's TTL has expired.

        If no TTL is set for this column, it never expires.

        Args:
            row_key: The row containing the column.
            column_name: The column to check.

        Returns:
            True if the column has expired, False if still alive
            or no TTL was set.

        """
        key = self._make_key(row_key, column_name)
        entry = self._entries.get(key)
        if entry is None:
            return False
        return entry.is_expired()

    def remove_ttl(self, row_key: str, column_name: str) -> None:
        """Remove the TTL for a specific column.

        Args:
            row_key: The row containing the column.
            column_name: The column to remove the TTL from.

        """
        key = self._make_key(row_key, column_name)
        self._entries.pop(key, None)

    def get_expired_columns(self, row_key: str) -> list[str]:
        """Get all expired column names for a given row.

        Args:
            row_key: The row to check for expired columns.

        Returns:
            A list of column names that have expired.

        """
        prefix = f"{row_key}:"
        expired: list[str] = []
        for key, entry in self._entries.items():
            if key.startswith(prefix) and entry.is_expired():
                column_name = key[len(prefix) :]
                expired.append(column_name)
        return expired

    def to_dict(self) -> dict[str, dict[str, float]]:
        """Convert all TTL entries to a dictionary.

        Returns:
            A dictionary mapping composite keys to TTL entry dicts.

        """
        return {key: entry.to_dict() for key, entry in self._entries.items()}

    @classmethod
    def from_dict(cls, data: dict[str, dict[str, float]]) -> TTLManager:
        """Create a TTLManager from a dictionary.

        Args:
            data: Dictionary mapping composite keys to TTL entry dicts.

        Returns:
            A new TTLManager instance.

        """
        manager = cls()
        for key, entry_data in data.items():
            manager._entries[key] = TTLEntry.from_dict(entry_data)
        return manager

    @property
    def entry_count(self) -> int:
        """Return the number of TTL entries being tracked.

        Returns:
            The count of tracked TTL entries.

        """
        return len(self._entries)
