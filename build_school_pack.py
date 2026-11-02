#!/usr/bin/env python3
"""
build_school_pack.py — ATHENA School Edition static pages
=========================================================
Turns school/scenes/*.md into site/school/: a pack page, one page per scene, one print page with all
three scripts, and the matching Homer text. The full edition (site/index.html) is never touched.

USAGE:
  python3 build_school_pack.py                 # writes site/school/ and refreshes site/sitemap.xml
  python3 build_school_pack.py --out DIR       # same, into DIR/school/
  python3 build_school_pack.py --preview DIR   # a private preview: links name their files, no print buttons
  python3 build_school_pack.py --extract-homer # refresh school/homer/*.txt from the Arc library (Butcher & Lang)
  python3 build_school_pack.py --cards         # re-render the link-preview images (needs google-chrome)

Before publishing, Ross decides the license. Until LICENSE_DECIDED is True every page carries a draft banner and a noindex tag.
"""

import html
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

import yaml

from build_athena_site import SITE_URL, write_sitemap

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "school")
MANUSCRIPT = os.path.join(HERE, "ATHENA_manuscript.md")

# Ross's call before publishing. Flip to True once he has chosen, and edit the license lines if he chooses another.
LICENSE_DECIDED = False
LICENSE_NAME = "CC BY-NC-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
CONTACT = "ross@arc-codex.com"     # already public on arc-codex.com/about
WORDS_PER_MINUTE = 130             # a steady reading aloud; staged_seconds in each scene adds the wordless action
PACK = "Athena School Edition"
HOMER_BOOKS = {"book-05": "V", "book-09": "IX", "book-23": "XXIII"}
LIBRARY_DB = "/srv/library/library.db"
BUTCHER_LANG_ID = 1728
PREVIEW = False                    # set by --preview

STAGE_RE = re.compile(r"^\[STAGING:\s*(.*)\]$")
BEAT_RE = re.compile(r"^\[BEAT (IN|OUT)(?::\s*(.*))?\]$")
FULL_DIR_RE = re.compile(r"^\([^()]*\)$")
PAREN_RE = re.compile(r"\(([^()]*)\)")


# ── scenes ─────────────────────────────────────────────────────────────────────
def parse_body(body):
    """Script lines → [('speaker', name) | ('stage', text) | ('beat', in/out, text) | ('line', text, is_bar) | ('gap',)]"""
    items = []
    for raw in body.split("\n"):
        line = raw.strip()
        if not line:
            continue
        stage, beat = STAGE_RE.match(line), BEAT_RE.match(line)
        if line.startswith("### "):
            items.append(("speaker", line[4:].strip()))
        elif stage:
            items.append(("stage", stage.group(1)))
        elif beat:
            items.append(("beat", beat.group(1), beat.group(2) or ""))
        elif line == "|":
            items.append(("gap",))
        elif line.startswith("| "):
            items.append(("line", line[2:], True))
        else:
            items.append(("line", line, False))
    return items


def spoken_words(items):
    return sum(len(PAREN_RE.sub(" ", i[1]).split()) for i in items if i[0] == "line")


def load_scenes():
    scenes = []
    folder = os.path.join(SRC, "scenes")
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            _, front, body = f.read().split("---\n", 2)
        scene = yaml.safe_load(front)
        scene["items"] = parse_body(body)
        scene["words"] = spoken_words(scene["items"])
        scene["minutes"] = round(scene["words"] / WORDS_PER_MINUTE + scene["staged_seconds"] / 60)
        scenes.append(scene)
    return sorted(scenes, key=lambda s: s["order"])


# ── links ──────────────────────────────────────────────────────────────────────
def href(cur, target):
    """A relative link from page `cur` to `target`, both site-relative. Preview pages name the file, since the preview host has no directory index."""
    link = os.path.relpath(target, os.path.dirname(cur) if not cur.endswith("/") else cur.rstrip("/"))
    if target.endswith("/"):
        link += "/index.html" if PREVIEW else "/"
    return link


def esc(text):
    return html.escape(text, quote=False)


