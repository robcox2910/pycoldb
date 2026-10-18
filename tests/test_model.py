"""Model check -- a ColumnFamily must behave exactly like a notebook of nested dicts.

A property test checks one rule for many inputs. A *model check* goes
further: Hypothesis invents a random *story* -- write this grade, delete
that one, wait three seconds, compact, read the other -- and plays it on
two things at once:

- the real ``ColumnFamily``;
- a **model**: a plain dict of dicts, row name -> column name -> what the
  notebook says about that grade.

After every step the two must agree. If they ever disagree, Hypothesis
shrinks the story to the shortest list of steps that still goes wrong.

The model is deliberately *not* a copy of ``ColumnFamily``'s code. It is a
plain notebook of the rules in the docs (the newest write wins, a delete
wins a tie, an expired grade is gone, compaction forgets what's crossed
out), so when the two disagree, the column family is the one to suspect.

Time comes from a pretend clock that only moves when the story says
"wait", so TTLs expire instantly and the test never sleeps.

See ``docs/property-testing.md`` for the walk-through.
"""

import unittest
from dataclasses import dataclass
from typing import cast

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, invariant, rule

from pycoldb.column import Column
from pycoldb.column_family import ColumnFamily
from pycoldb.compaction import compact_column_family
from pycoldb.errors import ColumnNotFoundError, InvalidTTLError, RowNotFoundError
from pycoldb.query import column_filter, query_with_filter, range_query
from pycoldb.ttl import TTLManager
from tests.strategies import (
    ColumnValue,
    PretendClock,
    any_names,
    column_values,
    few_names,
    timestamps,
    ttls,
)


@dataclass
class Grade:
    """One line in the notebook: a value and when it was written, maybe crossed out or timed."""

    value: ColumnValue
    timestamp: float
    deleted_at: float | None = None
    expires_at: float | None = None


def bad_ttls() -> st.SearchStrategy[float]:
    """Make a TTL the column family must refuse: zero or less."""
    return st.integers(max_value=0).map(float)


def delete_times() -> st.SearchStrategy[float | None]:
    """Make no time at all (use the default), or a delete time from 0 to 3 seconds."""
    # 0 is earlier than every write, and is the time a careless ``or`` drops.
    return st.one_of(st.none(), st.integers(min_value=0, max_value=3).map(float))


def maybe_names() -> st.SearchStrategy[str | None]:
    """Make no name at all (an open end of a range), or one of the few names."""
    return st.one_of(st.none(), few_names())


# --- The machine: one story, played on the column family and on the notebook --


