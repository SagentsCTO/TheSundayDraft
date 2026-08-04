# -*- coding: utf-8 -*-
import re, os

OUT = "episodes"
os.makedirs(OUT, exist_ok=True)

def paragraphize(text):
    # Insert paragraph breaks before common structural markers in these show notes.
    markers = [
        "Episode synopsis:", "Chapter 1", "Chapter 2", "Chapter 3", "Chapter 4",
        "Chapter 5", "Chapter 6", "Chapter 7", "Timestamps:", "TIMESTAMPS",
        "In this episode:", "We also talk about:", "We cover:", "Referenced in this episode:",
        "About The Sunday Draft", "About the show", "Key Topics Covered", "Key Timestamps",
        "🎧", "🎬", "📖", "🔗", "🎥", "▶️", "📌", "📣", "⏱️", "🎙️",
        "What We Get Into:", "Here's what we covered:", "Here's how our original doubts",
        "The report card", "The manifesto, revisited", "What's not in the manifesto",
        "The shadow hanging", "What's next", "The one-line recap",
    ]
    for m in markers:
        text = text.replace(m, "\n\n" + m)
    # Bullet markers "* " become their own lines
    text = re.sub(r"\s\*\s", "\n* ", text)
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    html_parts = []
    for part in parts:
        lines = [l.strip() for l in part.split("\n") if l.strip()]
        if all(l.startswith("* ") for l in lines) and len(lines) > 1:
            items = "".join(f"<li>{l[2:].strip()}</li>" for l in lines)
            html_parts.append(f"<ul>{items}</ul>")
        else:
            joined = " ".join(lines)
            html_parts.append(f"<p>{joined}</p>")
    return "\n".join(html_parts)

PAGE_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | The Sunday Draft</title>
<meta name="description" content="{meta_desc}">
<link rel="canonical" href="https://thesundaydraft.com/episodes/{slug}.html">

<meta property="og:title" content="{title} | The Sunday Draft">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:image" content="../assets/og-image.jpg">
<meta property="og:url" content="https://thesundaydraft.com/episodes/{slug}.html">
<meta name="twitter:card" content="summary_large_image">

<link rel="icon" href="../assets/favicon.png">
<link rel="apple-touch-icon" href="../assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../styles.css?v=7">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "PodcastEpisode",
  "name": {json_title},
  "description": {json_desc},
  "datePublished": "{iso_date}",
  "url": "https://thesundaydraft.com/episodes/{slug}.html",
  "partOfSeries": {{
    "@type": "PodcastSeries",
    "name": "The Sunday Draft",
    "url": "https://thesundaydraft.com"
  }},
  "associatedMedia": {{
    "@type": "MediaObject",
    "contentUrl": "https://open.spotify.com/episode/{spotify_id}"
  }}
}}
</script>
</head>
<body>

<header class="site-header">
  <div class="wrap header-inner">
    <a href="../index.html" class="logo"><img src="../assets/logo-wordmark.png" alt="The Sunday Draft" class="logo-img"></a>
    <nav class="nav">
      <a href="../index.html#episodes">Episodes</a>
      <a href="index.html">Archive</a>
      <a href="../index.html#listen">Listen</a>
      <a href="../index.html#about">About</a>
      <a href="../index.html#newsletter">Newsletter</a>
    </nav>
  </div>
</header>

<main>
  <article class="section episode-article">
    <div class="wrap wrap-narrow">
      <p class="eyebrow">{date_display} &middot; {duration}</p>
      <h1>{title}</h1>

      <div class="podcast-embed">
        <iframe src="https://open.spotify.com/embed/episode/{spotify_id}?utm_source=generator" width="100%" height="152" frameborder="0" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy" title="{title}"></iframe>
      </div>

      <div class="show-notes">
{body_html}
      </div>

      <p class="text-link"><a href="../index.html#listen">Find The Sunday Draft on YouTube, Spotify &amp; Apple Podcasts &rarr;</a></p>
      <p class="text-link"><a href="index.html">&larr; Back to all episodes</a></p>
    </div>
  </article>
