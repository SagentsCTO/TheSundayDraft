// Picks a random candidate from a topic card's data-pool JSON (see
// sync_episodes.py's build_topics_grid_html(), which computes each
// playlist's top-viewed candidates). Returns null — meaning "leave the
// server-rendered fallback alone" — if the pool is missing, malformed, or
// has fewer than 2 usable candidates (nothing to randomize between).
// Exported to `module.exports` (guarded below) purely so this can be unit
// tested from Node without a browser; that guard is a no-op in the browser.
function pickRandomTopicVideo(poolJson) {
  let pool;
  try {
    pool = JSON.parse(poolJson);
  } catch (e) {
    return null;
  }
  if (!Array.isArray(pool)) return null;

  // A YouTube video ID is always exactly 11 chars from this set; the
  // range is a little loose on purpose (in case that ever changes) but
  // this still guards against anything unexpected ending up in an
  // href/img src built from this data.
  const idPattern = /^[A-Za-z0-9_-]{6,20}$/;
  const valid = pool.filter(
    (p) => p && typeof p.id === "string" && idPattern.test(p.id) && typeof p.title === "string"
  );
  if (valid.length < 2) return null;

  return valid[Math.floor(Math.random() * valid.length)];
}

if (typeof document !== "undefined") {
  document.getElementById("year").textContent = new Date().getFullYear();

  // "What we cover" topic cards: each ships a data-pool of its top-viewed
  // candidate videos. Swap in a random one on every page load, so
  // refreshing shows a different (but still proven, popular) video per
  // topic instead of always the same one — see sync_episodes.py for how
  // the pool itself is computed and kept in sync with real view counts.
  document.querySelectorAll(".topic-card[data-pool]").forEach((card) => {
    const pick = pickRandomTopicVideo(card.dataset.pool);
    if (!pick) return; // malformed/too-small pool — leave the server-rendered fallback as-is

    card.href = `https://www.youtube.com/watch?v=${pick.id}`;
    const img = card.querySelector(".topic-thumb");
    if (img) img.src = `https://i.ytimg.com/vi/${pick.id}/hqdefault.jpg`;
    const h3 = card.querySelector("h3");
    if (h3) h3.textContent = pick.title;
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { pickRandomTopicVideo };
}
