# /// script
# requires-python = ">=3.11"
# ///
"""Static site generator for the newsletter portal."""

import re
import shutil
import tomllib
from datetime import datetime
from html import escape
from pathlib import Path

SHARED_DIR = Path(__file__).parent
REPO_ROOT = SHARED_DIR.parent
DIST_DIR = REPO_ROOT / "dist"
TEMPLATES_DIR = SHARED_DIR / "templates"
SHARED_STYLESHEET = SHARED_DIR / "assets" / "style.css"
DARK_STYLESHEET = SHARED_DIR / "assets" / "dark.css"


def load_config() -> dict:
    """Load topic registry.  Prefers topics.json; falls back to topics.toml."""
    json_path = REPO_ROOT / "topics.json"
    if json_path.exists():
        import json
        return json.loads(json_path.read_text())
    with open(REPO_ROOT / "topics.toml", "rb") as f:
        return tomllib.load(f)


def discover_dates(topic_dir: Path) -> list[str]:
    """Find all YYYY-MM-DD.md files, return sorted date strings (newest first)."""
    return sorted(
        [f.stem for f in topic_dir.glob("????-??-??.md")],
        reverse=True,
    )


def discover_html_archives(topic_dir: Path) -> dict[str, Path]:
    """Find all site/YYYY-MM-DD.html files, return {date: path}."""
    site_dir = topic_dir / "site"
    result = {}
    for f in site_dir.glob("????-??-??.html"):
        result[f.stem] = f
    return result


def get_latest_html(topic_dir: Path) -> str | None:
    html_path = topic_dir / "site" / "index.html"
    if html_path.exists():
        return html_path.read_text()
    return None


def extract_metadata(html: str) -> dict:
    """Parse signal rating and date from generated HTML."""
    rating_match = re.search(r'class="signal-rating">\s*(\d+)\s*/\s*(\d+)', html)
    date_match = re.search(r'class="masthead-date">(.+?)</div>', html)
    return {
        "signal_num": int(rating_match.group(1)) if rating_match else 0,
        "signal_max": int(rating_match.group(2)) if rating_match else 5,
        "signal_display": f"{rating_match.group(1)} / {rating_match.group(2)}" if rating_match else "",
        "date_display": date_match.group(1).strip() if date_match else "",
    }


def format_date_short(date_str: str) -> str:
    """Convert YYYY-MM-DD to 'Mar 22' format."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%b %d")
    except ValueError:
        return date_str


def format_date_archive(date_str: str) -> str:
    """Convert YYYY-MM-DD to 'Mar 22, 2026' format for the archive page."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%b %d, %Y")
    except ValueError:
        return date_str


def render_nav(topic_name: str, current_date: str, dates: list[str], current_idx: int) -> str:
    """Render navigation bar HTML."""
    nav_template = (TEMPLATES_DIR / "nav.html").read_text()

    prev_link = ""
    if current_idx < len(dates) - 1:
        prev_date = dates[current_idx + 1]
        prev_link = f'<a href="{prev_date}.html" class="portal-nav-date-arrow">&larr;</a>'

    next_link = ""
    if current_idx > 0:
        next_date = dates[current_idx - 1]
        next_link = f'<a href="{next_date}.html" class="portal-nav-date-arrow">&rarr;</a>'

    date_display = format_date_short(current_date)

    return (
        nav_template
        .replace("{{NAV_HOME_HREF}}", "../index.html")
        .replace("{{NAV_TOPIC_NAME}}", topic_name)
        .replace("{{NAV_PREV_LINK}}", prev_link)
        .replace("{{NAV_CURRENT_DATE}}", date_display)
        .replace("{{NAV_NEXT_LINK}}", next_link)
    )


def inject_nav(html: str, nav_html: str, slug: str = "", date: str = "") -> str:
    """Inject nav bar into existing HTML: add portal.css, body class, nav element."""
    # Rewrite style.css and dark.css paths to ../<file> (one level up from dist/<slug>/)
    html = re.sub(
        r'<link\s+rel="stylesheet"\s+href="style\.css"\s*/?>',
        '<link rel="stylesheet" href="../style.css">\n<link rel="stylesheet" href="../portal.css">',
        html,
    )
    html = re.sub(
        r'<link\s+rel="stylesheet"\s+href="dark\.css"\s*/?>',
        '<link rel="stylesheet" href="../dark.css">',
        html,
    )

    # Add has-portal-nav class and data-slug/data-date to body
    data_attrs = f' data-slug="{slug}" data-date="{date}"' if slug else ""
    html = re.sub(r"<body([^>]*)>", rf'<body\1 class="has-portal-nav"{data_attrs}>', html, count=1)

    # Insert nav right after <body ...>
    html = re.sub(
        r'(<body[^>]*>)',
        rf'\1\n{nav_html}',
        html,
        count=1,
    )

    return html


