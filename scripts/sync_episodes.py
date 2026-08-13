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

# Apple's iTunes Lookup API is the primary source for new episodes now: it
# carries the full, real show-notes text (unlike YouTube's RSS, which has no
# usable description field), and isn't capped the way the raw Substack/Apple
# RSS feed is. The YouTube "Full Episodes" playlist is only consulted
# afterward, to find a matching video_id for the embed.
APPLE_PODCAST_ID = "1887351307"
APPLE_LOOKUP_URL = (
    f"https://itunes.apple.com/lookup?id={APPLE_PODCAST_ID}&entity=podcastEpisode&limit=200"
)

# Videos that exist on the "Full Episodes" YouTube playlist but are
# deliberately kept off the site: they were never real Apple/Substack
# episodes (livestream clips with no real show notes), so switching the
# primary source to Apple already keeps them from being auto-added. This is
# just a belt-and-suspenders backstop in case that ever changes.
EXCLUDED_VIDEO_IDS = {
    "3I80QjKo7ic",  # Surviving the HARDEST Days to Everest Base Camp (EBC Part 2)
    "YJxedOV_-MU",  # The Collapse of Diplomacy - Is It Dead?
}

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


def fetch_apple_episodes():
    """Full episode list (title + complete description text) straight from
    Apple's iTunes Lookup API. Returns only the podcastEpisode entries (the
    first result is the show itself, not an episode)."""
    req = urllib.request.Request(APPLE_LOOKUP_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [r for r in data.get("results", []) if r.get("wrapperType") == "podcastEpisode"]


TIMESTAMP_LINE_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?\s*[–—-]")
SUBSTACK_FOOTER_RE = re.compile(
    r"\s*This is a public episode\. If you would like to discuss this with other subscribers.*$",
    re.IGNORECASE | re.DOTALL,
)


def apple_description_to_html(raw_description):
    """Converts Apple's raw episode description text into the same
    paragraph/list/heading HTML structure used across the rest of the site,
    instead of dumping it in as one unbroken blob."""
    text = SUBSTACK_FOOTER_RE.sub("", raw_description or "").strip()
    lines = [l.strip() for l in text.split("\n")]

    blocks = []
    for line in lines:
        if not line:
            continue
        if line.startswith("* "):
            blocks.append(("li", line[2:].strip()))
        elif TIMESTAMP_LINE_RE.match(line):
            blocks.append(("li", line))
        elif (line.isupper() and 3 < len(line) < 70) or (
            line.endswith(":") and len(line) < 70 and not line[:1].islower()
        ):
            blocks.append(("h", line))
        else:
            blocks.append(("p", line))

    html_parts = []
    cur_list = []

    def flush_list():
        nonlocal cur_list
        if cur_list:
            html_parts.append("<ul>" + "".join(f"<li>{x}</li>" for x in cur_list) + "</ul>")
            cur_list = []

    for kind, txt in blocks:
        if kind == "li":
            cur_list.append(txt)
        else:
            flush_list()
            html_parts.append(f"<p><strong>{txt}</strong></p>" if kind == "h" else f"<p>{txt}</p>")
    flush_list()
    return "\n".join(html_parts)


def format_duration(track_time_millis):
    if not track_time_millis:
        return None
    total_min = round(track_time_millis / 60000)
    hours, minutes = divmod(total_min, 60)
    if hours:
        return f"{hours} hr {minutes} min" if minutes else f"{hours} hr"
    return f"{minutes} min"


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
    known_slugs = {ep["slug"] for ep in manifest}
    # Matching "already have this episode" by slugified title is unreliable:
    # several existing entries were hand-trimmed to shorter slugs than what
    # slugify(Apple's raw trackName) produces (subtitles, emoji prefixes,
    # quote marks, etc. all differ). Release date is a far more reliable key
    # for a weekly show — two real episodes essentially never share a date.
    known_dates = {ep["iso_date"] for ep in manifest}

    try:
        apple_episodes = fetch_apple_episodes()
    except Exception as e:
        print(f"Could not fetch Apple episode list: {e}", file=sys.stderr)
        sys.exit(0)  # don't fail the whole workflow over a transient network hiccup

    # YouTube is now only consulted to find a video_id to embed alongside the
    # Apple-sourced text — matched by release date, since titles often differ
    # slightly between platforms (confirmed while building this site).
    try:
        yt_entries = parse_entries(fetch_feed())
    except Exception as e:
        print(f"Could not fetch YouTube playlist feed (non-fatal): {e}", file=sys.stderr)
        yt_entries = []

    def find_youtube_match(apple_release_date):
        try:
            apple_day = datetime.fromisoformat(apple_release_date.replace("Z", "+00:00")).date()
        except ValueError:
            return None
        best = None
        best_diff = None
        for e in yt_entries:
            if e["video_id"] in EXCLUDED_VIDEO_IDS:
                continue
            try:
                yt_day = datetime.fromisoformat(e["published"].replace("Z", "+00:00")).date()
            except ValueError:
                continue
            diff = abs((yt_day - apple_day).days)
            if diff <= 1 and (best_diff is None or diff < best_diff):
                best, best_diff = e, diff
        return best["video_id"] if best else None

    def apple_iso_date(ep_data):
        try:
            return datetime.fromisoformat(
                ep_data.get("releaseDate", "").replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")
        except ValueError:
            return None

    new_apple_episodes = [
        ep for ep in apple_episodes if apple_iso_date(ep) not in known_dates
    ]
    # oldest-to-newest so the manifest stays chronological when appending
    new_apple_episodes.sort(key=lambda ep: ep.get("releaseDate", ""))

    if not new_apple_episodes:
        print("No new episodes found. Nothing to do.")
        return

    added = []
    for ep_data in new_apple_episodes:
        slug = slugify(ep_data["trackName"])
        base_slug = slug
        n = 2
        while slug in known_slugs:
            slug = f"{base_slug}-{n}"
            n += 1
        known_slugs.add(slug)

        date_display, iso_date = format_date(ep_data.get("releaseDate", ""))
        meta_desc = (ep_data.get("shortDescription") or ep_data.get("description") or ep_data["trackName"])[:250]
        video_id = find_youtube_match(ep_data.get("releaseDate", ""))

        ep = {
            "slug": slug,
            "title": ep_data["trackName"],
            "meta_desc": meta_desc,
            "date_display": date_display,
            "iso_date": iso_date,
            "duration": format_duration(ep_data.get("trackTimeMillis")),
            "source": None,
            "spotify_id": None,
            "video_id": video_id,
            "apple_url": ep_data.get("trackViewUrl"),
            "content_html": apple_description_to_html(ep_data.get("description", "")),
        }
        manifest.append(ep)
        added.append(ep)

        page_html = render_episode_page(ep)
        with open(os.path.join(EPISODES_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
            f.write(page_html)
        print(f"Generated episodes/{slug}.html for: {ep_data['trackName']}")

    # Always keep the manifest sorted oldest-to-newest by date, rather than
    # relying on append order — otherwise newly-added (possibly older,
    # backfilled) episodes land at the wrong spot in the archive/sitemap.
    manifest.sort(key=lambda ep: ep["iso_date"])

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
