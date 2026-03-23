"""Keyspace -- the top-level container for column families.

Think of a keyspace as an entire **school**. Inside the school, there
are many different classes (column families), each with their own
gradebooks. The school organizes everything together.

In real databases like Cassandra, a keyspace is similar to a "database"
in MySQL or PostgreSQL. It groups related column families together and
can have its own configuration (like how many copies of data to keep).

Example:
    >>> from pycoldb.keyspace import Keyspace
    >>> from pycoldb.column import Column
    >>> school = Keyspace(name="school")
    >>> school.create_column_family("grades")
    >>> school.put("grades", "alice", Column(name="math", value="A+", timestamp=1000))
    >>> school.get_column("grades", "alice", "math").value
    'A+'

"""

from dataclasses import dataclass, field

from pycoldb.column import Column
from pycoldb.column_family import ColumnFamily
from pycoldb.errors import (
    ColumnFamilyAlreadyExistsError,
    ColumnFamilyNotFoundError,
)


@dataclass
class Keyspace:
    """A named container for multiple column families.

    A keyspace is the highest level of organization, like a school
    that contains many classrooms (column families).

    Attributes:
        name: The name of this keyspace.
        column_families: Dictionary mapping names to ColumnFamily objects.

    """

    name: str
    column_families: dict[str, ColumnFamily] = field(default_factory=lambda: {})

    def create_column_family(self, name: str) -> ColumnFamily:
        """Create a new column family in this keyspace.

        Args:
            name: The name for the new column family.

        Returns:
            The newly created ColumnFamily.

        Raises:
            ColumnFamilyAlreadyExistsError: If a column family with
                this name already exists.

        """
        if name in self.column_families:
            msg = f"Column family '{name}' already exists in keyspace '{self.name}'"
            raise ColumnFamilyAlreadyExistsError(msg)
        cf = ColumnFamily(name=name)
        self.column_families[name] = cf
        return cf

    def drop_column_family(self, name: str) -> None:
        """Remove a column family from this keyspace.

        Args:
            name: The column family name to remove.

        Raises:
            ColumnFamilyNotFoundError: If the column family doesn't exist.

        """
        if name not in self.column_families:
            msg = f"Column family '{name}' not found in keyspace '{self.name}'"
            raise ColumnFamilyNotFoundError(msg)
        del self.column_families[name]

    def get_column_family(self, name: str) -> ColumnFamily:
        """Get a column family by name.

        Args:
            name: The column family name.

        Returns:
            The ColumnFamily object.

        Raises:
            ColumnFamilyNotFoundError: If it doesn't exist.

        """
        if name not in self.column_families:
            msg = f"Column family '{name}' not found in keyspace '{self.name}'"
            raise ColumnFamilyNotFoundError(msg)
        return self.column_families[name]

    def put(
        self,
        cf_name: str,
        row_key: str,
        column: Column,
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        """Insert or update a column in a column family.

        A convenience method that combines getting the column family
        and inserting data in one step.

        Args:
            cf_name: The column family name.
            row_key: The row key.
            column: The column to insert or update.
            ttl_seconds: Optional TTL in seconds.

        Raises:
            ColumnFamilyNotFoundError: If the column family doesn't exist.

        """
        cf = self.get_column_family(cf_name)
        cf.put(row_key, column, ttl_seconds=ttl_seconds)

    def get_column(self, cf_name: str, row_key: str, column_name: str) -> Column:
        """Get a column from a column family.

        Args:
            cf_name: The column family name.
            row_key: The row key.
            column_name: The column name.

        Returns:
            The requested Column.

        Raises:
            ColumnFamilyNotFoundError: If the column family doesn't exist.
            RowNotFoundError: If the row doesn't exist.
            ColumnNotFoundError: If the column doesn't exist.

        """
        cf = self.get_column_family(cf_name)
        return cf.get_column(row_key, column_name)

    def column_family_names(self) -> list[str]:
        """Get the names of all column families.

        Returns:
            A sorted list of column family names.

        """
        return sorted(self.column_families.keys())

    @property
    def column_family_count(self) -> int:
        """Count the column families in this keyspace.

        Returns:
            The number of column families.

        """
        return len(self.column_families)

    def to_dict(self) -> dict[str, object]:
        """Convert this keyspace to a dictionary.

        Returns:
            A dictionary with name and column_families data.

        """
        return {
            "name": self.name,
            "column_families": {name: cf.to_dict() for name, cf in self.column_families.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Keyspace:
        """Create a Keyspace from a dictionary.

        Args:
            data: Dictionary with name and column_families data.

        Returns:
            A new Keyspace instance.

        """
        name = str(data["name"])
        cfs_data = data.get("column_families", {})

        column_families: dict[str, ColumnFamily] = {}
        if isinstance(cfs_data, dict):
            for cf_name, cf_data in cfs_data.items():  # pyright: ignore[reportUnknownVariableType]
                if isinstance(cf_data, dict):
                    cf_dict: dict[str, object] = {str(k): v for k, v in cf_data.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
                    column_families[str(cf_name)] = ColumnFamily.from_dict(cf_dict)  # pyright: ignore[reportUnknownArgumentType]

        return cls(name=name, column_families=column_families)
