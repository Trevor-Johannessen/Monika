---
name: notes
description: Take, read, update, or delete persistent notes
---

# Notes

When the user asks you to take a note, save something for later, read a note, look something up from notes, or update/revise a note, use the notes directory to read and write persistent notes.

## Directory

All notes are stored in `/etc/monika/notes`. If this directory does not exist, create it using `bash`.

## Note format

Every note file must begin with a metadata header block:

```
Created: YYYY-MM-DD
Last Modified: YYYY-MM-DD HH:MM
```

Followed by a blank line, then the note content in plain markdown.

Example:
```
Created: 2026-04-08
Last Modified: 2026-04-08 14:32

## Shopping list
- Milk
- Eggs
- Bread
```

## Finding notes

1. Use `list_files` on `/etc/monika/notes` to see available note files.
2. Use `read_file` to read a specific note.
3. If the user does not specify a note name, scan filenames and read relevant ones to find the right content.

## Writing a new note

1. Choose a descriptive snake_case filename (e.g. `shopping_list.md`, `project_ideas.md`).
2. Write the metadata header with today's date for both `Created` and `Last Modified`.
3. Add the note content below the header.
4. Use `write_file` to save the file to `/etc/monika/notes`.

## Updating an existing note

1. Use `read_file` to load the current content of the note.
2. Apply the user's changes to the content.
3. Update the `Last Modified` line to the current datetime.
4. Use `write_file` to save the updated file, preserving the original `Created` date.

## Revising notes to remove stale information

When reviewing or updating a note, check for content that is no longer relevant:

- Completed or outdated todo lists
- Time-sensitive reminders that have passed
- Temporary information that is clearly no longer applicable

Remove stale content without asking for confirmation, unless the removal is ambiguous. After revision, update the `Last Modified` datetime and briefly tell the user what was removed.

If a note becomes empty after revision (all content was stale), ask the user whether to delete the file or keep it.

## Deleting a note

Only delete a note if the user explicitly asks. Use `bash` to remove the file (e.g. `rm /etc/monika/notes/old_note.md`).