def dirs(text):
    """Stage notes in parentheses inside a spoken line go in italics."""
    return PAREN_RE.sub(lambda m: f'<i class="dir">({m.group(1)})</i>', esc(text))


# ── script ─────────────────────────────────────────────────────────────────────
def render_script(scene, first=False):
    out, n, open_speech = [], 0, False

    def row(text, is_bar):
        nonlocal n
        n += 1
        num = f'<span class="n" aria-hidden="true">{n}</span>' if n % 5 == 0 else ""
        return f'<p class="row{" bar" if is_bar else ""}">{num}{dirs(text)}</p>'

    for item in scene["items"]:
        kind = item[0]
        if kind == "speaker":
            if open_speech:
                out.append("</div>")
            out.append(f'<div class="speech"><p class="speaker">{esc(item[1])}</p>')
            open_speech = True
        elif kind == "stage":
            out.append(f'<p class="stage">{esc(item[1])}</p>')
        elif kind == "beat":
            label = "Beat in" if item[1] == "IN" else "Beat out"
            out.append(f'<p class="beat"><b>{label}</b>{esc(item[2])}</p>')
        elif kind == "gap":
            out.append('<p class="row bar gap" aria-hidden="true">&nbsp;</p>')
        elif FULL_DIR_RE.match(item[1]):
            out.append(f'<p class="stage">{esc(item[1][1:-1])}</p>')
        else:
            out.append(row(item[1], item[2]))
    if open_speech:
        out.append("</div>")
    parts = ", ".join(c["part"] for c in scene["cast"] if c["part"] != "Beat")
    return (f'<section class="script{" first" if first else ""}" id="script-{scene["slug"]}">'
            f'<header class="script-head"><p class="kicker">{PACK} · Book {scene["book"]} of the Odyssey · about {scene["minutes"]} minutes</p>'
            f'<h2>{esc(scene["title"])}</h2><p class="small"><b>Parts:</b> {esc(parts)}, and anyone keeping the beat.</p>'
            f'<p class="small">A rule down the left side means the line goes on the beat. Everything else is spoken. Line numbers are for rehearsal.</p></header>'
            + "\n".join(out) +
            f'<p class="small script-foot">{credit_line(scene["title"])}</p></section>')


# ── shared blocks ──────────────────────────────────────────────────────────────
def credit_line(title=None):
    what = f"“{esc(title)}” from {PACK}" if title else PACK
    label = LICENSE_NAME if LICENSE_DECIDED else f"proposed license {LICENSE_NAME}"
    return f"{what}, athena.arc-codex.com/school/. Written mostly by AI. {label}."


def draft_banner():
    if LICENSE_DECIDED:
        return ""
    return ('<div class="draft" role="note"><div class="wrap"><b>Draft, not published.</b> Question for Ross before publishing: '
            f'is {LICENSE_NAME} the right license? Every license line on these pages is a proposal until he decides.</div></div>')


def family_bar():
    # Same bar as control_plane/tools/family_bar.py, which only covers the sites' index pages.
    return ('<!-- arc-family --><nav class="noprint" aria-label="Site path" style="box-sizing:border-box;width:100%;padding:6px 12px;background:#0b1220;color:#94a3b8;'
            'font:13px/1.4 system-ui,sans-serif;position:relative;z-index:50"><a href="https://arc-codex.com" style="color:#e2e8f0">&larr; Arc Codex</a> &rsaquo; Athena &rsaquo; School Edition</nav><!-- /arc-family -->')


def rights_block():
    return ('<p>No scene here needs a recording. The full Athena was built around popular songs, but this edition uses none of their titles, hooks or lyrics. '
            'Use a beat your students make.</p>'
            '<p><b>If you want to use a real recording:</b> staging one in a show likely needs dramatic rights from the song’s owners, and a school’s usual music license '
            'often doesn’t cover that. Check with your school first. This is general information, not legal advice.</p>')


