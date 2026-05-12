---
name: tech-news-aggregator
description: Pull and summarize current technology news headlines from the internet
---

# Tech News Aggregator

When the user asks for tech news, "what's new in tech", a tech briefing, "catch me up on tech", or any variation that requests current technology headlines, gather fresh stories from the web and present a concise digest.

## When this skill applies

- Direct asks: "any tech news today", "what's happening in tech", "give me a tech briefing".
- Topical asks within tech: "what's new with AI", "latest on Apple", "any chip news this week". Treat the topic as a filter on the same workflow.
- Do **not** use this skill for non-tech news (general world news, sports, finance not specifically tied to tech companies).

## Workflow

1. **Search.** Use the `web_search` tool. Compose queries that bias toward recent results, e.g. `tech news today`, `AI news <current date>`, `<company> announcement this week`. Run two or three queries to cover breadth (general industry, AI/ML, and either hardware or one topic the user mentioned).
2. **Filter.** Keep stories from the last seven days. Discard rumor-mill posts, low-signal aggregator pages, and pieces older than a week unless the user explicitly asked for retrospective coverage.
3. **Deduplicate.** If multiple sources cover the same story, pick the most authoritative one (vendor announcement > major outlet > blog).
4. **Summarize.** For each story, write exactly one sentence that captures both what happened and why it matters. No bullets, no headlines.
5. **Present.** Cover three to seven stories in a single conversational paragraph (or short stretch of prose), ordered by significance. Use natural connective phrasing — "On the AI side,", "Meanwhile,", "Also worth noting,", etc. — instead of a list.

## Output format

Conversational prose. Each story gets one sentence and a parenthetical source at the end of that sentence. Example shape:

> Apple announced a new in-house modem this morning, signaling the end of its Qualcomm dependency (Reuters). On the AI side, Anthropic shipped a new agentic coding model that posts state-of-the-art SWE-bench numbers (The Verge). Meanwhile, a critical OpenSSL CVE dropped and most major distros already have patches out (Ars Technica).

Keep the whole response under roughly 150 words unless the user asks for depth. If the user wants more on a specific item, follow up with a deeper search on that story.

## Topical filters

If the user names a topic (AI, security, a specific company, etc.), restrict queries and results to that topic. If results are thin, say so plainly rather than padding with unrelated stories.

## Edge cases

- If `web_search` returns nothing useful, tell the user and offer to broaden the topic or look further back.
- If the user asks for news on a non-tech subject, decline this skill's scope and suggest a regular web search.
- Never fabricate headlines or sources. Every bullet must come from a real search result.
- Cite the source name in parentheses at the end of each bullet so the user can follow up. Do not invent URLs.
