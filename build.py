#!/usr/bin/env python3
"""Build the WIn Lab website into ./docs (the folder GitHub Pages serves).

    python3 build.py

All content lives in data/site.json and data/publications.json (outside ./docs).
Edit them with the admin page (python3 admin.py, or admin.exe) or by hand, then rebuild.
"""
import html, json, os, re, sys, hashlib

ROOT = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
SITE = os.path.join(ROOT, "docs")            # GitHub Pages serves this folder (Settings → Pages → /docs)
DATA = os.path.join(ROOT, "data")            # source data (stays local)
SITE_JSON = os.path.join(DATA, "site.json")
PUBS_JSON = os.path.join(DATA, "publications.json")

PAGES = [("Home", ""), ("Members", "members/"), ("Publications", "publications/"), ("News", "news/")]
OUTPUT_FILES = ["index.html", "members/index.html", "publications/index.html", "news/index.html"]


def load():
    site = json.load(open(SITE_JSON, encoding="utf-8"))
    pubs = json.load(open(PUBS_JSON, encoding="utf-8"))
    return site, pubs


# ---------------------------------------------------------------- helpers

def esc(s):
    return html.escape(str(s))


def write(path, content):
    p = os.path.join(SITE, path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    open(p, "w", encoding="utf-8").write(content)


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def asset_version(path):
    try:
        return hashlib.md5(open(os.path.join(SITE, path), "rb").read()).hexdigest()[:8]
    except FileNotFoundError:
        return "0"


def shell(site, title, body, depth, current):
    lab = site["lab"]
    up = "../" * depth
    nav = "".join(
        f'<li><a href="{up}{href or "./"}"{" aria-current=\"page\"" if name == current else ""}>{name}</a></li>'
        for name, href in PAGES)
    full = f'{lab["name"]} ({lab["short"]})' if current == "Home" else f'{title} — {lab["name"]}'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="format-detection" content="telephone=no">
  <title>{esc(full)}</title>
  <meta name="description" content="{esc(lab['name'])} ({esc(lab['short'])}), {esc(lab['university'])}. {esc(lab['tagline'])}">
  <link rel="icon" href="{up}assets/favicon.svg">
  <link rel="stylesheet" href="{up}assets/style.css?v={asset_version('assets/style.css')}">
</head>
<body class="page-{current.lower()}">
<header class="top">
  <div class="wrap">
    <a class="brand" href="{up or './'}"><span class="short">{esc(lab['short'])}</span><span class="long">{esc(lab['name'])}</span></a>
    <nav><ul class="nav">{nav}</ul></nav>
  </div>
</header>
<main class="main wrap">
{body}
</main>
<footer class="foot">
  <div class="wrap">
    <div>{esc(lab['name'])} · {esc(lab['university'])}</div>
    <div>{esc(lab['address'])} · <a href="mailto:{esc(lab['email'])}">{esc(lab['email'])}</a></div>
  </div>
</footer>
</body>
</html>
"""


# ---------------------------------------------------------------- publications

def lab_members(site):
    return ([site["professor"]["en"]] + [m["en"] for m in site["graduate"]] +
            [m["en"] for m in site["undergraduate"]] + [a["name"] for a in site["alumni"]])


def fmt_authors(site, a):
    """Bold every lab member (current and alumni); '*' becomes a superscript after the name."""
    a = esc(a)
    for name in lab_members(site):
        if not name:
            continue
        a = re.sub(rf'(\*?)(?<![\w>]){re.escape(name)}(?![\w<])',
                   lambda m: f"<b>{name}</b>" + ("<sup>*</sup>" if m.group(1) else ""), a)
    return a


def is_top(it):
    """Top-journal rule, reverse-engineered from the professor's old site: every entry whose IF note carries a
    'Top N%' JCR rank was highlighted (largest N seen: 13.59%), entries with an IF but no rank were not."""
    return bool(re.search(r'Top\s*\d', it.get("meta", "")))


def fmt_venue(it, status=None):
    """Venue text; for top journals, only the journal name (text before the first comma) is bolded."""
    v = status if status is not None else it["venue"]
    if is_top(it) and "," in v:
        j, rest = v.split(",", 1)
        return f"<b>{esc(j)}</b>,{esc(rest)}"
    return esc(v)


def grouped(pubs):
    return [(sec, [it for it in pubs["items"] if it["section"] == sec]) for sec in pubs["sections"]]


def build_publications(site, pubs):
    secs = grouped(pubs)
    published = sum(len(items) for sec, items in secs if sec not in ("Under Review", "Early Access"))
    anchors = "".join(f'<a href="#{slug(n)}">{esc(n)}</a>' for n, items in secs if items)
    out = ["<h1>Publications</h1>",
           f'<p class="lede">{published} published journal articles, plus papers in press and under review.<br>Lab members are shown in bold; <sup>*</sup> marks the corresponding author.</p>',
           f'<nav class="pub-nav">{anchors}</nav>']
    for name, items in secs:
        if not items:
            continue
        sub = ""
        if name == "Under Review": sub = "<small>Submitted and in revision</small>"
        if name == "Early Access": sub = "<small>Accepted, in press</small>"
        rows = []
        for i, it in enumerate(items, 1):
            top = " is-top" if is_top(it) else ""
            rows.append(f"""        <li class="pub{top}"><span class="num">{i}</span><div>
          <span class="title">{esc(it['title'])}</span>
          <span class="authors">{fmt_authors(site, it['authors'])}</span>
          <span class="venue">{fmt_venue(it)}</span>
          {f'<span class="meta">{esc(it["meta"])}</span>' if it.get('meta') else ''}
        </div></li>""")
        cls = "label" if not name[0].isdigit() else ""
        out.append(f'    <section class="year" id="{slug(name)}">\n      <h2 class="{cls}">{esc(name)}{sub}</h2>\n      <ul class="pubs">\n'
                   + "\n".join(rows) + "\n      </ul>\n    </section>")
    write("publications/index.html", shell(site, "Publications", "\n".join(out), 1, "Publications"))


def pubs_for(pubs, name):
    return [it for it in pubs["items"] if re.search(rf'(?<!\w){re.escape(name)}(?!\w)', it["authors"])]


def _pub_rows(site, items):
    rows = []
    for it in items:
        sec, rest = it["section"], it["venue"]
        if sec == "Early Access":
            status = re.sub(r',\s*Accepted$', "", rest) + ", accepted"
        else:
            status = rest
        top = ' class="is-top"' if is_top(it) else ""
        rows.append(f'<li{top}><span class="t">{esc(it["title"])}</span><span class="a">{fmt_authors(site, it["authors"])}</span><span class="v">{fmt_venue(it, status)}</span></li>')
    return rows


def _collapsible(rows, n_vis):
    head, tail = rows[:n_vis], rows[n_vis:]
    out = f'<ol class="mini-pubs">{"".join(head)}</ol>'
    if tail:
        out += (f'<div class="more" hidden><ol class="mini-pubs" start="{len(head) + 1}">{"".join(tail)}</ol></div>'
                f'<button type="button" class="toggle" aria-expanded="false" data-more="Show more ({len(tail)})" data-less="Show less">Show more ({len(tail)})</button>')
    return out


def member_pubs_html(site, pubs, name):
    """Two fields: 'Publications' = accepted (Early Access) + published, newest first, following the order of
    publications.json (Early Access, then years descending); 'Under Review' = submitted/in revision."""
    items = pubs_for(pubs, name)
    if not items:
        return ""
    n_vis = int(site["settings"].get("member_pubs_visible", 3))
    published = [it for it in items if it["section"] != "Under Review"]
    review = [it for it in items if it["section"] == "Under Review"]
    out = ""
    if published:
        out += f'<li class="pubs-field"><span>Publications</span><div>{_collapsible(_pub_rows(site, published), n_vis)}</div></li>'
    if review:
        out += f'<li class="pubs-field"><span>Under Review</span><div>{_collapsible(_pub_rows(site, review), n_vis)}</div></li>'
    return out


# ---------------------------------------------------------------- pages

def build_home(site):
    lab = site["lab"]
    areas = "\n".join(f"""          <li>
            <img src="assets/research/{esc(r['image'])}" alt="" loading="lazy">
            <strong>{esc(r['title'])}</strong><span>{esc(r['text'])}</span>
          </li>""" for r in site["research"])
    n = int(site["settings"].get("home_updates", 8))
    updates = "\n".join(
        f'<li><time datetime="{esc(x["date"])}">{esc(x["label"])}</time><span>{esc(x["title"])}</span></li>'
        for x in site["news"][:n])
    recruit = esc(lab["recruitment"]).replace(esc(lab["email"]), f'<a href="mailto:{esc(lab["email"])}">{esc(lab["email"])}</a>')
    body = f"""    <h1>{esc(lab['name'])}</h1>
    <p class="lede">{esc(lab['tagline'])}</p>
    <p class="affil">{esc(lab['affiliation'])}<br>Directed by Prof. <a href="members/">{esc(site['professor']['en'])}</a></p>

    <section class="section">
      <h2>Research areas</h2>
      <div>
        <ul class="areas">
{areas}
        </ul>
      </div>
    </section>

    <section class="section">
      <h2>Updates</h2>
      <div>
        <ul class="news-teaser">
{updates}
        </ul>
        <p style="margin-top:16px"><a href="news/">All updates</a></p>
      </div>
    </section>

    <section class="section">
      <h2>Recruitment</h2>
      <div>
        <p>{recruit}</p>
      </div>
    </section>"""
    write("index.html", shell(site, "Home", body, 0, "Home"))


def person(site, pubs, m, with_pubs):
    rows = f"<li><span>Course</span><span>{esc(m.get('course', ''))}</span></li>"
    if m.get("email"):
        rows += f'<li><span>E-mail</span><span><a href="mailto:{esc(m["email"])}">{esc(m["email"])}</a></span></li>'
    if m.get("interest"):
        rows += f"<li><span>Interest</span><span>{esc(m['interest'])}</span></li>"
    if with_pubs:
        rows += member_pubs_html(site, pubs, m["en"])
    return f"""          <li class="person">
            <div class="photo"><img src="../assets/photos/{slug(m['en'])}.jpg" alt="" onerror="this.remove()"></div>
            <div>
              <h3>{esc(m['en'])} <span class="ko">{esc(m.get('ko', ''))}</span></h3>
              <ul class="fields">{rows}</ul>
            </div>
          </li>"""


def build_members(site, pubs):
    P = site["professor"]
    cv = lambda rows: "".join(f"<li><span>{esc(r['date'])}</span><span>{esc(r['text'])}</span></li>" for r in rows)
    grad = "\n".join(person(site, pubs, m, True) for m in site["graduate"])
    ug = "\n".join(person(site, pubs, m, site["settings"].get("show_undergrad_pubs", True)) for m in site["undergraduate"])
    alumni = "\n".join(f'<li><strong>{esc(a["name"])}</strong><span>{esc(a["affiliation"])}</span></li>' for a in site["alumni"])
    body = f"""    <h1>Members</h1>

    <section class="section">
      <h2>Professor</h2>
      <div>
        <ul class="people">
          <li class="person prof">
            <div class="photo"><img src="../assets/photos/{slug(P['en'])}.jpg" alt="" onerror="this.remove()"></div>
            <div>
              <h3>{esc(P['en'])} <span class="ko">{esc(P['ko'])}</span></h3>
              <div class="role">{esc(P['role'])}</div>
              <ul class="fields">
                <li><span>E-mail</span><span><a href="mailto:{esc(P['email'])}">{esc(P['email'])}</a></span></li>
                <li><span>Office</span><span>{esc(P['office'])}</span></li>
                <li><span>Interest</span><span>{esc(P['interest'])}</span></li>
                <li><span>Education</span><ul class="sub">{cv(P['education'])}</ul></li>
                <li><span>Experience</span><ul class="sub">{cv(P['experience'])}</ul></li>
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
      <div>
        <ul class="alumni">
{alumni}
        </ul>
      </div>
    </section>
    <script>
    document.querySelectorAll('.toggle').forEach(function (btn) {{
      var box = btn.previousElementSibling;
      btn.addEventListener('click', function () {{
        var open = btn.getAttribute('aria-expanded') === 'true';
        if (open) {{
          box.classList.remove('open');
          box.addEventListener('transitionend', function h() {{ box.hidden = true; box.removeEventListener('transitionend', h); }});
        }} else {{
          box.hidden = false;
          requestAnimationFrame(function () {{ requestAnimationFrame(function () {{ box.classList.add('open'); }}); }});
        }}
        btn.setAttribute('aria-expanded', String(!open));
        btn.textContent = open ? btn.dataset.more : btn.dataset.less;
      }});
    }});
    </script>"""
    write("members/index.html", shell(site, "Members", body, 1, "Members"))


def build_news(site):
    items = "\n".join(f"""      <li>
        <time datetime="{esc(x['date'])}">{esc(x['label'])}</time>
        <div><h3>{esc(x['title'])}</h3><p>{esc(x['text'])}</p></div>
      </li>""" for x in site["news"])
    body = f'    <h1>News</h1>\n    <ul class="news">\n{items}\n    </ul>'
    write("news/index.html", shell(site, "News", body, 1, "News"))


# ---------------------------------------------------------------- images

def optimize_images():
    """Downscale oversized images in place. Member photos → 480x640 (3:4). Research images → max 800px.
    Returns the list of files that were rewritten."""
    changed = []
    try:
        from PIL import Image, ImageOps
    except ImportError:
        print("Pillow not installed; skipping image optimization (pip install pillow)")
        return changed
    photos = os.path.join(SITE, "assets/photos")
    for f in sorted(os.listdir(photos)) if os.path.isdir(photos) else []:
        p = os.path.join(photos, f)
        if not f.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        if im.width <= 480 and im.height <= 640 and abs(im.width / im.height - 0.75) < 0.02:
            continue
        im = ImageOps.fit(im, (480, 640), Image.LANCZOS, centering=(0.5, 0.4))
        im.save(p, "JPEG", quality=86, optimize=True)
        changed.append("assets/photos/" + f)
    research = os.path.join(SITE, "assets/research")
    for f in sorted(os.listdir(research)) if os.path.isdir(research) else []:
        p = os.path.join(research, f)
        im = Image.open(p)
        if max(im.size) > 800:
            im.convert("RGB").resize((800, int(800 * im.height / im.width)), Image.LANCZOS).save(p, "JPEG", quality=86, optimize=True)
            changed.append("assets/research/" + f)
    return changed


def build():
    changed = optimize_images()
    site, pubs = load()
    build_home(site); build_members(site, pubs); build_publications(site, pubs); build_news(site)
    return changed + OUTPUT_FILES


if __name__ == "__main__":
    for f in build():
        print("wrote", f)