def beat_block():
    return ('<p>Count 1, 2, 3, 4. Step on 1. Clap on 2. Step on 3. Clap on 4. Start slow, with a clap about every second and a half. For more drive, add a quick second step right after 3.</p>'
            '<p>Students can also drum on a desk, beatbox, or bring a beat they made themselves. Ask everyone to speak in their own voice. No one needs an accent or a “rap voice.”</p>')


def about_block(title=None):
    label = "License" if LICENSE_DECIDED else "Proposed license (not final)"
    return (f'<h3>Who wrote this</h3><p>Mostly machines. A person chose the story, the structure and the voice of Athena. A local AI model wrote the first draft of the full edition in 2026. '
            'Claude, an AI model made by Anthropic, rewrote these scenes for school, kept a few of the draft’s best lines, and checked the story against Butcher and Lang’s 1879 translation of Homer. '
            'These scenes have not yet been tried in a classroom.</p>'
            f'<h3>{label}</h3><p><a href="{LICENSE_URL}">Creative Commons BY-NC-SA 4.0</a>. You may copy, perform and change these scenes for classes and other noncommercial use, '
            'as long as you credit the source and share your changes under the same license. '
            'Because most of the text was written by machines, its copyright may be thin, and parts of it may have none. We ask you to follow these terms anyway, and we claim no more than the law gives. '
            'Butcher and Lang’s translation is in the public domain.</p>'
            f'<p class="small"><b>Credit line:</b> {credit_line(title)}</p>'
            f'<p class="small">Questions, or a report on how it went: {CONTACT}. To charge admission, please ask first. No ads, no sign-in and no tracking; these pages load nothing from other sites.</p>')


def print_buttons(path, scene=None):
    if PREVIEW:
        return '<p class="small noprint">The print buttons are switched off in this preview, because its frame blocks printing. They work on the real page.</p>'
    only = '<button type="button" onclick="printScript()">Print just the script</button>' if scene else ""
    return (f'<p class="actions noprint">{only}<button type="button" onclick="window.print()">Print this page</button>'
            f'<a href="{href(path, "school/scripts.html")}">All three scripts, ready to print</a></p>')


# ── pages ──────────────────────────────────────────────────────────────────────
def page(path, title, desc, body, og_image, indexed=True, body_class=""):
    fonts = href(path, "school/fonts/x")[:-1]
    robots = "index, follow, max-image-preview:large" if indexed and LICENSE_DECIDED else "noindex, follow"
    url = f"{SITE_URL}/{path}"
    image = f"{SITE_URL}/school/og/{og_image}.png"
    foot = ("" if LICENSE_DECIDED else "DRAFT · ") + f"{PACK} · written mostly by AI · athena.arc-codex.com/school · page "
    icon = f'<link rel="icon" type="image/png" sizes="192x192" href="{href(path, "images/icon-192.png")}">\n' if not PREVIEW else ""
    t, d = html.escape(title), html.escape(desc)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{url}">
<meta name="robots" content="{robots}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{PACK}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{t}">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{image}">
{icon}<style>{CSS.replace("FONTS/", fonts).replace("PRINTFOOT", foot)}</style>
</head>
<body class="{body_class}">
{family_bar()}
{draft_banner()}
{body}
<script>function printScript(){{document.body.classList.add('script-only');window.print();}}addEventListener('afterprint',function(){{document.body.classList.remove('script-only');}});</script>
</body>
</html>
"""


def scene_page(scene):
    path = f"school/{scene['slug']}/"
    cast = "".join(f'<tr><th scope="row">{esc(c["part"])}</th><td>{esc(c["who"])}</td><td>{esc(c["say"])}</td></tr>' for c in scene["cast"])
    notes = "".join(f'<li><b>{esc(n["label"])}:</b> {esc(n["text"])}</li>' for n in scene["content_note"])
    prompts = "".join(f'<li><b>{esc(p["kind"])}.</b> {esc(p["text"])}</li>' for p in scene["prompts"])
    differs = "".join(f"<li>{esc(d)}</li>" for d in scene["differs"])
    h = scene["homer"]
    link = href(path, f"school/homer/{h['page']}.html")
    body = f"""<main class="wrap">
