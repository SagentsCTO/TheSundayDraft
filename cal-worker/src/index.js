/**
 * Cloudflare Worker: a thin, secret-holding proxy in front of the Cal.com
 * API v2.
 *
 * Why this exists: TheSundayDraft.com is a static site (GitHub Pages) with
 * no server of its own, but a Cal.com API key must never be shipped to the
 * browser — anyone could read it out of the page source and book/cancel
 * arbitrary things, or worse, use it to call other Cal.com endpoints on
 * this account. This Worker is the only thing that ever sees the real key
 * (as a Cloudflare secret, set via `wrangler secret put CAL_API_KEY` — see
 * the README). The browser only ever talks to this Worker.
 *
 * Routes:
 *   GET  /api/availability?start=YYYY-MM-DD&end=YYYY-MM-DD&timeZone=IANA
 *     -> proxies Cal.com GET /v2/slots for CAL_USERNAME/CAL_EVENT_SLUG,
 *        returns { ok: true, slots: { "YYYY-MM-DD": ["2026-10-01T09:00:00-04:00", ...] } }
 *
 *   POST /api/book   body: { start, name, email, notes?, timeZone }
 *     -> proxies Cal.com POST /v2/bookings, returns
 *        { ok: true, booking: { start, end, ... } } or { ok: false, error }
 *
 *   GET  /api/upcoming-bookings
 *     -> proxies Cal.com GET /v2/bookings (this is the ONLY route that
 *        touches an endpoint returning attendee names/emails/notes), then
 *        strips every field down to just { start, end } before it leaves
 *        this Worker. This is a deliberate, public-facing endpoint (it
 *        shows which times are already taken) — it must NEVER pass through
 *        attendee info. See handleUpcomingBookings() for the allowlist.
 *        Returns { ok: true, booked: [{ start, end }, ...] }
 *
 * Everything else -> 404.
 */

const CAL_API_BASE = "https://api.cal.com";
const SLOTS_API_VERSION = "2024-09-04";
const BOOKINGS_API_VERSION = "2026-02-25";
const LIST_BOOKINGS_API_VERSION = "2026-05-01";

// Only these origins are allowed to call this Worker from a browser. Add
// a staging/preview origin here too if you ever need one.
const ALLOWED_ORIGINS = new Set([
  "https://thesundaydraft.com",
  "https://www.thesundaydraft.com",
]);

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MAX_UPCOMING = 20;

function corsHeaders(request) {
  const origin = request.headers.get("Origin");
  const headers = {
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    Vary: "Origin",
  };
  if (origin && ALLOWED_ORIGINS.has(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
  }
  return headers;
}

function json(data, status, request) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders(request),
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }

    if (url.pathname === "/api/availability" && request.method === "GET") {
      return handleAvailability(url, request, env);
    }

    if (url.pathname === "/api/book" && request.method === "POST") {
      return handleBook(request, env);
    }

    if (url.pathname === "/api/upcoming-bookings" && request.method === "GET") {
      return handleUpcomingBookings(request, env);
    }

    return json({ ok: false, error: "Not found" }, 404, request);
  },
};

async function handleAvailability(url, request, env) {
  const start = url.searchParams.get("start");
  const end = url.searchParams.get("end");
  const timeZone = url.searchParams.get("timeZone") || "UTC";

  if (!start || !end || !DATE_RE.test(start) || !DATE_RE.test(end)) {
    return json(
      { ok: false, error: "start and end are required, as YYYY-MM-DD" },
      400,
      request
    );
  }

  const calUrl = new URL(`${CAL_API_BASE}/v2/slots`);
  calUrl.searchParams.set("eventTypeSlug", env.CAL_EVENT_SLUG);
  calUrl.searchParams.set("username", env.CAL_USERNAME);
  calUrl.searchParams.set("start", start);
  calUrl.searchParams.set("end", end);
  calUrl.searchParams.set("timeZone", timeZone);
  calUrl.searchParams.set("format", "time");

  let calResp;
  try {
    calResp = await fetch(calUrl.toString(), {
      headers: {
        Authorization: `Bearer ${env.CAL_API_KEY}`,
        "cal-api-version": SLOTS_API_VERSION,
      },
    });
  } catch (e) {
    return json({ ok: false, error: "Could not reach Cal.com" }, 502, request);
  }

  const body = await calResp.json().catch(() => null);
  if (!calResp.ok || !body || body.status !== "success") {
    return json(
      { ok: false, error: extractCalError(body) || "Cal.com returned an error" },
      calResp.status || 502,
      request
    );
  }

  // Flatten { "2026-10-01": [{start:"..."}], ... } into plain ISO-string arrays.
  const slots = {};
  for (const [date, entries] of Object.entries(body.data || {})) {
    slots[date] = (entries || []).map((e) => e.start).filter(Boolean);
  }

  return json({ ok: true, slots }, 200, request);
}

