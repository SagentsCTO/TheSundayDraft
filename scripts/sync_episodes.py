#!/usr/bin/env python3
"""
Checks for episodes that don't have a show-notes page yet, and generates
one for each — plus regenerates the episode archive, the homepage's
"Latest episode" link/blurb, the homepage's "What we cover" topic cards
(from YouTube playlists), and sitemap.xml. Also re-checks every
already-synced episode against its current show notes and refreshes its
page (and the homepage blurb, if it's the latest one) if the host has
edited it since the original sync.

Show-notes text, along with everything else (release date, duration, an
Apple Podcasts URL), comes primarily from Apple's iTunes Lookup API
(APPLE_LOOKUP_URL). An earlier version of this script also tried the
show's own Substack RSS feed, since Apple's API is a separate system from
the Apple Podcasts app itself and can lag a day or more behind an edit;
that was dropped because Substack blocks GitHub Actions' shared runner
IPs outright (confirmed: the exact same request succeeds instantly from
any other network), so the feed fetch just failed on every CI run.

For the single newest episode only, this script also checks Spotify's Web
API (fetch_spotify_latest_episode()) and prefers its text over Apple's
whenever Apple's own text hasn't changed since last sync — catching a
same-day correction Apple hasn't crawled yet, without paying the cost of
matching every historical episode against a second source. Spotify has no
public feed (the anonymous embed-token endpoint some scrapers use is
itself IP-blocked, same as Substack's was), so this needs a Spotify
Developer app's client ID/secret (SPOTIFY_CLIENT_ID/SPOTIFY_CLIENT_SECRET)
and is skipped entirely if they aren't set.

This site intentionally does not embed any video or YouTube content on
episode pages — those pages exist to mirror what actually went out on
Apple (audio show notes only). The homepage's "Latest episode" video and
the "What we cover" topic cards are the only two places YouTube data is
used, and both are purely homepage decoration, unrelated to the episode
pages/archive/sitemap built from Apple.

Runs stdlib-only (no pip install needed) so it's cheap and reliable inside
GitHub Actions. Safe to run repeatedly: does nothing new if there's nothing
new on either Apple or the YouTube playlists.

The "What we cover" topic cards require a YOUTUBE_API_KEY environment
variable (a YouTube Data API v3 key, used only to auto-discover the
channel's playlists — see fetch_channel_playlists()). If it's not set, that
section of the update is skipped for the run (everything else — Apple sync,
archive, sitemap — still runs normally).
"""
import base64
import hashlib
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

# Apple's iTunes Lookup API — the sole source for episode metadata (release
# date, duration, an Apple Podcasts URL for the embed) and show-notes text.
# It's a separate system from the Apple Podcasts app itself, crawled on its
# own schedule, and can lag a day or more behind an edit the host makes to
# an episode's show notes after publishing — confirmed by comparing it
# against the app, which reflected an edit this API still hadn't picked up.
#
# This script previously also fetched the show's own Substack RSS feed
# directly (both api.substack.com and the main-site feed) to beat that lag,
# since that's the actual canonical source Apple/Spotify subscribe to. That
# was dropped: Substack 403s both feed URLs from GitHub Actions' shared
# runner IPs specifically — confirmed by fetching the exact same request
# from a normal network, which succeeds instantly — so it just failed noisily
# on every scheduled/CI run instead of ever helping. If same-day freshness
# is worth fighting for again, `git log -p` on this file has the removed
# fetch_substack_descriptions()/fetch_rss_items() implementation to start from.
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

# How many of each playlist's top-viewed videos to offer as candidates for
# a topic card — see build_topics_grid_html(). The randomization itself
# happens client-side, in the visitor's browser (script.js), on every page
# load; this script only computes the pool. 3 keeps every candidate a
# proven performer while still giving each refresh some variety.
TOPIC_POOL_SIZE = 3

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