<header class="plate"><div class="plate-banner"><span>{PACK}</span><span>Book {scene["book"]} of the Odyssey</span></div>
<div class="plate-main"><h1>{esc(scene["title"])}</h1><p class="hook">{esc(scene["hook"])}</p>
<dl class="facts"><div><dt>Time</dt><dd>About {scene["minutes"]} minutes</dd></div><div><dt>Cast</dt><dd>{esc(scene["speakers"])}</dd></div><div><dt>You need</dt><dd>A bare floor and a few chairs. No recording.</dd></div></dl></div></header>
{print_buttons(path, scene)}
<section class="teacher"><h2>What happens</h2><p>{esc(scene["summary"])}</p></section>
<section class="teacher"><h2>Cast</h2><div class="tablewrap"><table><thead><tr><th scope="col">Part</th><th scope="col">Who</th><th scope="col">Say it</th></tr></thead><tbody>{cast}</tbody></table></div>
<p class="small"><b>Other names:</b> {esc(scene["names"])} Any student can play any part.</p></section>
<section class="teacher"><h2>Content note</h2><ul>{notes}</ul></section>
<section class="teacher"><h2>The beat</h2><p>{esc(scene["beat"])}</p>{beat_block()}{rights_block()}</section>
{render_script(scene)}
<section class="teacher after-script"><h2>Three prompts</h2><ol>{prompts}</ol></section>
<section class="teacher"><h2>The matching passage of Homer</h2><p><a href="{link}#passage">Read {h["book"]}, {esc(h["range"])}</a> <span class="printonly">({SITE_URL}/school/homer/{h["page"]}.html)</span>, in Butcher and Lang’s public-domain translation.</p>
<h3>Where this scene differs from Homer</h3><ul>{differs}</ul></section>
<section class="teacher">{about_block(scene["title"])}</section>
<p class="noprint small"><a href="{href(path, "school/")}">All three scenes and teacher notes</a></p>
</main>"""
    title = f"{scene['title']}: Odyssey Book {scene['book']} Scene for the Classroom | {PACK}"
    desc = f"{scene['hook']} A free, printable {scene['minutes']}-minute classroom scene from a hip-hop retelling of the Odyssey. Small cast, a beat students make, no recording. Written mostly by AI."
    return path + "index.html", page(path, title, desc, body, scene["slug"])


def pack_page(scenes):
    path = "school/"
    cards = "".join(
        f'<li><a href="{href(path, "school/" + s["slug"] + "/")}"><span class="card-book">Book {s["book"]} · about {s["minutes"]} minutes · {esc(s["speakers"])}</span>'
        f'<span class="card-title">{esc(s["title"])}</span><span class="card-hook">{esc(s["hook"])}</span></a></li>' for s in scenes)
    body = f"""<main class="wrap">
