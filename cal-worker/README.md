# Cal.com booking proxy

A small Cloudflare Worker that sits between thesundaydraft.com and the
Cal.com API. It exists because the site itself is static (GitHub Pages) and
has nowhere safe to hold a secret API key — this Worker is that place.

## One-time setup

1. **Install Node.js** if you don't have it (check with `node -v` in
   Terminal — anything v18+ is fine).

2. **From this `cal-worker` folder**, install Wrangler (Cloudflare's CLI)
   and log in:

   ```
   cd cal-worker
   npm install -g wrangler
   wrangler login
   ```

   This opens a browser tab to log into (or create) a free Cloudflare
   account and authorize Wrangler. You only do this once.

3. **Fill in `wrangler.toml`**: open it and replace the two placeholder
   values with your actual Cal.com username and event-type slug. You can
   read both off the event's public booking link in your Cal.com dashboard
   (Event Types → click the event people should book → the link shown is
   `https://cal.com/<username>/<event-slug>`).

4. **Set your Cal.com API key as a secret** (this is the key step — it
   keeps the key out of git and out of this chat entirely):

   ```
   wrangler secret put CAL_API_KEY
   ```

   Paste the key when prompted. Wrangler sends it straight to Cloudflare,
   encrypted; it's never written to any file here.

5. **Deploy:**

   ```
   wrangler deploy
   ```

   This prints a URL like `https://sundaydraft-cal-proxy.<your-subdomain>.workers.dev`.
   Copy it.

6. **Point the site at it**: open `book.html` at the repo root and set the
   `WORKER_BASE_URL` constant near the top of its `<script>` block to the
   URL from step 5. Commit and push as usual.

## Making a change later

Edit `src/index.js`, then re-run `wrangler deploy` from this folder. No
need to touch the API key again unless you rotate it (`wrangler secret put
CAL_API_KEY` again to replace it).

## Costs

Cloudflare Workers' free tier (100,000 requests/day) is far more than a
podcast booking page needs — this should cost $0.
