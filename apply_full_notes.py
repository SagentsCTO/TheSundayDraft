import sys, os, json, re
sys.path.insert(0, "scripts")
import sync_episodes as se
from apple_full_notes import RAW

TS_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?\s*[–—-]")


def to_html(raw):
    lines = [l.strip() for l in raw.split("\n")]
    blocks = []
    for line in lines:
        if not line:
            continue
        if line.startswith("* "):
            blocks.append(("li", line[2:].strip()))
        elif TS_RE.match(line):
            blocks.append(("li", line))
        elif (line.isupper() and 3 < len(line) < 70) or (
            line.endswith(":") and len(line) < 70 and not line[:1].islower()
        ):
            blocks.append(("h", line))
        else:
            blocks.append(("p", line))

    html_parts = []
    cur_list = []

    def flush_list():
        nonlocal cur_list
        if cur_list:
            html_parts.append("<ul>" + "".join(f"<li>{x}</li>" for x in cur_list) + "</ul>")
            cur_list = []

    for kind, text in blocks:
        if kind == "li":
            cur_list.append(text)
        else:
            flush_list()
            if kind == "h":
                html_parts.append(f"<p><strong>{text}</strong></p>")
            else:
                html_parts.append(f"<p>{text}</p>")
    flush_list()
    return "\n".join(html_parts)


with open("episodes/episodes.json") as f:
    manifest = json.load(f)

updated = 0
missing = []
for ep in manifest:
    raw = RAW.get(ep["slug"])
    if raw is None:
        missing.append(ep["slug"])
        continue
    ep["content_html"] = to_html(raw)
    ep.pop("body_paragraphs", None)
    updated += 1

for ep in manifest:
    html = se.render_episode_page(ep)
    with open(os.path.join("episodes", f"{ep['slug']}.html"), "w", encoding="utf-8") as f:
        f.write(html)

with open("episodes/episodes.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write("\n")

with open("episodes/index.html", "w", encoding="utf-8") as f:
    f.write(se.render_index(list(reversed(manifest))))

with open("sitemap.xml", "w", encoding="utf-8") as f:
    f.write(se.render_sitemap(list(reversed(manifest))))

newest = max(manifest, key=lambda e: e["iso_date"])
se.update_homepage(newest)

print(f"Updated {updated} episodes with full Apple show notes.")
if missing:
    print("MISSING raw text for:", missing)
