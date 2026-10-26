# What is a Column-Family Store?

## The Spreadsheet That Breaks the Rules

You know how in a regular spreadsheet, every row has the exact same columns? If column A is "Name" and column B is "Age", then every single row must have a Name and an Age cell.

A **column-family store** is like a spreadsheet that breaks that rule. Each row gets to choose its own columns!

### The School Analogy

Imagine a school where every student has a record card. In a regular school database (like a spreadsheet), every student's card would look identical:

| Student | Math | Science | Art | Music |
|---------|------|---------|-----|-------|
| Alice   | A+   | A       | B+  | ---   |
| Bob     | B    | ---     | --- | A     |

See all those "---" empty spots? That's wasted space! Alice doesn't take Music, and Bob doesn't take Science or Art.

In a column-family store, each student's card only has the columns they actually need:

**Alice's card:** `math: A+`, `science: A`, `art: B+`

**Bob's card:** `math: B`, `music: A`

No wasted space! Each row stores only what it needs.

## Key Concepts

### Column (A Single Cell)
The smallest piece of data. It has a **name** (like "math"), a **value** (like "A+"), and a **timestamp** (when it was written). The timestamp helps us know which data is newest.

### Row (A Student's Record)
A row has a unique **key** (like the student's name) and a collection of columns. Each row can have completely different columns.

### Column Family (A Gradebook)
A named group of rows. Think of it as one teacher's gradebook. The "grades" column family holds all students' grades. The "attendance" column family holds attendance records.

### Keyspace (The Whole School)
The top-level container that holds multiple column families. It's like the entire school containing all the gradebooks.

## Real-World Uses

Column-family stores like **Apache Cassandra** and **HBase** are used by:
- **Netflix** -- tracking what millions of users are watching
- **Instagram** -- storing user feeds and messages
- **Spotify** -- managing playlists and listening history

They're great when:
- Different records need different fields
- You have LOTS of data (billions of rows)
- You need fast reads and writes

## Install

```bash
pip install fromscratch-pycoldb
```

Or get the whole series at once with `pip install fromscratch-pystack`. To read the code or run the tests, clone it from [GitHub](https://github.com/robcox2910/pycoldb).

## Getting Started

```python
from pycoldb import Keyspace, Column

# Create a school (keyspace)
school = Keyspace(name="school")

# Create a gradebook (column family)
school.create_column_family("grades")

# Add grades for Alice (she takes math and science)
school.put("grades", "alice", Column(name="math", value="A+"))
school.put("grades", "alice", Column(name="science", value="A"))

# Add grades for Bob (he takes math and music)
school.put("grades", "bob", Column(name="math", value="B"))
school.put("grades", "bob", Column(name="music", value="A"))

# Read Alice's math grade
grade = school.get_column("grades", "alice", "math")
print(f"Alice's math grade: {grade.value}")  # A+
```
