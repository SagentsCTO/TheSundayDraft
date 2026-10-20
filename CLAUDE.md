# CLAUDE.md — context for any Claude session working on this repo

This file is read automatically by Claude Code at the start of a session in
this repo. It exists so a fresh session (or a fresh Claude Code instance)
doesn't have to rediscover things that were already learned the hard way.
Keep it updated when something here goes stale — an outdated rule here is
worse than no rule.

## What this is

**TheSundayDraft.com** — a static website for The Sunday Draft podcast.
Hosted free on GitHub Pages ("Deploy from branch") from
[github.com/SagentsCTO/TheSundayDraft](https://github.com/SagentsCTO/TheSundayDraft),
custom domain via the `CNAME` file + DNS. No build step, no framework —
plain HTML/CSS/JS plus two automated subsystems (episode sync, a booking
page) described below.

Anything pushed to `main` goes live within ~1–2 minutes automatically.
There is no separate "deploy" step for the site itself — **except** the
Cal.com booking proxy, which is a separately-deployed Cloudflare Worker
(see docs/BOOKING_SYSTEM.md).

## The one rule that overrides everything else here

**Never run `git add` / `git commit` / `git push` on the user's local
machine on his behalf.** He has said this explicitly and repeatedly. If
you're working through a device bridge or similar, write/edit files there,
then hand him the exact git commands to run himself, with a comment
explaining each one. This applies no matter how convenient it would be to
just do it — don't.

Also never call `wrangler deploy` on his behalf (see docs/BOOKING_SYSTEM.md)
for the same reason — it's his Cloudflare session. Give him the command.

## Map of the repo

| Path | What it is |
|---|---|
| `index.html`, `styles.css`, `script.js` | The homepage. Mostly hand-edited, except two marker-delimited sections auto-rewritten by the sync script (see docs/EPISODE_SYNC.md) |
| `episodes/` | Auto-generated show-notes pages + `episodes/index.html`, one per episode |
| `scripts/sync_episodes.py` | The automation that keeps episodes/homepage current — see **docs/EPISODE_SYNC.md** |
| `.github/workflows/sync-episodes.yml` | Runs the sync script on a schedule + on every Pages build + manually |
| `book.html` | Custom "book a conversation" page — see **docs/BOOKING_SYSTEM.md** |
| `cal-worker/` | Cloudflare Worker that proxies Cal.com's API (holds the real API key) — see **docs/BOOKING_SYSTEM.md** and `cal-worker/README.md` |
| `sitemap.xml`, `robots.txt`, `CNAME` | Standard static-site plumbing, auto/rarely touched |
| Root-level `*.py` other than `scripts/sync_episodes.py` (`add_apple_episodes.py`, `apple_full_notes.py`, `backfill.py`, `cleanup.py`, `gen_episodes.py`, `update_from_youtube.py`) | One-off/legacy scripts from earlier iterations of the sync approach. Not part of the live automation — don't assume they still run or are current before touching them. |

## Before you push anything

`scripts/sync_episodes.py` runs automatically and pushes its own commits
(`"Auto-add new episode show notes"`) via GitHub Actions — meaning
`origin/main` can move forward at any time, independent of whatever you're
working on. Before pushing (or telling the user to push):

1. `git fetch origin main`
2. Compare `origin/main` against whatever base you edited from
3. If it's moved, pull/merge first rather than force-pushing over it

This isn't optional — skipping it has caused real conflicts before.

## Hard-won gotchas

- **Never let anything `sync_episodes.py` writes to `index.html` be
  non-deterministic run-to-run.** This script runs on a weekly cron *and*
  on every GitHub Pages `page_build` event — including the `page_build`
  triggered by the workflow's own auto-commit. If a run's output can
  differ from the previous run for no reason other than randomness, the
  auto-commit step will treat that as a real change, commit it, trigger
  another `page_build`, and loop indefinitely. **This actually happened**
  on 2026-09-24 (confirmed: two auto-commits four minutes apart reshuffled
  several homepage cards with no new episode involved) — full writeup and
  the fix in docs/EPISODE_SYNC.md. If a feature calls for visual variety
  (e.g. "show something different on every page load"), do it
  **client-side** in `script.js`, never inside the Python script.

- **If working through a device bridge / remote-file-transfer tool**:
  some implementations have a stale-cache bug where re-using a previously
  transferred filename can silently write old cached content even when a
  "force overwrite" flag is set. Always use a fresh, uniquely-numbered
  filename per file transfer, and verify with a checksum (e.g.
  `shasum -a 256`) on both sides after every write, before telling the
  user it's done.

- **A cloud sandbox's own scratch git clone is not the user's machine.**
  If something (a stop-hook, a linter, etc.) flags "uncommitted changes"
  or "untracked files" in a throwaway clone you made for testing, that's
  not the user's repo — don't try to commit or push from it. Clean it up
  locally and move on.

- **Cal.com's intake-form questions can be relabeled without changing
  their underlying field key.** If the booking form's questions ever look
  different again, don't assume a new field means a new custom-field
  slug — check the actual **Identifier** in Cal.com's dashboard before
  changing any code. Details in docs/BOOKING_SYSTEM.md.

## Secrets (names only — never put values in this repo or in chat)

| Secret | Where it lives | Used by |
|---|---|---|
| `YOUTUBE_API_KEY` | GitHub Actions secret | `scripts/sync_episodes.py` (topics grid, playlist discovery) |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | GitHub Actions secret | `scripts/sync_episodes.py` (freshness fallback for show notes) |
| `CAL_API_KEY` | Cloudflare Worker secret (`wrangler secret put`) | `cal-worker/src/index.js` only — never shipped to the browser |

## Testing conventions used in this project

- `scripts/sync_episodes.py` changes: write offline tests that monkey-patch
  its network-calling functions (no real API key or network needed) —
  see docs/EPISODE_SYNC.md for the pattern.
- `cal-worker/src/index.js` changes: import the module directly in a small
  Node script, stub `globalThis.fetch`, and assert on both the HTTP
  response and (for bookings) the exact payload sent to Cal.com.
- `book.html` changes: a tiny local Node HTTP server that serves the file
  with `WORKER_BASE_URL` rewritten to same-origin, mocking the Worker's
  routes, driven by Playwright (`/opt/pw-browsers/chromium`) for the real
  click-through flow. These test scripts aren't checked into the repo —
  ask for them to be recreated (the pattern is simple, see this file's
  history/docs) or request they be added under a `tests/` folder.
- Never live-test `POST /api/book` against production — it creates a real
  Cal.com booking on the user's actual calendar.

## More detail

- **docs/EPISODE_SYNC.md** — the episode/homepage automation, the marker
  system, data-source fallback chain, and the auto-commit-loop incident.
- **docs/BOOKING_SYSTEM.md** — the Cal.com booking system end to end.
- **cal-worker/README.md** — one-time setup / redeploy steps for the Worker.
- **README.md** — human-facing project overview.