def discover_media(topic_dir: Path, date: str) -> dict[str, Path | None]:
    """Find media files for a given date in topics/<slug>/media/."""
    media_dir = topic_dir / "media"
    if not media_dir.exists():
        return {"banner": None, "context": None, "infographic": None, "slides": None, "podcast": None, "video": None}
    return {
        "banner":      next(media_dir.glob(f"{date}-banner.png"),      None),
        "context":     next(media_dir.glob(f"{date}-context.png"),     None),
        "infographic": next(media_dir.glob(f"{date}-infographic.png"), None),
        "slides":      next(media_dir.glob(f"{date}-slides.pdf"),      None),
        "podcast":     next(media_dir.glob(f"{date}-podcast.mp3"),     None),
        "video":       next(media_dir.glob(f"{date}-video.mp4"),       None),
    }


def copy_media(media: dict[str, Path | None], topic_dist: Path) -> dict[str, str]:
    """Copy media files to dist/<slug>/media/. Returns relative URLs."""
    import shutil as _shutil
    media_dist = topic_dist / "media"
    urls: dict[str, str] = {}
    for key, src in media.items():
        if src and src.exists():
            media_dist.mkdir(exist_ok=True)
            dst = media_dist / src.name
            _shutil.copy2(src, dst)
            urls[key] = f"media/{src.name}"
    return urls


def render_banner_infographic(url: str) -> str:
    """Render the full-width banner infographic block placed after the masthead."""
    return (
        f'<div class="banner-infographic">'
        f'<div class="banner-infographic-label">Issue Overview &middot; NotebookLM</div>'
        f'<img src="{url}" alt="Issue overview infographic">'
        f'</div>'
    )


def render_context_infographic(url: str) -> str:
    """Render the context infographic block embedded inside Section 05 tip-container."""
    return (
        f'<div class="context-infographic">'
        f'<div class="context-infographic-label">Visual Summary &middot; NotebookLM</div>'
        f'<img src="{url}" alt="Context briefing infographic">'
        f'</div>'
    )


def render_media_section(slug: str, date: str, media: dict[str, str]) -> str:
    """Render media section HTML.

    Shows infographic and slides if available.
    Shows Generate buttons for podcast/video (calls /api/generate/{slug}/{date}/{type}).
    """
    parts: list[str] = []

    if media.get("infographic"):
        parts.append(
            f'<div class="media-item media-infographic">'
            f'<div class="media-label">Infographic</div>'
            f'<img src="{media["infographic"]}" alt="Issue infographic" class="media-img">'
            f'</div>'
        )

    if media.get("slides"):
        parts.append(
            f'<div class="media-item media-slides">'
            f'<div class="media-label">Slide Deck</div>'
            f'<a href="{media["slides"]}" class="media-download" target="_blank" download>'
            f'&#x1F4F2; Download Slides (PDF)</a>'
            f'</div>'
        )

    if media.get("podcast"):
        parts.append(
            f'<div class="media-item media-podcast">'
            f'<div class="media-label">Podcast</div>'
            f'<audio controls class="media-audio" src="{media["podcast"]}"></audio>'
            f'</div>'
        )
    else:
        parts.append(
            f'<div class="media-item media-on-demand" id="pod-{slug}-{date}">'
            f'<div class="media-label">Podcast</div>'
            f'<button class="media-gen-btn" '
            f'onclick="startGeneration(\'{slug}\',\'{date}\',\'podcast\',this)">'
            f'&#x25B6; Generate Podcast</button>'
            f'</div>'
        )

    if media.get("video"):
        parts.append(
            f'<div class="media-item media-video">'
            f'<div class="media-label">Video</div>'
            f'<video controls class="media-video-player" src="{media["video"]}"></video>'
            f'</div>'
        )
    else:
        parts.append(
            f'<div class="media-item media-on-demand" id="vid-{slug}-{date}">'
            f'<div class="media-label">Video</div>'
            f'<button class="media-gen-btn" '
            f'onclick="startGeneration(\'{slug}\',\'{date}\',\'video\',this)">'
            f'&#x25B6; Generate Video</button>'
            f'</div>'
        )

    inner = "\n".join(parts)
    script = _media_js()
    return (
        f'<section class="portal-media-section" data-slug="{slug}" data-date="{date}">\n'
        f'<h2 class="section-title">Media</h2>\n'
        f'<div class="media-grid">\n{inner}\n</div>\n'
        f'{script}\n'
        f'</section>'
    )


