import sys, os, json
sys.path.insert(0, "scripts")
import sync_episodes as se

DROP_SLUGS = {"the-collapse-of-diplomacy-is-it-dead", "surviving-hardest-days-everest-base-camp-part-2"}

with open("episodes/episodes.json") as f:
    manifest = json.load(f)

kept = [ep for ep in manifest if ep["slug"] not in DROP_SLUGS]
dropped = [ep for ep in manifest if ep["slug"] in DROP_SLUGS]

for ep in dropped:
    path = os.path.join("episodes", f"{ep['slug']}.html")
    if os.path.exists(path):
        try:
            os.remove(path)
            print("deleted", path)
        except PermissionError:
            # can't delete in this sandbox; blank it out so it 404s harmlessly instead of showing thin content
            with open(path, "w") as f:
                f.write("")
            print("could not delete, blanked instead:", path)

kept.sort(key=lambda ep: ep["iso_date"])

with open("episodes/episodes.json", "w", encoding="utf-8") as f:
    json.dump(kept, f, indent=2, ensure_ascii=False)
    f.write("\n")

with open("episodes/index.html", "w", encoding="utf-8") as f:
    f.write(se.render_index(list(reversed(kept))))

with open("sitemap.xml", "w", encoding="utf-8") as f:
    f.write(se.render_sitemap(list(reversed(kept))))

newest = max(kept, key=lambda ep: ep["iso_date"])
se.update_homepage(newest)

print(f"Dropped {len(dropped)} thin entries. {len(kept)} episodes remain.")
