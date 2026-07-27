"""Custom exceptions for the pycoldb column-family store.

Think of these like the different warning signs you might see at school:
- "Room not found" when you look for a classroom that doesn't exist
- "Student not found" when you look for someone who isn't enrolled
- "Gradebook not found" when a teacher's gradebook is missing

Each exception tells you exactly what went wrong so you can fix it!
"""


class PyColDBError(Exception):
    """Base exception for all pycoldb errors.

    This is like a general "something went wrong" sign. All other
    error types are more specific versions of this one.
    """


class KeyspaceNotFoundError(PyColDBError):
    """Raise when a keyspace cannot be found.

    A keyspace is like a whole school. This error means you tried
    to look up a school that doesn't exist in our system.
    """


class KeyspaceAlreadyExistsError(PyColDBError):
    """Raise when trying to create a keyspace that already exists.

    You can't build a second school with the same name right next
    to the first one -- that would be confusing!
    """


class ColumnFamilyNotFoundError(PyColDBError):
    """Raise when a column family cannot be found.

    A column family is like a class gradebook. This error means
    the gradebook you asked for doesn't exist yet.
    """


class ColumnFamilyAlreadyExistsError(PyColDBError):
    """Raise when trying to create a column family that already exists.

    You can't have two gradebooks with the exact same name in
    the same school -- teachers would get confused!
    """


class RowNotFoundError(PyColDBError):
    """Raise when a row cannot be found.

    A row is like a student's record. This error means no student
    with that ID exists in the gradebook.
    """


class ColumnNotFoundError(PyColDBError):
    """Raise when a column cannot be found within a row.

    A column is like a specific grade or piece of info. This error
    means that particular piece of information hasn't been recorded
    for this student.
    """


class InvalidTTLError(PyColDBError, ValueError):
    """Raise when an invalid TTL (time-to-live) value is provided.

    TTL is like a sticky note that falls off after a certain time.
    This error means you tried to set a nonsensical expiration time
    (like a negative number of seconds).

    It is both a PyColDBError and a plain ValueError, so code that
    catches either kind of error will still catch it.
    """


class PersistenceError(PyColDBError):
    """Raise when saving or loading data fails.

    This is like trying to save your homework but your binder is
    broken, or trying to open a file that got corrupted.
    """
