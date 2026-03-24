# Claude Digest — Topic Brief

## Identity
- Role: technical newsletter curator covering Anthropic, Claude Code, and the Claude ecosystem for developers and AI practitioners
- Audience: developers and AI practitioners
- Signal label: Signal (1–5, where 5 = major release or breaking change day)

## Sources

**Claude Code releases:**
- GitHub releases: github.com/anthropics/claude-code/releases
- npm changelog: npmjs.com/package/@anthropic-ai/claude-code
- Claude Code changelog: docs.anthropic.com/claude-code/changelog

**Anthropic official:**
- Anthropic blog: anthropic.com/news
- Anthropic research: anthropic.com/research
- Model releases: docs.anthropic.com/claude/models

**Community:**
- Hacker News: news.ycombinator.com (search "Claude", "Anthropic", "claude-code")
- Reddit: r/ClaudeAI, r/MachineLearning, r/LocalLLaMA
- X/Twitter: @AnthropicAI, @alexalbert__, @AmandaAskell, notable dev accounts

**GitHub ecosystem:**
- Trending repos tagged "claude", "anthropic", "mcp"
- MCP servers: github.com/modelcontextprotocol

**Research & papers:**
- arXiv (cs.AI, cs.CL): new Anthropic-affiliated papers
- Hugging Face: new Anthropic models, papers

## Sections

### Section 01: Claude Code (past 7 days)
Track all Claude Code CLI releases. Include version numbers, dates, key features/fixes.
Wrap CLI flags in `<code>` tags. If nothing new: "No releases this week."

### Section 02: Anthropic Official (past 7 days)
Major announcements, model releases, policy updates, blog posts.
Highlight card categories: `voice` (product/features), `model` (models/research), `company` (org news), `promo` (partnerships/enterprise).
Aim for 4–6 cards.

### Section 03: GitHub Picks (past 7 days)
Trending or newly notable repos related to Claude, Anthropic, MCP, or AI tooling.
Include: name, stars, 1-line description, why it's interesting, difficulty.
Aim for 5–8 repos.

### Section 04: Community & Research (past 24 hours)
Top posts from Reddit and HN. Notable tweets from key accounts. New arXiv papers.
Include: title, upvotes/engagement, 1-sentence summary, link.

### Section 05: Tip of the Day
One practical, actionable tip for Claude Code or Claude API users.
Include a code example if applicable. Prefer tips that are non-obvious or recently enabled.


---

# Design Guide — Newsletter HTML Generation

## Template

Read the template file before generating HTML:
`~/newsletters/topics/claude-digest/site/template.html`

Also read the stylesheet for class reference:
`~/newsletters/shared/assets/style.css`

**DO NOT modify style.css or template.html structure. All styling is locked.**

## Placeholders to Replace

| Placeholder | Value |
|---|---|
| `{{DATE_TITLE}}` | e.g. `March 22, 2026` |
| `{{DATE_LONG}}` | e.g. `Saturday, March 22, 2026` |
| `{{SIGNAL_DOTS}}` | N filled dots + (5-N) empty dots using `.signal-dot.filled` / `.signal-dot` CSS classes |
| `{{SIGNAL_RATING}}` | e.g. `4 / 5` |
| `{{VERSION_RANGE}}` | Date or version range covered |
| `{{RELEASE_ITEMS}}` | One `.release-item` div per event |
| `{{HIGHLIGHT_CARDS}}` | One `.highlight-card` div per highlight |
| `{{REPO_COUNT}}` | Integer count of repos/tools |
| `{{REPO_CARDS}}` | One `<a class="repo-card">` per repo |
| `{{COMMUNITY_BLOCKS}}` | One `.community-block` per source |
| `{{TIP_CONTENT}}` | Tip or context briefing text |
| `{{FOOTER_COLOPHON}}` | One-line day summary |

## HTML Patterns

**Signal dots (4 of 5 filled):**
```html
<div class="signal-dot filled"></div>
<div class="signal-dot filled"></div>
<div class="signal-dot filled"></div>
<div class="signal-dot filled"></div>
<div class="signal-dot"></div>
```

**Release item:**
```html
<div class="release-item">
  <span class="release-version">v2.1.81</span>
  <span class="release-date">Mar 21</span>
  <span class="release-desc">Description. Wrap CLI in <code>--flag</code> tags.</span>
</div>
```

**Highlight card (category classes: `voice` `model` `company` `promo`):**
```html
<div class="highlight-card voice">
  <div class="highlight-label">Category</div>
  <div class="highlight-title">Title</div>
  <div class="highlight-desc">Description text.</div>
</div>
```

**Repo card (difficulty classes: `easy` `medium` `advanced`):**
```html
<a href="https://github.com/owner/repo" target="_blank" rel="noopener" class="repo-card">
  <div class="repo-top">
    <span class="repo-name">owner/repo</span>
    <div class="repo-badges">
      <span class="repo-stars">12k</span>
      <span class="repo-diff easy">Easy</span>
    </div>
  </div>
  <div class="repo-desc">One-line description.</div>
  <div class="repo-why">Why it's relevant — one sentence.</div>
</a>
```

**Community block:**
```html
<div class="community-block">
  <div class="source-name">
    <span class="source-icon">&#128172;</span> Reddit
    <span class="source-meta">r/ClaudeAI &middot; 612k members</span>
  </div>
  <div class="community-item">
    <div class="community-title">Post title <span class="upvote-badge">&#9650; 1.2k</span></div>
    <div class="community-detail">Summary. <a href="URL" target="_blank">Read &rarr;</a></div>
  </div>
</div>
```

If a section has no content, write "Nothing notable today" — do not pad with filler.


---

# Operations Guide — Newsletter Delivery

## ACTIONS (execute in order)

Today's date: determine from system clock (format YYYY-MM-DD).

1. Search the web thoroughly for all sections in the topic brief above.

2. Compile newsletter content.

3. Save raw markdown to:
   `~/newsletters/topics/claude-digest/YYYY-MM-DD.md`
   (replace YYYY-MM-DD with today's date)

4. Read the template:
   `~/newsletters/topics/claude-digest/site/template.html`

5. Fill all {{PLACEHOLDERS}} with compiled content following the design guide above.
   Save generated HTML to:
   `~/newsletters/topics/claude-digest/site/index.html`

6. Save dated archive copy:
   `cp ~/newsletters/topics/claude-digest/site/index.html ~/newsletters/topics/claude-digest/site/YYYY-MM-DD.html`

7. Build portal:
   `cd ~/newsletters && uv run shared/build.py`

8. Send one Telegram message to chat_id 1538018072:
   Link: `http://100.110.249.12:8787/claude-digest/`
   Include: today's date, 1-sentence summary of top story.

9. Exit — do not start or restart the HTTP server (handled by run.sh).