# Show ID pulled straight out of SPOTIFY_SHOW_URL above rather than
# duplicated, so the two constants can't drift apart.
SPOTIFY_SHOW_ID = SPOTIFY_SHOW_URL.rstrip("/").rsplit("/", 1)[-1]
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_EPISODES_URL = f"https://api.spotify.com/v1/shows/{SPOTIFY_SHOW_ID}/episodes"

# A bare "Mozilla/5.0" (no browser/OS/engine details) is a well-known bot
# signature — several real-world scrapers send exactly that string, so
# services that bot-filter on User-Agent can and do reject it outright. A
# complete, realistic desktop-browser string is the standard fix and costs
# nothing on services that don't check it at all, so it's used for every
# fetch in this script.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {"User-Agent": BROWSER_USER_AGENT}

CTA_LINE_RE = re.compile(
    r"^(subscribe|follow|watch on|listen on|find us|to hear more|referenced|timestamps?|"
    r"\d{1,2}:\d{2}|🎥|🎧|🎬|📖|🔗|▶️|📌|📣|⏱️|🎙️)",
    re.IGNORECASE,
)


def fetch_apple_episodes():
    """Full episode list (title + complete description text) straight from
    Apple's iTunes Lookup API. Returns only the podcastEpisode entries (the
    first result is the show itself, not an episode). The sole source for
    episode metadata (release date, duration, Apple URL) and show-notes
    text."""
    req = urllib.request.Request(APPLE_LOOKUP_URL, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [r for r in data.get("results", []) if r.get("wrapperType") == "podcastEpisode"]


def apple_iso_date(ep_data):
    try:
        return datetime.fromisoformat(
            ep_data.get("releaseDate", "").replace("Z", "+00:00")
        ).strftime("%Y-%m-%d")
    except ValueError:
        return None


def get_spotify_access_token():
    """Client Credentials OAuth token (https://accounts.spotify.com/api/token)
    — the grant meant for reading public catalog data with no user login,
    same shape as this script's other API-key-gated fetch (see
    YOUTUBE_API_KEY). Returns None, never raises, when SPOTIFY_CLIENT_ID/
    SPOTIFY_CLIENT_SECRET aren't set or the request fails, so callers can
    just skip the Spotify check entirely when it's not configured."""
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        SPOTIFY_TOKEN_URL,
        data=b"grant_type=client_credentials",
        headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("access_token")
    except Exception as e:
        print(f"Could not get Spotify access token: {e}", file=sys.stderr)
        return None


def fetch_spotify_latest_episode():
    """(title, raw_html_description, release_date_iso) for the show's most
    recently released episode on Spotify, via the official Web API — the
    only source for Spotify's own show-notes text, since Spotify has no
    public feed (see the module docstring). Returns None on any failure,
    including missing credentials (see get_spotify_access_token()), so this
    is purely additive: callers just skip the Spotify check and fall back
    to Apple-only behavior when it's unavailable."""
    token = get_spotify_access_token()
    if not token:
        return None
    url = f"{SPOTIFY_EPISODES_URL}?market=US&limit=5"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Could not fetch Spotify episodes: {e}", file=sys.stderr)
        return None
    items = [ep for ep in data.get("items", []) if ep.get("release_date")]
    if not items:
        return None
    latest = max(items, key=lambda ep: ep["release_date"])
    raw_html = latest.get("html_description") or latest.get("description") or ""
    return latest.get("name", ""), raw_html, latest["release_date"]


def html_description_to_plain_text(desc_html):
    """Converts real (if loosely-authored) HTML — <p> paragraphs, <a href>
    links, occasional <br>/<li> — into the plain newline-separated shape
    description_to_html()'s block-classifying heuristics (bullets,
    pseudo-headings, CTA lines, the footer strip) expect, same as Apple's
    own plain-text field already is. Used for Spotify's html_description
    field. Intentionally generic rather than a full HTML parser, since the
    actual markup is inconsistent across episodes."""
    text = desc_html or ""
    text = re.sub(r"(?is)</\s*(p|div|h[1-6])\s*>", "\n\n", text)
    text = re.sub(r"(?is)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?is)<\s*li[^>]*>", "* ", text)
    text = re.sub(r"(?is)</\s*li\s*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    text = html.unescape(text)
    # Rich-text editors often leave an "empty" paragraph as a zero-width
    # space or non-breaking space rather than nothing — without this it
    # survives stripping/splitting below and renders as a blank <p>.
    text = text.replace("​", "").replace("﻿", "").replace("\xa0", " ")
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(lines).strip()


def _text_hash(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _fetch_playlist_entries_rss(playlist_id, limit=5):
    """Newest-first list of {video_id, title} for a YouTube playlist, via its
    informal public RSS feed (no API key needed). Returns [] on any
    fetch/parse failure — including a 404, which YouTube returns for some
    playlists (e.g. older short-format playlist IDs) even though the
    playlist itself is public and works fine everywhere else on YouTube."""
    url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            root = ET.fromstring(resp.read())
    except Exception:
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


def _fetch_playlist_entries_api(playlist_id, api_key, limit=5, fetch_count=50):
    """Same shape of result as _fetch_playlist_entries_rss, via the official
    YouTube Data API's playlistItems.list instead of the informal RSS feed.
    Used as a fallback for playlists the RSS feed 404s on. Fetches up to
    fetch_count items (a single page — comfortably more than any of this
    channel's playlists currently hold) and sorts by each video's original
    publish date (contentDetails.videoPublishedAt), so results are correct
    regardless of the order items were added to the playlist. Returns [] on
    any failure."""
    url = (
        "https://www.googleapis.com/youtube/v3/playlistItems"
        f"?part=snippet,contentDetails&playlistId={playlist_id}&maxResults={fetch_count}&key={api_key}"
    )
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Could not fetch playlist {playlist_id} via YouTube Data API: {e}", file=sys.stderr)
        return []

    entries = []
    for item in data.get("items", []):
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        video_id = content_details.get("videoId") or snippet.get("resourceId", {}).get("videoId", "")
        title = (snippet.get("title") or "").strip()
        published = content_details.get("videoPublishedAt") or snippet.get("publishedAt", "")
        # Skip items for videos that were deleted or made private after
        # being added to the playlist — YouTube reports these with a
        # placeholder title instead of omitting them.
        if not video_id or not title or title in ("Deleted video", "Private video"):
            continue
        entries.append({"video_id": video_id, "title": title, "published": published})
    entries.sort(key=lambda e: e["published"], reverse=True)
    return entries[:limit]


def fetch_playlist_entries(playlist_id, limit=5):
    """Newest-first list of {video_id, title} for a YouTube playlist. Tries
    the informal public RSS feed first (fast, no API key needed, and what
    every playlist on this channel used successfully until one didn't).
    Falls back to the official YouTube Data API (playlistItems.list, needs
    YOUTUBE_API_KEY) when the RSS feed comes back empty — this is what
    actually happens for this channel's "Full Episodes" playlist, whose
    older short-format ID the RSS endpoint 404s on even though the playlist
    is public and works everywhere else on YouTube. Returns [] only if
    both sources fail (or the fallback isn't available)."""
    entries = _fetch_playlist_entries_rss(playlist_id, limit)
    if entries:
        return entries

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print(
            f"Could not fetch playlist {playlist_id} via RSS, and no "
            "YOUTUBE_API_KEY set for the Data API fallback.",
            file=sys.stderr,
        )
        return []

    entries = _fetch_playlist_entries_api(playlist_id, api_key, limit)
    if not entries:
        print(f"Could not fetch playlist {playlist_id} via RSS or the Data API fallback.", file=sys.stderr)
    return entries


def fetch_playlist_video_ids_api(playlist_id, api_key, cap=200):
    """Every {video_id, title} in a playlist (paginated through
    playlistItems.list), up to `cap` items total. Unlike
    _fetch_playlist_entries_api, this doesn't stop at the newest few — it's
    used when every video in the playlist needs to be considered, not just
    the most recent ones (see fetch_playlist_entries_by_views()). `cap`
    bounds quota/runtime on an unexpectedly huge playlist; none of this
    channel's topic playlists are anywhere near it. Skips deleted/private
    placeholder entries. Returns [] on any failure."""
    entries = []
    page_token = ""
    try:
        while len(entries) < cap:
            url = (
                "https://www.googleapis.com/youtube/v3/playlistItems"
                f"?part=snippet,contentDetails&playlistId={playlist_id}&maxResults=50&key={api_key}"
                + (f"&pageToken={page_token}" if page_token else "")
            )
            req = urllib.request.Request(url, headers=BROWSER_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                video_id = content_details.get("videoId") or snippet.get("resourceId", {}).get("videoId", "")
                title = (snippet.get("title") or "").strip()
                if not video_id or not title or title in ("Deleted video", "Private video"):
                    continue
                entries.append({"video_id": video_id, "title": title})
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        print(f"Could not list videos in playlist {playlist_id}: {e}", file=sys.stderr)
        return []
    return entries[:cap]


def fetch_video_view_counts(video_ids, api_key):
    """{video_id: view_count} for a list of video IDs, via videos.list
    (batched 50 at a time — the API's max per call). A batch that fails is
    simply missing from the result rather than raising, since one bad
    batch shouldn't take down the whole ranking; a video with no view-count
    data just won't be able to win the "most viewed" comparison."""
    counts = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=statistics&id={','.join(batch)}&key={api_key}"
        )
        try:
            req = urllib.request.Request(url, headers=BROWSER_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"Could not fetch view counts for a batch of videos: {e}", file=sys.stderr)
            continue
        for item in data.get("items", []):
            vid = item.get("id")
            try:
                counts[vid] = int(item.get("statistics", {}).get("viewCount", 0))
            except (TypeError, ValueError):
                counts[vid] = 0
    return counts


def fetch_playlist_entries_by_views(playlist_id, api_key, limit=5):
    """Most-viewed-first list of {video_id, title, views} across every
    video in a playlist — used to build each topic's rotation pool of
    proven, popular videos on the homepage instead of just its newest (see
    build_topics_grid_html()). Returns [] if the playlist can't be listed
    at all."""
    entries = fetch_playlist_video_ids_api(playlist_id, api_key)
    if not entries:
        return []
    views = fetch_video_view_counts([e["video_id"] for e in entries], api_key)
    for e in entries:
        e["views"] = views.get(e["video_id"], 0)
    entries.sort(key=lambda e: e["views"], reverse=True)
    return entries[:limit]


# `data-pool` carries the topic's full candidate list (top-viewed videos,
# already de-duped against the homepage's featured "Latest episode") as
# JSON, so script.js can pick a different one at random on every page
# load. The href/img/h3 above are the static fallback — what's shown to
# search engines and any visitor without JavaScript — and are always the
# single most-viewed candidate, i.e. pool[0].
TOPIC_CARD_TMPL = """        <a class="topic-card" href="https://www.youtube.com/watch?v={video_id}" target="_blank" rel="noopener" data-pool="{pool_json}">
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
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
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
            req = urllib.request.Request(url, headers=BROWSER_HEADERS)
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
    Data API). Each card's static content (used for search engines and any
    visitor without JavaScript) is that playlist's single most-viewed
    video. Alongside it, the card carries a `data-pool` JSON attribute
    listing its top TOPIC_POOL_SIZE most-viewed videos — script.js reads
    that on every page load and swaps in a random one of them, so a real
    visitor sees a different (but still proven, popular) video each time
    they refresh, without this script or the homepage HTML needing to
    change between YouTube-data syncs. The homepage's 'Latest episode'
    video (the newest video in FULL_EPISODES_PLAYLIST_ID) is excluded from
    the pool when possible, so the homepage doesn't show the same video
    twice; if that's the only video available for a topic, it's shown
    anyway (duplicate allowed rather than an empty card).

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
        entries = fetch_playlist_entries_by_views(pl["id"], api_key, limit=TOPIC_POOL_SIZE)
        if not entries:
            print(f"Playlist '{pl['title']}' unreachable/empty — aborting topics-grid update.", file=sys.stderr)
            return None
        pool = [e for e in entries if e["video_id"] != latest_video_id]
        if not pool:
            pool = entries
        chosen = pool[0]  # most-viewed of the pool — the static/no-JS fallback
        pool_json = html.escape(
            json.dumps([{"id": e["video_id"], "title": e["title"]} for e in pool]),
            quote=True,
        )
        cards.append(
            TOPIC_CARD_TMPL.format(
                video_id=chosen["video_id"],
                label=html.escape(pl["title"]),
                title=html.escape(chosen["title"]),
                pool_json=pool_json,
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


def description_to_html(raw_description):
    """Converts a plain-text episode description (Apple's raw text, or
    Spotify's HTML already run through html_description_to_plain_text())
    into the same paragraph/list/heading HTML structure used across the
    rest of the site, instead of dumping it in as one unbroken blob."""
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


def refresh_existing_episodes(manifest, apple_episodes):
    """Already-synced episodes otherwise never get looked at again: an
    episode is matched as "new" (see main()) by title+date, so once it's in
    the manifest, its content_html is frozen at whatever text was captured
    at sync time. If the host edits an episode's show notes after it's
    already live on the site — fixing a typo, adding a link, expanding a
    paragraph — that edit was silently dropped forever, including from the
    homepage's "Latest episode" blurb, which is pulled from this same
    content_html. This re-matches every manifest entry to its current Apple
    text by normalized title first, then by iso_date if the title itself
    was also edited since the original sync — confirmed happening in
    practice (the F-16 squadron episode's Apple title changed from "27
    Years in an F-16 Squadron" to "serving with an elite F-16 Squadron"
    sometime after it synced), and title-only matching would silently drop
    that episode from every future refresh, Spotify check included, since
    it'd never match Apple's list again. Rewrites content_html/meta_desc
    whenever the matched episode's text has actually changed since.

    For whichever entry is currently the newest episode only, this also
    checks Spotify (see fetch_spotify_latest_episode()) and prefers its text
    over Apple's when Apple's hasn't changed — Apple can lag a real edit by
    a day or more, and Spotify sometimes has already picked it up. This
    can't just compare "does Spotify's rendered text differ from what's
    stored," though: Spotify's html_description and Apple's description are
    differently formatted even when nothing was edited, so that would flip
    the episode back and forth between the two sources' phrasing on every
    single run, forever, with a spurious commit each time. Instead each
    source's *raw* text is hashed and stored (apple_desc_hash/
    spotify_desc_hash on the episode dict), and a source only "wins" when
    its own hash has changed since it was last recorded — not merely
    because it disagrees with the other source's wording.

    Returns (updated, hashes_dirty): updated is the list of episode dicts
    whose visible content_html actually changed (each already mutated
    in-place in `manifest`); hashes_dirty is True if apple_desc_hash/
    spotify_desc_hash moved on any episode even when content_html didn't —
    which happens on every episode's very first run under this hashing
    scheme (no baseline recorded yet) and whenever a source's text changes
    to something that happens to render identically. The caller must persist
    the manifest whenever hashes_dirty is True, not just when updated is
    non-empty — otherwise the freshly-computed hashes are only ever held in
    memory for this one run and never actually establish a baseline,
    silently defeating the whole point of tracking them."""
    apple_by_title = {
        normalize_title(ep_data.get("trackName", "")): ep_data
        for ep_data in apple_episodes
    }
    apple_by_date = {}
    for ep_data in apple_episodes:
        d = apple_iso_date(ep_data)
        if d:
            apple_by_date[d] = ep_data

    latest_ep = max(manifest, key=lambda ep: ep["iso_date"]) if manifest else None
    spotify_latest = fetch_spotify_latest_episode() if latest_ep is not None else None

    updated = []
    hashes_dirty = False
    for ep in manifest:
        key = normalize_title(ep["title"])
        apple_ep = apple_by_title.get(key) or apple_by_date.get(ep.get("iso_date"))
        if not apple_ep:
            continue
        raw_text = apple_ep.get("description", "")
        apple_hash = _text_hash(raw_text)
        apple_changed = apple_hash != ep.get("apple_desc_hash")

        spotify_changed = False
        spotify_raw_html = None
        sp_hash = None
        if ep is latest_ep and spotify_latest is not None:
            _sp_title, sp_raw_html, sp_date = spotify_latest
            # Matched by release date, not title: the title check used here
            # originally broke on exactly the same title-drift problem the
            # Apple match above works around (ep["title"] is never rewritten
            # when a host edit changes it, so a stale stored title would
            # permanently fail to match Spotify's current one).
            if sp_date == ep.get("iso_date"):
                sp_hash = _text_hash(sp_raw_html)
                spotify_changed = sp_hash != ep.get("spotify_desc_hash")
                spotify_raw_html = sp_raw_html

        # Always record both sources' current hashes, whether or not either
        # one ends up winning below — otherwise a source that didn't win
        # this time would look "changed" again next run purely from a stale
        # baseline, not an actual edit.
        if apple_changed:
            ep["apple_desc_hash"] = apple_hash
            hashes_dirty = True
        if sp_hash is not None and sp_hash != ep.get("spotify_desc_hash"):
            ep["spotify_desc_hash"] = sp_hash
            hashes_dirty = True

        if apple_changed:
            new_content_html = description_to_html(raw_text)
        elif spotify_changed:
            new_content_html = description_to_html(html_description_to_plain_text(spotify_raw_html))
        else:
            continue

        if not new_content_html or new_content_html == ep.get("content_html"):
            continue
        ep["content_html"] = new_content_html
        ep["meta_desc"] = (apple_ep.get("shortDescription") or apple_ep.get("description") or ep["title"])[:250]
        ep.pop("body_paragraphs", None)
        updated.append(ep)
    return updated, hashes_dirty


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

    # A failure here is NOT allowed to abort the whole run (no sys.exit) —
    # Apple's iTunes Lookup API is known to fail intermittently from
    # GitHub-hosted runners specifically (their shared IP ranges get
    # rate-limited by third-party APIs) and a transient hiccup shouldn't
    # crash the whole sync. Both new-episode detection and the show-notes
    # refresh below need this list, so an empty result here just means
    # nothing to do this run (both naturally no-op on []) rather than a
    # partial/crashed run.
    try:
        apple_episodes = fetch_apple_episodes()
    except Exception as e:
        print(f"Could not fetch Apple episode list: {e}", file=sys.stderr)
        apple_episodes = []

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

    # Pick up edits the host made to already-published show notes (see
    # refresh_existing_episodes() docstring). This runs against the full
    # episode lists, independent of whether anything new was added — an
    # edit to an old episode's notes has nothing to do with whether this
    # week also happened to publish a new one. sync_new_episodes() already
    # wrote out the manifest/index/sitemap when it ran, but not the
    # per-episode page for an already-existing episode, and it doesn't run
    # at all when there's no new episode — so both are handled here.
    updated_existing, hashes_dirty = refresh_existing_episodes(manifest, apple_episodes)
    for ep in updated_existing:
        page_html = render_episode_page(ep)
        with open(os.path.join(EPISODES_DIR, f"{ep['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(page_html)
        print(f"Refreshed episodes/{ep['slug']}.html — show notes changed since last sync.")
    # Written whenever hashes_dirty too, not just on a visible content
    # change — see refresh_existing_episodes()'s docstring on why skipping
    # that write would silently break its Apple/Spotify change tracking.
    if updated_existing or hashes_dirty:
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")
    if updated_existing:
        with open(os.path.join(EPISODES_DIR, "index.html"), "w", encoding="utf-8") as f:
            f.write(render_index(list(reversed(manifest))))

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

    print(f"Added {len(added)} new episode(s). Refreshed {len(updated_existing)} existing episode(s) with changed show notes.")


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
        raw_text = ep_data.get("description", "")

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
            "content_html": description_to_html(raw_text),
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
