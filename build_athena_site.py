#!/usr/bin/env python3
"""
build_athena_site.py — ATHENA illustrated-edition static site generator
========================================================================
Turns ATHENA_manuscript.md + an images/ folder into ONE long, self-contained
Classics-Illustrated-styled HTML page (index.html). No frameworks, no Arc Codex
article pipeline, no accordions, no counter-analyst — a creation presented as a
creation.

IMAGE ARCHITECTURE (future-proofed — you just drop files in images/):
  images/cover.jpg              → the cover plate at the top
  images/book01.jpg .. book24   → one illustration per book's chapter plate
  images/book01_turn03.jpg ...  → OPTIONAL per-turn illustrations (auto-detected)

If an image file is missing, an attractive placeholder panel renders instead —
NO code change needed. To add art: generate it (Leonardo/Firefly/etc), save it
with the right filename in images/, re-run this script. Done.

USAGE:
  python3 build_athena_site.py                       # reads ./ATHENA_manuscript.md, writes ./site/index.html
  python3 build_athena_site.py MANUSCRIPT OUTDIR IMAGESDIR

The manuscript stays PURE TEXT. All presentation lives here.
"""

import os
import re
import sys
import html
import shutil
import datetime

# ── paths ────────────────────────────────────────────────────────────────────
MANUSCRIPT = sys.argv[1] if len(sys.argv) > 1 else "ATHENA_manuscript.md"
OUTDIR     = sys.argv[2] if len(sys.argv) > 2 else "site"
IMAGESDIR  = sys.argv[3] if len(sys.argv) > 3 else "images"

# ── canonical site identity (used for SEO: canonical, Open Graph, sitemap) ────
SITE_URL   = "https://athena.arc-codex.com"   # no trailing slash
OG_IMAGE   = SITE_URL + "/images/cover.png"    # brand cover art
# Google Search Console verification. Two paths (use either):
#   (a) HTML-file: drop the google<hash>.html Google gives you into site/ —
#       survives rebuilds (the builder never deletes site/ root files).
#   (b) Meta-tag: paste ONLY the token value (the content=... string) here and
#       rebuild; an empty string emits no tag.
GOOGLE_SITE_VERIFICATION = ""

ROMAN = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII",
         "XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX","XXI","XXII","XXIII","XXIV"]
ROMAN_TO_NUM = {r: i+1 for i, r in enumerate(ROMAN)}

# Image extensions we'll accept, in priority order
IMG_EXTS = [".jpg", ".jpeg", ".png", ".webp", ".avif"]


def find_image(basename: str) -> str | None:
    """Return the web path to images/<basename>.<ext> if any exists, else None."""
    for ext in IMG_EXTS:
        candidate = os.path.join(IMAGESDIR, basename + ext)
        if os.path.exists(candidate):
            return f"images/{basename}{ext}"
    return None


