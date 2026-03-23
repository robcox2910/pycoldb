# Tombstones -- Crossing Out Instead of Erasing

## What is a Tombstone?

Imagine writing in a notebook with a pen (not a pencil!). When you make a mistake, you can't erase it. Instead, you draw a line through it. That crossed-out text is still visible, but everyone knows to ignore it.

A **tombstone** works the same way. When you delete data in a column-family store, it's not immediately removed. Instead, a special marker (the tombstone) is placed saying "this data was deleted."

## Why Not Just Delete It?

In a real distributed database like Cassandra, your data lives on multiple computers. If you just delete data from one computer, the other computers still have it. They might think "Oh, this computer is missing data, let me send it back!" -- and your deleted data comes back like a zombie!

Tombstones prevent this. Every computer sees the tombstone and knows "this was intentionally deleted, don't bring it back."

```python
from pycoldb import ColumnFamily, Column

grades = ColumnFamily(name="grades")

# Add a grade
grades.put("alice", Column(name="math", value="A+"))

# Delete it (creates a tombstone)
grades.delete_column("alice", "math")

# The tombstone is there
tombstones = grades.get_tombstones()
print(len(tombstones))  # 1
print(tombstones[0].column_name)  # 'math'
```

## Cleaning Up Tombstones

Tombstones take up space. Over time, you should clean them up using **compaction** -- that's like rewriting your notebook on a fresh page, leaving out all the crossed-out stuff.
