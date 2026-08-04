import sys, os, json
from datetime import datetime
sys.path.insert(0, "scripts")
import sync_episodes as se

def fmt(iso_ts):
    dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    return dt.strftime("%B %-d, %Y"), dt.strftime("%Y-%m-%d")

# Exact data pulled from the "Full Episodes" YouTube playlist RSS (authoritative per user request).
# slug -> (video_id, iso_timestamp)
YT_MATCH = {
    "the-fixer-amjad-tadros": ("GccCMYvh2Hk", "2026-07-27T16:30:31.000Z"),
    "indias-gen-z-movement-crisis": ("QcYh7PLYL3Q", "2026-07-19T20:54:29.000Z"),
    "why-socialism-struggles": ("Af6B0dnzFdI", "2026-07-12T22:54:45.000Z"),
    "why-companies-arent-getting-roi-on-ai": ("hZecGEV_hRU", "2026-07-06T02:37:25.000Z"),
    "think-your-way-out-of-billionaire-driven-ai-replacement": ("zHDoXQMrETQ", "2026-06-29T05:39:49.000Z"),
    "piff-paff-politics-cockroach-party-one-month-in": ("FpmGSA_OrIg", "2026-06-14T23:33:45.000Z"),
    "are-we-enabling-ai-to-replace-us": ("G0HdpMbAm2I", "2026-06-07T13:00:06.000Z"),
    "raising-them-in-your-cage": ("iTqqB-GC3OU", "2026-05-31T17:00:47.000Z"),
    "troll-wars-explaining-indian-culture-to-the-internet": ("JfWPm4gP4w0", "2026-05-29T22:01:44.000Z"),
    "the-war-that-broke-americas-spirit": ("ItYufEz9p6U", "2026-05-11T02:11:53.000Z"),
    "from-invisible-children-to-ice-detention-the-story-so-far": ("qCQdHHXc_8M", "2026-05-03T23:39:21.000Z"),
    "monthly-ama-child-psychology-social-media-screen-time-ai": ("3e2nW3BhlEg", "2026-04-27T06:45:11.000Z"),
}

with open("episodes/episodes.json") as f:
    manifest = json.load(f)

updated = 0
for ep in manifest:
    if ep["slug"] in YT_MATCH:
        vid, ts = YT_MATCH[ep["slug"]]
        date_display, iso_date = fmt(ts)
        ep["video_id"] = vid
        ep["date_display"] = date_display
        ep["iso_date"] = iso_date
        if ep.get("source") == "substack":
            ep["source"] = "youtube"
        updated += 1

# Two episodes that exist on the YouTube playlist but had no page at all yet.
new_from_youtube = [
    {
        "slug": "surviving-hardest-days-everest-base-camp-part-2",
        "title": "Surviving the HARDEST Days to Everest Base Camp (EBC Part 2)",
        "meta_desc": "Part 2 of the Everest Base Camp trek: Tengboche, Labuche, Gorak Shep, and the moment Varun and Aneesh finally reached base camp.",
        "video_id": "3I80QjKo7ic",
        "iso_ts": "2026-07-05T06:54:33.000Z",
        "source": "youtube",
        "body_paragraphs": [
            "Part 2 of Raj's conversation with Varun and Aneesh about their Everest Base Camp trek — picking up from Namche Bazaar and pushing on through Tengboche, Labuche, and Gorak Shep to the moment they finally reached base camp.",
            "Full details are in the video — watch it on YouTube for the complete conversation.",
        ],
    },
    {
        "slug": "the-collapse-of-diplomacy-is-it-dead",
        "title": "The Collapse of Diplomacy - Is It Dead?",
        "meta_desc": "A conversation on whether traditional diplomacy still works in a world of social-media brinkmanship and unilateral moves.",
        "video_id": "YJxedOV_-MU",
        "iso_ts": "2026-05-24T17:48:55.000Z",
        "source": "youtube",
        "body_paragraphs": [
            "A conversation on The Sunday Draft about whether traditional diplomacy still works in a world of social-media brinkmanship, unilateral moves, and summits that play out in public before they happen behind closed doors.",
            "Full details are in the video — watch it on YouTube for the complete conversation.",
        ],
    },
]

existing_slugs = {ep["slug"] for ep in manifest}
for e in new_from_youtube:
    if e["slug"] in existing_slugs:
        continue
    date_display, iso_date = fmt(e["iso_ts"])
    ep = {
        "slug": e["slug"],
        "title": e["title"],
        "meta_desc": e["meta_desc"],
        "date_display": date_display,
        "iso_date": iso_date,
        "duration": None,
        "source": e["source"],
        "spotify_id": None,
        "video_id": e["video_id"],
        "body_paragraphs": e["body_paragraphs"],
    }
    manifest.append(ep)
    updated += 1
    print("added new:", ep["slug"])

# Regenerate every episode page (cheap, and keeps everything in sync with corrected data)
for ep in manifest:
    html = se.render_episode_page(ep)
    with open(os.path.join("episodes", f"{ep['slug']}.html"), "w", encoding="utf-8") as f:
        f.write(html)

manifest.sort(key=lambda ep: ep["iso_date"])

with open("episodes/episodes.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write("\n")

with open("episodes/index.html", "w", encoding="utf-8") as f:
    f.write(se.render_index(list(reversed(manifest))))

with open("sitemap.xml", "w", encoding="utf-8") as f:
    f.write(se.render_sitemap(list(reversed(manifest))))

newest = max(manifest, key=lambda ep: ep["iso_date"])
se.update_homepage(newest)

print(f"Updated/added {updated} entries. Manifest now has {len(manifest)} total.")
