---
name: recipe-manager
description: Look up, save, or answer questions about recipes and cooking instructions
---

# Recipes

When the user asks about a recipe, cooking instructions, or meal preparation, look up the recipe in the local collection and answer their questions.

## Directory

All recipe files are stored in `/etc/monika/recipes`. If this directory does not exist, create it with `bash`.

## Finding a recipe

1. Use `bash` to list files in `/etc/monika/recipes` (e.g. `ls /etc/monika/recipes`).
2. Match the user's request against available filenames. Recipe files use kebab-case naming (e.g. `vodka-sauce.md`, `chicken-parmesan.md`).
3. If a match is found, use `bash` to read the file (e.g. `cat /etc/monika/recipes/vodka-sauce.md`) and load the full recipe into context.
4. Answer the user's question using the recipe content. For step-based questions (e.g. "What do I do after adding the cheeses?"), locate the relevant step and provide the next instruction.

## Recipe not found

If the recipe is not available locally:

1. Tell the user the recipe is unavailable.
2. Ask if they would like you to look it up online.
3. If the user agrees, use `web_search` to find the recipe and present it.
4. **Do not save the recipe automatically.** Ask the user if they would like to save it to `/etc/monika/recipes` first.
5. Only save the recipe if the user explicitly confirms.

## Saving recipes

- **User-provided recipes:** Save immediately to `/etc/monika/recipes` without asking for confirmation.
- **Online recipes:** Always ask the user for confirmation before saving.
- Use kebab-case filenames (e.g. `beef-stew.md`).
- Write files using `bash` (e.g. `cat << 'EOF' > /etc/monika/recipes/beef-stew.md`).
- Save recipes in a clean markdown format with sections for ingredients, instructions, and any relevant notes.
