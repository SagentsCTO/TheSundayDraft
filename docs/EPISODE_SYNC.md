# Episode sync & homepage automation

What `scripts/sync_episodes.py` does, how it's triggered, and — most
importantly — the incident that shaped how its homepage-facing features
must be built from now on.

## What it does

On every run:

1. Checks for episodes without a show-notes page yet and generates one
   (`episodes/{slug}.html`) — plus regenerates `episodes/index.html` and
   `sitemap.xml`.
2. Re-checks every already-synced episode against its current show notes
   and refreshes its page (and the homepage blurb, if it's the latest one)
   if the host has edited it since the original sync.
3. Updates the homepage's **"Latest episode"** blurb/link and **"What we
   cover"** topic cards.

It's stdlib-only Python (no `pip install`), safe to run repeatedly, and
does nothing if there's nothing new on either Apple or the YouTube
playlists.

## Where show-notes text comes from

**Apple's iTunes Lookup API is the primary and normally sole source** for
show-notes text, release date, duration, and the Apple Podcasts URL for
every episode. An earlier version also tried the show's Substack RSS feed,
but that was dropped: Substack blocks GitHub Actions' shared runner IP
range outright (confirmed — the identical request succeeds instantly from
any other network), so it just failed on every CI run.

**For the single newest episode only**, the script also checks Spotify's
Web API and prefers Spotify's text over Apple's whenever Apple's own text
hasn't changed since the last sync — this catches a same-day correction
Apple hasn't crawled yet, without paying the cost of matching every
historical episode against a second source. This needs
`SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` and is skipped entirely if
they're not set.

**This site intentionally embeds no video/YouTube content on episode
pages** — those pages mirror what actually went out on Apple (audio show
notes only). YouTube data is used in exactly two places, both purely
homepage decoration, unrelated to the episode archive: the homepage's
"Latest episode" video embed, and the "What we cover" topic cards below.

## The marker system (why manual homepage edits are safe)

This script never rewrites all of `index.html` — it only replaces the text
between specific HTML comment markers, via regex substitution:

- `<!-- LATEST-BLURB-START --> ... <!-- LATEST-BLURB-END -->`
- `<!-- LATEST-LINK-START -->` (rewrites the `href` of the following `<a>`)
- `<!-- TOPICS-GRID-START --> ... <!-- TOPICS-GRID-END -->`

Anything else in `index.html` — nav, hero copy, section subtitles, etc. —
is only ever touched by a human (or Claude) editing it directly, and is
never at risk from a script run. When editing homepage copy, it's fine to
edit directly; just don't edit *inside* those marker blocks by hand if you
want the script's next run to still make sense of them.

## How it's triggered — read this before changing anything homepage-facing

`.github/workflows/sync-episodes.yml` runs this script:

- **Weekly**, Monday 14:00 UTC (the day after new Sunday episodes drop)
- **On every GitHub Pages `page_build` event** — which fires automatically
  after *any* push to `main`, **including this workflow's own auto-commit**
- Manually, via `workflow_dispatch`

After running, the workflow does `git add -A` and commits/pushes
**anything that changed**, as `"Auto-add new episode show notes"`.

## ⚠️ The auto-commit-loop incident (2026-09-24) — do not repeat this

An earlier version of the "What we cover" feature picked a random one of
each playlist's top-3 most-viewed videos **inside this Python script**,
freshly on every run, to give the homepage some rotation instead of always
showing the single most-viewed video.

This broke the self-limiting assumption the workflow depends on: normally,
if nothing new needs syncing, the script produces byte-identical output,
so there's nothing to commit, so a `page_build` triggered by "nothing
happened" is a no-op. A *fresh random pick every run* breaks that — every
run looked like a real change, got auto-committed, which triggered another
`page_build`, which ran the script again, which randomized again... an
unbounded loop.

**This actually happened in production.** Confirmed by comparing two
consecutive auto-commits four minutes apart: several topic cards had
changed to different videos from the same pool, with no new episode
involved — direct evidence of the loop actively running.

**The fix**, now in place: all randomness moved **client-side**, into
`script.js`. `sync_episodes.py`'s `build_topics_grid_html()` only computes
a fully deterministic pool of each playlist's top `TOPIC_POOL_SIZE`
(currently 3) most-viewed videos, and embeds that pool as a `data-pool`
JSON attribute on each topic card (with the single most-viewed video
rendered as the static `href`/`img`/`h3` — the fallback for search engines
and any visitor without JavaScript). `script.js`'s `pickRandomTopicVideo()`
then picks one of the pool at random **on every page load**, in the
visitor's own browser — so refreshing the page shows a different video,
with zero randomness on the server side and nothing for the auto-commit
workflow to loop on.

**The rule going forward**: nothing this script writes to `index.html` may
differ between two runs unless the underlying real data (view counts, new
episodes, etc.) actually changed. If a future feature wants variety on
every page load/visit, implement it in `script.js`, not here.

## YouTube topics grid — current mechanics

- Topic playlists are auto-discovered from the channel via the YouTube
  Data API (`fetch_channel_playlists()`) — excludes
  `FULL_EPISODES_PLAYLIST_ID` and `AUDIO_RSS_PLAYLIST_ID`
  (`EXCLUDED_TOPIC_PLAYLIST_IDS`). A new playlist on the channel shows up
  automatically, no code change needed.
- `fetch_playlist_entries_by_views()` paginates the entire playlist,
  batches view-count lookups (`videos.list`, 50 IDs per call — the API
  max), and returns the top `limit` most-viewed videos, most-viewed first.
- The homepage's featured "Latest episode" video is excluded from each
  topic's pool when possible (so the homepage doesn't show the same video
  twice); if that's a playlist's only video, it's shown anyway — a
  duplicate is better than an empty card.
- Requires `YOUTUBE_API_KEY`. If it's not set, the topics-grid update is
  skipped for that run (everything else still runs normally).
- `build_topics_grid_html()` returns `None` (never a partial grid) if the
  API key is missing, the channel/playlist list can't be fetched, or *any*
  individual playlist fails — a half-built grid would silently drop topics
  rather than fail loudly, and wouldn't come back until the next
  successful run overwrote it.

## Testing this script

No network or real API key needed for logic tests — monkey-patch the
network-calling functions on the imported module before calling the
function under test, e.g.:

```python
import importlib.util
spec = importlib.util.spec_from_file_location("sync_episodes", "scripts/sync_episodes.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

mod.fetch_channel_playlists = lambda api_key: [{"id": "PL_A", "title": "Topic A"}]
mod.fetch_playlist_entries_by_views = lambda playlist_id, api_key, limit=5: [...]
mod.os.environ["YOUTUBE_API_KEY"] = "fake-key-for-test"

result = mod.build_topics_grid_html()
```

Things worth asserting whenever this area changes:

- Output is **byte-identical across repeated calls** with the same input
  data (the property the whole loop incident hinged on)
- The static fallback (`href`/`img`/`h3`) is the single most-viewed video
- `data-pool` is valid JSON and safely escaped for an HTML attribute (test
  with a title containing quotes/ampersands/apostrophes)
- The latest-episode exclusion and single-video fallback both work
- An unreachable playlist aborts the whole grid (`None`), not a partial one

## Running it manually

```bash
YOUTUBE_API_KEY=... SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=... \
  python3 scripts/sync_episodes.py
```

Or from GitHub: Actions tab → "Sync new episodes" → Run workflow.
