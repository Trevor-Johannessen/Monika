# Visualize

When the user asks you to visualize, display, or "show" them something, create an HTML dashboard or visual and save it using the file tools.

## Directory

All HTML files are stored in `/etc/monika/etc/html`.

## Before creating a new file

1. Use `list_files` on `/etc/monika/etc/html` to check for existing HTML files.
2. Each HTML file starts with a comment describing its purpose (e.g. `<!-- Dashboard showing daily weather summary -->`). Use these to determine if an existing file is relevant.
3. If a file looks relevant, use `read_file` to inspect it further.
4. If it matches what the user needs, return the path to the existing file instead of creating a new one.

## Creating a new HTML file

1. Use `write_file` to create the file in `/etc/monika/files/html`.
2. The **first line** must be an HTML comment describing the file's purpose.
3. Use a descriptive, kebab-case filename (e.g. `weather-dashboard.html`).
4. Write complete, self-contained HTML with inline CSS and JS.
5. Use modern, clean styling. Prefer dark themes with good contrast.
6. Make the visualization responsive and visually appealing.
7. Avoid external dependencies unless from a well-known CDN (e.g. Chart.js, D3).