</main>

<footer class="site-footer">
  <div class="wrap footer-inner">
    <p>&copy; <span id="year"></span> The Sunday Draft.</p>
    <div class="social-links">
      <a href="https://www.youtube.com/@TheSundayDraft" target="_blank" rel="noopener">YouTube</a>
      <a href="https://bsky.app/profile/thesundaydraft.bsky.social" target="_blank" rel="noopener">BlueSky</a>
      <a href="https://thesundaydraft.substack.com" target="_blank" rel="noopener">Substack</a>
    </div>
  </div>
</footer>

<script src="../script.js"></script>
</body>
</html>
"""

episodes = [
{
"slug": "is-the-internet-still-real",
"title": "Is the Internet Still Real? (with Ross Thorpe, founder of Rooverse)",
"meta_desc": "Ross Thorpe, founder of Rooverse, on building a human-only social platform, why 71% of images online are now AI-generated, and what it's doing to how we think.",
"date_display": "August 2, 2026",
"iso_date": "2026-08-02",
"duration": "58 min",
"spotify_id": "7BgHMIK52ggZwKQXZi3nv7",
"text": """This week on The Sunday Draft, श्रीraj sat down with Ross Thorpe — founder of Rooverse, a social media platform built on one radical rule: no AI, ever. Every post is human-verified. Every image, video, and piece of text is checked and blocked if it's AI-generated. We get into why he built it, whether a platform that refuses to use AI can actually survive as a business, and the bigger picture: research on how LLMs are quietly reshaping our ability to think, why dating apps are getting dystopian, and why Rooverse backs its data up in space (yes, literally). Episode synopsis: 71% of images uploaded online are now AI-generated. Over half of all internet traffic isn't human anymore. And the average 18-year-old will spend 25 years of their life scrolling. Ross Thorpe isn't just worried about it — he built something to fight it. In this conversation, we dig into the research behind AI's effect on how we think, what "authentic" even means anymore, and whether a human-only corner of the internet is a real business or a beautiful idea that can't scale. It's a conversation about trust, attention, and what we're actually giving up every time we open an app. If you've ever felt like the internet stopped feeling human — this one's for you.""",
},
{
"slug": "the-fixer-amjad-tadros",
"title": "The Fixer: 33 Years Inside the Middle East with CBS News' Amjad Tadros",
"meta_desc": "Amjad Tadros, the fixer who arranged access for CBS News and 60 Minutes across the Middle East for 33 years, on his book The Fixer and three decades of history.",
"date_display": "July 27, 2026",
"iso_date": "2026-07-27",
"duration": "1 hr 4 min",
"spotify_id": "1giaSPDIIoL7ssvBqVcTB0",
"text": """For 33 years, Amjad Tadros was the man CBS News and 60 Minutes relied on to get the story — the fixer who arranged access, built trust, and quietly made the impossible interviews happen across Iraq, Saudi Arabia, Qatar, Syria, Yemen, and beyond. He covered every Iraq war from 1990 to 2003, worked alongside legends like Ed Bradley, Bob Simon, and Mike Wallace, and even became an accidental, unwitting favorite of Saddam Hussein after a chance encounter as a young engineer turned translator. In this conversation, Amjad Tadros — now a date farmer in Jordan's Jordan Valley — talks about his book The Fixer, his front-row seat to three decades of Middle East history, and why he believes today's conflicts (including the current war with Iran) are eerie repeats of 2003. We get into the real cost of war beyond the headlines, the misunderstandings between the West and the Arab world, the death of legacy journalism, and what it's actually like to live a few miles from a falling missile. A rare, honest look at the region from someone who was actually there.""",
},
{
"slug": "indias-gen-z-movement-crisis",
"title": "India's Gen-Z Movement Crisis: Why Modi's Government Reacted Now",
"meta_desc": "Raj and returning co-host Kanti Kumar unpack India's Cockroach Janata Party protest movement, the Jantar Mantar hunger strikes, and the Modi government's first reaction.",
"date_display": "July 19, 2026",
"iso_date": "2026-07-19",
"duration": "54 min",
"spotify_id": "7IKHF8wjigmK8ljTrVK3P5",
"text": """Two months ago, a satirical jab at India's Chief Justice — who called Gen Z's unemployed youth "cockroaches" — sparked an online joke. That joke became the Cockroach Janata Party, and the joke became a movement: peaceful protests across India's major cities, weeks of hunger strikes at Jantar Mantar, and a single demand — the resignation of Education Minister Dharmendra Pradhan over years of leaked national exam papers and the students who paid the price for it. This week, the story took a turn. Environmentalist and educator Sonam Wangchuk, twenty days into a hunger strike in solidarity with the protesters, was removed from the site before dawn — quietly, and disguised as a medical procedure. He's continuing his fast in hospital. It's the first real reaction from the Modi government after weeks of silence. Raj is joined by returning co-host Kanti Kumar to unpack what's actually happening on the ground: the significance of Jantar Mantar as one of the only sanctioned protest sites in Delhi, the long and complicated history of hunger strikes as a tool of Indian protest — from Gandhi to Anna Hazare to the farmers' movement — and what happens when that tool meets a government unwilling to bend. They talk about the risk of the movement turning violent, why it hasn't, and why empathy — or the absence of it — might be the real story here. It's part news update, part reflection on what democracy owes its citizens between elections. And with a march to Parliament reportedly on the horizon, this might just be the beginning of the next phase.""",
},
{
"slug": "why-socialism-struggles",
"title": "Why Socialism Struggles: An Economist Takes on the Mamdani Effect",
"meta_desc": "Economist Dr. Doug Cardell joins to unpack democratic socialism, the Mamdani effect in New York, and five concrete reforms he proposes to fix American politics.",
"date_display": "July 12, 2026",
"iso_date": "2026-07-12",
"duration": "48 min",
"spotify_id": "49SOmVDKWuRkGw34YOG9ql",
"text": """Democratic socialism is on the rise in America — and it all traces back to one election. Zohran Mamdani becoming Mayor of New York City kicked off a wave of politicians breaking from traditional Democratic politics toward democratic socialism. But what actually IS democratic socialism, and how does it differ from capitalism, traditional socialism, and fascism? On this episode of The Sunday Draft, I sit down with Dr. Doug Cardell — economist, educator, U.S. veteran, former congressional aide, corporate CEO, and author of the bestseller "Why Socialism Struggles: Exposing the Economic Errors That Undermine Utopian Ideals" — to unpack it all. We cover: Why Dr. Cardell believes no economy can be centrally planned (the "complex systems" argument). A real-time report card on Mamdani's first 100 days — rent freezes, city-run grocery stores, and whether they'll actually work. The U-Haul Growth Index debate: is New York really seeing a mass exodus? Why Dr. Cardell argues fascism and socialism are closer to each other than people think — and why capitalism isn't the same thing as government. Five concrete reforms Dr. Cardell proposes to fix American politics regardless of your ideology: bill expiration dates, supermajority requirements, single-issue bills, restricting lobbying dollars, and fair redistricting. Kerala, India (my home state) as a real-world 70-year experiment in democratic socialism — and why voters just ended it. Why he wrote his book, and what he thinks is really at stake for the U.S. This is a respectful, substantive debate between two people who don't fully agree — and that's the point. Whatever side of this you're on, I think you'll walk away understanding the argument better.""",
},
{
"slug": "why-companies-arent-getting-roi-on-ai",
"title": "Why Companies Aren't Getting ROI on AI (with Brenn Hill)",
"meta_desc": "Engineering leader Brenn Hill breaks down the AI ROI myth, why token-based pricing fails for business planning, and his cost/verification/intent-clarity framework.",
"date_display": "July 6, 2026",
"iso_date": "2026-07-06",
"duration": "57 min",
"spotify_id": "0fHtfh4uAaP38UTqV4dzGR",
"text": """Everyone's spending big on AI coding tools — but is anyone actually measuring if it's working? In this episode, we're joined by Brenn Hill, a Berlin-based engineering leader and author of "The Delivery Gap," to break down the AI ROI myth: why token-based pricing is nearly useless for real business planning, why companies like Uber and Microsoft have pulled back on major AI investments, and the three-part framework (cost, verification, intent clarity) Brenn uses to actually measure whether AI is paying off. We also talk about: Why AI gets you "80% of the way there" — and why that's not the same as production-ready. Machine catch rate vs. change failure rate, and why they matter more than token counts. Why tokens can't be compared across AI providers or even across tasks. What it's like navigating Berlin's housing crisis as an American expat. Entrepreneurial culture differences between the US, Vietnam, and Australia. Brenn's book, "The Delivery Gap," lays out the research behind what's actually working (and mostly not) in AI-assisted software delivery — plus practical roadmaps for engineering leaders and individual contributors navigating this shift.""",
},
{
"slug": "think-your-way-out-of-billionaire-driven-ai-replacement",
"title": "Think Your Way Out of Billionaire-Driven AI Replacement",
"meta_desc": "Mohammed Nabil on AIDOP, a methodology for using AI to sharpen your own thinking, and a vision of collective intelligence and global citizen governance.",
"date_display": "June 28, 2026",
"iso_date": "2026-06-28",
"duration": "1 hr 22 min",
"spotify_id": "6PvenM3NZxaOSx0zMjKpPo",
"text": """Nabil went from spray-painting harassers' backs in Cairo to building a framework for how humans survive AI displacement. He's not pessimistic. He's proposing three interconnected ideas: a methodology for using AI to sharpen your thinking, a path to collective intelligence, and a vision of global citizen governance. This isn't abstract philosophy. It's actionable right now. And somewhat radical. Or is it? Listen for: how to use AI as a debate partner (not replacement), why billionaires won't voluntarily share AI gains, and what you can do about it. Chapter 1: Harass the Harassers — The Origin Story. Nabil shares how a campaign to fight sexual harassment in Cairo (2012-2015) led to legislation change, international coverage, and ultimately showed him the power of direct action against systems. Chapter 2: Why Both Experts and Mobs Are Wrong. Blind elitism, ignorant populism, and why algorithms push us into both traps. The introduction to Enlightened Populism. Chapter 3: AIDOP — Use AI to Sharpen Your Own Thinking. The methodology: prompt AI to criticize your work, publish the unedited debate within 24 hours. Revolutionary impact on education, policy, publishing, contracts. Chapter 4: What Global Governance Looks Like. Citizen assemblies, universal basic income, reduced work hours, and a world where creativity thrives because people have time to think. Chapter 5: The Feasibility Question. Hard truths: communities splinter, billionaires won't cooperate, distracted populations are hard to mobilize. But it's already happening globally in pockets. Chapter 6: Your First Action Step. Learn to prompt AI better. Make it debate you. Publish the transcript. That's AIDOP. That's how you start practicing Enlightened Populism today.""",
},
{
"slug": "we-left-a-piece-of-us-there",
"title": '"We Left a Piece of Us There" — Everest Base Camp Trek, Part 1',
"meta_desc": "Varun and Aneesh relive their March Everest Base Camp trek: the Lukla flight, Namche Bazaar, altitude sickness, and the truth behind the Sherpa \"scam\" headlines.",
"date_display": "June 22, 2026",
"iso_date": "2026-06-22",
"duration": "59 min",
"spotify_id": "0FIewYmjd4dyICFAbr265T",
"text": """Varun and Aneesh flew into one of the world's most dangerous airports, laced up their boots, and started walking. No warm-up day. No easing in. Just a 17-seat plane, a thin cotton curtain between them and the cockpit, and a Sherpa named Prakash setting the pace. In Part 1 of this two-part conversation, Raj sits down with Varun and Aneesh to relive their March EBC trek — from the frantic weather delays at Kathmandu's domestic terminal to the grueling uphill grind into Namche Bazaar. Along the way they get honest about overpacking, the surprisingly good toilets, dal bhat for every single meal, and why taking a hot shower at altitude nearly sent Varun into hypothermia. They also get into the story that was circulating online about Sherpa "scams" — and why, as always, the truth on the ground looked very different from the headlines. In this episode: why the time on your Lukla flight ticket is basically fiction, what "dal bhat power" actually means and why carbs rule the mountain, the Hillary Bridge, 800 steps, and the climb that will humble you, oxygen saturation checks, AMS symptoms, and how Prakash kept them honest, the two-sided story behind the helicopter evacuation "scam", and what Varun wishes he'd packed differently. Part 2 drops next week — Tengboche, Labuche, Gorak Shep, and the moment they finally saw Everest Base Camp.""",
},
{
"slug": "piff-paff-politics-cockroach-party-one-month-in",
"title": "Piff-Paff Politics: The Cockroach Party, One Month In",
"meta_desc": "A one-month report card on India's Cockroach Janata Party protest movement, its five-point manifesto, and the fear that it succeeds just enough to be absorbed.",
"date_display": "June 14, 2026",
"iso_date": "2026-06-14",
"duration": "1 hr 29 min",
"spotify_id": "04qzMdjLg3LdIfmjbVRJ78",
"text": """My cohost Nidhin and I have a complicated personal history with cockroaches. Growing up as NRI kids in the Gulf in the 80s and 90s, the first thing every household bought was a can of Piff Paff. Which, as it turns out, is exactly the branding logic behind the Cockroach Janata Party (CJP) — the satirical Indian youth movement that's been the subject of two episodes of The Sunday Draft now, three weeks apart. The one-line recap, for anyone just joining us: on May 15th, Chief Justice of India Surya Kant made an off-the-cuff remark during a Supreme Court hearing calling unemployed youngsters "cockroaches" and "parasites of society." The next day, a 30-year-old public relations student named Abhijeet Dipke turned the insult into a website, a manifesto, and an Instagram account. Within 78 hours: 3 million followers. Within a week: over 20 million. The report card, one month on covers how our original doubts have held up: is this genuine or astroturf, will Dipke actually show up, does it have a real leader, will it register as a political party, will it just die out as an online fad. The manifesto, revisited: the five-point manifesto hasn't changed a word since May 24th, including no Rajya Sabha seat for any retired Chief Justice, canceling media licenses owned by Ambani and Adani, and women's rights. What's not in the manifesto, interestingly, is anything about education — even though that's the actual demand driving every protest so far. The shadow hanging over all of this is the Aam Aadmi Party precedent: the fear isn't that CJP gets crushed, it's that it succeeds just enough to get absorbed. What's next: we're planning to bring on an actual Gen Z voice for a future episode, once this movement has been through a real test rather than just riding a growth curve.""",
},
{
"slug": "are-we-enabling-ai-to-replace-us",
"title": "Are We Enabling AI to Replace Us?",
"meta_desc": "Raj and his oldest friend Nidhin, both IT veterans, on the Mercor story, whether AI displacement hits in two years or five, and what happens after the jobs go.",
"date_display": "June 7, 2026",
"iso_date": "2026-06-07",
"duration": "1 hr 22 min",
"spotify_id": "1O8ToZVEiwP77SoLIU8GI1",
"text": """In this episode of The Sunday Draft, Raj sits down with his oldest friend and fellow IT veteran Nidhin for an honest, unfiltered conversation about the one question nobody wants to answer at work: are we actively enabling AI to replace us? These are two guys who started their careers in the post-dot-com era, survived every wave of tech change since, and are now staring down the biggest shift yet. What we get into: The Mercor Story — a $10 billion startup founded by three 21-year-olds is paying doctors, lawyers, engineers, and IT professionals $50–$150/hour to train AI models for Meta, OpenAI, and Anthropic, and what a growing wave of lawsuits and a major data breach reveal about what's really going on underneath the hood. The "2 Years vs 5 Years" Debate — Nidhin thinks IT professionals have about two years before AI fundamentally changes their jobs; Raj thinks maybe five. Can You Actually Trust Anthropic? — Raj questions whether Anthropic's "ethical AI" positioning is genuine conviction or just a smarter marketing strategy. What Happens After the Jobs Go? — the conversation goes beyond careers into what mass displacement actually does to society and the next generation entering a job market that looks nothing like the one we walked into. India, Unrest, and the Bigger Picture — connecting youth unemployment, political instability, and the AI wave hitting emerging markets, drawing a line from Bangladesh to what's stirring in India right now.""",
},
{
"slug": "raising-them-in-your-cage",
"title": "Raising Them in Your Cage — AMA with a Child Psychologist",
"meta_desc": "Child psychologist Tvarita Iyer Vemuri on Culture-Bound Syndromes, how parents pass anxiety to children through inherited rituals, screen addiction, and neurodivergence.",
"date_display": "May 31, 2026",
"iso_date": "2026-05-31",
"duration": "1 hr 34 min",
"spotify_id": "0zrJqsj9rRJ7k3PSD0NaDw",
"text": """This month's AMA started with a question most of us have never thought to ask: what if the anxiety your child carries isn't theirs? What if it was handed down — through rituals, rules, and family beliefs — before they were old enough to question any of it? Tvarita Iyer Vemuri, award-winning child psychologist and our resident expert on The Sunday Draft, joined श्रीraj and co-host Varun Vijay Nair for a wide-ranging conversation. Here's what we covered: What Culture-Bound Syndromes actually are — clinically recognised patterns of psychological distress that only exist within specific cultural frameworks, from Nazar to Dhat Syndrome. The CBS in disguise — everyday beliefs we pass to children without realising it, like "finish everything on your plate," which has a measurable link to emotional eating and obesity in adolescence. Screen addiction and what it's actually telling you — children addicted to screens almost always have an escape they needed; the device isn't the problem, it's filling a gap. Neurodivergence, over-diagnosis, and the wave of ADHD labels — partly people finally understanding themselves, partly a new problem with parents bringing in children for traits that are just personality. What a child-friendly society actually looks like — not structural, but about inclusion, and society catching up to children rather than asking children to hide. The closing image: a person is radiant when they are stress-free, happy, and content, and that happiness radiates outward. If we raise happier children, we get a happier society.""",
},
{
"slug": "troll-wars-explaining-indian-culture-to-the-internet",
"title": "Troll Wars: Explaining Indian Culture to the Internet",
"meta_desc": "Addressing the most common misconceptions and online trolling points about India's diverse population, languages, food, and traditions.",
"date_display": "May 25, 2026",
"iso_date": "2026-05-25",
"duration": "26 min",
"spotify_id": "2b7zyIJ6MVgAb38ecRjlDW",
"text": """In this episode, we address, dismantle, and answer the most common (and sometimes wacky) questions, misconceptions, and online trolling points regarding India's massive, diverse population and rich heritage. From language barriers to cultural traditions, we dive deep into what it truly means to navigate Indian identity in the digital age. Key topics covered: the reality of trolling and cultural misunderstanding, and how online discourse shapes and sometimes stereotypes Indian culture across global social media. The "language" myth — deconstructing the common misconception of "speaking Indian" and breaking down the sheer linguistic diversity of the subcontinent. Traditions vs. stereotypes — answering FAQs about daily life, modern clothing choices, regional culinary realities (no, not everyone is a vegetarian), and the religious significance behind historical traditions. Unity in massive diversity — how India blends ancient spiritual history with a highly active, modern digital population.""",
},
{
"slug": "is-the-era-of-cheap-oil-over",
"title": "Is the Era of Cheap Oil Over?",
"meta_desc": "Raj and Varun unpack the shifting landscape of global energy, geopolitical power plays, and whether America is ready to pivot away from cheap oil.",
"date_display": "May 17, 2026",
"iso_date": "2026-05-17",
"duration": "1 hr 22 min",
"spotify_id": "6GeerDqvvgHRXcNQkmG4Vg",
"text": """In this deep-dive episode of The Sunday Draft, Raj and Varun unpack the shifting landscape of global energy, geopolitical power plays, and what it means for the future of American society. From escalating military conflicts threatening trade routes to high-level diplomatic summits, they explore the fragile systems keeping the modern world running. Is the era of cheap energy officially over, and is America ready to pivot?""",
},
]

