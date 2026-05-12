---
name: reminder
description: Create, list, or evaluate pending reminders that fire on the next prompt after their conditions are met
---

# Reminders

A reminder pairs a **trigger condition** (when it should fire) with a **message** (what to tell the user). Reminders fire on the next prompt after their condition is satisfied — there is no push delivery.

This skill applies in two situations:

1. **The user asks for a reminder.** Phrases like "remind me to…", "tell me when…", "next time I ask about X, mention Y", or "in 10 minutes remind me to…". Create a reminder file.
2. **Pending reminders are attached to the current prompt.** The controller injects any saved reminders under a `Pending reminders:` block in the prompt context. Evaluate each one — if its trigger has been met, surface its message to the user and delete the file. If not, leave it alone and do not mention it.

## Directory

All reminders live in `/etc/monika/reminders/`. Create the directory with `bash` (`mkdir -p`) if it does not exist before writing the first reminder.

## Reminder file format

Filename: a short kebab-case slug derived from the reminder, with a `.md` extension (e.g. `drink-water.md`, `ask-about-deploy.md`). If a file by that name already exists, append a short suffix.

File body:

```
Created: YYYY-MM-DD HH:MM:SS
Trigger: <one-line trigger description>

<reminder message>
```

- `Created`: the current datetime when the reminder was created.
- `Trigger`: a single line describing the condition. Be precise so it can be evaluated later without ambiguity. Use the formats below.
- Message: free-form text that will be shown to the user when the reminder fires.

### Trigger formats

- **Absolute time** — `after 2026-05-11 17:30`. Use this for "at 5:30pm", "tomorrow morning", etc. Resolve relative times against the current `time` attribute before saving.
- **Relative duration** — convert to an absolute datetime using the current `time` attribute (e.g. "in 10 minutes" at `2026-05-11 14:00:00` becomes `after 2026-05-11 14:10`). Always save the resolved absolute form, never the raw duration.
- **Context condition** — `when <natural-language condition>`. Use this when the trigger depends on what the user says next, e.g. `when the user mentions cooking`, `when the user next talks about the deploy`.
- **Always** — `always` for reminders that should surface on the very next prompt regardless of content.

If the user's request is ambiguous about timing, ask one short clarifying question before saving.

## Creating a reminder

1. Parse the trigger and message from the user's request.
2. Resolve any relative times against the current `time` attribute.
3. Pick a kebab-case filename and write the file using `bash` (heredoc to `/etc/monika/reminders/<name>.md`).
4. Briefly confirm what was saved and when it will fire (e.g. "Got it, I'll remind you to drink water after 2:10pm.").

## Evaluating pending reminders

When the prompt context includes a `Pending reminders:` block, before responding to the user's actual request:

1. Read each reminder's `Trigger` line.
2. For `after <datetime>` triggers, compare against the current `time` attribute. Fire if the current time is at or past the trigger.
3. For `when <condition>` triggers, fire if the user's current message clearly satisfies the condition.
4. For `always`, fire unconditionally.
5. For each reminder that fires:
   - Lead your reply with the reminder message, framed naturally ("Reminder: …" or woven into the response).
   - Delete the reminder file with `bash` (`rm /etc/monika/reminders/<file>`).
6. For reminders that do not fire, do nothing — do not mention them, do not modify them.

If multiple reminders fire on the same prompt, surface them all.

## Listing reminders

If the user asks what reminders are pending, `ls /etc/monika/reminders/` and read each file. Reply conversationally — describe what each reminder is and when it fires in natural prose ("You've got one set for 5:30 to drink water, and another for the next time you mention the deploy."). Avoid bulleted lists unless the user explicitly asks for one. Do not mention the `Created` line unless asked.

## Removing a reminder

If the user asks to cancel or remove a reminder, `rm` the corresponding file. If the target is ambiguous, list pending reminders first and ask which one.

## Edge cases

- If `/etc/monika/reminders/` is empty or missing, no reminders are pending — proceed with the user's request normally.
- Never fire the same reminder twice. Always delete the file after firing.
- If a reminder's trigger is malformed or unparseable, surface it on the next prompt and let the user clarify.
