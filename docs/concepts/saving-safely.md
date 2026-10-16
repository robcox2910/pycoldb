# Saving Safely -- Never Half a File

The simple way to save -- wipe the file, then write it out again -- has a
nasty problem: if the computer crashes halfway through, you're left with half
a file, and your data is gone.

So saving works like a careful student copying out their homework:

1. Write the new version on a **fresh sheet** -- a temporary file right next
   to the real one.
2. Make sure the **ink is dry** -- `fsync` pushes the bytes out of the
   computer's memory and onto the disk.
3. **Swap** the fresh sheet in for the old one in a single instant step.

At every moment there's a complete file: the old one or the new one, never
half of each. Real databases like SQLite and PostgreSQL use the same trick.
The code lives in `atomic.py`.
