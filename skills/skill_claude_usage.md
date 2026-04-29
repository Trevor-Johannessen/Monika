---
name: claude-usage
description: Report Claude API spending and remaining credit balance
---

# Claude API Usage

When the user asks about Claude API usage, spending, costs, or remaining credits/balance, use the `bash` tool to query the Anthropic API and report the results.

## Getting monthly spending

Use `curl` to fetch usage data from the Anthropic API. The API key is available as the `ANTHROPIC_API_KEY` environment variable.

```bash
curl -s "https://api.anthropic.com/v1/usage?billing_period=$(date +%Y-%m)" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

If that endpoint doesn't work, try fetching the current month's usage with a date range:

```bash
START=$(date +%Y-%m-01)
END=$(date +%Y-%m-%d)
curl -s "https://api.anthropic.com/v1/usage?start_date=${START}&end_date=${END}" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

## Getting credit balance

```bash
curl -s "https://api.anthropic.com/v1/account/credits" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

## Reporting results

- Report total cost/spend in dollars for the current month.
- Report remaining credit balance in dollars.
- If an endpoint returns an error or unexpected response, report what was returned so the user can investigate.
- Keep the response brief: one or two sentences with the key numbers.
