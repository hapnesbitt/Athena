#!/usr/bin/env python3
"""
One-shot patcher for build_athena_site.py
Adds: skip link, sticky Contents pill, per-book prev/next nav, nav aria-labels,
focus-visible styling, and a PWA service worker for offline/install.
Idempotent + makes a .bak. Run from /home/www/Athena_clb/:
    python3 patch_athena.py && ./rebuild_site.sh
"""
import shutil, sys, os

SRC = "build_athena_site.py"
if not os.path.exists(SRC):
    sys.exit(f"ERROR: run from the dir containing {SRC}")

shutil.copy(SRC, SRC + ".bak")
s = open(SRC, encoding="utf-8").read()
orig = s

def patch(anchor, replacement, sentinel, label):
    """Replace `anchor` with `replacement`; skip if `sentinel` already present."""
    global s
    if sentinel in s:
        print(f"  skip (already applied): {label}")
        return
    if s.count(anchor) != 1:
        print(f"  WARN anchor count={s.count(anchor)} (need 1): {label}")
        return
    s = s.replace(anchor, replacement)
    print(f"  ok: {label}")

# 1) Per-book footer: prev/next + contents (ROMAN is 1-indexed via num-1) ------
patch(
    "f'<a class=\"totop\" href=\"#top\">▲ back to contents</a>'",
    ("f'<nav class=\"book-nav\" aria-label=\"Book navigation\">'\n"
     "            + (f'<a class=\"bn-prev\" href=\"#book{b[\"num\"]-1:02d}\">← Book {ROMAN[b[\"num\"]-2]}</a>' if b[\"num\"] > 1 else '<span class=\"bn-prev disabled\" aria-hidden=\"true\"></span>')\n"
     "            + '<a class=\"bn-top\" href=\"#top\">↑ Contents</a>'\n"
     "            + (f'<a class=\"bn-next\" href=\"#book{b[\"num\"]+1:02d}\">Book {ROMAN[b[\"num\"]]} →</a>' if b[\"num\"] < len(books) else '<span class=\"bn-next disabled\" aria-hidden=\"true\"></span>')\n"
     "            + '</nav>'"),
    'class="book-nav"',
    "per-book prev/next nav",
)

# 2) Skip link as first body element ------------------------------------------
patch(
    '<body>\n<span id="top"></span>',
    '<body>\n<a class="skip-link" href="#contents">Skip to contents</a>\n<span id="top"></span>',
    'class="skip-link"',
    "skip link",
)

# 3) Contents nav: id + aria-label --------------------------------------------
patch(
    '<nav class="contents">',
    '<nav class="contents" id="contents" aria-label="Table of contents">',
    'id="contents"',
    "contents nav id + aria-label",
)

# 4) Sticky Contents pill at top of <main> ------------------------------------
patch(
    '<main>\n{books}',
    '<main>\n<a class="sticky-top" href="#top" aria-label="Back to contents">↑ Contents</a>\n{books}',
    'class="sticky-top"',
    "sticky contents pill",
)

# 5) Register service worker before </body> -----------------------------------
patch(
    '<footer class="colophon">',
    ('<script>\n'
     "if ('serviceWorker' in navigator) {\n"
     "  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(()=>{}));\n"
     "}\n"
     '</script>\n'
     '<footer class="colophon">'),
    "serviceWorker.register",
    "service worker registration",
)

# 6) CSS — inject before the closing </style> of the template -----------------
CSS = """
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
"""
patch("</style>", CSS + "\n</style>", "a11y + breadcrumb upgrades", "CSS block")

open(SRC, "w", encoding="utf-8").write(s)
print("\n" + ("CHANGED" if s != orig else "no changes"))
print(f"Backup: {SRC}.bak")
