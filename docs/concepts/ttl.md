# TTL -- Temporary Sticky Notes

## What is TTL?

TTL stands for **Time To Live**. It's like putting a temporary sticky note on your locker that says "Remember: test on Friday!" After Friday, that note isn't useful anymore and should be removed.

With TTL, you can tell a column "expire after X seconds." Once the time is up, the column is considered gone.

## When is TTL Useful?

- **Login sessions**: "This login token is valid for 30 minutes"
- **Cached data**: "Remember this calculation for 5 minutes"
- **Temporary messages**: "Show this announcement for 24 hours"

```python
from pycoldb import ColumnFamily, Column

cache = ColumnFamily(name="sessions")

# This session expires in 1800 seconds (30 minutes)
cache.put(
    "user123",
    Column(name="token", value="abc-xyz"),
    ttl_seconds=1800,
)

# Before 30 minutes: works fine
token = cache.get_column("user123", "token")

# After 30 minutes: raises ColumnNotFoundError!
# The sticky note has "fallen off"
```

## How Does It Work?

Under the hood, the TTL manager records when each column was created and how long it should live. Every time you try to read a column, it checks: "Has this column's time run out?" If yes, it acts as if the column doesn't exist.

The actual data isn't deleted right away -- it sticks around until **compaction** cleans it up. This is more efficient than constantly checking and deleting expired data.
