# Compaction -- Cleaning Up

## What is Compaction?

After a while, your data can get messy. You've got:
- **Tombstones** (crossed-out data waiting to be cleaned up)
- **Expired columns** (sticky notes whose time has run out)

**Compaction** is like going through your messy notebook and rewriting everything on a fresh page, leaving out all the crossed-out stuff and expired sticky notes.

## Why Compact?

1. **Save space** -- Tombstones and expired data take up room
2. **Speed up reads** -- Less clutter means faster lookups
3. **Keep things tidy** -- A clean database is a happy database

```python
from pycoldb import ColumnFamily, Column
from pycoldb.compaction import compact_column_family

grades = ColumnFamily(name="grades")

# Add some data
grades.put("alice", Column(name="math", value="A+"))
grades.put("alice", Column(name="science", value="A"))
grades.put("bob", Column(name="math", value="B"))

# Delete some data (creates tombstones)
grades.delete_column("alice", "science")
grades.delete_column("bob", "math")

# Compact! Returns how many entries were cleaned up
cleaned = compact_column_family(grades)
print(f"Cleaned up {cleaned} entries")  # Cleaned up 2 entries
```

## When Does Compaction Happen?

In real databases like Cassandra, compaction runs automatically in the background. In our educational version, you call it manually whenever you want to clean up. This lets you see exactly what's happening and learn how it works!
