# Create Skill

When the user asks you to create a new skill, teach you something new, or add a new capability, write a skill file so the behavior persists across future sessions.

## What is a skill

Skills are plain markdown files placed in the `skills/` directory of the monika repo. Every `*.md` file in that directory is loaded into your system prompt at startup. A skill file describes a behavior, domain of knowledge, or set of instructions you should follow when a relevant situation arises.

## Where to save skill files

All skill files go in `$PWD/skills/`. Use the `write_file` tool (via the filesystem agent) to create the file.

- Filename format: `skill_{skill_name}.md` using snake_case (e.g. `skill_recipes.md`, `skill_set_timers.md`)
- Do not use spaces or hyphens in the filename

## How to write a skill file

A skill file is a markdown document. It should:

1. Start with a `# Title` heading that names the skill
2. Describe **when** the skill applies — what kinds of user requests trigger it
3. Describe **what to do** — step-by-step instructions or behavioral guidance, written clearly for an agent to follow
4. Include relevant directory paths, file naming conventions, or tool usage if the skill involves reading/writing files or calling external services
5. Include edge cases and fallback behavior where relevant

Keep skill files focused on one domain or behavior. Do not combine unrelated behaviors into a single file.

## After creating the skill

Tell the user the skill has been saved and will be available the next time the service starts. Skills are only loaded at startup, so the current session does not pick up newly written files.

## Example skill file

```markdown
# Set Timers

When the user asks you to set a timer or remind them about something, schedule a reminder using the task scheduler.

## How to set a timer

1. Parse the duration or time from the user's request.
2. Use the schedule_task tool to create a reminder at the specified time.
3. Confirm with the user what was scheduled and when it will fire.

## If scheduling fails

Tell the user the timer could not be set and ask them to try again.
```