# ── manuscript parsing ─────────────────────────────────────────────────────────
def parse_manuscript(text: str):
    """
    Returns (front_matter_lines, books) where each book is:
      {num, roman, title, song_line, blocks:[...]}
    A block is ('muse', text) | ('turn', n, speaker, emoji, lines[]) | ('exit', lines[])
    """
    lines = text.split("\n")
    books = []
    front = []
    cur = None

    book_re = re.compile(r"^#\s+ATHENA\s+—\s+Book\s+([IVXLC]+):\s*(.*)$")
    turn_re = re.compile(r"^###\s+Turn\s+(\d+)\s+—\s+([A-Z][A-Za-z'’ ]+?)\s*(\S+)?\s*$")
    muse_re = re.compile(r"^###\s+MUSE\s*(\S+)?\s*$")
    misc_h3 = re.compile(r"^###\s+(.*)$")

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        mb = book_re.match(line)
        if mb:
            if cur:
                books.append(cur)
            roman = mb.group(1)
            cur = {
                "num": ROMAN_TO_NUM.get(roman, len(books) + 1),
                "roman": roman,
                "title": mb.group(2).strip(),
                "song_line": "",
                "blocks": [],
            }
            i += 1
            continue

        if cur is None:
            # front matter (title page + TOC) — we render our own, so we mostly skip,
            # but keep nothing; our masthead replaces it.
            i += 1
            continue

        # song credit line: italic *“Song”* (Artist) — appears near book top
        if not cur["blocks"] and not cur["song_line"]:
            ms = re.match(r"^\*.*\*\s*$", line.strip())
            # The manuscript uses a TOC for songs; within a book the song shows in
            # the Muse card. We capture an explicit subtitle line if present.
        # MUSE card
        mm = muse_re.match(line)
        if mm:
            emoji = mm.group(1) or "🎩"
            body = []
            i += 1
            while i < n and not lines[i].startswith("### ") and not book_re.match(lines[i]):
                if lines[i].strip() == "---":
                    i += 1
                    continue
                body.append(lines[i])
                i += 1
            cur["blocks"].append(("muse", emoji, "\n".join(body).strip()))
            continue

        # TURN
        mt = turn_re.match(line)
        if mt:
            tnum = int(mt.group(1))
            speaker = mt.group(2).strip()
            emoji = mt.group(3) or ""
            body = []
            i += 1
            while i < n and not lines[i].startswith("### ") and not book_re.match(lines[i]):
                if lines[i].strip() == "---":
                    i += 1
                    continue
                body.append(lines[i])
                i += 1
            cur["blocks"].append(("turn", tnum, speaker, emoji, "\n".join(body).strip()))
            continue

        # other ### heading (e.g. EXIT) — render as a soft divider block
        mo = misc_h3.match(line)
        if mo:
            label = mo.group(1).strip()
            body = []
            i += 1
            while i < n and not lines[i].startswith("### ") and not book_re.match(lines[i]):
                if lines[i].strip() == "---":
                    i += 1
                    continue
                body.append(lines[i])
                i += 1
            cur["blocks"].append(("misc", label, "\n".join(body).strip()))
            continue

        i += 1

    if cur:
        books.append(cur)
    return front, books


# ── song map (book number -> (song, artist)) ──────────────────────────────────
# Kept here so the chapter plate can show the song credit even though the
# manuscript body doesn't repeat it. Edit freely.
SONG_MAP = {
    1:  ("Deal With It", "Ashnikko"),
    2:  ("Fast", "Saweetie"),
    3:  ("Freak", "Pitbull"),
    4:  ("Rude Boy", "Rihanna"),
    5:  ("My Type", "Saweetie"),
    6:  ("Rain On Me", "Lady Gaga & Ariana Grande"),
    7:  ("Mic Drop", "Steve Aoki"),
    8:  ("Every Day", "A$AP Rocky"),
    9:  ("Bad Habits", "Ed Sheeran"),
    10: ("Don't Stop", "Megan Thee Stallion"),
    11: ("Get Ugly", "Jason Derulo"),
    12: ("Outta Your Mind", "Lil Jon"),
    13: ("WOW", "Post Malone"),
    14: ("Without Me", "Halsey"),
    15: ("Bounce Back", "Little Mix"),
    16: ("Lay", "Jason Derulo"),
    17: ("Walk It Out", "Usher"),
    18: ("No Tears Left To Cry", "Ariana Grande"),
    19: ("Savage Love", "Jason Derulo"),
    20: ("Up", "Cardi B"),
    21: ("Black Widow", "Iggy Azalea"),
    22: ("All About That Bass", "Meghan Trainor"),
    23: ("New Rules", "Dua Lipa"),
    24: ("Work", "Britney Spears"),
}


# ── rendering helpers ──────────────────────────────────────────────────────────
STAGING_RE = re.compile(r"\[STAGING:\s*(.*?)\]", re.DOTALL)


def render_body(text: str) -> str:
    """Render a turn/muse body: staging directions as styled asides, rest as verse lines."""
    out = []
    # Split on staging directions, keep them
    pos = 0
    for m in STAGING_RE.finditer(text):
        before = text[pos:m.start()]
        if before.strip():
            out.append(render_verse(before))
        stage = html.escape(m.group(1).strip())
        out.append(f'<p class="stage">{stage}</p>')
        pos = m.end()
    tail = text[pos:]
    if tail.strip():
        out.append(render_verse(tail))
    return "\n".join(out)


