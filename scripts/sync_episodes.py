#!/usr/bin/env python3
"""
Checks Apple Podcasts for episodes that don't have a show-notes page yet,
and generates one for each — plus regenerates the episode archive, the
homepage's "Latest episode" link/blurb, the homepage's "What we cover" topic
cards (from YouTube playlists), and sitemap.xml.

This site intentionally does not embed any video or YouTube content on
episode pages — those pages exist to mirror what actually went out on
Apple/Substack (audio show notes only). The homepage's "Latest episode"
video and the "What we cover" topic cards are the only two places YouTube
data is used, and both are purely homepage decoration, unrelated to the
episode pages/archive/sitemap built from Apple.

Runs stdlib-only (no pip install needed) so it's cheap and reliable inside
GitHub Actions. Safe to run repeatedly: does nothing new if there's nothing
new on either Apple or the YouTube playlists.

The "What we cover" topic cards require a YOUTUBE_API_KEY environment
variable (a YouTube Data API v3 key, used only to auto-discover the
channel's playlists — see fetch_channel_playlists()). If it's not set, that
section of the update is skipped for the run (everything else — Apple sync,
archive, sitemap — still runs normally).
"""
import html
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

# Apple's iTunes Lookup API is the sole source for episodes: full real show-
# notes text, not capped the way the raw Substack/Apple RSS feed is.
APPLE_PODCAST_ID = "1887351307"
APPLE_LOOKUP_URL = (
    f"https://itunes.apple.com/lookup?id={APPLE_PODCAST_ID}&entity=podcastEpisode&limit=200"
)

# "Full Episodes" playlist — drives the static video embed at the top of the
# homepage (that embed itself isn't touched by this script; it's just used
# here as the de-dupe reference for the topic cards below).
FULL_EPISODES_PLAYLIST_ID = "PLCxPsA1wKBkk"

# YouTube auto-generates this playlist from the podcast RSS feed (audio-only
# episodes) — it's not a hand-curated topic and shouldn't show up as one.
AUDIO_RSS_PLAYLIST_ID = "PLVmSsoYIlm7fbnYQh4ZGK8M-l3KNtk1iX"

# "What we cover" homepage section: one card per topic playlist on the
# channel, each showing the latest video from that playlist. The list of
# topic playlists is no longer hardcoded — it's discovered automatically
# from the channel via the YouTube Data API (see fetch_channel_playlists()),
# so a newly created playlist shows up on its own, no code change needed.
# The playlists below are excluded from the topic cards since they aren't
# "topics" (add other playlist IDs here too, e.g. Shorts/Livestreams, if the
# channel ever gets a playlist that shouldn't be treated as a topic).
EXCLUDED_TOPIC_PLAYLIST_IDS = {FULL_EPISODES_PLAYLIST_ID, AUDIO_RSS_PLAYLIST_ID}

# Handle used to resolve the channel ID via the Data API (channels.list
# ?forHandle=...). Matches the @handle already used in the site's YouTube
# links.
YOUTUBE_HANDLE = "TheSundayDraft"

YT_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}

# Show-level (not episode-level) follow links, used for the "Follow on X" nudge
# under embedded players — plays via the embed don't register as a follow on
# either platform, so this is a one-click way for listeners to actually
# subscribe on the platform they're already listening in.
SPOTIFY_SHOW_URL = "https://open.spotify.com/show/2EoiIdSHex4INCZVOmkU1F"
APPLE_SHOW_URL = "https://podcasts.apple.com/us/podcast/the-sunday-draft/id1887351307"

CTA_LINE_RE = re.compile(
    r"^(subscribe|follow|watch on|listen on|find us|referenced|timestamps?|"
    r"\d{1,2}:\d{2}|🎥|🎧|🎬|📖|🔗|▶️|📌|📣|⏱️|🎙️)",
    re.IGNORECASE,
)


