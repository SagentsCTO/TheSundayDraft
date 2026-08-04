#!/usr/bin/env python3
"""
Checks the 'Full Episodes' YouTube playlist for videos that don't have a
show-notes page yet, and generates one for each — plus regenerates the
episode archive, the homepage's "Latest episode" blurb, and sitemap.xml.

Runs stdlib-only (no pip install needed) so it's cheap and reliable inside
GitHub Actions. Safe to run repeatedly: does nothing if there's nothing new.
"""
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPISODES_DIR = os.path.join(ROOT, "episodes")
MANIFEST_PATH = os.path.join(EPISODES_DIR, "episodes.json")
INDEX_PATH = os.path.join(ROOT, "index.html")
SITEMAP_PATH = os.path.join(ROOT, "sitemap.xml")

PLAYLIST_ID = "PLCxPsA1wKBkk"  # "Full Episodes" playlist — Shorts are never added here
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?playlist_id={PLAYLIST_ID}"

# Show-level (not episode-level) follow links, used for the "Follow on X" nudge
# under embedded players — plays via the embed don't register as a follow on
# either platform, so this is a one-click way for listeners to actually
# subscribe on the platform they're already listening in.
SPOTIFY_SHOW_URL = "https://open.spotify.com/show/2EoiIdSHex4INCZVOmkU1F"
APPLE_SHOW_URL = "https://podcasts.apple.com/us/podcast/the-sunday-draft/id1887351307"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

CTA_LINE_RE = re.compile(
    r"^(subscribe|follow|watch on|listen on|find us|referenced|timestamps?|"
    r"\d{1,2}:\d{2}|🎥|🎧|🎬|📖|🔗|▶️|📌|📣|⏱️|🎙️)",
    re.IGNORECASE,
)


def fetch_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_entries(xml_bytes):
    root = ET.fromstring(xml_bytes)
    entries = []
    for entry in root.findall("atom:entry", NS):
        video_id = entry.findtext("yt:videoId", default="", namespaces=NS)
        title = entry.findtext("atom:title", default="", namespaces=NS)
        published = entry.findtext("atom:published", default="", namespaces=NS)
        group = entry.find("media:group", NS)
        description = ""
        if group is not None:
            description = group.findtext("media:description", default="", namespaces=NS) or ""
        if video_id and title:
            entries.append({
                "video_id": video_id,
                "title": title.strip(),
                "published": published,
                "description": description.strip(),
            })
    # newest first, by published date
    entries.sort(key=lambda e: e["published"], reverse=True)
    return entries


def slugify(title):
    s = title.lower()
    s = re.sub(r"[’'\"()]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:80].rstrip("-")


def clean_description(text):
    lines = [l.strip() for l in text.splitlines()]
    kept = []
    for l in lines:
        if not l:
            continue
        if CTA_LINE_RE.match(l):
            continue
        kept.append(l)
        if len(kept) >= 6:  # keep it to a reasonable show-notes length
            break
    return kept


def format_date(published_iso):
    try:
        dt = datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.utcnow()
    return dt.strftime("%B %-d, %Y") if os.name != "nt" else dt.strftime("%B %d, %Y"), dt.strftime("%Y-%m-%d")


PAGE_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | The Sunday Draft</title>
<meta name="description" content="{meta_desc}">
<link rel="canonical" href="https://thesundaydraft.com/episodes/{slug}.html">

<meta property="og:title" content="{title} | The Sunday Draft">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:image" content="../assets/og-image.jpg">
<meta property="og:url" content="https://thesundaydraft.com/episodes/{slug}.html">
<meta name="twitter:card" content="summary_large_image">

<link rel="icon" href="../assets/favicon.png">
<link rel="apple-touch-icon" href="../assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../styles.css?v=11">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "PodcastEpisode",
  "name": {json_title},
  "description": {json_desc},
  "datePublished": "{iso_date}",
  "url": "https://thesundaydraft.com/episodes/{slug}.html",
  "partOfSeries": {{
    "@type": "PodcastSeries",
    "name": "The Sunday Draft",
    "url": "https://thesundaydraft.com"
  }},
  "associatedMedia": {{
    "@type": "MediaObject",
    "contentUrl": "{media_url}"
  }}
}}
</script>
</head>
<body>

