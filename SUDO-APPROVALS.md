# Monika Sudo Approval Framework

When Monika's agents need to run commands with elevated privileges (using `sudo`), they use the sudo approval framework instead of running them directly. This creates an audit trail and gives you control over what runs on your system.

## How It Works

1. **Agent detects it needs sudo:** When an agent realizes it needs elevated privileges, instead of attempting to run `sudo` directly, it calls the `request_sudo_approval` MCP tool.

2. **Approval block created:** The tool captures:
   - Session ID (so the conversation can be resumed)
   - What the agent was working on (context)
   - Why it needs sudo (purpose)
   - What the command actually does
   - What could go wrong (risks)

3. **Request queued:** All of this goes into `~/.monika/pending-approval.sh` as a structured approval block.

4. **You review:** Run `~/.monika/approve-pending.py` to see all pending approvals. Each block displays the context, purpose, command, and risks.

5. **You decide:** For each block, answer yes or no.
   - **Yes:** The command executes and the agent's conversation resumes from where it left off
   - **No:** The block stays pending; the agent never runs the command

## Files

- **`~/.monika/pending-approval.sh`**: Queue of pending approval blocks (automatically managed by Monika)
- **`~/.monika/approve-pending.py`**: Interactive approval review script — run this to approve or reject
- **`orchestrationAgent.py`**: Contains the `request_sudo_approval` tool implementation

## Reviewing Approvals

```bash
~/.monika/approve-pending.py
```

This will display each pending approval one at a time, showing:
1. The context summary (what the agent was doing)
2. The purpose (why it needs sudo)
3. The actual sudo command
4. The risks (what could go wrong)

Answer `y` or `n` for each one. Approved blocks are removed from the queue; rejected ones remain for later review.

## Example Approval Block

When added to `pending-approval.sh`, an approval block looks like:

```
@@APPROVAL_BLOCK_START
SESSION_ID: 12345-abcde
CONTEXT: Configuring a new systemd service for the backup daemon
PURPOSE: Need to move the service file to /etc/systemd/system/ and reload systemd
COMMAND: systemctl daemon-reload
RISKS: If the service file is malformed, this could prevent services from starting. Low risk since this only reloads configurations, doesn't stop anything.
@@APPROVAL_BLOCK_END
```

## For Developers

When writing an agent that needs sudo, call the `request_sudo_approval` tool with:

- `session_id`: The current session ID (track this from the SDK)
- `command`: The full command to run (without `sudo` prefix)
- `context`: One line summarizing what you were doing
- `purpose`: One line explaining why you need sudo
- `risks`: One line describing what could go wrong

Example:
```
request_sudo_approval(
    session_id="current-session-id",
    command="cp /home/user/config /etc/service.conf && chown root:root /etc/service.conf",
    context="Setting up a new service configuration file",
    purpose="Need root permissions to write to /etc/ and change file ownership",
    risks="Could overwrite an existing service config if paths are wrong"
)
```

The agent then **stops and waits**. It does not retry or continue. The user reviews the approval, and if approved, the agent's conversation resumes automatically.