<header class="plate"><div class="plate-banner"><span>Free for classrooms</span><span>Homer’s Odyssey, with a beat</span></div>
<div class="plate-main"><h1>{PACK}</h1><p class="hook">Three short scenes from a hip-hop retelling of the Odyssey. Each fits one class period with a small cast, and none needs a recording.</p></div></header>
{print_buttons(path)}
<section><h2>The scenes</h2><ul class="cards">{cards}</ul></section>
<section><h2>One class period</h2><ol><li><b>5 minutes:</b> teach the beat.</li><li><b>10 minutes:</b> read the scene aloud around the circle, with no parts yet.</li><li><b>20 minutes:</b> small groups pick parts and rehearse one section.</li><li><b>10 minutes:</b> show the work.</li><li><b>5 minutes:</b> talk through one prompt.</li></ol><p>Times on each scene are estimates from the word count. Time your own read.</p></section>
<section><h2>Making the beat</h2>{beat_block()}</section>
<section><h2>Music and rights</h2>{rights_block()}</section>
<section><h2>About this edition</h2>{about_block()}
<p>These scenes come from the <a href="{SITE_URL}/">full Athena</a>, a dinner-theater script for adult audiences. The full edition has not been edited for school and it names the songs, so look at it yourself before you share it.</p></section>
</main>"""
    desc = "Three free, printable scenes from a hip-hop retelling of Homer's Odyssey. One class period, small casts, no recording needed. Written mostly by AI, and it says so."
    return path + "index.html", page(path, f"{PACK}: Three Odyssey Scenes for the Classroom", desc, body, "pack")


def scripts_page(scenes):
    path = "school/scripts.html"
    scripts = "\n".join(render_script(s, first=(i == 0)) for i, s in enumerate(scenes))
    button = "" if PREVIEW else '<button type="button" onclick="window.print()">Print all three</button>'
    body = (f'<div class="wrap noprint"><p class="actions">{button}<a href="{href(path, "school/")}">Back to the teacher notes</a></p>'
            '<p class="small">Each script starts on a new page, so you can copy one scene or all three.</p></div>'
            f'<main class="wrap">{scripts}</main>')
    desc = "All three Athena School Edition scripts on one page, with page breaks between scenes."
    return path, page(path, f"All Three Scripts | {PACK}", desc, body, "pack", indexed=False, body_class="all-scripts")


def homer_page(scene):
    h = scene["homer"]
    path = f"school/homer/{h['page']}.html"
    with open(os.path.join(SRC, "homer", h["page"] + ".txt"), encoding="utf-8") as f:
        paras = [p for p in f.read().split("\n\n") if p.strip()]
    start, end = " ".join(h["start"].split()), " ".join(h["end"].split())
    out, found = [], 0
    for p in paras:
        if start in p:
            out.append(f'<p class="marker" id="passage">The scene “{esc(scene["title"])}” starts here</p>')
            found += 1
        if end in p:
            cut = p.index(end) + len(end)
            out.append(f"<p>{esc(p[:cut])}</p>")
            out.append('<p class="marker">The scene ends here</p>')
            found += 1
            p = p[cut:].strip()
            if not p:
                continue
        out.append(f"<p>{esc(p)}</p>")
    if found != 2:
        sys.exit(f"{path}: passage markers found {found} times, expected 2")
    body = f"""<main class="wrap homer">
<p class="noprint small"><a href="{href(path, "school/" + scene["slug"] + "/")}">Back to “{esc(scene["title"])}”</a></p>
<h1>The Odyssey, {h["book"]}</h1><p class="small">Homer, translated by S. H. Butcher and A. Lang, 1879. Public domain.</p>
<p class="small">{esc(h["note"])} The whole book is here, so students can read around the scene. Read it before you hand it out: it is plainer about violence and sex than the script.</p>
<p class="small noprint">The whole translation: <a href="https://arc-codex.com/library/{BUTCHER_LANG_ID}">Arc Codex Library</a> or <a href="https://www.gutenberg.org/ebooks/{BUTCHER_LANG_ID}">Project Gutenberg</a>.</p>
{"".join(out)}
</main>"""
    desc = f"{h['book']} of Homer's Odyssey in Butcher and Lang's public-domain translation, marked to match the classroom scene {scene['title']}."
    return path, page(path, f"Odyssey {h['book']}, Butcher and Lang | {PACK}", desc, body, scene["slug"], indexed=False)


# ── steps ──────────────────────────────────────────────────────────────────────
def extract_homer():
    """One book of the library's Butcher & Lang text → clean paragraphs, without footnotes."""
    con = sqlite3.connect(f"file:{LIBRARY_DB}?mode=ro", uri=True)
    text = con.execute("select text from work_texts where gutenberg_id=?", (BUTCHER_LANG_ID,)).fetchone()[0].replace("\r\n", "\n")
    marks = list(re.finditer(r"(?m)^\s*BOOK ([IVXL]+)\.\s*$", text))[24:]     # the first 24 are the table of contents
    os.makedirs(os.path.join(SRC, "homer"), exist_ok=True)
    for name, roman in HOMER_BOOKS.items():
        i = next(k for k, m in enumerate(marks) if m.group(1) == roman)
        stop = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        chunk = text[marks[i].end():stop]
        paras = []
        for p in re.split(r"\n\s*\n", chunk):
            p = " ".join(p.split())
            if not p or p == "image" or re.match(r"^\[\d+\]", p):
                continue
            paras.append(re.sub(r"\[\d+\]", "", p))
        with open(os.path.join(SRC, "homer", name + ".txt"), "w", encoding="utf-8") as f:
            f.write("\n\n".join(paras) + "\n")
        print(f"{name}: {len(paras)} paragraphs")


