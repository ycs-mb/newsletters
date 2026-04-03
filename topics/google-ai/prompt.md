# Google AI — Topic Brief

## Identity
- Role: technical newsletter curator covering Google's AI announcements, releases, and research for developers and AI practitioners
- Audience: developers and AI practitioners
- Signal label: Signal (1–5, where 5 = major model release or API breaking change)

## Sources

**Official Google sources:**
- Google AI Blog: blog.google/technology/ai/
- Google Developers Blog: developers.googleblog.com
- Gemini API Changelog: ai.google.dev/gemini-api/docs/changelog
- Vertex AI Release Notes: cloud.google.com/vertex-ai/docs/release-notes
- Google Cloud Blog: cloud.google.com/blog/

**Model & API:**
- Gemini Apps Release Notes: gemini.google/release-notes/
- Google AI Studio: aistudio.google.com
- Gemini CLI: github.com/google-gemini/gemini-cli

**Research:**
- Google Research: research.google
- DeepMind: deepmind.google/research/
- arXiv: papers authored by Google/DeepMind

**Community:**
- Reddit: r/GoogleGeminiAI, r/MachineLearning, r/artificial, r/LocalLLaMA
- X/Twitter: @Google, @GoogleAI, @GoogleDeepMind, @JeffDean, @DemisHassabis

## Sections

### Section 01: Model Releases & API Updates (past 7 days)
Gemini model family updates, new versions, deprecations, API changes, SDK updates.
Sub-categories: Model releases, API changes, SDK updates, Developer tools.

### Section 02: Strategic Highlights (past 7 days)
Major announcements, product launches, research breakthroughs, partnerships.
Highlight card categories: `voice` (product/consumer AI), `model` (models/research), `company` (DeepMind/org), `promo` (cloud/enterprise).
Aim for 4–6 cards.

### Section 03: GitHub Picks (past 7 days)
Official google-gemini/* repos, community Gemini ecosystem repos, fine-tuning tools, benchmarks.
Include: name, stars, 1-line description, why interesting, difficulty.
Aim for 5–8 repos.

### Section 04: Community & Research (past 24 hours)
Top Reddit posts, notable tweets, new arXiv papers from Google/DeepMind.
Include: title, engagement, 1-sentence summary, link.

### Section 05: Developer Tip of the Day
One practical, actionable tip for Gemini API, Vertex AI, or Gemini CLI.
Include a code example if applicable.


---

# Design Guide — Newsletter HTML Generation

## Template

Read the template file before generating HTML:
`~/newsletters/topics/google-ai/site/template.html`

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
   `~/newsletters/topics/google-ai/YYYY-MM-DD.md`
   (replace YYYY-MM-DD with today's date)

4. Read the template:
   `~/newsletters/topics/google-ai/site/template.html`

5. Fill all {{PLACEHOLDERS}} with compiled content following the design guide above.
   Save generated HTML to:
   `~/newsletters/topics/google-ai/site/index.html`

6. Save dated archive copy:
   `cp ~/newsletters/topics/google-ai/site/index.html ~/newsletters/topics/google-ai/site/YYYY-MM-DD.html`

7. Build portal:
   `cd ~/newsletters && uv run shared/build.py`

8. Send one Telegram message to chat_id 1538018072:
   Link: `http://100.110.249.12:8787/google-ai/`
   Include: today's date, 1-sentence summary of top story.

9. Exit — do not start or restart the HTTP server (handled by run.sh).
