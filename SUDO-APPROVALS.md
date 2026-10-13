# Monika Sudo Approval Framework

When Monika needs to run a command with elevated privileges (`sudo`), she does not run it directly. She calls the `request_sudo_approval` MCP tool, which queues the request in the lab-wide approval framework (source in `~/repos/scripts/sudo-approval/`, see its README; `sudolib` comes from `~/repos/lib`, installed to `/usr/local/lib/homelab/`). This creates an audit trail and gives you control over what runs on your system.

## How It Works

1. **Monika calls `request_sudo_approval`** with:
   - `command`: The full command to run (without `sudo` prefix)
   - `context`: One line summarizing what she was doing
   - `purpose`: One line explaining why she needs sudo
   - `risks`: One line describing what could go wrong

2. **Request queued:** The tool calls `sudolib.request_approval()`, which appends a block to `~/.local/share/sudo-approval/pending.sh`. The tool fills in the rest itself:
   - `SOURCE`: `discord` when the current turn came from Discord, otherwise `monika`
   - `REPLY_TO`: the Discord thread or channel id, for Discord turns
   - `HOST`: the machine Monika runs on, so the command runs there
   - `SESSION_ID`: a timestamped id that only tells requests apart in the queue (Monika has one session)

3. **You review:** Run `~/.local/share/sudo-approval/approve.py` and approve, deny or postpone each request.

4. **Monika is told the outcome:** `approve.py` sends a prompt into her session saying whether the command was approved and ran, failed, or was denied. For a Discord request, her reply is posted to the thread the request came from.

## Example Approval Block

```
@@APPROVAL_BLOCK_START
SOURCE: discord
SESSION_ID: monika-20261009-152233
HOST: deploy1
REPLY_TO: 1424567890123456789
CONTEXT: Redeploying Wordle server with keyboard fix
PURPOSE: Need root to restart the systemd service
COMMAND: systemctl restart wordle-server
RISKS: Service restart will briefly interrupt active game sessions
@@APPROVAL_BLOCK_END
```

The agent then **stops and waits**. It does not retry or continue until it is told the outcome.
