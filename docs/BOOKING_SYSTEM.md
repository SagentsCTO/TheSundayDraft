# Booking system (Cal.com + Cloudflare Worker + book.html)

Lets a visitor book a recording slot with Raj directly from the site, at
`book.html` (also linked from the homepage).

## Why a Cloudflare Worker exists

The site is static (GitHub Pages) — there's nowhere safe on it to hold a
Cal.com API key. `book.html` never talks to Cal.com directly; it only
talks to a small Cloudflare Worker (`cal-worker/`, deployed as
`sundaydraft-cal-proxy`), which is the *only* thing that ever sees the
real key (stored as a Cloudflare secret via `wrangler secret put
CAL_API_KEY` — never in any file in this repo).

- Live Worker URL: `https://sundaydraft-cal-proxy.raj-a61.workers.dev`
- Cal.com event being booked: `cal.com/the-sunday-draft/record`

## Files

| Path | What it is |
|---|---|
| `book.html` | Custom booker UI (calendar → time slots → form → confirmation). Not Cal.com's embed — a hand-built page that only calls the Worker. |
| `cal-worker/src/index.js` | The Worker itself — the proxy in front of Cal.com's API v2 |
| `cal-worker/wrangler.toml` | Non-secret config (`CAL_USERNAME`, `CAL_EVENT_SLUG`) — safe to commit |
| `cal-worker/README.md` | One-time setup / how to redeploy |

## Worker routes

- `GET /api/availability?start=YYYY-MM-DD&end=YYYY-MM-DD&timeZone=IANA` —
  proxies Cal.com's `GET /v2/slots`
- `POST /api/book` — proxies Cal.com's `POST /v2/bookings`
- `GET /api/upcoming-bookings` — proxies Cal.com's `GET /v2/bookings`, but
  **this is the only route that ever touches an endpoint with attendee
  names/emails/notes**, and strips every field down to just
  `{ start, end }` before it leaves the Worker. It's a deliberate,
  public-facing endpoint (it drives the "already booked" calendar markers
  on `book.html`) — see `handleUpcomingBookings()`'s allowlist comment
  before ever widening what it returns.

All three enforce CORS to `https://thesundaydraft.com` /
`https://www.thesundaydraft.com` only.

## ⚠️ Intake form fields ↔ Cal.com identifiers — read before changing either side

`book.html`'s form does **not** mirror Cal.com's booking form
automatically — it's a hand-built form that the Worker maps onto Cal.com's
`bookingFieldsResponses`. If the Cal.com form changes, `book.html` and the
Worker have to be updated to match by hand, or bookings can silently drop
data or get rejected as missing a required field.

As of 2026-09-24, the mapping is:

| `book.html` field | Label shown to booker | Cal.com API key | Notes |
|---|---|---|---|
| `name` | "Name" | `attendee.name` | |
| `email` | "Email" | `attendee.email` | |
| `expertise` | "What is your area of expertise?" | `bookingFieldsResponses.title` | This is Cal.com's **built-in** meeting-title/"What is this meeting about?" field — just relabeled on the dashboard. It is **not** a bespoke custom-field slug. |
| `notes` | "List any topics you would like to cover." | `bookingFieldsResponses.notes` | Cal.com's built-in additional-notes field, relabeled and made **required** (previously optional, previously labeled "What would you like to talk about? (optional)"). |

**If the Cal.com intake form changes again**: don't guess a field's API
key from its label. In Cal.com: **Event Types → record → Advanced tab →
click the question to edit it → its "Identifier" field is the actual key**
to use in `bookingFieldsResponses`. Built-in fields (title, notes, guests,
location) keep their fixed system key regardless of relabeling; a genuinely
new custom question gets its own identifier, which may or may not match a
slugified version of its label — check, don't assume.

Both `book.html` (HTML `required` + browser-native validation) and the
Worker (`handleBook()`, explicit checks) validate required fields — the
Worker's checks exist so a request that somehow bypasses the browser still
fails with a clear error instead of a confusing generic Cal.com 400.

## Buffer time between bookings

Configured entirely on Cal.com's side — **Event Types → record → Limits
tab → Buffer time before/after event**. No code involved: the Worker's
`/api/availability` just proxies whatever Cal.com's own slot computation
returns, so a buffer set there is automatically respected everywhere
(the time-slot list, the calendar's booked-day markers), with zero changes
needed here.

## Calendar UI (booked-time markers)

`book.html` shows which times are already taken directly on the calendar —
a dot on any day with a booking, a CSS-only hover/focus tooltip listing the
times, and a small legend — rather than a separate scrolling list (an
earlier version did that; it didn't scale past a handful of bookings).
Driven by `/api/upcoming-bookings`; see `loadBookedMarkers()` and
`renderDays()` in `book.html`. This data is independent of whichever
month's availability is currently being viewed.

## Deploying a change

- **`book.html` only** → push to `main` as usual; GitHub Pages picks it up.
- **`cal-worker/src/index.js` or `wrangler.toml`** → from the `cal-worker/`
  folder, run `wrangler deploy` (needs the user's own `wrangler login`
  session — don't run this on the user's behalf). This is a *separate*
  deploy step from pushing to `main`; the Worker doesn't redeploy itself.
- If a change touches **both sides** (like the intake-form field mapping),
  redeploy the Worker before or immediately after pushing `book.html` —
  the old Worker + new `book.html` (or vice versa) can silently mismatch
  on which fields are required/sent.

## Testing this system

- **Worker logic**: import `cal-worker/src/index.js` directly in a small
  Node script, stub `globalThis.fetch` to return canned Cal.com responses,
  and assert on both the HTTP response *and* (for `/api/book`) the exact
  payload the Worker would send to Cal.com — this is how the
  `title`/`notes` field mapping above was verified.
- **`book.html` UI**: a tiny local Node HTTP server serves the file with
  `WORKER_BASE_URL` rewritten to same-origin (avoids CORS, needs zero
  changes to the real file), mocking the three routes; Playwright
  (`/opt/pw-browsers/chromium`) drives the actual click-through flow
  (pick a day → pick a slot → fill the form → confirm), plus the
  conflict/error path.
- These test scripts aren't checked into this repo yet — they're quick to
  recreate from the patterns above, or ask for them to be added under a
  `tests/` folder so they don't need rebuilding each session.
- **Never live-test `POST /api/book` against production** — it creates a
  real event on the actual Cal.com calendar. Availability (`GET`) is safe
  to hit live.
