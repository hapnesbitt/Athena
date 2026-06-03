#!/usr/bin/env python3
"""
assemble.py — stitch the 24 polished scenes into one manuscript.

Reads scene_book1_polished.md … scene_book24_polished.md (in order), prepends a
title page + table of contents (book titles from scribe.BOOKS, songs/artists from
ATHENA_song_map.md), puts a page-break divider between books, and writes the whole
thing to ATHENA_manuscript.md.

Books still on the review list get an invisible HTML marker `<!-- REVIEW: book N -->`
at the top of their section so you can jump to them; it does not render.

Read-and-concatenate ONLY — this never modifies any scene file. Pure stdlib.

  python3 assemble.py
"""

import os
import re
import sys
from datetime import datetime

from scribe import BOOKS   # ordered book titles (scene_id), single source of truth

HERE          = os.path.dirname(os.path.abspath(__file__))
SONG_MAP_PATH = os.path.join(HERE, "ATHENA_song_map.md")
OUT_PATH      = os.path.join(HERE, "ATHENA_manuscript.md")

# Books still needing a human pass — marked invisibly so they're easy to find.
# 4, 6, 16 resolved in the polished files; 23 keeps its marker (song still echoes
# the voice bible — flagged for a later rewrite pass).
REVIEW_BOOKS = {23}

# A divider that reads as a rule in Markdown and a real page break when printed.
PAGE_BREAK = '\n<div style="page-break-after: always;"></div>\n\n---\n\n'


def roman_to_int(s):
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = vals.get(ch, 0)
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


def parse_song_map(path):
    """Return {book_number: (song, artist)} parsed from the canonical song map."""
    songs, cur = {}, None
    head_re = re.compile(r'^###\s+Book\s+([IVXLCDM]+)\s+[—-]\s+["“](.+?)["”]')
    art_re  = re.compile(r'^\*\*Artists?:\*\*\s*(.+?)\s*$')   # Artist: or Artists:
    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return songs
    for line in text.splitlines():
        h = head_re.match(line)
        if h:
            cur = roman_to_int(h.group(1))
            songs[cur] = (h.group(2).strip(), "")
            continue
        a = art_re.match(line)
        if a and cur is not None and songs.get(cur) and not songs[cur][1]:
            songs[cur] = (songs[cur][0], a.group(1).strip())
    return songs


def scene_text(book_id):
    """Return (text, source) preferring the polished scene, falling back to raw."""
    polished = os.path.join(HERE, f"scene_book{book_id}_polished.md")
    raw      = os.path.join(HERE, f"scene_book{book_id}.md")
    if os.path.isfile(polished):
        return open(polished, encoding="utf-8").read().strip(), "polished"
    if os.path.isfile(raw):
        return open(raw, encoding="utf-8").read().strip(), "raw"
    return None, "missing"


def build_toc(songs):
    lines = ["## Contents", ""]
    for n in range(1, 25):
        title = BOOKS[str(n)]["scene_id"]            # e.g. "Book V — Calypso's Island"
        song, artist = songs.get(n, ("", ""))
        tail = ""
        if song:
            tail = f' — *“{song}”*' + (f" ({artist})" if artist else "")
        flag = "  <!-- review -->" if n in REVIEW_BOOKS else ""  # invisible in render
        lines.append(f"{n}. **{title}**{tail}{flag}")
    return "\n".join(lines)


def title_page(songs):
    review = ", ".join(str(n) for n in sorted(REVIEW_BOOKS))
    return (
        "# ATHENA\n"
        "## The HipHop Odyssey\n\n"
        "*An immersive dinner-theater retelling of the Odyssey — 24 books, 24 contrafacts.*\n\n"
        f"*Assembled {datetime.now():%Y-%m-%d} from the polished scenes. "
        "Generated file — edit the scene files, not this one.*\n\n"
        f"<!-- review list at assembly time: books {review} -->\n\n"
        + PAGE_BREAK
        + build_toc(songs)
    )


def main():
    songs = parse_song_map(SONG_MAP_PATH)
    parts = [title_page(songs)]
    coverage = []  # (book, source)

    for n in range(1, 25):
        text, source = scene_text(str(n))
        coverage.append((n, source))
        body = PAGE_BREAK
        if n in REVIEW_BOOKS:
            body += f"<!-- REVIEW: book {n} -->\n\n"
        if text is None:
            body += (f"# ATHENA — {BOOKS[str(n)]['scene_id']}\n\n"
                     f"<!-- MISSING: no scene file for book {n} -->\n")
        else:
            if source == "raw":
                body += f"<!-- NOTE: book {n} not yet polished — using raw scene -->\n\n"
            body += text + "\n"
        parts.append(body)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")

    # Report coverage so it's clear what went in.
    pol = [b for b, s in coverage if s == "polished"]
    raw = [b for b, s in coverage if s == "raw"]
    missing = [b for b, s in coverage if s == "missing"]
    print(f"✓ wrote {OUT_PATH}")
    print(f"  {len(pol)} polished, {len(raw)} raw-fallback, {len(missing)} missing")
    if raw:
        print(f"  raw-fallback (polish these): {', '.join(map(str, raw))}")
    if missing:
        print(f"  MISSING scene files: {', '.join(map(str, missing))}")
    print(f"  review markers inserted for books: {', '.join(map(str, sorted(REVIEW_BOOKS)))}")
    if not songs:
        print("  ! song map not parsed — TOC has titles only")


if __name__ == "__main__":
    main()
