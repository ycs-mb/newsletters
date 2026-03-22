# Design Guide — Newsletter HTML Generation

## Template

Read the template file before generating HTML:
`~/newsletters/topics/{SLUG}/site/template.html`

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