<header class="site-header">
  <div class="wrap header-inner">
    <a href="../index.html" class="logo"><img src="../assets/logo-wordmark.png" alt="The Sunday Draft" class="logo-img"></a>
    <nav class="nav">
      <a href="../index.html#episodes">Latest</a>
      <a href="index.html">Episodes</a>
      <a href="../index.html#listen">Listen</a>
      <a href="../index.html#about">About</a>
      <a href="../index.html#newsletter">Newsletter</a>
    </nav>
  </div>
</header>

<main>
  <article class="section episode-article">
    <div class="wrap wrap-narrow">
      <p class="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>

      <div class="{embed_class}">
        {embed_html}
      </div>

      <div class="show-notes">
{body_html}
      </div>

      <p class="text-link"><a href="../index.html#listen">Find The Sunday Draft on YouTube, Spotify &amp; Apple Podcasts &rarr;</a></p>
      <p class="text-link"><a href="index.html">&larr; Back to all episodes</a></p>
    </div>
  </article>
</main>

<footer class="site-footer">
  <div class="wrap footer-inner">
    <p>&copy; <span id="year"></span> The Sunday Draft.</p>
    <div class="social-links">
      <a href="https://www.youtube.com/@TheSundayDraft" target="_blank" rel="noopener">YouTube</a>
      <a href="https://bsky.app/profile/thesundaydraft.bsky.social" target="_blank" rel="noopener">BlueSky</a>
      <a href="https://thesundaydraft.substack.com" target="_blank" rel="noopener">Substack</a>
    </div>
  </div>
</footer>

<script src="../script.js"></script>
</body>
</html>
"""

INDEX_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>All Episodes | The Sunday Draft</title>
<meta name="description" content="Every episode of The Sunday Draft, with full show notes: geopolitics, technology, parenting, culture, and the human cost of policy.">
<link rel="canonical" href="https://thesundaydraft.com/episodes/index.html">
<link rel="icon" href="../assets/favicon.png">
<link rel="apple-touch-icon" href="../assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../styles.css?v=11">
</head>
<body>

<header class="site-header">
  <div class="wrap header-inner">
    <a href="../index.html" class="logo"><img src="../assets/logo-wordmark.png" alt="The Sunday Draft" class="logo-img"></a>
    <nav class="nav">
      <a href="../index.html#episodes">Latest</a>
      <a href="index.html">Episodes</a>
      <a href="../index.html#listen">Listen</a>
      <a href="../index.html#about">About</a>
      <a href="../index.html#newsletter">Newsletter</a>
    </nav>
  </div>
</header>

<main>
  <section class="section episode-article">
    <div class="wrap wrap-narrow">
      <h1>All episodes</h1>
      <p class="section-sub" style="text-align:left; margin-left:0;">Full show notes for every conversation, in order.</p>
      <div class="episode-list">
{items}
      </div>
    </div>
  </section>
</main>

<footer class="site-footer">
  <div class="wrap footer-inner">
    <p>&copy; <span id="year"></span> The Sunday Draft.</p>
    <div class="social-links">
      <a href="https://www.youtube.com/@TheSundayDraft" target="_blank" rel="noopener">YouTube</a>
      <a href="https://bsky.app/profile/thesundaydraft.bsky.social" target="_blank" rel="noopener">BlueSky</a>
      <a href="https://thesundaydraft.substack.com" target="_blank" rel="noopener">Substack</a>
    </div>
  </div>
</footer>

<script src="../script.js"></script>
</body>
</html>
"""