def _media_js() -> str:
    """Inline JS for on-demand media generation buttons (injected once per page)."""
    return """<script>
function startGeneration(slug, date, type, btn) {
  btn.disabled = true;
  btn.textContent = '⏳ Generating…';
  fetch('/api/generate/' + slug + '/' + date + '/' + type, {method: 'POST'})
    .then(r => r.json())
    .then(data => {
      if (data.job_id) pollJob(data.job_id, slug, date, type, btn);
      else { btn.textContent = '❌ Error'; btn.disabled = false; }
    })
    .catch(() => { btn.textContent = '❌ Error'; btn.disabled = false; });
}
function pollJob(jobId, slug, date, type, btn) {
  fetch('/api/jobs/' + jobId)
    .then(r => r.json())
    .then(data => {
      if (data.status === 'done') { location.reload(); }
      else if (data.status === 'failed') {
        btn.textContent = '❌ Failed: ' + (data.error || 'unknown');
        btn.disabled = false;
      } else {
        btn.textContent = '⏳ ' + (data.step || 'Generating…');
        setTimeout(() => pollJob(jobId, slug, date, type, btn), 10000);
      }
    })
    .catch(() => setTimeout(() => pollJob(jobId, slug, date, type, btn), 15000));
}
</script>"""


def render_topic_card(slug: str, topic: dict, meta: dict) -> str:
    accent = topic.get("accent", "terracotta")
    latest_date = meta.get("latest_date", "")
    signal = meta.get("signal_display", "")
    signal_label = topic.get("signal_label", "Signal")

    signal_text = f"{signal_label} {signal}" if signal else ""
    date_text = format_date_short(latest_date) if latest_date else ""

    return f'''      <a href="{slug}/index.html" class="portal-card accent-{accent}">
        <div class="portal-card-eyebrow">{topic.get("eyebrow", "")}</div>
        <div class="portal-card-title">{topic["name"]}</div>
        <div class="portal-card-desc">{topic["description"]}</div>
        <div class="portal-card-meta">
          <span>{date_text}</span>
          <span class="portal-card-signal">{signal_text}</span>
        </div>
      </a>
'''


def render_archive_item(entry: dict) -> str:
    """Render a single archive list row."""
    accent = escape(entry.get("accent", "terracotta"))
    topic_name = escape(entry["topic_name"])
    description = escape(entry["topic_description"])
    date_display = escape(entry["date_display"])
    href = escape(entry["href"])

    return f'''      <a href="{href}" class="archive-item accent-{accent}">
        <div class="archive-item-main">
          <span class="archive-item-label">{topic_name}</span>
          <span class="archive-item-topic">{description}</span>
        </div>
        <span class="archive-item-date">{date_display}</span>
      </a>
'''


def build_archive(archive_entries: list[dict]) -> str:
    """Build the combined cross-topic archive page."""
    template = (TEMPLATES_DIR / "archive.html").read_text()
    if archive_entries:
        items_html = "".join(render_archive_item(e) for e in archive_entries)
    else:
        items_html = '      <div class="archive-empty">No archived issues yet.</div>\n'

    now = datetime.now()
    today = now.strftime("%A, %B %d, %Y")
    colophon = f"{len(archive_entries)} archived issues &middot; {now.strftime('%B %d, %Y')}"

    return (
        template
        .replace("{{DATE_LONG}}", today)
        .replace("{{ARCHIVE_COUNT}}", str(len(archive_entries)))
        .replace("{{ARCHIVE_ITEMS}}", items_html)
        .replace("{{FOOTER_COLOPHON}}", colophon)
    )


def build_landing(config: dict, topic_metas: dict, archive_count: int = 0) -> str:
    template = (TEMPLATES_DIR / "landing.html").read_text()

    cards_html = ""
    built_topic_count = 0
    for slug, topic in config.items():
        if slug not in topic_metas:
            continue
        meta = topic_metas.get(slug, {})
        cards_html += render_topic_card(slug, topic, meta)
        built_topic_count += 1

    today = datetime.now().strftime("%A, %B %d, %Y")
    colophon = f"{built_topic_count} briefings &middot; {datetime.now().strftime('%B %d, %Y')}"

    return (
        template
        .replace("{{DATE_LONG}}", today)
        .replace("{{TOPIC_COUNT}}", str(built_topic_count))
        .replace("{{ARCHIVE_COUNT}}", str(archive_count))
        .replace("{{TOPIC_CARDS}}", cards_html)
        .replace("{{FOOTER_COLOPHON}}", colophon)
    )


