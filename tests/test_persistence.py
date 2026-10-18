"""Tests for persistence (save/load) functionality."""

import json
import os
from collections.abc import Sequence
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


class _SimulatedCrashError(OSError):
    """Stands in for the power going out part-way through a save."""


def test_interrupted_save_keeps_the_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a crash mid-save used to leave a truncated, unloadable file."""
    ks = Keyspace(name="s")
    ks.create_column_family("a")
    path = tmp_path / "data.json"
    save_keyspace(ks, path)
    before = path.read_bytes()
    ks.create_column_family("b")

    def write_half_then_crash(self: Path, data: str, *_args: object, **_kwargs: object) -> int:
        with self.open("w", encoding="utf-8") as handle:
            handle.write(data[: len(data) // 2])
        raise _SimulatedCrashError

    def crash(*_args: object) -> None:
        raise _SimulatedCrashError

    monkeypatch.setattr(Path, "write_text", write_half_then_crash)
    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises((OSError, PersistenceError)):
        save_keyspace(ks, path)
    monkeypatch.undo()
    assert path.read_bytes() == before
    load_keyspace(path)
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


WRONG_SHAPES = [
    "{}",
    '{"name": "k", "column_families": [1]}',
    '{"name": "k", "column_families": {"cf": 1}}',
]


class TestWrongShapeFiles:
    """Valid JSON that isn't a saved keyspace is refused, never loaded as empty."""

    @pytest.mark.parametrize("content", WRONG_SHAPES)
    def test_wrong_shape_raises_persistence_error_naming_the_file(
        self, tmp_path: Path, content: str
    ) -> None:
        """Loading it raises PersistenceError with the file name, so it can't be overwritten."""
        path = tmp_path / "saved.json"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(PersistenceError, match=r"saved\.json"):
            load_keyspace(path)


def _save_file(
    *,
    family: dict[str, object] | None = None,
    row: dict[str, object] | None = None,
    column: dict[str, object] | None = None,
    tombstones: dict[str, object] | None = None,
    ttl: Sequence[object] | None = None,
) -> str:
    """Return a one-grade save file (alice's math), with any part swapped for something else."""
    math = {"name": "math", "value": "A", "timestamp": 1.0} if column is None else column
    alice = {"key": "alice", "columns": {"math": math}, "tombstones": tombstones or {}}
    grades = {
        "name": "grades",
        "rows": {"alice": alice if row is None else row},
        "ttl": list(ttl or []),
    }
    return json.dumps({"name": "school", "column_families": {"grades": family or grades}})


DAMAGED_FILES = {
    # Found by test_any_bytes_on_disk_load_or_raise_persistence_error.
    "not UTF-8 text": b"\x80",
    # Python refuses to read a whole number this long (a ValueError).
    "5000-digit number": b"1" * 5000,
    # Nested too deep for json to read (a RecursionError).
    "nested too deep": b"[" * 100_000,
    # Too big for a float (an OverflowError).
    "timestamp too big": _save_file(
        column={"name": "math", "value": "A", "timestamp": 10**400}
    ).encode(),
    # Shapes save_keyspace never writes, which used to load as something else.
    "value is a list": _save_file(column={"name": "math", "value": [1], "timestamp": 1.0}).encode(),
    "timestamp is text": _save_file(
        column={"name": "math", "value": "A", "timestamp": "1"}
    ).encode(),
    "timestamp is true": _save_file(
        column={"name": "math", "value": "A", "timestamp": True}
    ).encode(),
    "column under the wrong name": _save_file(
        column={"name": "art", "value": "A", "timestamp": 1.0}
    ).encode(),
    "row under the wrong key": _save_file(
        row={"key": "bob", "columns": {}, "tombstones": {}}
    ).encode(),
    "family under the wrong name": _save_file(
        family={"name": "art", "rows": {}, "ttl": []}
    ).encode(),
    "family without rows": _save_file(family={"name": "grades", "ttl": []}).encode(),
    "column both live and deleted": _save_file(
        tombstones={"math": {"column_name": "math", "deleted_at": 1.0}}
    ).encode(),
    "the same TTL twice": _save_file(
        ttl=[{"row_key": "alice", "column_name": "math", "created_at": 1.0, "ttl_seconds": 5.0}] * 2
    ).encode(),
    "TTL of zero": _save_file(
        ttl=[{"row_key": "alice", "column_name": "math", "created_at": 1.0, "ttl_seconds": 0}]
    ).encode(),
}


class TestDamagedSaveFiles:
    """Every damaged save file is refused with a PersistenceError naming it, never another error."""

    @pytest.mark.parametrize("content", DAMAGED_FILES.values(), ids=DAMAGED_FILES.keys())
    def test_damaged_file_raises_persistence_error(self, tmp_path: Path, content: bytes) -> None:
        """Loading it raises PersistenceError with the file name."""
        path = tmp_path / "saved.json"
        path.write_bytes(content)
        with pytest.raises(PersistenceError, match=r"saved\.json"):
            load_keyspace(path)

    def test_the_undamaged_file_loads(self, tmp_path: Path) -> None:
        """The file the damaged ones start from is a good save file."""
        path = tmp_path / "saved.json"
        path.write_text(
            _save_file(
                ttl=[{"row_key": "alice", "column_name": "math", "created_at": 1, "ttl_seconds": 5}]
            ),
            encoding="utf-8",
        )
        assert load_keyspace(path).get_column_family("grades").ttl_manager.entry_count == 1