def render_episode_page(ep):
    # Every episode page pairs the full Apple-sourced show notes (body_paragraphs)
    # with a single audio/video player. Spotify's compact, image-free player is
    # the default whenever a spotify_id exists; otherwise fall back to YouTube,
    # then a plain link to Substack or Apple Podcasts.

    def youtube_embed():
        return (
            "video-embed",
            f'<iframe src="https://www.youtube.com/embed/{ep["video_id"]}" '
            f'title="{ep["title"]}" frameborder="0" '
            f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
            f'allowfullscreen></iframe>',
            f'https://www.youtube.com/watch?v={ep["video_id"]}',
        )

    def spotify_embed():
        # height=80 is Spotify's compact "audio bar" embed: no cover art, just
        # the play button and scrubber.
        return (
            "podcast-embed podcast-embed-compact",
            f'<iframe src="https://open.spotify.com/embed/episode/{ep["spotify_id"]}?utm_source=generator" '
            f'width="100%" height="80" frameborder="0" '
            f'allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" '
            f'loading="lazy" title="{ep["title"]}"></iframe>',
            f'https://open.spotify.com/episode/{ep["spotify_id"]}',
        )

    def substack_embed():
        return (
            "substack-embed",
            f'<a class="btn btn-primary" href="{ep["substack_url"]}" target="_blank" rel="noopener">'
            f'Listen to this episode on Substack &rarr;</a>',
            ep["substack_url"],
        )

    def apple_embed():
        # Real Apple Podcasts embed player (embed.podcasts.apple.com), not just
        # a link-out. 175px is Apple's documented minimum height for the
        # single-episode player.
        parsed = urlparse(ep["apple_url"])
        i = parse_qs(parsed.query).get("i", [None])[0]
        query = f"i={i}" if i else ""
        src = f"https://embed.podcasts.apple.com{parsed.path}" + (f"?{query}" if query else "")
        return (
            "podcast-embed podcast-embed-apple",
            f'<iframe src="{src}" width="100%" height="175" frameborder="0" '
            f'sandbox="allow-forms allow-popups allow-same-origin allow-scripts allow-storage-access-by-user-activation allow-top-navigation-by-user-activation" '
            f'allow="autoplay *; encrypted-media *;" loading="lazy" title="{ep["title"]}"></iframe>',
            ep["apple_url"],
        )

    if ep.get("spotify_id"):
        embed_class, embed_html, media_url = spotify_embed()
    elif ep.get("video_id"):
        embed_class, embed_html, media_url = youtube_embed()
    elif ep.get("apple_url"):
        embed_class, embed_html, media_url = apple_embed()
    elif ep.get("substack_url"):
        embed_class, embed_html, media_url = substack_embed()
    else:
        embed_class = "podcast-embed"
        embed_html = ""
        media_url = "https://thesundaydraft.com"

    # Follow nudges for both platforms, always shown together under the embed
    # regardless of which player is actually embedded — plays via an embed
    # don't register as a follow on either platform, so this is the one-click
    # way for a listener to actually subscribe wherever they prefer.
    embed_html += (
        '<p class="embed-nudge">'
        f'<a href="{SPOTIFY_SHOW_URL}" target="_blank" rel="noopener">Follow on Spotify &rarr;</a>'
        ' &middot; '
        f'<a href="{APPLE_SHOW_URL}" target="_blank" rel="noopener">Follow on Apple Podcasts &rarr;</a>'
        '</p>'
    )

    eyebrow = ep["date_display"]
    if ep.get("duration"):
        eyebrow += f' &middot; {ep["duration"]}'

    if ep.get("content_html"):
        body_html = ep["content_html"]
    else:
        body_html = "\n".join(f"<p>{p}</p>" for p in ep.get("body_paragraphs", [ep["meta_desc"]]))

    return PAGE_TMPL.format(
        title=ep["title"],
        meta_desc=ep["meta_desc"],
        slug=ep["slug"],
        json_title=json.dumps(ep["title"]),
        json_desc=json.dumps(ep["meta_desc"]),
        iso_date=ep["iso_date"],
        media_url=media_url,
        eyebrow=eyebrow,
        embed_class=embed_class,
        embed_html=embed_html,
        body_html=body_html,
    )


