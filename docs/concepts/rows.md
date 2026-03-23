# Rows -- Student Records

## What is a Row?

A row is like a **student's record card**. Each card has:
- A **key** (the student's unique ID, like their name)
- A set of **columns** (the information on the card)

The magic is that each student's card can have different columns!

## Sparse Rows

In a regular table, every row must have every column (even if it's empty). In a column-family store, rows are **sparse** -- they only store the columns they actually have data for.

```python
from pycoldb import Row, Column

# Alice takes math and science
alice = Row(key="alice")
alice.put_column(Column(name="math", value="A+"))
alice.put_column(Column(name="science", value="A"))

# Bob takes math and music (different columns!)
bob = Row(key="bob")
bob.put_column(Column(name="math", value="B"))
bob.put_column(Column(name="music", value="A"))

# Each row has its own set of columns
print(alice.column_names())  # ['math', 'science']
print(bob.column_names())    # ['math', 'music']
```

## Row Keys

Every row needs a unique key, just like every student needs a unique student ID. If you try to add data with the same key, it updates the existing row instead of creating a new one.
