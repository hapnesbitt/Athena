"""School edition pages: everything a teacher was promised is on each page, and nothing from the dinner-theater edition or the song map leaked in."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENES = ("calypsos-offer", "nobody", "the-olive-tree")
# Multi-word song titles can't appear anywhere; one-word titles are ordinary words, so they are only checked in page titles and headings.
SONGS = ("Deal With It", "Rude Boy", "My Type", "Rain On Me", "Mic Drop", "Bad Habits", "Don't Stop", "Get Ugly", "Outta Your Mind",
         "Without Me", "Bounce Back", "Walk It Out", "No Tears Left", "Savage Love", "Black Widow", "All About That Bass", "New Rules")
ONE_WORD_SONGS = ("Fast", "Freak", "WOW", "Lay", "Up", "Work", "Every Day")
FRAMING = ("ladies and gentlemen", "esteemed", "patrons", "diners", "from the tables", "raise a glass", "toast", "dance-off", "Turn 1")


def built(tmp_path):
    subprocess.run([sys.executable, "build_school_pack.py", "--out", str(tmp_path)], cwd=ROOT, check=True, capture_output=True)
    return tmp_path / "school"


def test_every_scene_page_has_what_was_promised(tmp_path):
    school = built(tmp_path)
    for slug in SCENES:
        page = (school / slug / "index.html").read_text(encoding="utf-8")
        for needle in ("<title>", 'name="description"', f'rel="canonical" href="https://athena.arc-codex.com/school/{slug}/"', 'property="og:image"', 'name="twitter:card"',
                       "<h2>Cast</h2>", "minutes", "<h2>What happens</h2>", "<h2>Content note</h2>", "Alcohol", "Violence", "CC BY-NC-SA 4.0", "AI model", "dramatic rights",
                       "not legal advice", "#passage", "<h2>Three prompts</h2>", 'class="script'):
            assert needle in page, f"{slug}: missing {needle}"
        prompts = re.search(r"<h2>Three prompts</h2><ol>(.*?)</ol>", page, re.S).group(1)
        assert prompts.count("<li>") == 3, slug


def test_no_dinner_theater_framing_or_song_titles(tmp_path):
    school = built(tmp_path)
    for source in (ROOT / "school" / "scenes").glob("*.md"):
        text = source.read_text(encoding="utf-8")
        for word in FRAMING + SONGS:
            assert word.lower() not in text.lower(), f"{source.name}: {word}"
        assert not re.search(r"[\U0001F300-\U0001FAFF]", text), f"{source.name}: emoji"
    for slug in SCENES:
        page = (school / slug / "index.html").read_text(encoding="utf-8")
        heads = " ".join(a + b for a, b in re.findall(r"<title>(.*?)</title>|<h1>(.*?)</h1>", page))
        for word in ONE_WORD_SONGS + SONGS:
            assert not re.search(rf"\b{re.escape(word)}\b", heads), f"{slug}: {word}"


def test_story_errors_stay_fixed():
    scene = lambda name: (ROOT / "school" / "scenes" / f"{name}.md").read_text(encoding="utf-8")
    nobody = scene("nobody")
    assert "Crete" not in nobody and "secret" not in nobody and "Maron" in nobody
    calypso = scene("calypsos-offer")
    assert "Seven years" in calypso and "sea-witch" not in calypso and "Ten years on" not in calypso and "Styx" in calypso
    olive = scene("the-olive-tree")
    assert "Calypso" not in olive and "olive" in olive and "Move it out here" in olive


def test_all_scripts_print_with_a_break_between_scenes(tmp_path):
    school = built(tmp_path)
    page = (school / "scripts.html").read_text(encoding="utf-8")
    assert page.count('<section class="script') == 3
    assert ".script{break-before:page" in page


def test_full_edition_rebuild_keeps_school_pages_in_the_sitemap(tmp_path):
    built(tmp_path)
    subprocess.run([sys.executable, "build_athena_site.py", "ATHENA_manuscript.md", str(tmp_path), "images"], cwd=ROOT, check=True, capture_output=True)
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://athena.arc-codex.com/</loc>" in sitemap
    assert "<loc>https://athena.arc-codex.com/school/</loc>" in sitemap
    for slug in SCENES:
        assert f"<loc>https://athena.arc-codex.com/school/{slug}/</loc>" in sitemap
