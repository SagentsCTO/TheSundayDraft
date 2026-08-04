# The Sunday Draft — website

Live at [thesundaydraft.com](https://thesundaydraft.com), hosted free on GitHub Pages from [github.com/SagentsCTO/TheSundayDraft](https://github.com/SagentsCTO/TheSundayDraft). No build step, no framework — just `index.html`, `styles.css`, `script.js`, and an `assets/` folder.

## What's wired up

- **Latest episode** embeds your Spotify show player — it auto-updates every Sunday when a new episode drops, no maintenance required. (A YouTube playlist embed was tried first, but this channel mixes in Shorts, which YouTube's classic iframe player can't play — that's what caused the "this video is unavailable" error. Spotify's embed doesn't have that problem.)
- **Newsletter** embeds your real Substack subscribe widget.
- **Listen everywhere** links to your real YouTube, Spotify, and Apple Podcasts pages.
- **Footer** links to YouTube, BlueSky, and Substack.
- **Logo, favicon, and social-share image** use your actual logo files (`assets/logo-wordmark.png`, `assets/favicon.png`, `assets/apple-touch-icon.png`, `assets/og-image.jpg`).
- **About / topics** sections use your channel's actual description and subject pillars.

## Fully automatic new episodes

`.github/workflows/sync-episodes.yml` runs `scripts/sync_episodes.py` once a day (14:00 UTC) on GitHub's own servers — no laptop, no push from you, no asking Claude. It:

1. Checks the "Full Episodes" YouTube playlist's RSS feed for any video not already in `episodes/episodes.json`.
2. Generates a full show-notes page for it (`episodes/{slug}.html`) with a YouTube embed, cleaned-up description, and SEO/structured-data tags.
3. Regenerates `episodes/index.html` and `sitemap.xml`.
4. Updates the homepage's "Latest episode" blurb and "Read the full show notes" link.
5. Commits and pushes automatically — only if there's actually something new (safe to run daily forever).

**One-time setup required:** GitHub Actions needs permission to push. In the repo, go to Settings → Actions → General → Workflow permissions, and select "Read and write permissions," then Save. Without this, the workflow will run but fail on the push step.

**To test it right now** instead of waiting for the daily run: go to the Actions tab → "Sync new episodes" → Run workflow. Check the run log — it'll either say "No new episodes found" (if the playlist hasn't changed) or show you exactly what it generated.

**What it won't get right automatically:** the YouTube video description becomes the show notes verbatim (minus obvious CTA/timestamp lines it filters out), so it won't read as polished as the hand-written ones. If you want it curated, just message Claude with the episode details and ask for a page instead of waiting for the bot.

## Optional: a real video embed instead of audio

If you'd rather show video on the homepage, send the YouTube link to a specific full episode (not a Short) and the Spotify embed can be swapped for a direct video embed. Best long-term fix: create a dedicated "Full Episodes" playlist on YouTube (excluding Shorts) and add each episode to it going forward — the embed can point at that playlist so it keeps auto-updating without breaking on Shorts.

## Pushing future changes

The repo already has everything live. To make changes:

1. Edit files locally, or directly on github.com (pencil icon on any file).
2. Commit to `main` — GitHub Pages redeploys automatically within a minute or two.

If working locally:
```
git clone https://github.com/SagentsCTO/TheSundayDraft.git
cd TheSundayDraft
# make edits
git add .
git commit -m "Update site"
git push
```

## Domain / DNS

Custom domain is `thesundaydraft.com`, configured via the `CNAME` file in the repo root plus DNS records at the registrar (GoDaddy): four `A` records at `@` pointing to GitHub's Pages IPs, and a `CNAME` record for `www` pointing to `sagentscto.github.io`. Already set up and verified.
