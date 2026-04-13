# To-Do List Manager

When the user asks you to add something to their to-do list, create a new to-do item file or update their to-do list. When the user asks to read their to-do list, display only the subject lines of all to-do items.

## Directory

All to-do items are stored in `/etc/monika/todos`. Create this directory if it does not exist.

## Adding a to-do item

1. When the user wants to add something to their to-do list, extract the subject or main task.
2. Create a new file in `/etc/monika/todos` with a descriptive kebab-case filename based on the task (e.g., `buy-groceries.md`, `finish-report.md`).
3. Write a simple file with a subject line and optional details:
   ```
   Subject: [Task name]
   Created: YYYY-MM-DD HH:MM
   
   [Optional: Additional details about the task]
   ```
4. Confirm with the user that the item has been added.

## Reading the to-do list

1. When the user asks to see their to-do list, read all files in `/etc/monika/todos`.
2. Extract the subject line from each file (the text after "Subject:").
3. Display only the subject lines in a simple list format, one per line.
4. Do not display file paths, creation dates, or additional details.

## Edge cases

- If the `/etc/monika/todos` directory does not exist, create it automatically.
- If there are no to-do items, tell the user their list is empty.
- If the user wants to remove a to-do item, delete the corresponding file from `/etc/monika/todos` and confirm the deletion.