for ep in episodes:
    ep["body_html"] = paragraphize(ep["text"])
    ep["json_title"] = repr(ep["title"]).replace("'", '"') if False else __import__("json").dumps(ep["title"])
    ep["json_desc"] = __import__("json").dumps(ep["meta_desc"])

for ep in episodes:
    html = PAGE_TMPL.format(**ep)
    path = os.path.join(OUT, ep["slug"] + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", path)

# Archive index page
items_html = []
for ep in episodes:
    excerpt = ep["meta_desc"]
    items_html.append(f'''
    <a class="episode-list-item" href="{ep["slug"]}.html">
      <p class="eyebrow">{ep["date_display"]} &middot; {ep["duration"]}</p>
      <h3>{ep["title"]}</h3>
      <p>{excerpt}</p>
    </a>''')

INDEX_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>All Episodes | The Sunday Draft</title>
<meta name="description" content="Every episode of The Sunday Draft, with full show notes: geopolitics, technology, parenting, culture, and the human cost of policy.">
<link rel="canonical" href="https://thesundaydraft.com/episodes/index.html">
<link rel="icon" href="../assets/favicon.png">
<link rel="apple-touch-icon" href="../assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../styles.css?v=7">
</head>
<body>

<header class="site-header">
  <div class="wrap header-inner">
    <a href="../index.html" class="logo"><img src="../assets/logo-wordmark.png" alt="The Sunday Draft" class="logo-img"></a>
    <nav class="nav">
      <a href="../index.html#episodes">Latest</a>
      <a href="index.html">Archive</a>
      <a href="../index.html#listen">Listen</a>
      <a href="../index.html#about">About</a>
      <a href="../index.html#newsletter">Newsletter</a>
    </nav>
  </div>
</header>

<main>
  <section class="section episode-article">
    <div class="wrap wrap-narrow">
      <h1>All episodes</h1>
      <p class="section-sub" style="text-align:left; margin-left:0;">Full show notes for every conversation, in order.</p>
      <div class="episode-list">
{items}
      </div>
    </div>
  </section>
</main>

<footer class="site-footer">
  <div class="wrap footer-inner">
    <p>&copy; <span id="year"></span> The Sunday Draft.</p>
    <div class="social-links">
      <a href="https://www.youtube.com/@TheSundayDraft" target="_blank" rel="noopener">YouTube</a>
      <a href="https://bsky.app/profile/thesundaydraft.bsky.social" target="_blank" rel="noopener">BlueSky</a>
      <a href="https://thesundaydraft.substack.com" target="_blank" rel="noopener">Substack</a>
    </div>
  </div>
</footer>

<script src="../script.js"></script>
</body>
</html>
"""

with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
    f.write(INDEX_TMPL.format(items="".join(items_html)))
print("wrote", os.path.join(OUT, "index.html"))

