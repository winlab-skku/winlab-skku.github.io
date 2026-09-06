#!/usr/bin/env python3
"""Build the site. Run `python3 build.py` after editing data/pubs.txt or this file."""
import html, re, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
THEME = sys.argv[1] if len(sys.argv) > 1 else "base"
OUT = ROOT if THEME == "base" else os.path.join(ROOT, "variants", THEME)
LAB = "Wireless Intelligence Lab"
LAB_SHORT = "WIn Lab"
UNIV = "Sungkyunkwan University"
LAB_MEMBER = "Kisong Lee"        # names to bold in publication lists

PAGES = [("Home", "index.html"), ("Members", "members/index.html"),
         ("Publications", "publications/index.html"), ("News", "news/index.html")]


def shell(title, body, depth, current):
    up = "../" * depth
    nav = "".join(
        f'<li><a href="{up}{href}"{" aria-current=\"page\"" if name == current else ""}>{name}</a></li>'
        for name, href in PAGES)
    full = f"{LAB} ({LAB_SHORT})" if current == "Home" else f"{title} — {LAB}"
    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{full}</title>
  <link rel="stylesheet" href="{up}assets/style.css">
</head>
<body class="page-{current.lower()}">"""
    foot = """      School of Electronic and Electrical Engineering<br>
      Sungkyunkwan University, Suwon 16419<br>
      <a href="mailto:kisonglee@skku.edu">kisonglee@skku.edu</a>"""
    if THEME == "base":
        return f"""{head}
<div class="frame">
  <aside class="side">
    <div>
      <a class="brand" href="{up}index.html">{LAB}<small>{LAB_SHORT} · {UNIV}</small></a>
      <ul class="nav">{nav}</ul>
    </div>
    <div class="side-foot">
{foot}
    </div>
  </aside>
  <main class="main">
{body}
  </main>
</div>
</body>
</html>
"""
    return f"""{head}
<header class="top">
  <div class="wrap">
    <a class="brand" href="{up}index.html"><span class="short">{LAB_SHORT}</span><span class="long">{LAB}</span></a>
    <nav><ul class="nav">{nav}</ul></nav>
  </div>
</header>
<main class="main wrap">
{body}
</main>
<footer class="foot">
  <div class="wrap">
    <div>{LAB} · {UNIV}</div>
    <div>{foot.replace("<br>", " · ")}</div>
  </div>