class ColumnFamilyMachine(RuleBasedStateMachine):
    """Play random writes, deletes, waits, compactions and reads on a ColumnFamily and a notebook."""

    # Row names we've used before. Brand-new random names almost never repeat,
    # so rules also pick from here to read, rewrite or delete a row that
    # really is (or was) in the column family.
    rows = Bundle("rows")

    def __init__(self) -> None:
        """Start with an empty column family, an empty notebook and a stopped clock."""
        super().__init__()
        self.clock = PretendClock()
        self.cf = ColumnFamily(name="grades", ttl_manager=TTLManager(clock=self.clock))
        self.model: dict[str, dict[str, Grade]] = {}

    # --- Reading the notebook ------------------------------------------------

    def is_live(self, grade: Grade) -> bool:
        """Say whether a reader can see this grade: not crossed out, not expired."""
        return grade.deleted_at is None and (
            grade.expires_at is None or self.clock.now < grade.expires_at
        )

    def live_grades(self, row: str) -> dict[str, Grade]:
        """Return the grades a reader can see in one row, by column name."""
        return {name: g for name, g in self.model.get(row, {}).items() if self.is_live(g)}

    def live_rows(self) -> list[str]:
        """Return the names of the rows that have at least one grade a reader can see."""
        return sorted(row for row in self.model if self.live_grades(row))

    # --- Writing -------------------------------------------------------------

    def write(self, row: str, column: Column, ttl: float | None) -> None:
        """Write one grade to both, by the rule "the newest write wins; a delete wins a tie"."""
        self.cf.put(row, column, ttl_seconds=ttl)
        old = self.model.setdefault(row, {}).get(column.name)
        if old is not None and old.deleted_at is not None and column.timestamp <= old.deleted_at:
            return  # too old to undo the delete: ignored
        if old is not None and old.deleted_at is None and column.timestamp < old.timestamp:
            return  # older than what's there: ignored
        expires_at = None if ttl is None else self.clock.now + ttl
        self.model[row][column.name] = Grade(column.value, column.timestamp, expires_at=expires_at)

    @rule(
        target=rows,
        row=any_names(),
        name=few_names(),
        value=column_values(),
        timestamp=timestamps(),
        ttl=ttls(),
    )
    def put_new_row(
        self, row: str, name: str, value: ColumnValue, timestamp: float, ttl: float | None
    ) -> str:
        """Write a grade into a fresh row, and remember the row for later steps."""
        self.write(row, Column(name=name, value=value, timestamp=timestamp), ttl)
        return row

    @rule(row=rows, name=few_names(), value=column_values(), timestamp=timestamps(), ttl=ttls())
    def put_again(
        self, row: str, name: str, value: ColumnValue, timestamp: float, ttl: float | None
    ) -> None:
        """Write a grade into a row we've used before."""
        self.write(row, Column(name=name, value=value, timestamp=timestamp), ttl)

    @rule(row=st.one_of(rows, any_names()), name=few_names(), ttl=bad_ttls())
    def put_with_a_bad_ttl(self, row: str, name: str, ttl: float) -> None:
        """Refuse a TTL of zero or less, and change nothing."""
        with pytest.raises(InvalidTTLError):
            self.cf.put(row, Column(name=name, value="x", timestamp=3.0), ttl_seconds=ttl)

    @rule(row=rows, name=few_names(), value=column_values())
    def change_the_column_after_writing_it(self, row: str, name: str, value: ColumnValue) -> None:
        """Write a grade, then change the Column: the stored grade must not change."""
        column = Column(name=name, value=value, timestamp=3.0)
        self.write(row, column, None)
        column.value = "changed afterwards"

    # --- Deleting ------------------------------------------------------------

    @rule(row=st.one_of(rows, any_names()), name=few_names(), timestamp=delete_times())
    def delete_column(self, row: str, name: str, timestamp: float | None) -> None:
        """Delete a grade: a row with nothing live, or a grade that isn't live, is refused."""
        if not self.live_grades(row):
            with pytest.raises(RowNotFoundError):
                self.cf.delete_column(row, name, timestamp=timestamp)
            return
        grade = self.live_grades(row).get(name)
        if grade is None:
            with pytest.raises(ColumnNotFoundError):
                self.cf.delete_column(row, name, timestamp=timestamp)
            return
        self.cf.delete_column(row, name, timestamp=timestamp)
        grade.deleted_at = grade.timestamp if timestamp is None else timestamp
        grade.expires_at = None

    @rule(row=st.one_of(rows, any_names()), timestamp=delete_times())
    def delete_row(self, row: str, timestamp: float | None) -> None:
        """Delete every live grade in a row; a row with nothing live is refused."""
        live = self.live_grades(row)
        if not live:
            with pytest.raises(RowNotFoundError):
                self.cf.delete_row(row, timestamp=timestamp)
            return
        self.cf.delete_row(row, timestamp=timestamp)
        for grade in live.values():
            grade.deleted_at = grade.timestamp if timestamp is None else timestamp
            grade.expires_at = None

    # --- Time and tidying ----------------------------------------------------

    @rule(seconds=st.integers(min_value=1, max_value=3))
    def wait(self, seconds: int) -> None:
        """Move the pretend clock forward a few seconds."""
        self.clock.now += seconds

    @rule()
    def compact(self) -> None:
        """Compact: the notebook forgets crossed-out and expired grades, and the count matches."""
        forgotten = 0
        for row in list(self.model):
            grades = self.model[row]
            for name in [name for name, g in grades.items() if not self.is_live(g)]:
                del grades[name]
                forgotten += 1
            if not grades:
                del self.model[row]
        assert compact_column_family(self.cf) == forgotten

    # --- Reading -------------------------------------------------------------

    @rule(row=st.one_of(rows, any_names()), name=few_names())
    def get_column(self, row: str, name: str) -> None:
        """Read one grade: the notebook's value, or the right not-found error."""
        live = self.live_grades(row)
        if not live:
            with pytest.raises(RowNotFoundError):
                self.cf.get_column(row, name)
        elif name not in live:
            with pytest.raises(ColumnNotFoundError):
                self.cf.get_column(row, name)
        else:
            column = self.cf.get_column(row, name)
            assert (column.name, repr(column.value)) == (name, repr(live[name].value))
            assert column.timestamp == live[name].timestamp
            column.value = "changed after reading"  # must not reach the stored grade

    @rule(row=st.one_of(rows, any_names()))
    def get_row(self, row: str) -> None:
        """Read a whole row: the notebook's live grades, or RowNotFoundError if there are none."""
        assert self.cf.has_row(row) == bool(self.live_grades(row))
        if not self.live_grades(row):
            with pytest.raises(RowNotFoundError):
                self.cf.get_row(row)
            return
        found = self.cf.get_row(row)
        assert found.column_names(self.cf.ttl_manager) == sorted(self.live_grades(row))
        found.put_column(Column(name="sneaky", value="x", timestamp=99.0))  # must not stick

    @rule(
        start=maybe_names(),
        end=maybe_names(),
        with_start=st.booleans(),
        with_end=st.booleans(),
        names=st.lists(few_names(), max_size=3),
    )
    def query(
        self, start: str | None, end: str | None, with_start: bool, with_end: bool, names: list[str]
    ) -> None:
        """Query a range of rows, with and without a column filter: a plain loop must agree."""
        wanted = [
            row
            for row in self.live_rows()
            if (start is None or row > start or (with_start and row == start))
            and (end is None or row < end or (with_end and row == end))
        ]
        found = range_query(self.cf, start, end, inclusive_start=with_start, inclusive_end=with_end)
        assert [r.key for r in found] == wanted
        for row in found:
            kept = [c.name for c in column_filter(row, names, self.cf.ttl_manager)]
            assert kept == sorted(n for n in self.live_grades(row.key) if n in names)
        expected = [
            (row, sorted(n for n in self.live_grades(row) if n in names))
            for row in wanted
            if any(n in names for n in self.live_grades(row))
        ]
        filtered = query_with_filter(
            self.cf, names, start, end, inclusive_start=with_start, inclusive_end=with_end
        )
        assert [(key, [c.name for c in cols]) for key, cols in filtered] == expected

    @invariant()
    def same_rows_and_grades(self) -> None:
        """After every step, the column family shows exactly the notebook's live rows and grades."""
        assert self.cf.row_keys() == self.live_rows()
        assert self.cf.row_count == len(self.live_rows())
        for row in self.live_rows():
            found = self.cf.get_row(row).get_columns(ttl_manager=self.cf.ttl_manager)
            expected = sorted(self.live_grades(row).items())
            assert [(c.name, repr(c.value), c.timestamp) for c in found] == [
                (name, repr(g.value), g.timestamp) for name, g in expected
            ]

    @invariant()
    def same_crossed_out_grades(self) -> None:
        """After every step, the tombstones match the notebook's crossed-out grades and times."""
        crossed_out = sorted(
            (name, g.deleted_at)
            for grades in self.model.values()
            for name, g in grades.items()
            if g.deleted_at is not None
        )
        assert (
            sorted((t.column_name, t.deleted_at) for t in self.cf.get_tombstones()) == crossed_out
        )


# why: 20 steps find the same bugs; 50 (the default) is most of the run time
ColumnFamilyMachine.TestCase.settings = settings(stateful_step_count=20)
# pytest runs this like any other test class: one run plays 100 random stories.
# (Hypothesis doesn't say what type ``TestCase`` is, so ``cast`` tells pyright.)
TestColumnFamilyModel = cast("type[unittest.TestCase]", ColumnFamilyMachine.TestCase)
