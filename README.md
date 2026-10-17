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

## Related Projects

| Project | Description |
|---------|-------------|
| [py-os](https://github.com/robcox2910/py-os) | Educational operating system concepts |
| [pebble-lang](https://github.com/robcox2910/pebble-lang) | A toy programming language |
| [pydb](https://github.com/robcox2910/pydb) | Educational relational database engine |
| [pyweb](https://github.com/robcox2910/pyweb) | Educational web framework |
| [pygit](https://github.com/robcox2910/pygit) | Educational Git implementation |
| [pycrypt](https://github.com/robcox2910/pycrypt) | Educational cryptography library |
| [pynet](https://github.com/robcox2910/pynet) | Educational networking library |
| [pysearch](https://github.com/robcox2910/pysearch) | Educational search engine |
| [pymq](https://github.com/robcox2910/pymq) | Educational message queue |
| [pykv](https://github.com/robcox2910/pykv) | Educational key-value store |
| [pycoldb](https://github.com/robcox2910/pycoldb) | Educational column-family store (this project) |
| [pystack](https://github.com/robcox2910/pystack) | Unified platform integrating all projects |

## License

MIT
