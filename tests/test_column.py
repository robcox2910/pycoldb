"""Tests for the Column data structure."""

from pycoldb.column import Column

TIMESTAMP_1000 = 1000.0
TIMESTAMP_2000 = 2000.0
VALUE_42 = 42
VALUE_99 = 99


class TestColumnCreation:
    """Test creating columns with various parameters."""

    def test_create_column_with_string_value(self) -> None:
        """Create a column with a string value."""
        col = Column(name="grade", value="A+", timestamp=TIMESTAMP_1000)
        assert col.name == "grade"
        assert col.value == "A+"
        assert col.timestamp == TIMESTAMP_1000

    def test_create_column_with_int_value(self) -> None:
        """Create a column with an integer value."""
        col = Column(name="score", value=VALUE_99, timestamp=TIMESTAMP_1000)
        assert col.value == VALUE_99

    def test_create_column_with_float_value(self) -> None:
        """Create a column with a float value."""
        expected = 3.14
        col = Column(name="pi", value=expected, timestamp=TIMESTAMP_1000)
        assert col.value == expected

    def test_create_column_with_bool_value(self) -> None:
        """Create a column with a boolean value."""
        col = Column(name="active", value=True, timestamp=TIMESTAMP_1000)
        assert col.value is True

    def test_create_column_with_none_value(self) -> None:
        """Create a column with a None value."""
        col = Column(name="empty", value=None, timestamp=TIMESTAMP_1000)
        assert col.value is None

    def test_default_timestamp(self) -> None:
        """Verify that timestamp defaults to current time."""
        col = Column(name="test", value="val")
        assert col.timestamp > 0


class TestColumnSerialization:
    """Test converting columns to/from dictionaries."""

    def test_to_dict(self) -> None:
        """Convert a column to a dictionary."""
        col = Column(name="grade", value="A+", timestamp=TIMESTAMP_1000)
        result = col.to_dict()
        assert result["name"] == "grade"
        assert result["value"] == "A+"
        assert result["timestamp"] == TIMESTAMP_1000

    def test_from_dict(self) -> None:
        """Create a column from a dictionary."""
        data: dict[str, str | int | float | bool | None] = {
            "name": "grade",
            "value": "A+",
            "timestamp": TIMESTAMP_1000,
        }
        col = Column.from_dict(data)
        assert col.name == "grade"
        assert col.value == "A+"
        assert col.timestamp == TIMESTAMP_1000

    def test_roundtrip(self) -> None:
        """Verify to_dict and from_dict produce identical columns."""
        original = Column(name="score", value=VALUE_42, timestamp=TIMESTAMP_2000)
        restored = Column.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.value == original.value
        assert restored.timestamp == original.timestamp

    def test_from_dict_missing_timestamp(self) -> None:
        """Handle a dictionary with no timestamp field."""
        data: dict[str, str | int | float | bool | None] = {
            "name": "test",
            "value": "val",
        }
        col = Column.from_dict(data)
        assert col.timestamp == 0.0