def build():
    config = load_config()

    # Clean and recreate dist/
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()

    # Copy shared assets
    shutil.copy2(SHARED_STYLESHEET, DIST_DIR / "style.css")
    shutil.copy2(SHARED_DIR / "portal.css", DIST_DIR / "portal.css")
    if DARK_STYLESHEET.exists():
        shutil.copy2(DARK_STYLESHEET, DIST_DIR / "dark.css")

    # Copy management page
    manage_src = TEMPLATES_DIR / "manage.html"
    if manage_src.exists():
        shutil.copy2(manage_src, DIST_DIR / "manage.html")

    topic_metas = {}
    archive_entries: list[dict] = []

    for slug, topic in config.items():
        topic_dir = REPO_ROOT / topic["folder"]

        # Candidate dates = union of markdown dates and archived HTML dates
        md_dates = set(discover_dates(topic_dir))
        html_archives = discover_html_archives(topic_dir)
        candidate_dates = sorted(md_dates | set(html_archives.keys()), reverse=True)

        latest_html = get_latest_html(topic_dir)

        # Resolve emitted dates: only dates with actual HTML
        emitted_dates: list[str] = []
        for idx, date in enumerate(candidate_dates):
            if date in html_archives:
                emitted_dates.append(date)
            elif idx == 0 and latest_html:
                emitted_dates.append(date)

        # Skip early if there is nothing to emit, avoiding an empty dist/<slug>/ dir
        if not emitted_dates and not latest_html:
            print(f"  Skipping {slug}: no site HTML found")
            continue

        # Create topic output directory (deferred until we know we'll write to it)
        topic_dist = DIST_DIR / slug
        topic_dist.mkdir(parents=True, exist_ok=True)

        # Process emitted dates
        latest_output_html = None
        for i, date in enumerate(emitted_dates):
            if date in html_archives:
                page_html = html_archives[date].read_text()
            elif i == 0 and latest_html:
                page_html = latest_html
            else:
                continue

            nav_html = render_nav(topic["name"], date, emitted_dates, i)
            output_html = inject_nav(page_html, nav_html, slug=slug, date=date)
            media = copy_media(discover_media(topic_dir, date), topic_dist)

            # Inject banner infographic after masthead
            banner_html = render_banner_infographic(media["banner"]) if media.get("banner") else ""
            output_html = output_html.replace("{{BANNER_INFOGRAPHIC}}", banner_html)

            # Inject context infographic inside Section 05 tip-container
            context_html = render_context_infographic(media["context"]) if media.get("context") else ""
            output_html = output_html.replace("{{CONTEXT_INFOGRAPHIC}}", context_html)

            # Inject bottom media section (podcast / video on-demand)
            media_html = render_media_section(slug, date, media)
            output_html = output_html.replace("{{MEDIA_SECTION}}", media_html)

            (topic_dist / f"{date}.html").write_text(output_html)

            if i == 0:
                latest_output_html = output_html

            # One archive entry per canonical dated issue
            archive_entries.append({
                "slug": slug,
                "topic_name": topic["name"],
                "topic_description": topic["description"],
                "accent": topic.get("accent", "terracotta"),
                "date": date,
                "date_display": format_date_archive(date),
                "href": f"../{slug}/{date}.html",
            })

        # Write topic index and collect metadata
        if latest_output_html:
            (topic_dist / "index.html").write_text(latest_output_html)
            source_html = (html_archives[emitted_dates[0]].read_text()
                           if emitted_dates[0] in html_archives else latest_html)
            meta = extract_metadata(source_html or "")
            meta["dates"] = emitted_dates
            meta["latest_date"] = emitted_dates[0]
            topic_metas[slug] = meta
        elif latest_html:
            nav_html = render_nav(topic["name"], "", [], 0)
            output_html = inject_nav(latest_html, nav_html, slug=slug)
            output_html = output_html.replace("{{MEDIA_SECTION}}", "")
            (topic_dist / "index.html").write_text(output_html)
            meta = extract_metadata(latest_html)
            meta["dates"] = []
            meta["latest_date"] = ""
            topic_metas[slug] = meta
        print(f"  {slug}: {len(emitted_dates)} date(s)")

    # Sort archive: newest first, then by topic name for stable ordering
    archive_entries.sort(key=lambda e: e["topic_name"])
    archive_entries.sort(key=lambda e: e["date"], reverse=True)

    # Build archive page
    archive_dist = DIST_DIR / "archives"
    archive_dist.mkdir(parents=True, exist_ok=True)
    archive_html = build_archive(archive_entries)
    (archive_dist / "index.html").write_text(archive_html)

    # Build landing page
    landing_html = build_landing(config, topic_metas, len(archive_entries))
    (DIST_DIR / "index.html").write_text(landing_html)

    print(f"\nBuilt portal: {len(topic_metas)} topics, {len(archive_entries)} archive entries → dist/")


if __name__ == "__main__":
    build()
