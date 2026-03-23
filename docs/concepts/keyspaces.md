# Keyspaces -- The Whole School

## What is a Keyspace?

A keyspace is like the **entire school** -- it contains all the gradebooks (column families) and organizes everything together.

In database terms, a keyspace is similar to a "database" in MySQL or PostgreSQL. It's the top-level container.

```python
from pycoldb import Keyspace, Column

# Create a school
school = Keyspace(name="school")

# Add different gradebooks
school.create_column_family("grades")
school.create_column_family("attendance")
school.create_column_family("contacts")

# What gradebooks do we have?
print(school.column_family_names())
# ['attendance', 'contacts', 'grades']
```

## Why Keyspaces?

Imagine you're running two schools. Each school has its own set of gradebooks, and you don't want them mixed up. Keyspaces keep everything separate and organized.

```python
# Two different schools, each with their own data
elementary = Keyspace(name="elementary")
middle_school = Keyspace(name="middle_school")

elementary.create_column_family("grades")
middle_school.create_column_family("grades")

# Each school's "grades" is completely separate
```
