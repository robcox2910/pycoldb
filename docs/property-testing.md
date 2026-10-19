# Property Testing (Copying Out the Gradebook)

## The Proofreader

Picture the school office at the end of term. The gradebooks are a mess:
grades crossed out, sticky notes that ran out of time, corrections on top
of corrections. So someone copies each gradebook onto fresh pages, leaving
out everything crossed out or expired. That's
[compaction](concepts/compaction.md).

Before anyone throws the old pages away, the proofreader checks the copy.
The usual way to check would be to pick one student, say alice, cross out
her math grade, copy the book, and make sure her math grade is still gone.
That's an **example test**. It's useful, but it only tells you about the
one gradebook you thought of.

Now imagine a proofreader who never gets tired. All night they invent
gradebooks: grades written over, deleted, rewritten with an older date,
grades that expire, students whose every grade is gone. For each one they
ask the same question of the old pages and the new copy, and they check a
single rule:

> Whatever the old pages say, the fresh copy says exactly the same.

That rule is a **property**. It doesn't say what any one gradebook looks
like. It says something that must be true for *every* gradebook.

When the proofreader finds a gradebook that breaks the rule, they don't
hand back a forty-page mess. They try again with fewer students, fewer
grades, smaller numbers, checking it still goes wrong each time, until it's
as small as it can be. That boiling-down is called **shrinking**, and it's
the best part: the smallest failing gradebook usually points straight at
the bug.