def render_verse(text: str) -> str:
    """Render plain verse/prose lines, preserving line breaks within a stanza."""
    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    html_blocks = []
    for b in blocks:
        lines = [html.escape(ln.strip()) for ln in b.split("\n") if ln.strip()]
        html_blocks.append('<p class="verse">' + "<br>".join(lines) + "</p>")
    return "\n".join(html_blocks)


def image_or_placeholder(basename: str, alt: str, kind: str) -> str:
    """Return an <img> if the file exists, else an attractive placeholder panel."""
    path = find_image(basename)
    if path:
        return (f'<figure class="plate-art {kind}">'
                f'<img src="{path}" alt="{html.escape(alt)}" loading="lazy">'
                f'</figure>')
    return (f'<figure class="plate-art placeholder {kind}" '
            f'data-slot="{basename}">'
            f'<div class="ph-inner"><span class="ph-mark">✦</span>'
            f'<span class="ph-label">{html.escape(alt)}</span>'
            f'<span class="ph-file">images/{basename}.jpg</span></div>'
            f'</figure>')


# ── HTML assembly ───────────────────────────────────────────────────────────────
def build_html(books) -> str:
    cover = image_or_placeholder("cover", "ATHENA — cover plate", "cover")

    # Table of contents
    toc_items = []
    for b in books:
        song, artist = SONG_MAP.get(b["num"], ("", ""))
        song_credit = f' &middot; <em>“{html.escape(song)}”</em>' if song else ""
        toc_items.append(
            f'<li><a href="#book{b["num"]:02d}">'
            f'<span class="toc-num">{b["roman"]}</span>'
            f'<span class="toc-title">{html.escape(b["title"])}</span>'
            f'<span class="toc-song">{song_credit}</span></a></li>'
        )
    toc = "<ol class='toc'>" + "\n".join(toc_items) + "</ol>"

    # Books
    book_sections = []
    for b in books:
        song, artist = SONG_MAP.get(b["num"], ("", ""))
        art = image_or_placeholder(f"book{b['num']:02d}",
                                   f"Book {b['roman']}: {b['title']}", "book")
        blocks_html = []
        for blk in b["blocks"]:
            if blk[0] == "muse":
                _, emoji, body = blk
                blocks_html.append(
                    f'<section class="muse"><div class="muse-tab">'
                    f'<span class="muse-emoji">{html.escape(emoji)}</span> THE MUSE</div>'
                    f'<div class="muse-body">{render_body(body)}</div></section>'
                )
            elif blk[0] == "turn":
                _, tnum, speaker, emoji, body = blk
                # per-turn optional image
                turn_art = ""
                tpath = find_image(f"book{b['num']:02d}_turn{tnum:02d}")
                if tpath:
                    turn_art = (f'<figure class="turn-art">'
                                f'<img src="{tpath}" alt="{html.escape(speaker)}" loading="lazy">'
                                f'</figure>')
                blocks_html.append(
                    f'<section class="turn">'
                    f'<h3 class="turn-head"><span class="turn-no">Turn {tnum}</span>'
                    f'<span class="turn-speaker">{html.escape(speaker)}</span>'
                    f'<span class="turn-emoji">{html.escape(emoji)}</span></h3>'
                    f'{turn_art}'
                    f'<div class="turn-body">{render_body(body)}</div></section>'
                )
            elif blk[0] == "misc":
                _, label, body = blk
                blocks_html.append(
                    f'<section class="misc"><h3 class="misc-head">{html.escape(label)}</h3>'
                    f'<div class="turn-body">{render_body(body)}</div></section>'
                )

        song_credit = ""
        if song:
            song_credit = (f'<p class="plate-song">danced to '
                           f'<strong>“{html.escape(song)}”</strong>'
                           f'<span class="plate-artist">{html.escape(artist)}</span></p>')

        book_sections.append(
            f'<article class="book" id="book{b["num"]:02d}">'
            f'<header class="plate">'
            f'<div class="plate-banner"><span class="plate-issue">No. {b["num"]}</span>'
            f'<span class="plate-series">ATHENA · THE HIPHOP ODYSSEY</span></div>'
            f'<div class="plate-main">'
            f'<div class="plate-text">'
            f'<p class="plate-bookno">Book {b["roman"]}</p>'
            f'<h2 class="plate-title">{html.escape(b["title"])}</h2>'
            f'{song_credit}</div>'
            f'{art}'
            f'</div></header>'
            f'<div class="book-text">{"".join(blocks_html)}</div>'
            f'<nav class="book-nav" aria-label="Book navigation">'
            + (f'<a class="bn-prev" href="#book{b["num"]-1:02d}">← Book {ROMAN[b["num"]-2]}</a>' if b["num"] > 1 else '<span class="bn-prev disabled" aria-hidden="true"></span>')
            + '<a class="bn-top" href="#top">↑ Contents</a>'
            + (f'<a class="bn-next" href="#book{b["num"]+1:02d}">Book {ROMAN[b["num"]]} →</a>' if b["num"] < len(books) else '<span class="bn-next disabled" aria-hidden="true"></span>')
            + '</nav>'
            f'</article>'
        )

    verification = (
        f'<meta name="google-site-verification" content="{html.escape(GOOGLE_SITE_VERIFICATION)}">\n'
        if GOOGLE_SITE_VERIFICATION else "")
    return (PAGE_TEMPLATE
            .replace("{cover}", cover)
            .replace("{toc}", toc)
            .replace("{verification}", verification)
            .replace("{books}", "\n".join(book_sections)))


