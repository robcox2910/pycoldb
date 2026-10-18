"""Persistence -- saving and loading keyspaces to/from JSON files.

Think of this like saving your video game progress. When you turn off
the game (stop the program), your data doesn't disappear -- it's saved
to a file. When you start the game again, you can load your save file
and pick up where you left off.

We use JSON files because they're human-readable -- you can open them
in any text editor and see your data laid out in a nice structure.

Example:
    >>> from pycoldb.persistence import save_keyspace, load_keyspace
    >>> from pycoldb.keyspace import Keyspace
    >>> ks = Keyspace(name="school")
    >>> ks.create_column_family("grades")
    ColumnFamily(name='grades', ...)

"""

import json
from pathlib import Path
from typing import cast

from pycoldb.atomic import atomic_write_text
from pycoldb.errors import PersistenceError
from pycoldb.keyspace import Keyspace


def save_keyspace(keyspace: Keyspace, file_path: str | Path) -> None:
    """Save a keyspace to a JSON file.

    Serialize all the keyspace's data (column families, rows, columns,
    tombstones, TTL settings) into a JSON file.

    Args:
        keyspace: The keyspace to save.
        file_path: Path to the output JSON file.

    Raises:
        PersistenceError: If the file cannot be written.

    """
    path = Path(file_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = keyspace.to_dict()
        atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True))
    except OSError as exc:
        msg = f"Failed to save keyspace to '{file_path}': {exc}"
        raise PersistenceError(msg) from exc


def load_keyspace(file_path: str | Path) -> Keyspace:
    """Load a keyspace from a JSON file.

    Deserialize a keyspace from a previously saved JSON file,
    restoring all column families, rows, columns, tombstones,
    and TTL settings.

    Args:
        file_path: Path to the JSON file to load.

    Returns:
        The deserialized Keyspace.

    Raises:
        PersistenceError: If the file cannot be read or parsed, or isn't
            something save_keyspace could have written (each column filed
            under its own name, every value and time the right type, and
            so on).

    """
    path = Path(file_path)
    try:
        text = path.read_text(encoding="utf-8")
    # A file that isn't UTF-8 text (a photo, a zip, a corrupted save) fails
    # while decoding, not while reading, so it needs catching too.
    except (OSError, UnicodeDecodeError) as exc:
        msg = f"Failed to load keyspace from '{file_path}': {exc}"
        raise PersistenceError(msg) from exc
    try:
        data: object = json.loads(text)
    # JSONDecodeError is a kind of ValueError; a plain ValueError also means a
    # number too long for Python to read, and RecursionError means lists or
    # objects nested too deep. Each one is a file we can't load.
    except (ValueError, RecursionError) as exc:
        msg = f"Failed to load keyspace from '{file_path}': {exc}"
        raise PersistenceError(msg) from exc

    # Refuse anything save_keyspace could never have written, rather than
    # loading it as something else that the next save would write over.
    try:
        _check_keyspace(data)
        return Keyspace.from_dict(cast("dict[str, object]", data))
    # OverflowError: a number too big to be a float, like 10**400.
    except (_NotASaveFileError, KeyError, TypeError, ValueError, OverflowError) as exc:
        msg = f"Invalid keyspace data in '{file_path}': {exc}"
        raise PersistenceError(msg) from exc


class _NotASaveFileError(ValueError):
    """Say what's wrong with a file that save_keyspace could never have written."""


def _require(ok: bool, problem: str) -> None:
    """Raise _NotASaveFileError saying ``problem`` unless ``ok``."""
    if not ok:
        raise _NotASaveFileError(problem)


def _is_number(value: object) -> bool:
    """Say whether ``value`` is a JSON number (True and False don't count)."""
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_column_value(value: object) -> bool:
    """Say whether a column can hold ``value``: text, a number, True/False or None."""
    return value is None or isinstance(value, str | int | float)


def _as_object(value: object) -> dict[str, object]:
    """Return ``value`` as a JSON object (its keys are always text)."""
    return cast("dict[str, object]", value)


def _check_keyspace(data: object) -> None:
    """Check ``data`` is shaped exactly like a saved keyspace."""
    _require(isinstance(data, dict), "expected a JSON object")
    fields = _as_object(data)
    _require(isinstance(fields.get("name"), str), "the keyspace has no name")
    families = fields.get("column_families")
    _require(isinstance(families, dict), "no column families")
    for name, family in _as_object(families).items():
        _check_family(name, family)


def _check_family(name: str, data: object) -> None:
    """Check ``data`` is a saved column family filed under its own ``name``."""
    _require(isinstance(data, dict), f"column family '{name}' is not an object")
    fields = _as_object(data)
    _require(fields.get("name") == name, f"column family '{name}' is filed under another name")
    rows, ttl = fields.get("rows"), fields.get("ttl")
    _require(isinstance(rows, dict), f"column family '{name}' has no rows")
    _require(isinstance(ttl, list), f"column family '{name}' has no TTL list")
    for key, row in _as_object(rows).items():
        _check_row(key, row)
    timed: set[tuple[object, object]] = set()
    for record in cast("list[object]", ttl):
        _require(isinstance(record, dict), f"a TTL in '{name}' is not an object")
        entry = _as_object(record)
        _require(
            isinstance(entry.get("row_key"), str)
            and isinstance(entry.get("column_name"), str)
            and _is_number(entry.get("created_at"))
            and _is_number(entry.get("ttl_seconds")),
            f"a TTL in '{name}' is missing a name or a time",
        )
        # set_ttl refuses a TTL that isn't positive, so a saved one never is.
        _require(not cast("float", entry["ttl_seconds"]) <= 0, f"a TTL in '{name}' isn't positive")
        pair = (entry["row_key"], entry["column_name"])
        _require(pair not in timed, f"a column in '{name}' has two TTLs")
        timed.add(pair)


def _check_row(key: str, data: object) -> None:
    """Check ``data`` is a saved row filed under its own ``key``."""
    _require(isinstance(data, dict), f"row '{key}' is not an object")
    fields = _as_object(data)
    _require(fields.get("key") == key, f"row '{key}' is filed under another key")
    columns, tombstones = fields.get("columns"), fields.get("tombstones")
    _require(isinstance(columns, dict), f"row '{key}' has no columns")
    _require(isinstance(tombstones, dict), f"row '{key}' has no tombstones")
    for name, column in _as_object(columns).items():
        _require(isinstance(column, dict), f"column '{name}' in row '{key}' is not an object")
        cell = _as_object(column)
        _require(
            cell.get("name") == name
            and "value" in cell
            and _is_column_value(cell["value"])
            and _is_number(cell.get("timestamp")),
            f"column '{name}' in row '{key}' isn't a saved column",
        )
    for name, tombstone in _as_object(tombstones).items():
        _require(isinstance(tombstone, dict), f"tombstone '{name}' in row '{key}' is not an object")
        mark = _as_object(tombstone)
        _require(
            mark.get("column_name") == name and _is_number(mark.get("deleted_at")),
            f"tombstone '{name}' in row '{key}' isn't a saved tombstone",
        )
        # A write takes the tombstone away, and a delete takes the column away.
        _require(name not in _as_object(columns), f"column '{name}' in row '{key}' is also deleted")
