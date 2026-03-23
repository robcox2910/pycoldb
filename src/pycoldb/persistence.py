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
        path.write_text(json.dumps(data, indent=2, sort_keys=True))
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
        PersistenceError: If the file cannot be read or parsed.

    """
    path = Path(file_path)
    try:
        text = path.read_text()
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"Failed to load keyspace from '{file_path}': {exc}"
        raise PersistenceError(msg) from exc

    if not isinstance(data, dict):
        msg = f"Invalid keyspace data in '{file_path}': expected a JSON object"
        raise PersistenceError(msg)

    return Keyspace.from_dict(data)  # pyright: ignore[reportUnknownArgumentType]