def fetch_apple_episodes():
    """Full episode list (title + complete description text) straight from
    Apple's iTunes Lookup API. Returns only the podcastEpisode entries (the
    first result is the show itself, not an episode)."""
    req = urllib.request.Request(APPLE_LOOKUP_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [r for r in data.get("results", []) if r.get("wrapperType") == "podcastEpisode"]


def fetch_playlist_entries(playlist_id, limit=5):
    """Newest-first list of {video_id, title} for a YouTube playlist, via its
    public RSS feed (no API key needed — same mechanism used everywhere else
    in this script). Returns [] on any fetch/parse failure rather than
    raising, since a single broken topic playlist shouldn't take down the
    rest of the sync."""
    url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            root = ET.fromstring(resp.read())
    except Exception as e:
        print(f"Could not fetch playlist {playlist_id}: {e}", file=sys.stderr)
        return []

    entries = []
    for entry in root.findall("atom:entry", YT_NS):
        video_id = entry.findtext("yt:videoId", default="", namespaces=YT_NS)
        title = entry.findtext("atom:title", default="", namespaces=YT_NS)
        published = entry.findtext("atom:published", default="", namespaces=YT_NS)
        if video_id and title:
            entries.append({"video_id": video_id, "title": title.strip(), "published": published})
    entries.sort(key=lambda e: e["published"], reverse=True)
    return entries[:limit]


TOPIC_CARD_TMPL = """        <a class="topic-card" href="https://www.youtube.com/watch?v={video_id}" target="_blank" rel="noopener">
          <img class="topic-thumb" src="https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" alt="" loading="lazy">
          <span class="topic-label">{label}</span>
          <h3>{title}</h3>
        </a>"""


def fetch_channel_id(api_key):
    """Resolves the channel's numeric ID (UC...) from its @handle via the
    YouTube Data API. Needed because playlists.list requires a channelId,
    not a handle. Returns None on any failure."""
    url = (
        "https://www.googleapis.com/youtube/v3/channels"
        f"?part=id&forHandle={YOUTUBE_HANDLE}&key={api_key}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Could not resolve channel ID for @{YOUTUBE_HANDLE}: {e}", file=sys.stderr)
        return None
    items = data.get("items", [])
    if not items:
        print(f"No channel found for handle @{YOUTUBE_HANDLE}.", file=sys.stderr)
        return None
    return items[0]["id"]


def fetch_channel_playlists(api_key):
    """Every playlist on the channel (paginated), via the YouTube Data API,
    minus anything in EXCLUDED_TOPIC_PLAYLIST_IDS. This replaces the old
    hardcoded TOPIC_PLAYLISTS list — a new playlist created on the channel
    shows up here automatically, no code change needed. Sorted newest-
    created-first, so a freshly made playlist appears at the front of
    'What we cover'. Returns None on any failure (distinct from an empty
    list, which is a valid — if unusual — "no topic playlists" result)."""
    channel_id = fetch_channel_id(api_key)
    if not channel_id:
        return None

    playlists = []
    page_token = ""
    try:
        while True:
            url = (
                "https://www.googleapis.com/youtube/v3/playlists"
                f"?part=snippet&channelId={channel_id}&maxResults=50&key={api_key}"
                + (f"&pageToken={page_token}" if page_token else "")
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("items", []):
                pid = item.get("id")
                snippet = item.get("snippet", {})
                if not pid or pid in EXCLUDED_TOPIC_PLAYLIST_IDS:
                    continue
                playlists.append({
                    "id": pid,
                    "title": snippet.get("title", "").strip(),
                    "published": snippet.get("publishedAt", ""),
                })
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        print(f"Could not fetch channel playlists: {e}", file=sys.stderr)
        return None

    playlists.sort(key=lambda p: p["published"], reverse=True)
    return playlists


def build_topics_grid_html():
    """One card per playlist discovered on the channel (via the YouTube
    Data API), showing each playlist's newest video — unless that video is
    the same one currently featured as the homepage's 'Latest episode' (the
    newest video in FULL_EPISODES_PLAYLIST_ID), in which case that topic
    falls back to its second-newest video instead, so the homepage doesn't
    show the same video twice. If a topic playlist has only one video, it's
    shown regardless (duplicate allowed rather than an empty card).

    Returns None (not a partial result) if the API key is missing, the
    channel/playlist list can't be fetched, or ANY individual playlist
    (including the Full Episodes one used for de-dupe) fails to fetch. A
    half-built grid would be worse than leaving the homepage untouched: it
    would silently drop topics rather than fail loudly, and the missing
    cards wouldn't come back until the next successful run overwrote them."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("YOUTUBE_API_KEY not set — aborting topics-grid update.", file=sys.stderr)
        return None

    topic_playlists = fetch_channel_playlists(api_key)
    if topic_playlists is None:
        print("Could not fetch channel playlists — aborting topics-grid update.", file=sys.stderr)
        return None
    if not topic_playlists:
        print("No topic playlists found on channel — aborting topics-grid update.", file=sys.stderr)
        return None

    latest_entries = fetch_playlist_entries(FULL_EPISODES_PLAYLIST_ID, limit=1)
    if not latest_entries:
        print("Full Episodes playlist unreachable — aborting topics-grid update.", file=sys.stderr)
        return None
    latest_video_id = latest_entries[0]["video_id"]

    cards = []
    for pl in topic_playlists:
        entries = fetch_playlist_entries(pl["id"], limit=2)
        if not entries:
            print(f"Playlist '{pl['title']}' unreachable/empty — aborting topics-grid update.", file=sys.stderr)
            return None
        chosen = entries[0]
        if chosen["video_id"] == latest_video_id and len(entries) > 1:
            chosen = entries[1]
        cards.append(
            TOPIC_CARD_TMPL.format(
                video_id=chosen["video_id"],
                label=html.escape(pl["title"]),
                title=html.escape(chosen["title"]),
            )
        )
    return "\n".join(cards)


def update_topics_grid():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    grid_html = build_topics_grid_html()
    if grid_html is None:
        print("Leaving 'What we cover' unchanged this run.", file=sys.stderr)
        return

    new_html, n = re.subn(
        r'(<!-- TOPICS-GRID-START -->).*?(\s*<!-- TOPICS-GRID-END -->)',
        lambda m: f'{m.group(1)}\n{grid_html}{m.group(2)}',
        html,
        flags=re.S,
    )
    if n == 0:
        print("TOPICS-GRID markers not found in index.html — skipping.", file=sys.stderr)
        return

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)
    print("Updated 'What we cover' topic cards.")


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
        elif CTA_LINE_RE.match(line):
            # Cross-platform promo boilerplate ("🎧 Listen above, or find us on
            # Spotify and Apple Podcasts.", "🎬 Watch on YouTube.", etc.) is
            # redundant now that the page already has a real embed plus
            # explicit Spotify/Apple follow links underneath it — drop it
            # instead of duplicating it into the show notes body.
            continue
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


def normalize_title(title):
    """Loose-match key for 'is this episode already in the manifest' —
    lowercased, quotes/parens stripped, whitespace collapsed. Titles are the
    one thing that stay consistent between Apple and the manifest, unlike
    slugs (hand-trimmed) or dates (Apple's releaseDate vs. YouTube's publish
    date can differ by several days for the same episode)."""
    t = title.lower().strip()
    t = re.sub(r"[’'\"“”()]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


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
    # Every episode page pairs the full Apple-sourced show notes with a single
    # AUDIO player only — no video, no YouTube, by design. This site's episode
    # pages exist to mirror what went out on Apple/Substack; anyone who wants
    # video watches on YouTube itself. Spotify's compact, image-free player is
    # the default whenever a spotify_id exists; otherwise fall back to Apple's
    # embed player, then a plain link to Substack.

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


def first_paragraph_text(content_html):
    """Plain-text first <p>...</p> out of an episode's full show notes HTML,
    with any inner tags (like <strong>) stripped. Used for the homepage
    blurb so it shows the real, untruncated opening paragraph from Apple's
    full description — not the shortDescription field, which Apple itself
    caps at ~250 characters server-side with no ellipsis."""
    if not content_html:
        return None
    m = re.search(r"<p>(.*?)</p>", content_html, re.S)
    if not m:
        return None
    return re.sub(r"<[^>]+>", "", m.group(1)).strip()


def update_homepage(latest_ep):
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    blurb = (
        first_paragraph_text(latest_ep.get("content_html"))
        or " ".join(latest_ep.get("body_paragraphs", [latest_ep["meta_desc"]])[:1])
        or latest_ep["meta_desc"]
    )

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
    # Matching "already have this episode" on release date alone isn't
    # reliable either: Apple's actual releaseDate for an episode can be
    # several days off from the date we stored when it was first added via
    # the old YouTube-publish-date pipeline (confirmed — this created three
    # duplicate entries the first time this ran against the existing
    # manifest). Title is the one field that's consistently identical
    # between Apple and whatever's already in the manifest, so an episode is
    # only treated as new if BOTH its date and its normalized title are
    # unrecognized — matching on either one alone is enough to skip it.
    known_dates = {ep["iso_date"] for ep in manifest}
    known_titles = {normalize_title(ep["title"]) for ep in manifest}

    try:
        apple_episodes = fetch_apple_episodes()
    except Exception as e:
        print(f"Could not fetch Apple episode list: {e}", file=sys.stderr)
        sys.exit(0)  # don't fail the whole workflow over a transient network hiccup

    def apple_iso_date(ep_data):
        try:
            return datetime.fromisoformat(
                ep_data.get("releaseDate", "").replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")
        except ValueError:
            return None

    new_apple_episodes = [
        ep for ep in apple_episodes
        if apple_iso_date(ep) not in known_dates
        and normalize_title(ep["trackName"]) not in known_titles
    ]
    # oldest-to-newest so the manifest stays chronological when appending
    new_apple_episodes.sort(key=lambda ep: ep.get("releaseDate", ""))

    if not new_apple_episodes:
        print("No new episodes found on Apple.")
        added = []
    else:
        added = sync_new_episodes(manifest, known_slugs, new_apple_episodes)

    # The homepage "Latest episode" blurb/link is regenerated from whatever
    # the manifest's newest episode is on EVERY run, not just runs that add
    # a new one. It used to only be refreshed inside sync_new_episodes(),
    # which meant a logic change to how the blurb is built (e.g. pulling the
    # full first paragraph instead of the truncated meta_desc) wouldn't take
    # effect until the next brand-new episode synced — so an already-synced
    # "latest" episode kept showing whatever the old code wrote, even after
    # the fix shipped and a manual re-run was tried. Running this
    # unconditionally means the homepage always reflects the current script
    # logic against the current newest episode, and is a no-op (rewrites the
    # same content) when nothing's actually changed.
    if manifest:
        newest = max(manifest, key=lambda ep: ep["iso_date"])
        update_homepage(newest)

    # "What we cover" runs every time, independent of whether Apple had a new
    # episode — it depends on YouTube playlist activity, which has its own
    # cadence unrelated to when new episodes get published.
    update_topics_grid()

    print(f"Added {len(added)} new episode(s).")


def sync_new_episodes(manifest, known_slugs, new_apple_episodes):
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

        ep = {
            "slug": slug,
            "title": ep_data["trackName"],
            "meta_desc": meta_desc,
            "date_display": date_display,
            "iso_date": iso_date,
            "duration": format_duration(ep_data.get("trackTimeMillis")),
            "source": None,
            "spotify_id": None,
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

    # Homepage blurb/link is now refreshed unconditionally in main() after
    # this function returns, not here — see the comment there for why.

    return added


if __name__ == "__main__":
    main()