</footer>
</body>
</html>
"""


def write(path, content):
    p = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(content)


# ---------- Publications ----------
def parse_pubs():
    sections, cur = [], None
    for line in open(os.path.join(ROOT, "data/pubs.txt"), encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            cur = (line[3:], [])
            sections.append(cur)
            continue
        m = re.match(r'(.*?),?\s*“(.*?),?”\s*(.*)', line)
        if not m:
            raise ValueError("Cannot parse: " + line)
        authors, title, rest = m.groups()
        meta = ""
        mm = re.match(r'(.*?)\s*\((IF.*)\)\s*$', rest)
        if mm:
            rest, meta = mm.group(1), mm.group(2)
        cur[1].append((authors, title, rest, meta))
    return sections


def fmt_authors(a):
    a = html.escape(a)
    a = a.replace("*" + LAB_MEMBER, f"<b>{LAB_MEMBER}</b><sup>*</sup>")
    a = re.sub(rf'(?<!<b>){LAB_MEMBER}(?!</b>)', f"<b>{LAB_MEMBER}</b>", a)
    return a


def build_publications():
    secs = parse_pubs()
    published = sum(len(s[1]) for s in secs if s[0] not in ("Under Review", "Early Access"))
    anchors = "".join(f'<a href="#{slug(n)}">{html.escape(n)}</a>' for n, _ in secs)
    out = [f"<h1>Publications</h1>",
           f'<p class="lede">{published} published journal articles, plus papers in press and under review.<br><sup>*</sup> marks the corresponding author.</p>',
           f'<nav class="pub-nav">{anchors}</nav>']
    for name, items in secs:
        sub = ""
        if name == "Under Review": sub = "<small>Submitted and in revision</small>"
        if name == "Early Access": sub = "<small>Accepted, in press</small>"
        rows = []
        for i, (authors, title, rest, meta) in enumerate(items, 1):
            rows.append(f"""        <li class="pub"><span class="num">{i}</span><div>
          <span class="title">{html.escape(title)}</span>
          <span class="authors">{fmt_authors(authors)}</span>
          <span class="venue">{html.escape(rest)}</span>
          {f'<span class="meta">{html.escape(meta)}</span>' if meta else ''}
        </div></li>""")
        out.append(f'    <section class="year" id="{slug(name)}">\n      <h2 class="{'label' if not name[0].isdigit() else ''}">{html.escape(name)}{sub}</h2>\n      <ul class="pubs">\n'
                   + "\n".join(rows) + "\n      </ul>\n    </section>")
    write("publications/index.html", shell("Publications", "\n".join(out), 1, "Publications"))


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# ---------- Home ----------
def build_home():
    updates = "\n".join(
        f'<li><time datetime="{d}">{label}</time><span>{html.escape(t)}</span></li>'
        for d, label, t, _ in NEWS[:8])
    body = f"""    <h1>Wireless Intelligence Lab</h1>
    <p class="lede">Optimization and learning for intelligent wireless networks, from the ground to the sky. We design UAV and satellite communications, wireless-powered networks, and secure resource allocation using both classical optimization and deep learning.</p>
    <p class="affil">School of Electronic and Electrical Engineering, Sungkyunkwan University<br>Directed by Prof. <a href="members/index.html">Kisong Lee</a></p>

    <section class="section">
      <h2>Research areas</h2>
      <div>
        <ul class="areas">
          <li><strong>Aerial and satellite communications</strong><span>UAV trajectory design, multi-UAV coordination, LEO satellite beam placement, and space-air-ground integrated networks.</span></li>
          <li><strong>Online and offline optimization</strong><span>Convex, combinatorial, and learning-based resource allocation with practical channel models such as building blockage and probabilistic LoS.</span></li>
          <li><strong>Energy ICT</strong><span>Wireless power transfer, energy harvesting, and self-sustaining networks.</span></li>
          <li><strong>Information security</strong><span>Physical-layer security, cooperative jamming, and anti-jamming communications.</span></li>
          <li><strong>Agentic AI communications</strong><span>AI agents for designing and operating communication systems, edge inference, and wireless federated learning.</span></li>
        </ul>
      </div>
    </section>

    <section class="section">
      <h2>Updates</h2>
      <div>
        <ul class="news-teaser">
{updates}
        </ul>
        <p style="margin-top:16px"><a href="news/index.html">All updates</a></p>
      </div>
    </section>

    <section class="section">
      <h2>Recruitment</h2>
      <div>
        <p>We are looking for graduate students and undergraduate researchers with a passion for wireless communications, optimization, and machine learning. If you are interested, contact Prof. Lee at <a href="mailto:kisonglee@skku.edu">kisonglee@skku.edu</a> with a short introduction and your CV.</p>
      </div>
    </section>"""
    write("index.html", shell("Home", body, 0, "Home"))


# ---------- People ----------
PROF = {
    "en": "Kisong Lee", "ko": "이기송",
    "role": "Professor, School of Electronic and Electrical Engineering",
    "email": "kisonglee@skku.edu",
    "interest": "Online/offline optimization, energy ICT, information security, aerial and satellite communications, agentic AI communications",
    "education": [
        ("Aug. 2013", "Ph.D. in Electrical Engineering, KAIST (Advisor: Prof. Dong-Ho Cho)"),
        ("Aug. 2009", "M.S. in Electrical Engineering, KAIST"),
        ("Aug. 2007", "B.S. in Electrical Engineering, KAIST"),
    ],
    "experience": [
        ("2026.09 –", "Professor, Sungkyunkwan University"),
        ("2020.03 – 2026.08", "Professor / Associate Professor, Dongguk University"),
        ("2017.09 – 2020.02", "Associate / Assistant Professor, Chungbuk National University"),
        ("2015.03 – 2017.08", "Assistant Professor, Kunsan National University"),
        ("2013.09 – 2015.02", "Researcher, ETRI"),
        ("2024.07 –", "IEEE Senior Member"),
    ],
}

# (English name, Korean name, course, email, research interest). Fill in the TODO fields.
GRAD = [
    ("Gitae Park", "박기태", "Graduate student (20XX.03 ~)", "TODO@skku.edu", "UAV communications, non-terrestrial networks, federated learning"),
    ("Chaeyeon Kim", "김채연", "Graduate student (20XX.03 ~)", "TODO@skku.edu", "UAV placement and beamforming, LEO satellite systems"),
    ("Gihyeon Jang", "장기현", "Graduate student (20XX.03 ~)", "TODO@skku.edu", "UAV–UGV cooperative delivery"),
    ("Hyungwoo Lee", "이형우", "Graduate student (20XX.03 ~)", "TODO@skku.edu", "Blockage-aware UAV communications, RSMA"),
]
UNDERGRAD = [
    ("Kangwoo Cho", "조강우", "Undergraduate researcher (20XX.XX ~)", "TODO@skku.edu", "Anti-jamming communications, UAV swarms"),
    ("Donghee Kim", "김동희", "Undergraduate researcher (20XX.XX ~)", "TODO@skku.edu", "UAV-enabled secure communications"),
    ("Eunki Lee", "이은기", "Undergraduate researcher (20XX.XX ~)", "TODO@skku.edu", "Wireless communications"),
    ("Jaejin Lee", "이재진", "Undergraduate researcher (20XX.XX ~)", "TODO@skku.edu", "Wireless communications"),
    ("Garam Cho", "조가람", "Undergraduate researcher (20XX.XX ~)", "TODO@skku.edu", "Wireless communications"),
]
ALUMNI = [
    ("Seungeun Lee", "이승은", "Undergraduate researcher", "", "Current position: TODO"),
]


def obfuscate(email):
    return email


def person(en, ko, course, email, interest):
    slug_ = en.lower().replace(" ", "-")
    rows = f"<li><span>Course</span><span>{html.escape(course)}</span></li>"
    if email:
        rows += f'<li><span>E-mail</span><span><a href="mailto:{email}">{obfuscate(email)}</a></span></li>'
    if interest:
        rows += f"<li><span>Interest</span><span>{html.escape(interest)}</span></li>"
    return f"""          <li class="person">
            <div class="photo"><img src="../assets/photos/{slug_}.jpg" alt="" onerror="this.remove()"></div>
            <div>
              <h3>{en} <span class="ko">{ko}</span></h3>
              <ul class="fields">{rows}</ul>
            </div>
          </li>"""


def build_people():
    P = PROF
    cv = lambda rows: "".join(f"<li><span>{d}</span><span>{html.escape(t)}</span></li>" for d, t in rows)
    grad = "\n".join(person(*m) for m in GRAD)
    ug = "\n".join(person(*m) for m in UNDERGRAD)
    al = "\n".join(person(*m) for m in ALUMNI)
    body = f"""    <h1>Members</h1>

    <section class="section">
      <h2>Professor</h2>
      <div>
        <ul class="people">
          <li class="person prof">
            <div class="photo"><img src="../assets/photos/kisong-lee.jpg" alt="" onerror="this.remove()"></div>
            <div>
              <h3>{P["en"]} <span class="ko">{P["ko"]}</span></h3>
              <div class="role">{P["role"]}</div>
              <ul class="fields">
                <li><span>E-mail</span><span><a href="mailto:{P["email"]}">{obfuscate(P["email"])}</a></span></li>
                <li><span>Interest</span><span>{P["interest"]}</span></li>
                <li><span>Education</span><ul class="sub">{cv(P["education"])}</ul></li>
                <li><span>Experience</span><ul class="sub">{cv(P["experience"])}</ul></li>
              </ul>
            </div>
          </li>
        </ul>
      </div>
    </section>

    <section class="section">
      <h2>Graduate students</h2>
      <div><ul class="people">
{grad}
      </ul></div>
    </section>

    <section class="section">
      <h2>Undergraduate students</h2>
      <div><ul class="people">
{ug}
      </ul></div>
    </section>

    <section class="section">
      <h2>Alumni</h2>
      <div><ul class="people">
{al}
      </ul></div>
    </section>"""
    write("members/index.html", shell("Members", body, 1, "Members"))


# ---------- News ----------
NEWS = [
    ("2026-09-01", "Sep 1, 2026", "Lab moves to Sungkyunkwan University",
     "Prof. Kisong Lee joins the School of Electronic and Electrical Engineering at Sungkyunkwan University as Professor."),
    ("2026-06", "Jun 2026", "Undergraduate Paper Award, KICS Summer Conference",
     "Encouragement Prize for an undergraduate paper at the 2026 KICS Summer Conference (한국통신학회 하계학술대회 학부우수논문상 장려상)."),
    ("2026-02", "Feb 2026", "Haedong Best Paper Award, KICS Winter Conference",
     "Excellence Prize at the 2026 KICS Winter Conference (해동우수논문상 우수상)."),
    ("2025-11", "Nov 2025", "Best Paper Award, KICS Summer Conference",
     "Best paper award at the 2025 KICS Summer Conference (한국통신학회 하계학술대회 우수논문상)."),
    ("2025-01", "Jan 2025", "Best Paper Award at IEEE ICOIN 2025",
     "Awarded by the IEEE Computer Society at the International Conference on Information Networking."),
    ("2024-12", "Dec 2024", "Haedong Young Engineer Award",
     "Prof. Lee receives the Haedong Young Engineer Award (Academic) from KICS and the Haedong Foundation (해동젊은공학인상 학술상)."),
    ("2024-07", "Jul 2024", "IEEE Senior Member",
     "Prof. Lee is elevated to IEEE Senior Member."),
    ("2023-06", "Jun 2023", "Haedong Best Paper Award, KICS Summer Conference",
     "Excellence Prize at the 2023 KICS Summer Conference (해동우수논문상 우수상)."),
    ("2020-07", "Jul 2020", "30th Excellent Science and Technology Paper Award",
     "Awarded by the Korean Federation of Science and Technology Societies (제30회 과학기술우수논문상, 한국과학기술단체총연합회)."),
    ("2019-11", "Nov 2019", "Best Paper Award, KICS Summer Conference",
     "Best paper award at the 2019 KICS Summer Conference."),
    ("2018-11", "Nov 2018", "Two KICS awards",
     "Best Paper Award for the KICS domestic journal and Best Paper Award at the 2018 KICS Summer Conference."),
    ("2013-04", "Apr 2013", "Kim Choong-Ki Award, KAIST",
     "Research Excellence Award, KAIST."),
]


def build_news():
    items = "\n".join(f"""      <li>
        <time datetime="{d}">{label}</time>
        <div><h3>{html.escape(t)}</h3><p>{html.escape(p)}</p></div>
      </li>""" for d, label, t, p in NEWS)
    body = f'    <h1>News</h1>\n    <ul class="news">\n{items}\n    </ul>'
    write("news/index.html", shell("News", body, 1, "News"))


if __name__ == "__main__":
    build_home(); build_people(); build_publications(); build_news()
    print("built")
