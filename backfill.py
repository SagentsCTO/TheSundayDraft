import sys, os, re, json
sys.path.insert(0, "scripts")
import sync_episodes as se

def html_to_paragraphs(html, max_paras=6):
    # split on paragraph boundaries, strip tags, drop the boilerplate CTA paragraph
    parts = re.split(r"</p>\s*<p>", html)
    paras = []
    for p in parts:
        text = re.sub(r"<[^>]+>", "", p)
        text = text.replace("&#38;", "&").strip()
        if not text or text.startswith("This is a public episode"):
            continue
        paras.append(text)
        if len(paras) >= max_paras:
            break
    return paras

new_entries = [
{
    "slug": "the-war-that-broke-americas-spirit",
    "title": "The War That Broke America’s Spirit",
    "meta_desc": "Spirit Airlines collapsed overnight. Raj and Varun unpack what it revealed about jet fuel, the Strait of Hormuz, and the assumption that oil would always be cheap.",
    "date_display": "May 10, 2026",
    "iso_date": "2026-05-10",
    "duration": None,
    "source": "substack",
    "spotify_id": None,
    "video_id": None,
    "substack_url": "https://thesundaydraft.substack.com/p/live-with-the-sunday-draft",
    "content_html": """<p>Varun just got back from trekking to Everest Base Camp. Fourteen days through Nepal, no signal, no news. Meanwhile, a war had started and it’s been escalating. And an airline many budget travelers relied on closed its counters, grounded their planes, fired their staff, and stranded their passengers.</p><p>Spirit Airlines collapsed on May 2nd, 2026. 3am. No warning. Seventeen thousand jobs gone before most people’s alarms went off. But this episode isn’t really about Spirit Airlines.</p><p>It’s about what Spirit’s death revealed — about jet fuel, the Strait of Hormuz, and the assumption that every American system was quietly built on: that oil would always be cheap, always be stable, always be there.</p><p>Raj and Varun spent a Sunday morning unpacking it. The rescue fares that were also a land grab. The Indian aviation system teetering on the edge. Why you can live off a 7-Eleven in Japan and need a car to reach one in America. What Italy, Singapore, and India get right that the US keeps getting wrong. And the middle class that keeps getting squeezed from every direction with nowhere to go.</p><p>No scripts. No prep. Just two friends peeling back the layers.</p>""",
},
{
    "slug": "from-invisible-children-to-ice-detention-the-story-so-far",
    "title": "From Invisible Children to ICE Detention — The Story So Far | The Sunday Draft LIVE",
    "meta_desc": "One month in, Alicia flips the format and interviews Raj about why he started The Sunday Draft — and walks through the stories the show has covered so far.",
    "date_display": "May 3, 2026",
    "iso_date": "2026-05-03",
    "duration": None,
    "source": "substack",
    "spotify_id": None,
    "video_id": None,
    "substack_url": "https://thesundaydraft.substack.com/p/from-invisible-children-to-ice-detention",
    "content_html": """<p><strong>One Month In — Five episodes. Stories that matter to people paying attention.</strong></p><p>This week marks one month of The Sunday Draft, and instead of the usual format, the tables got flipped. Alicia — globetrotter, Substack regular, and the very first person Raj ever went live with — sat across from him and asked the questions.</p><p>What followed was an honest, unhurried look at what this show is actually trying to do and why.</p><p>Raj talked about how The Sunday Draft came to life — the name, the co-host he found by luck, and the gap he kept seeing: stories that matter getting a blip of coverage and then disappearing. The kind of stories that don’t trend but don’t go away either.</p><p>They walked through the episodes so far. The 46 million children in India invisible to the education system — a number so large it doesn’t feel real until someone like Raman puts a face on it. The child psychologist on the front lines of a social media addiction epidemic that nobody wants to call an epidemic yet. The Mohammad Deepak story, where identity and defiance collided in a politically charged corner of India. And the Meenu Batra case — where immigration policy stopped being abstract and became someone’s life.</p><p>They also talked about what it costs to build something like this alongside a full-time job, what trolls actually signal, and what independence means when the left and right feel equally exhausted.</p><p>A month in. Still figuring out the connective tissue. Still showing up every Sunday.</p>""",
},
{
    "slug": "monthly-ama-child-psychology-social-media-screen-time-ai",
    "title": "Monthly AMA on Child Psychology, Social Media, Screen Time & AI",
    "meta_desc": "Child psychologist Tvarita Iyer Vemuri launches a monthly AMA series, tackling teen tech addiction, the parental mirror effect, and print vs. digital reading.",
    "date_display": "April 27, 2026",
    "iso_date": "2026-04-27",
    "duration": None,
    "source": "substack",
    "spotify_id": None,
    "video_id": "LABLASxn6I4",
    "content_html": """<p>Your Questions. Real Answers. Honest Conversation.</p><p>In this inaugural Ask Me Anything episode of The Sunday Draft Podcast, we sit down with Tvarita Iyer Vemuri, an award-winning child psychologist, to tackle one of the most pressing challenges facing parents and caregivers today: how technology is reshaping childhood development.</p><p>Whether you’re worried about your toddler’s tablet time, concerned about your teen’s social media addiction, or simply trying to navigate the digital parenting landscape—this episode is for you.</p><p>Tvarita recently received recognition from Nestology, a leading platform specializing in early childhood development (ages 0-3) using Montessori methods. Fifty percent of US teens self-report being addicted to social media, spending 9+ hours daily on platforms, while children under 5 in India average 2.2 hours a day on screens.</p><p>There’s no magic age where children suddenly become addicted to screens. What matters is parental modeling, environmental factors, how devices are introduced, and individual susceptibility — children naturally copy their parents’ technology habits.</p><p>Gaming, YouTube, and online resources provide real educational value. The goal isn’t elimination — it’s intentional, purposeful usage that supports learning and development rather than passive consumption. Research shows better information retention with print reading vs. screens, but the solution is cultivating a reading culture where both formats have a place.</p><p>This episode launches The Sunday Draft’s monthly Ask Me Anything series, with Tvarita answering questions each month on child mental health, screen time, parenting strategies, and learning development.</p>""",
},
]

with open("episodes/episodes.json") as f:
    manifest = json.load(f)

known_slugs = {ep["slug"] for ep in manifest}
added = 0
for e in new_entries:
    if e["slug"] in known_slugs:
        continue
    ep = dict(e)
    ep["body_paragraphs"] = html_to_paragraphs(e.pop("content_html"))
    manifest.append(ep)
    page_html = se.render_episode_page(ep)
    with open(os.path.join("episodes", f"{ep['slug']}.html"), "w", encoding="utf-8") as f:
        f.write(page_html)
    print("wrote", ep["slug"])
    added += 1

with open("episodes/episodes.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write("\n")

with open("episodes/index.html", "w", encoding="utf-8") as f:
    f.write(se.render_index(list(reversed(manifest))))

with open("sitemap.xml", "w", encoding="utf-8") as f:
    f.write(se.render_sitemap(list(reversed(manifest))))

newest = max(manifest, key=lambda ep: ep["iso_date"])
se.update_homepage(newest)

print(f"Backfilled {added} historical episode(s). Manifest now has {len(manifest)} total.")