# ── the page template (CSS inline → fully self-contained) ─────────────────────
PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ATHENA — The HipHop Odyssey · An Illustrated Edition</title>
<meta name="description" content="An immersive dinner-theater retelling of Homer's Odyssey — 24 books, 24 songs. A collaborative-AI illustrated edition.">
<!-- SEO: canonical + crawl directives -->
<link rel="canonical" href="https://athena.arc-codex.com/">
<meta name="robots" content="index, follow, max-image-preview:large">
{verification}<!-- Open Graph (Facebook, Bluesky, Mastodon, LinkedIn link previews) -->
<meta property="og:type" content="book">
<meta property="og:site_name" content="ATHENA — The HipHop Odyssey">
<meta property="og:title" content="ATHENA — The HipHop Odyssey · An Illustrated Edition">
<meta property="og:description" content="An immersive dinner-theater retelling of Homer's Odyssey — 24 books, 24 songs. A collaborative-AI illustrated edition.">
<meta property="og:url" content="https://athena.arc-codex.com/">
<meta property="og:image" content="https://athena.arc-codex.com/images/cover.png">
<meta property="og:image:alt" content="ATHENA — The HipHop Odyssey cover art">
<meta property="og:locale" content="en_US">
<!-- Twitter / X card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="ATHENA — The HipHop Odyssey · An Illustrated Edition">
<meta name="twitter:description" content="An immersive dinner-theater retelling of Homer's Odyssey — 24 books, 24 songs.">
<meta name="twitter:image" content="https://athena.arc-codex.com/images/cover.png">
<!-- PWA / installable app -->
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#1f4e79">
<link rel="icon" type="image/png" sizes="192x192" href="images/icon-192.png">
<link rel="icon" type="image/png" sizes="512x512" href="images/icon-512.png">
<!-- iOS home-screen app -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ATHENA">
<link rel="apple-touch-icon" href="images/icon-180.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Alfa+Slab+One&family=Spectral:ital,wght@0,400;0,600;1,400;1,600&family=Oswald:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    --paper:#f4e9d2;        /* warm cream paper */
    --paper-2:#eaddbf;      /* deeper parchment */
    --ink:#231b16;          /* near-black brown ink */
    --red:#c5352f;          /* comic-book red */
    --blue:#1f4e79;         /* Mediterranean ink blue */
    --blue-2:#2d7da3;       /* aegean teal-blue */
    --gold:#c2862a;         /* bronze-gold */
    --gold-2:#e0a83a;       /* brighter gold */
    --teal:#2f7d6b;         /* sea teal */
    --line:#231b16;
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{
    margin:0; background:var(--paper);
    color:var(--ink);
    font-family:'Spectral',Georgia,serif;
    font-size:19px; line-height:1.62;
    /* subtle halftone paper texture */
    background-image:
      radial-gradient(var(--paper-2) 0.5px, transparent 0.6px);
    background-size:7px 7px;
  }
  a{color:var(--red); text-decoration:none}
  a:hover{text-decoration:underline}

  /* ── Masthead ─────────────────────────────────────── */
  .masthead{
    position:relative; text-align:center;
    padding:46px 20px 30px;
    border-bottom:6px solid var(--ink);
    background:var(--blue);
    color:var(--paper);
  }
  .masthead .kicker{
    font-family:'Oswald',sans-serif; letter-spacing:.32em;
    text-transform:uppercase; font-size:13px; font-weight:600;
    color:var(--gold-2);
  }
  .masthead h1{
    font-family:'Alfa Slab One',display; margin:.08em 0 .05em;
    font-size:clamp(48px,11vw,120px); line-height:.92;
    color:var(--paper);
    text-shadow:4px 4px 0 var(--red), 8px 8px 0 rgba(0,0,0,.25);
    letter-spacing:.01em;
  }
  .masthead .sub{
    font-family:'Oswald',sans-serif; text-transform:uppercase;
    letter-spacing:.18em; font-size:clamp(14px,2.4vw,20px);
    color:var(--paper);
  }
  .masthead .meta{
    margin-top:14px; font-style:italic; color:var(--paper);
    opacity:.92; font-size:16px;
  }
  .cover-wrap{max-width:560px; margin:26px auto 0}

  /* ── Plate art / placeholders ─────────────────────── */
  .plate-art{margin:0; border:4px solid var(--ink); background:var(--paper-2);
    box-shadow:7px 7px 0 rgba(35,27,22,.5); overflow:hidden}
  .plate-art img{display:block; width:100%; height:auto}
  .plate-art.cover{border-width:5px}
  .plate-art.placeholder{
    aspect-ratio:4/3; display:flex; align-items:center; justify-content:center;
    background:
      repeating-linear-gradient(45deg,var(--paper) 0 14px,var(--paper-2) 14px 28px);
  }
  .plate-art.placeholder.cover{aspect-ratio:3/2}
  .ph-inner{display:flex; flex-direction:column; align-items:center; gap:7px;
    text-align:center; padding:24px; color:var(--blue)}
  .ph-mark{font-size:34px; color:var(--gold)}
  .ph-label{font-family:'Oswald',sans-serif; text-transform:uppercase;
    letter-spacing:.12em; font-size:14px; font-weight:600}
  .ph-file{font-family:'Oswald',sans-serif; font-size:11px; opacity:.6;
    letter-spacing:.06em}

  /* ── Contents ─────────────────────────────────────── */
  .contents{max-width:820px; margin:0 auto; padding:48px 22px 10px}
  .contents h2{
    font-family:'Alfa Slab One',display; font-size:30px; color:var(--red);
    text-align:center; margin:0 0 6px; letter-spacing:.02em}
  .contents .lede{text-align:center; font-style:italic; margin:0 auto 26px;
    max-width:600px; color:var(--ink)}
  .toc{list-style:none; margin:0; padding:0; columns:2; column-gap:34px}
  @media(max-width:640px){.toc{columns:1}}
  .toc li{break-inside:avoid; margin:0 0 4px}
  .toc a{display:flex; align-items:baseline; gap:10px; color:var(--ink);
    padding:7px 10px; border-bottom:1px dotted rgba(35,27,22,.35)}
  .toc a:hover{background:var(--paper-2); text-decoration:none}
  .toc-num{font-family:'Oswald',sans-serif; font-weight:700; color:var(--red);
    min-width:42px}
  .toc-title{font-weight:600}
  .toc-song{color:var(--blue); font-size:15px}

  /* ── Book / chapter plate ─────────────────────────── */
  .book{max-width:820px; margin:0 auto; padding:30px 22px 10px;
    border-top:3px solid var(--ink)}
  .book:first-of-type{border-top:none}
  .plate{margin:18px 0 22px; border:4px solid var(--ink); background:var(--paper-2);
    box-shadow:8px 8px 0 rgba(35,27,22,.45)}
  .plate-banner{display:flex; justify-content:space-between; align-items:center;
    background:var(--red); color:var(--paper); padding:7px 14px;
    font-family:'Oswald',sans-serif; text-transform:uppercase;
    letter-spacing:.14em; font-size:12px; font-weight:600;
    border-bottom:4px solid var(--ink)}
  .plate-issue{background:var(--ink); color:var(--gold-2); padding:2px 9px;
    border-radius:2px}
  .plate-main{display:grid; grid-template-columns:1fr 1fr; gap:0}
  @media(max-width:620px){.plate-main{grid-template-columns:1fr}}
  .plate-text{padding:22px 22px 24px; display:flex; flex-direction:column;
    justify-content:center; border-right:3px solid var(--ink)}
  @media(max-width:620px){.plate-text{border-right:none;
    border-bottom:3px solid var(--ink)}}
  .plate-bookno{font-family:'Oswald',sans-serif; text-transform:uppercase;
    letter-spacing:.2em; color:var(--blue); margin:0 0 2px; font-weight:600;
    font-size:15px}
  .plate-title{font-family:'Alfa Slab One',display; margin:0; color:var(--ink);
    font-size:clamp(28px,6vw,46px); line-height:.98}
  .plate-song{margin:14px 0 0; font-style:italic; color:var(--ink)}
  .plate-song strong{color:var(--red); font-style:normal; font-weight:600}
  .plate-artist{display:block; font-family:'Oswald',sans-serif; font-style:normal;
    text-transform:uppercase; letter-spacing:.1em; font-size:12px;
    color:var(--blue); margin-top:3px}
  .plate .plate-art{border:none; box-shadow:none}
  .plate .plate-art.placeholder{aspect-ratio:auto; min-height:200px}

  /* ── Muse cards ───────────────────────────────────── */
  .muse{margin:24px 0; background:var(--blue); color:var(--paper);
    border:3px solid var(--ink); box-shadow:5px 5px 0 rgba(35,27,22,.4);
    overflow:hidden}
  .muse-tab{background:var(--gold); color:var(--ink); display:inline-block;
    font-family:'Oswald',sans-serif; font-weight:700; letter-spacing:.16em;
    text-transform:uppercase; font-size:13px; padding:6px 16px 6px 14px;
    border-bottom:3px solid var(--ink); border-right:3px solid var(--ink)}
  .muse-emoji{margin-right:5px}
  .muse-body{padding:16px 22px 20px}
  .muse-body .verse{margin:0 0 12px; color:var(--paper)}
  .muse-body .stage{color:var(--gold-2)}

  /* ── Turns ────────────────────────────────────────── */
  .turn{margin:26px 0}
  .turn-head{display:flex; align-items:center; gap:12px; margin:0 0 10px;
    padding-bottom:7px; border-bottom:3px solid var(--ink)}
  .turn-no{font-family:'Oswald',sans-serif; font-weight:700;
    text-transform:uppercase; letter-spacing:.1em; font-size:13px;
    background:var(--ink); color:var(--paper); padding:3px 10px}
  .turn-speaker{font-family:'Alfa Slab One',display; font-size:24px;
    color:var(--red); line-height:1; letter-spacing:.01em}
  .turn-emoji{font-size:22px; margin-left:auto}
  .turn-body .verse{margin:0 0 14px}
  .turn-art{margin:0 0 14px; border:3px solid var(--ink);
    box-shadow:5px 5px 0 rgba(35,27,22,.35)}
  .turn-art img{display:block; width:100%; height:auto}

  /* staging directions */
  .stage{font-family:'Oswald',sans-serif; font-weight:500; font-style:normal;
    text-transform:uppercase; letter-spacing:.04em; font-size:13.5px;
    color:var(--teal); border-left:4px solid var(--gold); padding:4px 0 4px 14px;
    margin:12px 0; line-height:1.5}

  .misc{margin:24px 0}
  .misc-head{font-family:'Oswald',sans-serif; text-transform:uppercase;
    letter-spacing:.18em; color:var(--blue); font-size:15px;
    border-bottom:2px solid var(--ink); padding-bottom:6px}

  .totop{display:inline-block; margin:18px 0 8px; font-family:'Oswald',sans-serif;
    text-transform:uppercase; letter-spacing:.12em; font-size:12px; color:var(--blue)}

  /* ── Colophon footer ──────────────────────────────── */
  .colophon{max-width:820px; margin:40px auto 0; padding:30px 22px 70px;
    border-top:6px solid var(--ink); text-align:center}
  .colophon p{font-style:italic; max-width:620px; margin:0 auto 12px}
  .colophon .ai{font-style:normal; font-family:'Oswald',sans-serif;
    text-transform:uppercase; letter-spacing:.12em; font-size:13px;
    color:var(--blue)}
  .colophon a{color:var(--red)}

  /* a11y + breadcrumb upgrades */
  .skip-link{position:absolute; left:-9999px; top:0; z-index:1000;
    background:var(--ink); color:var(--paper); padding:10px 16px;
    font-family:'Oswald',sans-serif; text-decoration:none; border-radius:0 0 6px 0}
  .skip-link:focus{left:0}
  a:focus-visible, .toc a:focus-visible{outline:3px solid #c08a2d; outline-offset:2px}
  .sticky-top{position:fixed; right:16px; bottom:16px; z-index:900;
    background:var(--ink); color:var(--paper); padding:10px 14px; border-radius:24px;
    font-family:'Oswald',sans-serif; font-size:14px; text-decoration:none;
    box-shadow:0 3px 10px rgba(0,0,0,.3); opacity:.9}
  .sticky-top:hover{opacity:1}
  .book-nav{display:flex; align-items:center; justify-content:space-between;
    gap:12px; margin:8px 0 0; padding-top:14px; border-top:1px solid var(--ink)}
  .book-nav a{font-family:'Oswald',sans-serif; text-decoration:none; color:var(--ink);
    font-size:15px; padding:4px 2px}
  .book-nav a:hover{text-decoration:underline}
  .book-nav .bn-top{font-weight:600}
  .book-nav .disabled{flex:1}
  .bn-prev{flex:1; text-align:left}
  .bn-next{flex:1; text-align:right}
  @media print{.sticky-top,.skip-link{display:none}}

</style>
</head>
<body>
<a class="skip-link" href="#contents">Skip to contents</a>
<span id="top"></span>

<header class="masthead">
  <div class="kicker">Classics · Illustrated · Edition</div>
  <h1>ATHENA</h1>
  <div class="sub">The HipHop Odyssey</div>
  <div class="meta">An immersive dinner-theater retelling of Homer’s <em>Odyssey</em> — 24 books, 24 songs</div>
  <div class="cover-wrap">{cover}</div>
</header>

<nav class="contents" id="contents" aria-label="Table of contents">
  <h2>The Books</h2>
  <p class="lede">Twenty-four books, each danced to a song the performers already know. Tap a title to begin.</p>
  {toc}
</nav>

<main>
<a class="sticky-top" href="#top" aria-label="Back to contents">↑ Contents</a>
{books}
</main>

<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(()=>{}));
}
</script>
<footer class="colophon">
  <p>ATHENA was made as an experiment in <strong>collaborative AI</strong> — a human author conducting an ensemble of machines, every creative decision made by a person. The gods authored their own lines; the builder-AI signed her own.</p>
  <p class="ai">A collaborative-AI illustrated edition</p>
  <p><a href="https://github.com/hapnesbitt/Athena">Read the source &amp; the story on GitHub →</a></p>