In Python, the proofreader is a library called
[Hypothesis](https://hypothesis.readthedocs.io/). PyColDB's property tests
live in `tests/test_properties.py`, next to the ordinary example tests,
and the model check (more on that below) is in `tests/test_model.py`.

## A Property from PyColDB

Here's the proofreader's rule as a test. The strategies come from
`tests/strategies.py`:

```python
def few_names() -> st.SearchStrategy[str]:
    """Pick one of a few names, so steps keep landing on the same rows and columns."""
    return st.sampled_from(FEW_NAMES)


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
```

And the test itself:

```python
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
```

Line by line:

- **`few_names()`, `steps()` and `stories()`** are **strategies**:
  recipes for making random inputs. A story is a list of up to 12 steps,
  and each step is a `Put` (write a grade, maybe with a TTL), a `Delete`
  or a `Wait`. Every name comes from just three, `alice`, `bob` and
  `math`, so the steps keep bumping into each other: writing over a grade,
  deleting it, writing it again with an older date.
- **`@given(story=...)`** tells Hypothesis to run the test many times (100
  in a normal run), each time with a fresh story.
- **The docstring** says the rule in plain English. If you can't say the
  rule in one sentence, it probably isn't a good property yet.
- **`PretendClock()`** is a clock that only moves when a `Wait` step moves
  it. The column family's [TTL](concepts/ttl.md) manager reads it instead
  of the real clock, so a grade can expire in an instant and the test never
  has to sleep.
- **`what_readers_see(cf)`** asks every question a reader could ask: which
  rows are there, how many, does each row exist, what do `get_row`,
  `range_query` and `query_with_filter` hand back (whole rows, down to
  every timestamp), and what does `get_column` say for every row and
  column name.
  If a read raises, the error's *name* goes in the list, so "not found"
  counts as an answer too.
- **The `assert`** is the rule itself: compact, ask again, and every
  answer must be the same. This kind of property is called an
  **invariant**: something compaction must never change.

Notice what the test *doesn't* say. It never says "after deleting alice's
math, `get_column` raises". It doesn't need to know any answers. It only
needs to know the answers mustn't change.

There's a catch, though. **A compaction that does nothing at all passes
this property**, because doing nothing changes no answers. So a second
property sits beside it and checks that compaction really tidies up. Here
is every other property:

| Rule | Test |
|---|---|
| After compaction nothing deleted or expired is left, and the count says how much went | `test_compaction_leaves_no_tombstones_or_expired_columns` |
| Loading a saved keyspace gives back exactly the same families, rows, columns, deletes and TTLs | `test_save_then_load_gives_back_the_same_keyspace` |
| Whatever bytes are in the file, loading gives a keyspace or a `PersistenceError`, never another error | `test_any_bytes_on_disk_load_or_raise_persistence_error` |
| Whatever JSON is in the file, loading gives a keyspace or a `PersistenceError`, never another error | `test_any_json_on_disk_load_or_raise_persistence_error` |
| Whatever one piece of a real save file is swapped for, loading gives a keyspace or a `PersistenceError` | `test_any_damaged_save_file_load_or_raise_persistence_error` |

## Checking Against a Model

A property checks one action. But a column family is something you change
step by step, and bugs often hide in the *order* of steps: deleting a row,
then writing to it with an older date, then waiting, then compacting.

So the proofreader has a second trick. They keep their own notebook: a
plain list of every student and every grade, with a note beside each one
saying when it was written, whether it's crossed out, and when it runs
out. After every single step, they compare the gradebook with the
notebook. If the two ever disagree, something's wrong with the gradebook.

That notebook is a **model**: something simple that we already trust. For
a `ColumnFamily`, the model is a dict of dicts: row name, then column name,
then a `Grade`. Here's part of the check in `tests/test_model.py`:

```python
class ColumnFamilyMachine(RuleBasedStateMachine):
    rows = Bundle("rows")

    def __init__(self) -> None:
        super().__init__()
        self.clock = PretendClock()
        self.cf = ColumnFamily(name="grades", ttl_manager=TTLManager(clock=self.clock))
        self.model: dict[str, dict[str, Grade]] = {}

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
        self.write(row, Column(name=name, value=value, timestamp=timestamp), ttl)
        return row

    @rule()
    def compact(self) -> None:
        forgotten = 0
        for row in list(self.model):
            grades = self.model[row]
            for name in [name for name, g in grades.items() if not self.is_live(g)]:
                del grades[name]
                forgotten += 1
            if not grades:
                del self.model[row]
        assert compact_column_family(self.cf) == forgotten

    @invariant()
    def same_rows_and_grades(self) -> None:
        assert self.cf.row_keys() == self.live_rows()

TestColumnFamilyModel = cast("type[unittest.TestCase]", ColumnFamilyMachine.TestCase)
```

Piece by piece:

- **`RuleBasedStateMachine`** is Hypothesis's tool for testing things that
  change step by step. Hypothesis makes up a random **story** of steps and
  plays it.
- **`self.cf` and `self.model`** are the gradebook and the notebook, and
  `self.clock` is the pretend clock they share. Every story starts with
  both empty.
- **Each `@rule`** is one kind of step. It does the same thing to the
  column family and to the notebook. `put_new_row` writes a grade to both
  (the helper `write` applies the docs' rule in the notebook: the newest
  write wins, and a delete wins a tie). The real file has rules to write
  again, delete, wait, read and run range queries, and to change a
  `Column` after handing it in, to check the column family kept a copy.
- **`compact`** checks a return value: the notebook crosses out its own
  dead grades and counts them, and `compact_column_family` must report the
  same count.
- **`rows = Bundle("rows")`** is a bag of row names used earlier in the
  story. Two random names almost never match, so without it the story
  would hardly ever write to the same row twice. `put_new_row` puts its row
  in the bag (`target=rows`); later rules pull one out. The delete and read
  rules pick either a row from the bag or a brand-new name, so they try
  rows that exist *and* rows that don't.
- **The `@invariant()`** runs after every single step. The real one also
  checks the row count and every live grade, and a second invariant compares every
  tombstone and its time with the notebook's crossed-out grades.
- **`TestColumnFamilyModel = ...TestCase`** turns the machine into a test
  that pytest can find and run. One run plays 100 random stories, each up
  to 20 steps long (Hypothesis's default is 50, which finds the same bugs
  but takes most of the run time).

The notebook is a good model because it's obviously right and it's *not*
`ColumnFamily`'s code. It doesn't have rows, tombstones or a TTL manager,
just one note per grade. If we built the model by copying `ColumnFamily`,
any bug would be in both, and they'd agree perfectly about the wrong
answer.

## Try It Yourself

Let's break `delete_row` on purpose and watch the proofreader find it.

Open `src/pycoldb/column_family.py`, find `delete_row`, and change the
line inside its loop, as if you'd forgotten to pass on the time:

```python
            row.delete_column(col_name)  # was: row.delete_column(col_name, timestamp=timestamp)
```

Now `delete_row` ignores the time you give it and stamps each tombstone
with the grade's own time instead. Run the property tests:

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov
```

Hypothesis reports this (trimmed to the interesting part):

```
self = ColumnFamilyMachine({'rows': [VarReference(name='rows_0')]})

    @invariant()
    def same_crossed_out_grades(self) -> None:
        """After every step, the tombstones match the notebook's crossed-out grades and times."""
        crossed_out = sorted(
            (name, g.deleted_at)
            for grades in self.model.values()
            for name, g in grades.items()
            if g.deleted_at is not None
        )
>       assert (
            sorted((t.column_name, t.deleted_at) for t in self.cf.get_tombstones()) == crossed_out
        )
E       AssertionError: assert [('alice', 1.0)] == [('alice', 0.0)]
E         
E         At index 0 diff: ('alice', 1.0) != ('alice', 0.0)
E         
E         Full diff:
E           [
E               (
E                   'alice',...
E         
E         ...Full output truncated (6 lines hidden), use '-vv' to show
E       Failing test case: <state machine>
E       state = ColumnFamilyMachine()
E       state.same_crossed_out_grades()
E       state.same_rows_and_grades()
E       rows_0 = state.put_new_row(name='alice', row='alice', timestamp=1.0, ttl=None, value='')
E       state.same_crossed_out_grades()
E       state.same_rows_and_grades()
E       state.delete_row(row=rows_0, timestamp=0.0)
E       state.same_crossed_out_grades()
E       state.teardown()
```

Read the story at the bottom like a script. Hypothesis tried long, messy
stories, then shrank them down to **two steps**: write a grade for alice
at time `1.0`, then delete alice's whole row, saying "this delete happened
at time `0.0`". The tombstone says `1.0` (the grade's own time), but the
notebook knows the delete was at `0.0`. (`rows_0` is the bag's name for
the row `'alice'`.)

Wait, a delete *older* than the grade still crosses it out? Yes: that's
the documented rule. An explicit delete always crosses the grade out; its
time only decides which *later* writes can undo it.

That matters. A late write stamped `0.5` is newer than a delete at `0.0`,
so it should land. Against a tombstone at `1.0` it loses, and a real grade
silently disappears.

The example tests all still pass. Only the property notices: every
example that deletes a row uses the default time. The model check's
second invariant caught it; the six properties in `test_properties.py`
stay green, because none of them deletes a whole row.

Put the line back to `row.delete_column(col_name, timestamp=timestamp)`
and run the tests again. They pass.

!!! tip "Older Hypothesis versions"
    Older versions of Hypothesis print `Falsifying example:` instead of
    `Failing test case:`. It means the same thing.

## A Bug We Found

When we first wrote the compaction property, it failed on PyColDB's real
code, no deliberate bug needed:

```
E       At index 3 diff: 'RowNotFoundError' != '[]'
E       Failing test case: test_compaction_never_changes_what_reads_return(
E           story=[Put('alice', 'alice', None, 0.0, None), Delete('alice', 'alice')],
E       )
```

Two steps: write one grade for alice, then delete it. Before compaction,
`get_row("alice")` handed back a row with no grades in it (the `[]`).
After compaction, the empty row had been thrown away, so the same call
raised `RowNotFoundError`. Compaction had changed an answer.

The example tests checked that compaction removes empty rows, and that
`has_row` is `False` once every grade is deleted. Nobody asked `get_row`
the same question before *and* after compacting. The proofreader asks
every question both times, so it didn't need to think of that one.

The fix makes a row with nothing live left count as missing straight
away, as if compaction had already run. Every row lookup goes through one
helper:

```python
        if not self.has_row(row_key):  # was: if row_key not in self.rows:
```

The shrunk story is now an ordinary example test in
`tests/test_column_family.py`:

```python
    def test_a_row_whose_columns_were_all_deleted_is_not_found(self) -> None:
        """Regression (found by a property): get_row returned it until compaction, then raised."""
        cf = ColumnFamily(name="grades")
        cf.put("alice", Column(name="alice", value=None, timestamp=0.0))
        cf.delete_column("alice", "alice")
        with pytest.raises(RowNotFoundError):
            cf.get_row("alice")
```

It wasn't the only one. The properties and the model check found five
more: an old write that was rightly ignored still changed the column's
TTL; `put` with a TTL of `0` raised an error but wrote the grade anyway;
a column named twice in a filter came back twice; changing a `Column`
after `put` (or after reading it) changed the stored grade; and a save file
holding the single byte `0x80` made `load_keyspace` crash with a
`UnicodeDecodeError` instead of a `PersistenceError`. Each one is fixed and
pinned by its own example test.

Compaction does change one thing on purpose: it forgets tombstones. After
that, a very late write older than the delete is accepted again. Real
databases like Cassandra wait days before forgetting a tombstone for
exactly this reason.

## Run It Yourself

Run just the property tests and the model check (100 examples each, the
same every time):

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov
```

The `--no-cov` turns off the coverage check, which expects the *whole*
test suite to run and would fail on two files.

Run them the long way (2,000 random examples each, different every run)
to hunt for rarer bugs. It takes a few minutes:

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov --hypothesis-profile=thorough
```

The normal run uses a fixed seed, so it tries the same inputs every time
and a passing build means the same thing on every computer. The thorough
run is random, so each time you run it the proofreader brings a brand-new
pile of gradebooks. Both settings live in `conftest.py` at the top of the
project.

## Your Turn

Write one new property for PyColDB. Think about `range_query`. Whatever is
in the column family, what should be true of the keys it gives back, for
any start and end? What's the strategy for the start and end? What's the
`assert`? Run it and watch it pass. Then break `range_query` on purpose,
say by changing a `<` to `<=`, and watch the proofreader find it.
