# Pantry Management

When the user asks you to manage their pantry, track ingredients, suggest recipes, generate grocery lists, or review meal history, use the pantry management system.

## What it covers

This skill handles:
- **Inventory management**: Add, remove, or update pantry items with quantities
- **Recipe suggestions**: Recommend recipes based on available ingredients or minimal shopping
- **Smart grocery lists**: Generate lists by comparing current inventory to typical pantry baseline
- **Usage tracking**: Log all pantry changes to analyze consumption patterns
- **Meal history**: Track meals made and ingredients used to inform future decisions

## Directory structure

All pantry data lives in `/etc/monika/pantry/`:
- `inventory.md` - Current pantry items with quantities and units
- `pantry_log.csv` - Timestamped log of all adds/removals
- `meal_history.csv` - Record of meals made with dates and ingredients used
- `typical_pantry.md` - Reference baseline of usual pantry items (optional, user-created)

## Managing inventory

### Adding or removing items

1. Read the current `inventory.md` file
2. Parse the items list (format: `- Item Name: X units`)
3. Add/remove/update the specified item
4. Update `Last Modified` timestamp
5. Log the action to `pantry_log.csv` with: timestamp, action (add/remove/update), item, quantity, unit
6. Confirm the change to the user

### Viewing inventory

Simply read and display the current contents of `inventory.md` in a clean, readable format.

## Recipe suggestions

When the user asks "What can I make?" or "Suggest recipes":

1. Read the current `inventory.md`
2. Use the user's available ingredients to search for recipe ideas
3. If the user also says "minimal shopping" or "with just one or two things": search for recipes that need only 1-2 additional ingredients beyond what they have
4. Present recipes with:
   - Recipe name
   - Ingredients they already have (✓)
   - Ingredients they need to buy (✗)
5. If local recipes aren't available, use web_search to find recipes matching available ingredients
6. Ask if they'd like to save any recipes to `/etc/monika/recipes/`

## Smart grocery lists

When the user asks for a grocery list or mentions they want to restock:

1. Check if `typical_pantry.md` exists (user's baseline inventory)
   - If not, ask the user to create one by running a grocery list generation first, or provide one
2. Read the current `inventory.md`
3. Compare current items to typical items
4. Generate a list showing:
   - Items to restock (in typical but below current level or missing)
   - New items to try (if user has noted experimentation in meal history)
5. Organize by category if possible (pantry staples, produce, proteins, etc.)

## Usage tracking and analysis

The `pantry_log.csv` automatically logs every add/remove/update with timestamp.

When the user asks "How much X do I use?" or "Show me usage patterns":

1. Read `pantry_log.csv`
2. Filter for the specific item (if requested) or show all
3. Calculate:
   - Frequency of purchases (days between adds)
   - Average quantity purchased
   - Usage rate (if multiple logs for same item)
4. Present findings to help with grocery planning

## Meal history interface

### Logging a meal

When the user says "Log that meal" or "I made X today":

1. Parse the meal name and ingredients used
2. Append to `meal_history.csv` with: current date, meal_name, comma-separated ingredients used
3. Update inventory by removing those ingredients (with user confirmation)
4. Confirm the meal was logged

### Viewing meal history

When the user asks to see "recent meals" or "meals I've made":

1. Read `meal_history.csv`
2. Display in reverse chronological order
3. Optionally show statistics: most common meals, favorite ingredients, frequency of cooking

### Using history for decisions

When the user is deciding what to cook next:

1. Review recent meals from `meal_history.csv`
2. Check for variety (avoid suggesting same meal too recently)
3. Consider favorite ingredients that appear often
4. Suggest meals based on what's available AND preferences shown in history

## Edge cases and fallbacks

- **If inventory is empty**: Ask the user to add items or provide a typical pantry list
- **If pantry_log.csv is corrupted**: Recreate with header row and continue logging
- **If no recipes match available ingredients**: Suggest the user either add more pantry items or ask for simple recipes with just a few key ingredients
- **If typical_pantry.md doesn't exist**: For smart grocery lists, ask the user to either provide one or let you learn from first month of usage
- **If meal_history is empty**: Start fresh and begin logging; history becomes more useful over time

## File formats

### inventory.md
```
Created: YYYY-MM-DD
Last Modified: YYYY-MM-DD HH:MM

## Current Pantry

- Olive Oil: 3 cups
- Canned Tomatoes: 4 cans
- Pasta: 2 boxes
- Chicken Breast: 3 lbs
```

### pantry_log.csv
```
timestamp,action,item,quantity,unit
2026-04-13 11:03:59,add,Olive Oil,3,cups
2026-04-13 11:05:00,remove,Pasta,1,box
```

### meal_history.csv
```
date,meal_name,ingredients_used
2026-04-12,Pasta Marinara,Pasta;Canned Tomatoes;Olive Oil;Garlic
2026-04-11,Grilled Chicken,Chicken Breast;Olive Oil;Salt;Pepper
```

### typical_pantry.md (optional reference)
```
Created: YYYY-MM-DD
Last Modified: YYYY-MM-DD HH:MM

## Typical/Target Pantry

Standard items to maintain:
- Olive Oil: 2-3 cups
- Canned Tomatoes: 3-5 cans
- Pasta: 2-3 boxes
- Chicken Breast: 2-4 lbs
- Eggs: 1 dozen
```