async function handleBook(request, env) {
  let payload;
  try {
    payload = await request.json();
  } catch (e) {
    return json({ ok: false, error: "Invalid JSON body" }, 400, request);
  }

  const { start, name, email, notes, timeZone } = payload || {};

  if (!start || typeof start !== "string") {
    return json({ ok: false, error: "Missing booking time" }, 400, request);
  }
  if (!name || typeof name !== "string" || !name.trim()) {
    return json({ ok: false, error: "Name is required" }, 400, request);
  }
  if (!email || typeof email !== "string" || !EMAIL_RE.test(email)) {
    return json({ ok: false, error: "A valid email is required" }, 400, request);
  }
  if (!timeZone || typeof timeZone !== "string") {
    return json({ ok: false, error: "Missing timezone" }, 400, request);
  }

  const calBody = {
    start,
    eventTypeSlug: env.CAL_EVENT_SLUG,
    username: env.CAL_USERNAME,
    attendee: {
      name: name.trim(),
      email: email.trim(),
      timeZone,
    },
  };
  if (notes && typeof notes === "string" && notes.trim()) {
    calBody.bookingFieldsResponses = { notes: notes.trim() };
  }

  let calResp;
  try {
    calResp = await fetch(`${CAL_API_BASE}/v2/bookings`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.CAL_API_KEY}`,
        "cal-api-version": BOOKINGS_API_VERSION,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(calBody),
    });
  } catch (e) {
    return json({ ok: false, error: "Could not reach Cal.com" }, 502, request);
  }

  const body = await calResp.json().catch(() => null);
  if (!calResp.ok || !body || body.status !== "success") {
    // A 409-ish "slot no longer available" is common if two people book at
    // once — surface Cal.com's own message so the frontend can show
    // something meaningful instead of a generic failure.
    return json(
      { ok: false, error: extractCalError(body) || "Could not complete the booking" },
      calResp.status || 502,
      request
    );
  }

  const data = body.data || {};
  return json(
    {
      ok: true,
      booking: {
        start: data.start,
        end: data.end,
        uid: data.uid,
      },
    },
    201,
    request
  );
}

async function handleUpcomingBookings(request, env) {
  const calUrl = new URL(`${CAL_API_BASE}/v2/bookings`);
  calUrl.searchParams.set("status", "upcoming");
  calUrl.searchParams.set("sortStart", "asc");
  calUrl.searchParams.set("limit", "100");

  let calResp;
  try {
    calResp = await fetch(calUrl.toString(), {
      headers: {
        Authorization: `Bearer ${env.CAL_API_KEY}`,
        "cal-api-version": LIST_BOOKINGS_API_VERSION,
      },
    });
  } catch (e) {
    return json({ ok: false, error: "Could not reach Cal.com" }, 502, request);
  }

  const body = await calResp.json().catch(() => null);
  if (!calResp.ok || !body || body.status !== "success") {
    return json(
      { ok: false, error: extractCalError(body) || "Cal.com returned an error" },
      calResp.status || 502,
      request
    );
  }

  // This is the one Cal.com response in this whole Worker that carries
  // attendee names, emails, phone numbers, and free-text notes — this
  // endpoint is public, so ONLY start/end ever leave this function. Do not
  // widen this mapping without re-checking who can call this route.
  const booked = (Array.isArray(body.data) ? body.data : [])
    .filter(
      (b) =>
        b &&
        b.status === "accepted" &&
        b.eventType &&
        b.eventType.slug === env.CAL_EVENT_SLUG &&
        typeof b.start === "string" &&
        typeof b.end === "string"
    )
    .map((b) => ({ start: b.start, end: b.end }))
    .sort((a, b) => new Date(a.start) - new Date(b.start))
    .slice(0, MAX_UPCOMING);

  return json({ ok: true, booked }, 200, request);
}

function extractCalError(body) {
  if (!body) return null;
  if (typeof body.message === "string") return body.message;
  if (Array.isArray(body.message)) return body.message.join(", ");
  if (body.error && typeof body.error.message === "string") return body.error.message;
  return null;
}
