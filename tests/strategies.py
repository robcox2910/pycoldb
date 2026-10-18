"""Strategies -- recipes for random names, values and steps, shared by the property tests.

A strategy tells Hypothesis how to invent one kind of input. Each one here
is a named function, named for what it makes, with a one-line docstring.
``tests/test_properties.py`` and ``tests/test_model.py`` both use them.

The steps (``Put``, ``Delete`` and ``Wait``) are small records of "what to
do next". ``play`` carries one out on a column family.
"""

import contextlib
from dataclasses import dataclass

from hypothesis import strategies as st

from pycoldb.column import Column
from pycoldb.column_family import ColumnFamily
from pycoldb.errors import ColumnNotFoundError, RowNotFoundError

type ColumnValue = str | int | float | bool | None

# A handful of names. Random text almost never repeats, so steps that pick
# from these few keep landing on the same rows and columns: writing over a
# grade, deleting it, writing it again.
FEW_NAMES = ("alice", "bob", "math")

# A story is at most this many steps. Longer stories find the same bugs and
# take longer to invent; a failing story shrinks to a few steps anyway.
MOST_STEPS = 12


class PretendClock:
    """A clock that only moves when you move it, so tests never wait."""

    def __init__(self, start: float = 1000.0) -> None:
        """Start the clock at ``start`` seconds."""
        self.now = start

    def __call__(self) -> float:
        """Tell the time, the same way ``time.time()`` does."""
        return self.now


@dataclass(frozen=True)
class Put:
    """Write ``value`` into one column, stamped ``timestamp``, maybe with a TTL."""

    row: str
    column: str
    value: ColumnValue
    timestamp: float
    ttl_seconds: float | None


@dataclass(frozen=True)
class Delete:
    """Delete one column."""

    row: str
    column: str


@dataclass(frozen=True)
class Wait:
    """Move the pretend clock forward by ``seconds``."""

    seconds: float


type Step = Put | Delete | Wait


def play(step: Step, cf: ColumnFamily, clock: PretendClock) -> None:
    """Carry out one step on ``cf``, moving ``clock`` for a ``Wait``."""
    match step:
        case Put():
            column = Column(name=step.column, value=step.value, timestamp=step.timestamp)
            cf.put(step.row, column, ttl_seconds=step.ttl_seconds)
        case Delete():
            # Deleting a column that isn't there is refused; for a story
            # that's fine, the step just does nothing.
            with contextlib.suppress(RowNotFoundError, ColumnNotFoundError):
                cf.delete_column(step.row, step.column)
        case Wait():
            clock.now += step.seconds


def few_names() -> st.SearchStrategy[str]:
    """Pick one of a few names, so steps keep landing on the same rows and columns."""
    return st.sampled_from(FEW_NAMES)


def any_names() -> st.SearchStrategy[str]:
    """Make any name at all: empty, spaces, emoji, quotes, or one of the few."""
    return st.one_of(few_names(), st.text())


def column_values() -> st.SearchStrategy[ColumnValue]:
    """Make one value a column can hold: text, a whole number, a decimal, True/False or None."""
    # The allowed types are listed on Column.value in src/pycoldb/column.py.
    return st.one_of(
        st.text(),
        st.integers(),
        # NaN ("not a number") is never equal to itself, so ``==`` could never
        # confirm it came back. That's a rule of floats, not of PyColDB.
        st.floats(allow_nan=False),
        st.booleans(),
        st.none(),
    )


def timestamps() -> st.SearchStrategy[float]:
    """Make a write time from a few whole seconds, so two writes often tie."""
    # Writes start at 1 so a delete can be stamped 0, before every write.
    return st.integers(min_value=1, max_value=3).map(float)


def ttls() -> st.SearchStrategy[float | None]:
    """Make no TTL at all, or a TTL of a few whole seconds."""
    # set_ttl's docstring says a TTL must be positive.
    return st.one_of(st.none(), st.integers(min_value=1, max_value=3).map(float))


def puts(names: st.SearchStrategy[str]) -> st.SearchStrategy[Put]:
    """Make a write to a row and column whose names come from ``names``."""
    return st.builds(Put, names, names, column_values(), timestamps(), ttls())


def steps(names: st.SearchStrategy[str]) -> st.SearchStrategy[Step]:
    """Make one step of a story: a write, a delete, or a short wait."""
    return st.one_of(
        puts(names),
        st.builds(Delete, names, names),
        st.builds(Wait, st.integers(min_value=1, max_value=3).map(float)),
    )


def stories(names: st.SearchStrategy[str]) -> st.SearchStrategy[list[Step]]:
    """Make a short story of steps on one column family."""
    return st.lists(steps(names), max_size=MOST_STEPS)
