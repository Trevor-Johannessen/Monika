---
name: gym-tracker
description: Log and track gym workouts, exercises, sets, reps, and weights
---

# Gym Workout Tracker

When the user asks you to log a workout, add exercises, or track their gym sessions, use the gym CSV file to store and retrieve workout data.

## Directory

All gym workout data is stored in `/etc/monika/files/gym.csv`. Create the file if it does not exist.

## File format

The gym CSV uses the following structure:

```
Date,Exercise,Set,Weight,Reps,Notes
YYYY-MM-DD,Exercise Name,Set Number,Weight (lbs),Reps,Additional Notes
```

Example:
```
2026-04-16,Seated leg curl,1,130,12,
2026-04-16,Leg extension,2,145,,Hold 60 seconds
2026-04-16,Standing calf raise,1,210,,
```

## Logging a workout

1. Parse the user's workout data: exercises, sets, weights, reps, and any notes.
2. Read the current `/etc/monika/files/gym.csv` file (create if missing).
3. Add rows for today's date with each exercise and set.
4. For holds or notes without weight/reps, leave those fields empty and fill in the Notes column.
5. Write the updated file back.
6. Confirm the workout has been logged.

## Viewing workout history

1. When the user asks to see past workouts, read `/etc/monika/files/gym.csv`.
2. Display workouts organized by date, showing exercises with their sets, weights, and reps.
3. If the file is empty, tell the user there are no logged workouts yet.

## Edge cases

- If the user provides incomplete data (e.g., "Weights TBD"), leave those fields empty and add a note
- If weight is listed without reps (just a number), assume it's a max weight and leave reps blank
- If reps are listed without weight, record it in the Notes field
- Always use today's date unless the user specifies a different date