</footer>

</body>
</html>
"""


def main():
    if not os.path.exists(MANUSCRIPT):
        print(f"ERROR: manuscript not found at {MANUSCRIPT}", file=sys.stderr)
        sys.exit(1)
    with open(MANUSCRIPT, encoding="utf-8") as f:
        text = f.read()

    _, books = parse_manuscript(text)
    print(f"Parsed {len(books)} books.")

    os.makedirs(OUTDIR, exist_ok=True)
    # ensure images dir exists & is linked into the output so relative paths work
    os.makedirs(IMAGESDIR, exist_ok=True)
    out_images = os.path.join(OUTDIR, "images")
    if os.path.abspath(IMAGESDIR) != os.path.abspath(out_images):
        # copy (not symlink) so the site dir is self-contained for serving
        if os.path.exists(out_images):
            shutil.rmtree(out_images)
        shutil.copytree(IMAGESDIR, out_images)

    htmltext = build_html(books)
    out_index = os.path.join(OUTDIR, "index.html")
    with open(out_index, "w", encoding="utf-8") as f:
        f.write(htmltext)

    # ── PWA: emit manifest.json ─────────────────────────────────────────
    manifest = {
        "name": "ATHENA — The HipHop Odyssey",
        "short_name": "ATHENA",
        "description": "An illustrated dinner-theater retelling of Homer's Odyssey.",
        "start_url": "./",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#1f4e79",
        "theme_color": "#1f4e79",
        "icons": [
            {"src": "images/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "images/icon-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "any maskable"},
        ],
    }
    import json
    with open(os.path.join(OUTDIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # ── SEO: emit sitemap.xml + robots.txt ──────────────────────────────
    # ATHENA is a single-page document: all 24 books are #book01..#book24
    # anchors on one URL. Fragment URLs are not independently indexable, so
    # the sitemap correctly lists the one canonical page. lastmod tracks the
    # manuscript's last edit (falls back to build time).
    try:
        lastmod = datetime.date.fromtimestamp(os.path.getmtime(MANUSCRIPT)).isoformat()
    except OSError:
        lastmod = datetime.date.today().isoformat()
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url>\n    <loc>{SITE_URL}/</loc>\n'
        f'    <lastmod>{lastmod}</lastmod>\n'
        '    <changefreq>monthly</changefreq>\n'
        '    <priority>1.0</priority>\n  </url>\n'
        '</urlset>\n'
    )
    with open(os.path.join(OUTDIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap)
    robots = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "# ATHENA — The HipHop Odyssey · illustrated edition\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )
    with open(os.path.join(OUTDIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots)

    # ── PWA: ensure icons exist in the served images dir ────────────────
    # If the user hasn't supplied custom icons, ship the built-in ATHENA crest
    # that lives next to this script (icon-180/192/512.png).
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_images = os.path.join(OUTDIR, "images")
    os.makedirs(out_images, exist_ok=True)
    for icon in ("icon-180.png", "icon-192.png", "icon-512.png"):
        dest = os.path.join(out_images, icon)
        if not os.path.exists(dest):
            # prefer a user-provided icon in IMAGESDIR, else the bundled default
            src_user = os.path.join(IMAGESDIR, icon)
            src_default = os.path.join(script_dir, icon)
            src = src_user if os.path.exists(src_user) else (
                  src_default if os.path.exists(src_default) else None)
            if src:
                shutil.copy(src, dest)

    # report image slot status
    present, missing = [], []
    for b in books:
        slot = f"book{b['num']:02d}"
        (present if find_image(slot) else missing).append(slot)
    cover_status = "present" if find_image("cover") else "missing (placeholder)"
    print(f"Wrote {out_index}")
    print(f"Cover: {cover_status}")
    print(f"Book art present: {len(present)}/24   missing (placeholders): {len(missing)}")
    if missing:
        print("  drop files for: " + ", ".join(f"images/{m}.jpg" for m in missing[:6])
              + (" ..." if len(missing) > 6 else ""))


if __name__ == "__main__":
    main()
