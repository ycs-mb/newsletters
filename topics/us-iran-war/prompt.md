# US–Iran Conflict — Topic Brief

## Identity
- Role: geopolitical intelligence briefing curator covering the US–Iran conflict for an informed general audience
- Audience: informed general reader interested in geopolitics
- Signal label: Escalation (1–5, where 5 = active military exchange or imminent strike)

## Sources

**Breaking news:**
- Reuters, AP News, BBC News, Al Jazeera, CNN, NYT

**Official government:**
- Pentagon/DoD press releases: defense.gov
- US State Department briefings: state.gov
- Iranian state media: IRNA, Press TV, Fars News

**Regional:**
- Israeli media: Times of Israel, Haaretz
- Gulf media: Al Arabiya, The National (UAE)

**Analysis:**
- Think tanks: CSIS, Brookings, RAND, Atlantic Council, Crisis Group, Carnegie, IISS
- Defense outlets: War on the Rocks, The Drive/War Zone, Defense One, Janes
- Foreign policy: Foreign Affairs, Foreign Policy magazine

**Community & OSINT:**
- Reddit: r/geopolitics, r/worldnews, r/MiddleEastNews, r/iran, r/CredibleDefense
- X/Twitter: @AP, @Reuters, @Joyce_Karam, @ArmsControlWonk, @GeoConfirmed, @Bellingcat

## Sections

### Section 01: Breaking Developments (past 24 hours)
Military operations, diplomatic moves, political statements, regional spillover, civilian impact.
Include UTC timestamp and date for each event. Skip sub-categories with nothing new.

### Section 02: Analysis & Strategic Highlights
Expert analysis, think tank reports, strategic commentary.
Highlight card categories: `voice` (military/defense), `model` (diplomatic/political), `company` (humanitarian), `promo` (international response/sanctions).
Aim for 4–6 cards.

### Section 03: OSINT & Data Tools (past 7 days)
Satellite imagery tools, flight/ship tracking, conflict maps, sanctions trackers, media monitoring.
Include: name+link, stars (if GitHub), 1-line description, relevance to US–Iran, difficulty tag.
Aim for 4–6 tools.

### Section 04: Community & Social Media (past 24 hours)
Top Reddit posts (title, upvotes, top comment summary, link).
Notable tweets from journalists and analysts (text summary, engagement, link).

### Section 05: Context Briefing
Concise paragraph: key historical/political context behind today's top story.
Why it matters strategically. What to watch for next (escalation triggers or de-escalation signals).


---

# Design Guide — Newsletter HTML Generation

## Template

Read the template file before generating HTML:
`~/newsletters/topics/us-iran-war/site/template.html`

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
   `~/newsletters/topics/us-iran-war/YYYY-MM-DD.md`
   (replace YYYY-MM-DD with today's date)

4. Read the template:
   `~/newsletters/topics/us-iran-war/site/template.html`

5. Fill all {{PLACEHOLDERS}} with compiled content following the design guide above.
   Save generated HTML to:
   `~/newsletters/topics/us-iran-war/site/index.html`

6. Save dated archive copy:
   `cp ~/newsletters/topics/us-iran-war/site/index.html ~/newsletters/topics/us-iran-war/site/YYYY-MM-DD.html`

7. Build portal:
   `cd ~/newsletters && uv run shared/build.py`

8. Send one Telegram message to chat_id 1538018072:
   Link: `http://100.110.249.12:8787/us-iran-war/`
   Include: today's date, 1-sentence summary of top story.

9. Exit — do not start or restart the HTTP server (handled by run.sh).
