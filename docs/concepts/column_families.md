# Column Families -- Gradebooks

## What is a Column Family?

A column family is like a **teacher's gradebook**. It's a named collection of rows (student records), where each row can have different columns.

Think of your school having different gradebooks:
- The **"grades"** gradebook has math scores, science scores, etc.
- The **"attendance"** gradebook has Monday, Tuesday, Wednesday entries
- The **"contacts"** gradebook has phone numbers and emails

Each gradebook (column family) groups related data together.

```python
from pycoldb import ColumnFamily, Column

# Create a gradebook for grades
grades = ColumnFamily(name="grades")

# Add student grades
grades.put("alice", Column(name="math", value="A+"))
grades.put("alice", Column(name="science", value="A"))
grades.put("bob", Column(name="math", value="B"))

# How many students have grades?
print(grades.row_count)  # 2
print(grades.row_keys()) # ['alice', 'bob']
```

## Why Not Just One Big Table?

Separating data into column families makes things faster. When you look up someone's grades, you don't have to read through their attendance records too. It's like having separate filing cabinets for different types of documents.
