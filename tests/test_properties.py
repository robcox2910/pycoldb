"""Property-based tests -- rules that must hold for *every* input.

An ordinary test checks one example someone thought of: "give alice an A+
in math, delete it, compact, and alice is gone". A property test states a
rule instead, such as "whatever the gradebook holds, compaction never
changes what a reader sees", and lets Hypothesis invent hundreds of
gradebooks to try to break it. If one breaks the rule, Hypothesis *shrinks*
it down to the smallest input that still fails, and shows you that.

Each test below says its rule in plain English in its docstring. The
strategies at the top are recipes for making random inputs; each one is
named for what it makes.

The step-by-step check of ``ColumnFamily`` against plain nested dicts lives
in ``tests/test_model.py``. See ``docs/property-testing.md`` for the
walk-through.
"""

import json
import tempfile
from pathlib import Path
from typing import cast

from hypothesis import given
from hypothesis import strategies as st

from pycoldb.column_family import ColumnFamily
from pycoldb.compaction import compact_column_family
from pycoldb.errors import ColumnNotFoundError, PersistenceError, RowNotFoundError
from pycoldb.keyspace import Keyspace
from pycoldb.persistence import load_keyspace, save_keyspace
from pycoldb.ttl import TTLManager
from tests.strategies import (
    FEW_NAMES,
    PretendClock,
    Step,
    any_names,
    few_names,
    play,
    stories,
)

# --- Strategies: recipes for random inputs -----------------------------------
# few_names(), any_names(), column_values(), timestamps() and stories() live
# in tests/strategies.py, shared with the model check.

# Junk JSON is built from at most this many plain pieces. Hypothesis allows
# 100 by default, which is slow to invent; small junk finds the same bugs.
MOST_JUNK_PIECES = 5


def gradebooks() -> st.SearchStrategy[dict[str, list[Step]]]:
    """Make a whole school's worth of stories: one story per column family name."""
    return st.dictionaries(any_names(), stories(any_names()), max_size=3)


def any_bytes() -> st.SearchStrategy[bytes]:
    """Make any run of raw bytes, including the empty one and ones that aren't text."""
    return st.binary()


def lists_and_objects_of(
    children: st.SearchStrategy[object],
) -> st.SearchStrategy[list[object] | dict[str, object]]:
    """Make a JSON list, or a JSON object with text keys, holding values made by ``children``."""
    return st.one_of(st.lists(children), st.dictionaries(st.text(), children))


def any_json() -> st.SearchStrategy[object]:
    """Make any small JSON value: null, true/false, numbers, text, lists and objects."""
    return st.recursive(
        st.one_of(st.none(), st.booleans(), st.integers(), st.floats(), st.text()),
        lists_and_objects_of,
        max_leaves=MOST_JUNK_PIECES,
    )


@st.composite
def damaged_save_files(draw: st.DrawFn) -> object:
    """Make a real save file with exactly one piece, at any depth, swapped for junk."""
    # Random JSON almost never looks like a save file, so the loader would
    # refuse it at the door. Damaging one spot in a real file gets the junk
    # past the door, down to the deeper checks.
    # Small gradebooks (few names, at most two families) are quick to make
    # and still have every kind of piece: columns, tombstones and TTLs.
    small = draw(st.dictionaries(few_names(), stories(few_names()), max_size=2))
    saved = keyspace_from(small).to_dict()
    document = json.loads(json.dumps(saved))  # exactly what save_keyspace writes
    spot = draw(st.sampled_from(list(every_spot(document))))
    return with_junk_at(document, spot, draw(any_json()))


# --- Helpers -----------------------------------------------------------------


def keyspace_from(gradebooks: dict[str, list[Step]]) -> Keyspace:
    """Return a keyspace with one column family per story, each story played on it."""
    keyspace = Keyspace(name="school")
    for name, story in gradebooks.items():
        clock = PretendClock()
        cf = ColumnFamily(name=name, ttl_manager=TTLManager(clock=clock))
        keyspace.column_families[name] = cf
        for step in story:
            play(step, cf, clock)
    return keyspace


def in_name_order(tree: object) -> object:
    """Return ``tree`` with every dict's keys in sorted order, all the way down."""
    # The save file lists names in sorted order, so a loaded dict comes back
    # sorted, whatever order the names were first written in.
    if isinstance(tree, dict):
        items = cast("dict[str, object]", tree)
        return {key: in_name_order(items[key]) for key in sorted(items)}
    if isinstance(tree, list):
        return [in_name_order(item) for item in cast("list[object]", tree)]
    return tree


