# The Sunday Draft — website

A free, static site for The Sunday Draft, built to deploy on GitHub Pages. No build step, no framework — just `index.html`, `styles.css`, and `script.js`.

## What's already wired up

- **Latest episodes** embed pulls automatically from your YouTube uploads playlist (`UU45awL7dke6c7OCEPdvxNqw`). You never have to touch this — it updates itself every time you publish.
- **About / topics** sections use your channel's actual description and subject pillars.
- **Newsletter form** and **listen-elsewhere buttons** are stubbed in and marked `TODO` — see below.

## 1. Put this on GitHub Pages (free hosting)

1. Create a new repo on GitHub, e.g. `thesundaydraft-site` (public repo — required for free Pages on a personal account).
2. Upload these three files (`index.html`, `styles.css`, `script.js`) to the repo root — drag-and-drop works fine on github.com, or:
   ```
   git init
   git add .
   git commit -m "Launch site"
   git branch -M main
   git remote add origin https://github.com/<your-username>/thesundaydraft-site.git
   git push -u origin main
   ```
3. In the repo: **Settings → Pages → Source → Deploy from a branch → `main` / `root`**.
4. Your site goes live at `https://<your-username>.github.io/thesundaydraft-site/` within a minute or two.

## 2. Optional: custom domain

If you buy a domain (e.g. `thesundaydraft.com` — a domain is the one part of this that isn't free, typically ~$12/yr):

1. Add a file named `CNAME` (no extension) to the repo root containing just your domain, e.g. `thesundaydraft.com`.
2. At your domain registrar, add a `CNAME` record pointing `www` to `<your-username>.github.io`, and `A` records for the apex domain to GitHub's IPs (185.199.108.153, .109.153, .110.153, .111.153).
3. In **Settings → Pages**, enter the custom domain and enable "Enforce HTTPS."

## 3. Fill in the TODOs

Open `index.html` and search for `TODO`:

- **Newsletter form action** — the form currently points to a placeholder Formspree URL. Sign up free at [formspree.io](https://formspree.io) (50 submissions/month free) or [buttondown.com](https://buttondown.com), create a form, and swap in your real endpoint. Buttondown is worth considering over Formspree since it's built for actually *sending* the weekly newsletter, not just collecting emails.
- **Listen-elsewhere buttons** (Spotify / Apple Podcasts) — add your real show links once you've submitted the RSS feed to those platforms.
- **Social links** in the footer — add Instagram/X if you have them, or delete the `<a>` tags you don't need.
- **`assets/og-image.jpg` and `assets/favicon.png`** — referenced but not included. Add a 1200×630 image for social share previews and a small square favicon; drop them in an `assets/` folder.

## Making changes later

Everything is plain HTML/CSS in two files — no build tools. Edit `index.html` for content, `styles.css` for design, then commit and push; Pages redeploys automatically in under a minute.
