import sys, os, json
sys.path.insert(0, "scripts")
import sync_episodes as se

NEW_EPISODES = [
    {
        "slug": "the-meenu-batra-case-withheld-from-due-process",
        "title": "The Meenu Batra Case: Withheld From Due Process",
        "meta_desc": "A Sikh court interpreter with 35 years in the US has been detained for over 40 days under a legal paradox: the same protection that bars her deportation is being used to justify holding her indefinitely.",
        "date_display": "April 26, 2026",
        "iso_date": "2026-04-26",
        "duration": "56 min",
        "source": "youtube",
        "spotify_id": None,
        "video_id": "9dGDHdYPx4g",
        "apple_url": "https://podcasts.apple.com/us/podcast/the-meenu-batra-case-withheld-from-due-process/id1887351307?i=1000763682109&uo=4",
        "body_paragraphs": [
            "On March 17, 2026, Meenu Batra — a 53-year-old court interpreter who has spent 35 years building a life and family in America — was arrested at Harlingen Airport in Texas while traveling to Milwaukee for the very work the U.S. courts have authorized her to do for two decades. More than 40 days later, she remains detained at the El Valle ICE Processing Center.",
            "The case turns on a legal paradox. Batra holds \"withholding of removal,\" a protection granted in 2000 that bars her deportation to India, where she fled anti-Sikh persecution in 1984 — the same violence that killed her parents. Under a Trump administration executive order targeting people with final removal orders, DHS is treating that protection as grounds for detention, even though it bars deportation to one country rather than ordering removal itself.",
            "Batra has no criminal record beyond a single speeding ticket in thirty years, holds work authorization through 2028, and is the only certified Punjabi, Hindi, and Urdu court interpreter in Texas. Four of her children are U.S. citizens, including one currently serving in the U.S. Army.",
            "We compare her case to Babblejit \"Bubbly\" Kaur, another Sikh woman detained in December 2025 who was released after 20 days once her habeas corpus petition succeeded — in the more sympathetic Ninth Circuit. Batra's case sits in the Fifth Circuit, historically less favorable to immigrant rights, which is why her attorney, Deepak Ahluwalia, is pursuing the same strategy with a far less certain outcome.",
            "The episode asks a bigger question than any one case: whether the protections the U.S. immigration system promises actually hold, or whether they can be inverted and used against the very people they were designed to shield.",
        ],
    },
    {
        "slug": "can-art-survive-war",
        "title": "Can Art Survive War?",
        "meta_desc": "How ongoing conflict and political decisions under both the Trump and Modi administrations are putting art and cultural heritage at risk — and what's lost when culture becomes collateral damage.",
        "date_display": "April 19, 2026",
        "iso_date": "2026-04-19",
        "duration": "48 min",
        "source": None,
        "spotify_id": None,
        "video_id": None,
        "apple_url": "https://podcasts.apple.com/us/podcast/can-art-survive-war/id1887351307?i=1000762210488&uo=4",
        "body_paragraphs": [
            "War doesn't just destroy lives — it erases culture, art, and centuries of human heritage. This episode looks at how ongoing conflict, political pressure, and government decisions under both the Trump and Modi administrations are putting art and cultural heritage at risk on multiple fronts.",
            "The conversation examines what gets lost when culture becomes collateral damage — from funding cuts and institutional pressure to the outright destruction of historic sites in active conflict zones — and asks what, if anything, can still be done to protect it.",
        ],
    },
    {
        "slug": "the-child-brain-trap",
        "title": "The Child Brain Trap: Social Media, AI, and What's Happening to Our Children",
        "meta_desc": "The first generation to grow up entirely inside the algorithm is here. What research from Pew, LocalCircle, and child psychologists reveals about anxiety, screens, and developing brains.",
        "date_display": "April 5, 2026",
        "iso_date": "2026-04-05",
        "duration": "1 hr 35 min",
        "source": "youtube",
        "spotify_id": None,
        "video_id": "LABLASxn6I4",
        "substack_url": "https://thesundaydraft.substack.com/p/social-media-and-ai-the-child-brain",
        "apple_url": "https://podcasts.apple.com/us/podcast/the-child-brain-trap-social-media-ai-and-whats/id1887351307?i=1000759417276&uo=4",
        "body_paragraphs": [
            "The first generation to grow up entirely inside the algorithm is already here. They have AI tutors, social media feeds, and screen time that rivals their hours in school — and the research on what this is doing to developing brains is more alarming than most parents realize.",
            "This episode examines the anxiety epidemic quietly taking hold in children as young as six, walking through what studies from Pew, LocalCircle, and leading child psychologists are actually finding, and what parents can do about it before the window to course-correct closes.",
            "Child psychologist Tvarita Iyer Vemuri joins for a wide-ranging conversation about modeling healthy tech habits, recognizing the signs of screen dependency, and rethinking what a child-friendly relationship with technology actually looks like.",
        ],
    },
    {
        "slug": "the-hindu-gym-owner-who-took-a-muslim-name",
        "title": "The Hindu Gym Owner Who Took a Muslim Name — and Paid the Price",
        "meta_desc": "A Hindu gym owner in India legally changes his name to Mohammed Deepak — a story about identity, belonging, and what tolerance looks like when it's actually tested.",
        "date_display": "March 29, 2026",
        "iso_date": "2026-03-29",
        "duration": "39 min",
        "source": None,
        "spotify_id": None,
        "video_id": None,
        "substack_url": "https://thesundaydraft.substack.com/p/mohammed-deepak",
        "apple_url": "https://podcasts.apple.com/us/podcast/the-hindu-gym-owner-who-took-a-muslim-name-and-paid-the-price/id1887351307?i=1000758076483&uo=4",
        "body_paragraphs": [
            "In India, a Hindu gym owner named Deepak Kumar legally changed his name to Mohammed Deepak — a deliberate act of interfaith solidarity that went viral, and that some read as an act of courage and others as an affront.",
            "The episode traces what followed: the backlash, the support, and the harder questions underneath the viral moment about who gets to define religious and cultural identity in a country where that identity has become increasingly weaponized.",
            "It's not an episode that takes sides. It's an attempt to sit with the discomfort of a story that resists a clean moral, and to ask what real tolerance looks like once it's actually tested rather than just professed.",
        ],
    },
    {
        "slug": "introducing-the-sunday-draft",
        "title": "Introducing The Sunday Draft",
        "meta_desc": "The debut episode: Raj and Kanti on why they started a podcast that reads like a Sunday newspaper over coffee — context and perspective instead of hot takes.",
        "date_display": "March 22, 2026",
        "iso_date": "2026-03-22",
        "duration": "27 min",
        "source": None,
        "spotify_id": None,
        "video_id": None,
        "apple_url": "https://podcasts.apple.com/us/podcast/introducing-the-sunday-draft/id1887351307?i=1000756835899&uo=4",
        "body_paragraphs": [
            "The debut episode of The Sunday Draft, co-hosted by Raj (based in the US) and Kanti (a veteran journalist based in India). The show is framed as a thoughtful, leisurely conversation — reading a Sunday newspaper over coffee — blending storytelling with current-affairs analysis to give listeners context and perspective rather than tell them what to think.",
            "Raj and Kanti open with the war involving Iran and its cascading effects on oil and energy markets, then ground it in what that actually looks like on the ground: LPG cylinder shortages in India, mandatory waiting periods of 25 to 45 days, rising premium petrol prices, and restaurants quietly cutting their menus to conserve gas.",
            "They talk about the slow decline of mainstream media, why podcasts, independent YouTube journalism, and Substack have become more trusted alternatives, and how Substack's shift toward video is starting to complement rather than compete with YouTube.",
            "The episode closes with why they built the show the way they did: a deliberately centrist, balanced space for conversation in a media landscape where polarization keeps replacing debate with argument.",
        ],
    },
]

with open("episodes/episodes.json") as f:
    manifest = json.load(f)

existing_slugs = {ep["slug"] for ep in manifest}
added = 0
for ep in NEW_EPISODES:
    if ep["slug"] in existing_slugs:
        print("skip (already exists):", ep["slug"])
        continue
    manifest.append(ep)
    added += 1

manifest.sort(key=lambda e: e["iso_date"])

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

print(f"Added {added} new episodes. Manifest now has {len(manifest)} total.")