def what_readers_see(cf: ColumnFamily) -> list[object]:
    """Return every answer a reader could get from ``cf`` for the names a story uses."""
    seen: list[object] = [cf.row_keys(), cf.row_count]
    for row in FEW_NAMES:
        seen.append(cf.has_row(row))
        try:
            seen.append(repr(cf.get_row(row).get_columns(ttl_manager=cf.ttl_manager)))
        except RowNotFoundError as exc:
            seen.append(type(exc).__name__)
        for column in FEW_NAMES:
            try:
                seen.append(repr(cf.get_column(row, column)))
            except (RowNotFoundError, ColumnNotFoundError) as exc:
                seen.append(type(exc).__name__)
    return seen


def every_spot(document: object, path: tuple[str | int, ...] = ()) -> list[tuple[str | int, ...]]:
    """Return the path to every value in a JSON document, the whole document included."""
    spots = [path]
    if isinstance(document, dict):
        for key, value in cast("dict[str, object]", document).items():
            spots += every_spot(value, (*path, key))
    elif isinstance(document, list):
        for index, value in enumerate(cast("list[object]", document)):
            spots += every_spot(value, (*path, index))
    return spots


def with_junk_at(document: object, spot: tuple[str | int, ...], junk: object) -> object:
    """Return ``document`` with the value at ``spot`` replaced by ``junk``."""
    if not spot:
        return junk
    parent = document
    for step in spot[:-1]:
        parent = cast("dict[str | int, object]", parent)[step]
    cast("dict[str | int, object]", parent)[spot[-1]] = junk
    return document


def load_or_refuse(path: Path) -> None:
    """Load the keyspace at ``path``, accepting only a PersistenceError refusal.

    A PersistenceError is caught and ignored: refusing a bad file is fine. Any
    *other* exception escapes and fails the test, and that is the whole check.
    """
    try:
        load_keyspace(path)
    except PersistenceError:
        return


# --- Compaction: tidying up never changes the answers ------------------------


@given(story=stories(few_names()))
def test_compaction_never_changes_what_reads_return(story: list[Step]) -> None:
    """Whatever was written, deleted or expired, every read gives the same answer after compaction."""
    clock = PretendClock()
    cf = ColumnFamily(name="grades", ttl_manager=TTLManager(clock=clock))
    for step in story:
        play(step, cf, clock)
    before = what_readers_see(cf)
    compact_column_family(cf)
    assert what_readers_see(cf) == before


@given(story=stories(few_names()))
def test_compaction_leaves_no_tombstones_or_expired_columns(story: list[Step]) -> None:
    """After compaction nothing deleted or expired is left, and the count says how much went."""
    clock = PretendClock()
    cf = ColumnFamily(name="grades", ttl_manager=TTLManager(clock=clock))
    for step in story:
        play(step, cf, clock)
    tombstones = len(cf.get_tombstones())
    expired = sum(len(cf.ttl_manager.get_expired_columns(row)) for row in cf.rows)
    assert compact_column_family(cf) == tombstones + expired
    assert cf.get_tombstones() == []
    for key, row in cf.rows.items():
        assert row.columns, "an empty row is left behind"
        assert row.column_names() == row.column_names(cf.ttl_manager), "an expired column is left"
        assert cf.ttl_manager.get_expired_columns(key) == []


# --- Save and load: whatever you save comes back -----------------------------


@given(gradebooks=gradebooks())
def test_save_then_load_gives_back_the_same_keyspace(gradebooks: dict[str, list[Step]]) -> None:
    """Loading a saved keyspace gives back exactly the same families, rows, columns, deletes and TTLs."""
    keyspace = keyspace_from(gradebooks)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "school.json"
        save_keyspace(keyspace, path)
        loaded = load_keyspace(path)
    # ``==`` thinks True == 1 == 1.0, so a value saved as True and loaded as
    # 1 would pass it. ``repr`` writes each one differently, at every depth.
    assert repr(in_name_order(loaded.to_dict())) == repr(in_name_order(keyspace.to_dict()))


# --- Loading junk: a bad save file is refused, never a crash ------------------


@given(junk=any_bytes())
def test_any_bytes_on_disk_load_or_raise_persistence_error(junk: bytes) -> None:
    """Whatever bytes are in the file, loading gives a keyspace or a PersistenceError, never another error."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "school.json"
        path.write_bytes(junk)
        load_or_refuse(path)


@given(document=any_json())
def test_any_json_on_disk_load_or_raise_persistence_error(document: object) -> None:
    """Whatever JSON is in the file, loading gives a keyspace or a PersistenceError, never another error."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "school.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        load_or_refuse(path)


@given(document=damaged_save_files())
def test_any_damaged_save_file_load_or_raise_persistence_error(document: object) -> None:
    """Whatever one piece of a real save file is swapped for, loading gives a keyspace or a PersistenceError."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "school.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        load_or_refuse(path)
