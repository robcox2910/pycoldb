# Columns -- The Building Blocks

## What is a Column?

A column is like a **single cell** in a spreadsheet, but smarter. Each column has three parts:

1. **Name** -- The column header (like "Math Grade")
2. **Value** -- The actual data (like "A+" or 95)
3. **Timestamp** -- When this data was written (like a date stamp)

## Why Timestamps?

Imagine you and your friend both try to update Alice's math grade at the same time. You write "A+" and your friend writes "A-". Which one wins?

The **timestamp** solves this! Whichever write happened most recently wins. It's like a "last edited" date on a Google Doc.

```python
from pycoldb import Column

# A grade recorded at time 1000
grade_v1 = Column(name="math", value="B", timestamp=1000)

# Updated later at time 2000
grade_v2 = Column(name="math", value="A+", timestamp=2000)

# The column with timestamp 2000 is the most recent
```

## What Can Go in a Column?

Columns can hold different types of values:
- **Strings**: `"A+"`, `"present"`, `"blue"`
- **Numbers**: `95`, `3.14`
- **Booleans**: `True`, `False`
- **None**: For "no value" / "unknown"
