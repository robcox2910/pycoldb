"""Tests for persistence (save/load) functionality."""

import json
from pathlib import Path

import pytest

from pycoldb.column import Column
from pycoldb.errors import PersistenceError
from pycoldb.keyspace import Keyspace
from pycoldb.persistence import load_keyspace, save_keyspace

TIMESTAMP_1000 = 1000.0
TIMESTAMP_2000 = 2000.0
VALUE_95 = 95
VALUE_88 = 88


class TestSaveKeyspace:
    """Test saving keyspaces to JSON files."""

    def test_save_creates_file(self, tmp_path: Path) -> None:
        """Verify save creates a JSON file."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        file_path = tmp_path / "test.json"
        save_keyspace(ks, file_path)
        assert file_path.exists()

    def test_save_valid_json(self, tmp_path: Path) -> None:
        """Verify saved file contains valid JSON."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        file_path = tmp_path / "test.json"
        save_keyspace(ks, file_path)
        data = json.loads(file_path.read_text())
        assert data["name"] == "school"

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Verify save creates parent directories if needed."""
        ks = Keyspace(name="school")
        file_path = tmp_path / "subdir" / "deep" / "test.json"
        save_keyspace(ks, file_path)
        assert file_path.exists()

    def test_save_string_path(self, tmp_path: Path) -> None:
        """Verify save works with string paths."""
        ks = Keyspace(name="school")
        file_path = str(tmp_path / "test.json")
        save_keyspace(ks, file_path)
        assert Path(file_path).exists()


class TestLoadKeyspace:
    """Test loading keyspaces from JSON files."""

    def test_load_roundtrip(self, tmp_path: Path) -> None:
        """Verify save then load preserves all data."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        ks.put("grades", "alice", Column(name="math", value=VALUE_95, timestamp=TIMESTAMP_1000))
        ks.put("grades", "bob", Column(name="science", value=VALUE_88, timestamp=TIMESTAMP_2000))

        file_path = tmp_path / "test.json"
        save_keyspace(ks, file_path)
        restored = load_keyspace(file_path)

        assert restored.name == "school"
        assert restored.column_family_count == 1
        assert restored.get_column("grades", "alice", "math").value == VALUE_95
        assert restored.get_column("grades", "bob", "science").value == VALUE_88

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        """Raise PersistenceError for missing files."""
        file_path = tmp_path / "nonexistent.json"
        with pytest.raises(PersistenceError, match="Failed to load"):
            load_keyspace(file_path)

    def test_load_invalid_json_raises(self, tmp_path: Path) -> None:
        """Raise PersistenceError for invalid JSON."""
        file_path = tmp_path / "bad.json"
        file_path.write_text("not valid json {{{")
        with pytest.raises(PersistenceError, match="Failed to load"):
            load_keyspace(file_path)

    def test_load_non_object_json_raises(self, tmp_path: Path) -> None:
        """Raise PersistenceError when JSON is not an object."""
        file_path = tmp_path / "array.json"
        file_path.write_text("[1, 2, 3]")
        with pytest.raises(PersistenceError, match="expected a JSON object"):
            load_keyspace(file_path)

    def test_load_with_tombstones(self, tmp_path: Path) -> None:
        """Verify tombstones survive save/load cycle."""
        ks = Keyspace(name="school")
        ks.create_column_family("grades")
        ks.put("grades", "alice", Column(name="math", value="A+", timestamp=TIMESTAMP_1000))
        cf = ks.get_column_family("grades")
        cf.delete_column("alice", "math")

        file_path = tmp_path / "test.json"
        save_keyspace(ks, file_path)
        restored = load_keyspace(file_path)

        restored_cf = restored.get_column_family("grades")
        tombstones = restored_cf.get_tombstones()
        assert len(tombstones) == 1
        assert tombstones[0].column_name == "math"