def render_cards(scenes, out):
    """Link-preview images, 1200x630. Rendered once and committed; run again only when a title or hook changes."""
    folder = os.path.join(out, "school", "og")
    os.makedirs(folder, exist_ok=True)
    rows = [(s["slug"], s["title"], s["hook"], f'Book {s["book"]} of the Odyssey · about {s["minutes"]} minutes') for s in scenes]
    rows.append(("pack", "Three Odyssey Scenes", "Free classroom scenes with a beat students make. No recording needed.", "One class period · small casts"))
    for slug, title, hook, line in rows:
        doc = (f'<!doctype html><meta charset="utf-8"><style>body{{margin:0;width:1200px;height:630px;box-sizing:border-box;background:#f4e9d2;color:#231b16;font-family:Georgia,serif;padding:44px}}'
               f'.b{{border:8px solid #231b16;height:100%;box-sizing:border-box;box-shadow:14px 14px 0 rgba(35,27,22,.45);display:flex;flex-direction:column}}'
               f'.r{{background:#c5352f;color:#f4e9d2;font:700 26px Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;padding:16px 30px;border-bottom:8px solid #231b16}}'
               f'.m{{padding:36px 40px;flex:1;display:flex;flex-direction:column;justify-content:center}}h1{{font-size:{"96" if len(title) < 18 else "78"}px;margin:0 0 20px;line-height:1.02}}p{{font-size:37px;line-height:1.25;margin:0}}.l{{font:600 26px Arial,sans-serif;color:#1f4e79;margin-top:24px}}</style>'
               f'<div class="b"><div class="r">{PACK}</div><div class="m"><h1>{esc(title)}</h1><p>{esc(hook)}</p><p class="l">{esc(line)}</p></div></div>')
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(doc)
        subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1", "--window-size=1200,630",
                        f"--screenshot={os.path.join(folder, slug + '.png')}", "file://" + f.name], check=True, capture_output=True)
        os.unlink(f.name)
        print("card", slug)


def artifact_main(doc):
    """The preview host wraps its main page in its own skeleton, so that one page drops the document tags."""
    head = re.search(r"<head>(.*)</head>", doc, re.S).group(1)
    head = re.sub(r"<title>.*?</title>", f"<title>{PACK}</title>", head, count=1)
    body = re.search(r"<body[^>]*>(.*)</body>", doc, re.S).group(1)
    return head + body


def build(out):
    scenes = load_scenes()
    pages = [pack_page(scenes), scripts_page(scenes)]
    pages += [scene_page(s) for s in scenes] + [homer_page(s) for s in scenes]
    for rel, doc in pages:
        dest = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if PREVIEW and rel == "school/index.html":
            doc = artifact_main(doc)
        old = None
        if os.path.exists(dest):
            with open(dest, encoding="utf-8") as f:
                old = f.read()
        if old != doc:          # the sitemap's lastmod comes from each page's file date
            with open(dest, "w", encoding="utf-8") as f:
                f.write(doc)
    fonts_out = os.path.join(out, "school", "fonts")
    os.makedirs(fonts_out, exist_ok=True)
    for name in os.listdir(os.path.join(SRC, "fonts")):
        shutil.copy(os.path.join(SRC, "fonts", name), fonts_out)
    for s in scenes:
        print(f'{s["slug"]}: {s["words"]} spoken words, about {s["minutes"]} minutes')
    print(f"Wrote {len(pages)} pages to {os.path.join(out, 'school')}")
    return scenes