def render_index(manifest):
    items = []
    for ep in manifest:
        items.append(
            f'\n    <a class="episode-list-item" href="{ep["slug"]}.html">\n'
            f'      <p class="eyebrow">{ep["date_display"]}'
            + (f' &middot; {ep["duration"]}' if ep.get("duration") else "")
            + f'</p>\n      <h3>{ep["title"]}</h3>\n      <p>{ep["meta_desc"]}</p>\n    </a>'
        )
    return INDEX_TMPL.format(items="".join(items))


def render_sitemap(manifest):
    urls = [("https://thesundaydraft.com/", "1.0"), ("https://thesundaydraft.com/episodes/index.html", "0.9")]
    for ep in manifest:
        urls.append((f'https://thesundaydraft.com/episodes/{ep["slug"]}.html', "0.8"))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, priority in urls:
        lines.append(f"  <url><loc>{loc}</loc><priority>{priority}</priority></url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def update_homepage(latest_ep):
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    blurb = " ".join(latest_ep.get("body_paragraphs", [latest_ep["meta_desc"]])[:1])
    if len(blurb) > 320:
        blurb = blurb[:317].rsplit(" ", 1)[0] + "…"

    html = re.sub(
        r'(<!-- LATEST-BLURB-START -->).*?(<!-- LATEST-BLURB-END -->)',
        lambda m: f'{m.group(1)}{blurb}{m.group(2)}',
        html,
        flags=re.S,
    )
    html = re.sub(
        r'(<!-- LATEST-LINK-START -->\s*<a )href="[^"]*"',
        lambda m: f'{m.group(1)}href="episodes/{latest_ep["slug"]}.html"',
        html,
    )

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    known_ids = {ep.get("video_id") for ep in manifest if ep.get("video_id")}
    known_slugs = {ep["slug"] for ep in manifest}

    try:
        xml_bytes = fetch_feed()
    except Exception as e:
        print(f"Could not fetch playlist feed: {e}", file=sys.stderr)
        sys.exit(0)  # don't fail the whole workflow over a transient network hiccup

    entries = parse_entries(xml_bytes)
    new_entries = [e for e in entries if e["video_id"] not in known_ids]
    # oldest-to-newest so the manifest stays chronological when appending
    new_entries.reverse()

    if not new_entries:
        print("No new episodes found. Nothing to do.")
        return

    added = []
    for e in new_entries:
        slug = slugify(e["title"])
        base_slug = slug
        n = 2
        while slug in known_slugs:
            slug = f"{base_slug}-{n}"
            n += 1
        known_slugs.add(slug)

        date_display, iso_date = format_date(e["published"])
        paragraphs = clean_description(e["description"]) or [e["title"]]
        meta_desc = paragraphs[0][:250]

        ep = {
            "slug": slug,
            "title": e["title"],
            "meta_desc": meta_desc,
            "date_display": date_display,
            "iso_date": iso_date,
            "duration": None,
            "source": "youtube",
            "spotify_id": None,
            "video_id": e["video_id"],
            "body_paragraphs": paragraphs,
        }
        manifest.append(ep)
        added.append(ep)

        page_html = render_episode_page(ep)
        with open(os.path.join(EPISODES_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
            f.write(page_html)
        print(f"Generated episodes/{slug}.html for: {e['title']}")

    # persist manifest without the transient body_paragraphs bloating it unnecessarily is fine to keep;
    # it's useful context for future runs/debugging, so we keep it.
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(EPISODES_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_index(list(reversed(manifest))))

    with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write(render_sitemap(list(reversed(manifest))))

    # newest overall episode (by iso_date) drives the homepage blurb
    newest = max(manifest, key=lambda ep: ep["iso_date"])
    update_homepage(newest)

    print(f"Added {len(added)} new episode(s).")


if __name__ == "__main__":
    main()
