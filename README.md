# PyColDB

An educational column-family store (wide-column database) built from scratch in Python. Part of the **PyLearn** platform for kids aged 12+.

## What is a Column-Family Store?

A column-family store is like a spreadsheet where every row can have different columns. Instead of forcing every record to have the same fields, each row picks and chooses what data it stores. Real-world examples include Apache Cassandra and HBase.

## Features

- **Columns** -- Name-value pairs with timestamps
- **Rows** -- Flexible records where each row has its own set of columns
- **Column Families** -- Named groups of rows (like gradebooks)
- **Keyspaces** -- Top-level containers for column families (like a school)
- **CRUD** -- Insert, read, update, and delete columns within rows
- **Range Queries** -- Get rows by key range (e.g., keys from "A" to "M")
- **Column Filtering** -- Get only specific columns from a row
- **TTL** -- Columns can expire after a time-to-live
- **Tombstones** -- Soft deletion with markers (like Cassandra)
- **Persistence** -- Save and load to JSON files
- **Compaction** -- Remove expired and deleted entries to reclaim space

## Quick Start

```python
from pycoldb import Keyspace, Column

# Create a keyspace (like a school)
school = Keyspace(name="school")

# Create a column family (like a gradebook)
school.create_column_family("grades")

# Add grades -- each student can have different columns!
school.put("grades", "alice", Column(name="math", value="A+"))
school.put("grades", "alice", Column(name="science", value="A"))
school.put("grades", "bob", Column(name="math", value="B"))
school.put("grades", "bob", Column(name="music", value="A"))

# Read a grade
grade = school.get_column("grades", "alice", "math")
print(f"Alice's math grade: {grade.value}")  # A+

# Range query -- get students from "alice" to "bob"
from pycoldb import range_query
cf = school.get_column_family("grades")
rows = range_query(cf, start_key="alice", end_key="bob")
for row in rows:
    print(f"{row.key}: {row.column_names()}")

# Save to disk
from pycoldb import save_keyspace, load_keyspace
save_keyspace(school, "school.json")
restored = load_keyspace("school.json")
```

## Installation

```bash
# From source
git clone https://github.com/robcox2910/pycoldb.git
cd pycoldb
uv sync --all-extras
```

## Development

```bash
uv run ruff check src/ tests/      # Lint
uv run ruff format src/ tests/      # Format
uv run pyright src tests            # Type check
uv run pytest                       # Test (90%+ coverage)
```

## Releasing

Other projects in the series ([PyStack](https://github.com/robcox2910/pystack)) use a pinned release of this one,
not whatever is on `main`. To publish a change for them:

1. Merge the change to `main`.
2. Tag it: `git tag -a vX.Y.Z -m vX.Y.Z && git push origin vX.Y.Z`.
   A change to the public API bumps the minor version (`v0.1.0` → `v0.2.0`);
   anything else bumps the patch (`v0.1.0` → `v0.1.1`).
3. In each project that uses it, edit the tag in `[tool.uv.sources]`, run
   `uv lock --upgrade-package <name>`, and open a pull request so CI checks
   the pair together.

<!-- series:start -->
## Related Projects

This project is one of a series that builds real systems "from scratch in Python" to teach how they work. See the [series home](https://robcox2910.github.io/) for the full story.

| Project | What it teaches | Repository | Docs |
| --- | --- | --- | --- |
| PyOS | Operating systems | [py-os](https://github.com/robcox2910/py-os) | [Docs](https://robcox2910.github.io/py-os/) |
| Pebble | Compilers and programming languages | [pebble-lang](https://github.com/robcox2910/pebble-lang) | [Docs](https://robcox2910.github.io/pebble-lang/) |
| PyDB | Relational databases | [pydb](https://github.com/robcox2910/pydb) | [Docs](https://robcox2910.github.io/pydb/) |
| PyKV | Key-value stores | [pykv](https://github.com/robcox2910/pykv) | [Docs](https://robcox2910.github.io/pykv/) |
| PyDocDB | Document databases | [pydoc-db](https://github.com/robcox2910/pydoc-db) | [Docs](https://robcox2910.github.io/pydoc-db/) |
| PyGraphDB | Graph databases | [pygraphdb](https://github.com/robcox2910/pygraphdb) | [Docs](https://robcox2910.github.io/pygraphdb/) |
| PyTSDB | Time-series databases | [pytsdb](https://github.com/robcox2910/pytsdb) | [Docs](https://robcox2910.github.io/pytsdb/) |
| PyVecDB | Vector databases | [pyvecdb](https://github.com/robcox2910/pyvecdb) | [Docs](https://robcox2910.github.io/pyvecdb/) |
| **PyColDB** | **Column-family databases** | [pycoldb](https://github.com/robcox2910/pycoldb) | [Docs](https://robcox2910.github.io/pycoldb/) |
| PyCrypt | Cryptography | [pycrypt](https://github.com/robcox2910/pycrypt) | [Docs](https://robcox2910.github.io/pycrypt/) |
| PyNet | Computer networking | [pynet](https://github.com/robcox2910/pynet) | [Docs](https://robcox2910.github.io/pynet/) |
| PyWeb | HTTP web servers | [pyweb](https://github.com/robcox2910/pyweb) | [Docs](https://robcox2910.github.io/pyweb/) |
| PyGit | Version control | [pygit](https://github.com/robcox2910/pygit) | [Docs](https://robcox2910.github.io/pygit/) |
| PySearch | Search engines | [pysearch](https://github.com/robcox2910/pysearch) | [Docs](https://robcox2910.github.io/pysearch/) |
| PyMQ | Message queues | [pymq](https://github.com/robcox2910/pymq) | [Docs](https://robcox2910.github.io/pymq/) |
| PyLLM | Language models (the brain) | [pyllm](https://github.com/robcox2910/pyllm) | [Docs](https://robcox2910.github.io/pyllm/) |
| PyStack | Full-stack integration | [pystack](https://github.com/robcox2910/pystack) | [Docs](https://robcox2910.github.io/pystack/) |
<!-- series:end -->

<!-- docs:start -->
## Documentation

Full docs (with kid-friendly explanations of every idea): https://robcox2910.github.io/pycoldb/
<!-- docs:end -->

## License

MIT