CSS = """
@font-face{font-family:Literata;src:url(FONTS/Literata-latin-normal.woff2) format("woff2");font-weight:400 700;font-style:normal;font-display:swap}
@font-face{font-family:Literata;src:url(FONTS/Literata-latin-italic.woff2) format("woff2");font-weight:400 700;font-style:italic;font-display:swap}
@font-face{font-family:"Public Sans";src:url(FONTS/PublicSans-latin-normal.woff2) format("woff2");font-weight:400 700;font-display:swap}
/* Athena's own palette and comic-plate look (build_athena_site.py), on self-hosted fonts so a school network loads nothing from other sites. */
:root{--paper:#f4e9d2;--paper-2:#eaddbf;--ink:#231b16;--red:#b32d27;--blue:#1f4e79;--gold:#9a6a1c;--muted:#594b3f;--line:#231b16;--shadow:rgba(35,27,22,.45);--on-red:#f4e9d2;
  --serif:Literata,Georgia,"Times New Roman",serif;--sans:"Public Sans",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#1b1713;--paper-2:#2a241d;--ink:#f1e6d0;--red:#f0897d;--blue:#8fbbe3;--gold:#dcae55;--muted:#c6b8a2;--line:#75685a;--shadow:rgba(0,0,0,.5);--on-red:#1b1713;color-scheme:dark}}
:root[data-theme="dark"]{--paper:#1b1713;--paper-2:#2a241d;--ink:#f1e6d0;--red:#f0897d;--blue:#8fbbe3;--gold:#dcae55;--muted:#c6b8a2;--line:#75685a;--shadow:rgba(0,0,0,.5);--on-red:#1b1713;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:18px/1.6 var(--serif)}
a{color:var(--red);text-underline-offset:2px}
a:focus-visible,button:focus-visible{outline:3px solid var(--gold);outline-offset:2px}
.wrap{max-width:46rem;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:18px}
.draft{background:var(--paper-2);border-bottom:3px solid var(--line);font:600 .9rem/1.45 var(--sans)}
.draft .wrap{padding-block:10px}
.plate{margin:12px 0 22px;border:4px solid var(--line);background:var(--paper-2);box-shadow:7px 7px 0 var(--shadow)}
.plate-banner{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 16px;background:var(--red);color:var(--on-red);padding:7px 14px;border-bottom:4px solid var(--line);font:700 .74rem var(--sans);letter-spacing:.09em;text-transform:uppercase}
.plate-main{padding:18px 20px 20px}
h1{margin:0 0 8px;font-size:clamp(2.2rem,8vw,3.5rem);line-height:1.04;font-weight:700;text-wrap:balance}
.hook{margin:0;font-size:1.15rem;font-style:italic}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(10rem,1fr));gap:10px 18px;margin:16px 0 0}
.facts dt{font:700 .7rem var(--sans);letter-spacing:.09em;text-transform:uppercase;color:var(--blue)}
.facts dd{margin:0;font-size:1rem;line-height:1.35}
h2{font-size:1.5rem;line-height:1.2;margin:28px 0 8px;padding-bottom:5px;border-bottom:3px solid var(--line);text-wrap:balance}
h3{font-size:1.08rem;margin:18px 0 4px}
ul,ol{padding-left:1.3em}li{margin:.35em 0}
.small{font-size:.9rem;line-height:1.5}
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;font:600 .9rem var(--sans)}
button{font:700 .9rem var(--sans);color:var(--ink);background:var(--paper-2);border:2px solid var(--line);padding:7px 13px;cursor:pointer}
button:hover{background:var(--paper)}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.95rem;line-height:1.4}
th,td{text-align:left;vertical-align:top;padding:7px 10px 7px 0;border-bottom:1px solid var(--line)}
thead th{font:700 .72rem var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--blue)}
td:last-child{white-space:nowrap;font-size:.86rem}
.cards{list-style:none;margin:0;padding:0;display:grid;gap:14px}
.cards li{margin:0}
.cards a{display:block;color:inherit;text-decoration:none;border:3px solid var(--line);background:var(--paper-2);box-shadow:5px 5px 0 var(--shadow);padding:13px 16px}
.cards a:hover .card-title{text-decoration:underline}
.card-book{display:block;font:700 .72rem/1.4 var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--blue)}
.card-title{display:block;font-size:1.6rem;font-weight:700;line-height:1.2;color:var(--red)}
.card-hook{display:block;font-style:italic}
.printonly{display:none}
/* the script */
.script{margin-top:34px;padding-top:6px;border-top:6px solid var(--line)}
.script-head h2{border:0;margin:2px 0 4px;padding:0;font-size:2rem}
.kicker{margin:10px 0 0;font:700 .72rem/1.4 var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--blue)}
.script-head .small{margin:4px 0}
.speaker{margin:1.15em 0 .15em 2.4rem;font:700 .8rem var(--sans);letter-spacing:.09em;text-transform:uppercase;color:var(--red)}
.row{position:relative;margin:0 0 0 2.4rem;padding-left:1rem;text-indent:-1rem;line-height:1.45}
.row.bar{border-left:3px solid var(--gold);padding-left:1.7rem}
.row.gap{height:.55em;line-height:.55em;overflow:hidden}
.n{position:absolute;left:-2.4rem;width:1.8rem;text-align:right;text-indent:0;top:.25em;font:.68rem var(--sans);color:var(--muted);user-select:none}
.stage{margin:.6em 0 .6em 2.4rem;font-style:italic;color:var(--muted);line-height:1.4;font-size:.95em}
.dir{color:var(--muted)}
.beat{margin:.65em 0 .4em 2.4rem;font:500 .78rem/1.4 var(--sans);color:var(--blue)}
.beat b{border:1.5px solid var(--blue);padding:0 .4em;margin-right:.35em;text-transform:uppercase;letter-spacing:.06em;font-size:.72rem;display:inline-block}
.script-foot{margin:1.8em 0 0 2.4rem;color:var(--muted)}
.homer p{margin:0 0 .9em}
.marker{font:700 .8rem var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--on-red);background:var(--red);padding:5px 10px;scroll-margin-top:12px}
@media (max-width:480px){.speaker,.row,.stage,.beat,.script-foot{margin-left:1.5rem}.n{left:-1.5rem;width:1.2rem}}
@media print{
  @page{margin:.75in .75in .8in;@bottom-center{content:"PRINTFOOT" counter(page);font:8.5pt Georgia,serif;color:#333}}
  :root,:root:not([data-theme="light"]),:root[data-theme="dark"]{--paper:#fff;--paper-2:#fff;--ink:#000;--red:#000;--blue:#000;--gold:#000;--muted:#222;--line:#000;--on-red:#000;color-scheme:light}
  body{background:#fff;font-size:11.5pt;line-height:1.4}
  .noprint,.draft,button{display:none!important}
  .printonly{display:inline}
  .wrap{max-width:none;padding:0}
  a{color:inherit;text-decoration:none}
  .plate{box-shadow:none;border-width:2px;margin-top:0}
  .plate-banner{border-bottom-width:2px}
  .script{break-before:page;border-top:0;margin-top:0;padding-top:0}
  .all-scripts .script.first,.script-only .script{break-before:auto}
  .after-script{break-before:page}
  .script-only .teacher,.script-only .plate,.script-only .actions{display:none!important}
  .speaker{break-after:avoid}
  .row,.stage,.beat{orphans:2;widows:2}
  .beat{break-after:avoid}
  .marker{border:1.5pt solid #000;background:#fff}
  h2,h3{break-after:avoid}
  li,tr{break-inside:avoid}
}
"""


def main():
    global PREVIEW
    args = sys.argv[1:]
    if "--extract-homer" in args:
        extract_homer()
        return
    out = os.path.join(HERE, "site")
    if "--preview" in args:
        PREVIEW = True
        out = args[args.index("--preview") + 1]
    elif "--out" in args:
        out = args[args.index("--out") + 1]
    scenes = build(out)
    if "--cards" in args:
        render_cards(scenes, out)
    if not PREVIEW:
        write_sitemap(out, MANUSCRIPT)
        print(f"Wrote {os.path.join(out, 'sitemap.xml')}")


if __name__ == "__main__":
    main()
